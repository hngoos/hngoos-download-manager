"""Persistent presentation controls; localization never changes task input values."""

import re
import tkinter as tk
from functools import lru_cache, wraps
from string import Formatter
from tkinter import ttk
from weakref import WeakKeyDictionary


def buffered_presentation(method):
    """Publish a complete Windows frame after Tk has finished a page/theme change."""
    @wraps(method)
    def change(owner, *args, **kwargs):
        import os
        window = owner.root if hasattr(owner, "root") else owner.app.root
        if os.name != "nt" or not window.winfo_ismapped():
            return method(owner, *args, **kwargs)
        if getattr(window, "_hdm_paint_depth", 0):
            return method(owner, *args, **kwargs)
        surface = getattr(window, "_hdm_preferences_surface", None)
        if (method.__name__ in {"set_preference", "apply_preferences"}
                and surface is not None and surface.winfo_ismapped()):
            # The scene retains its previous complete frame while its model is
            # updated. Native erasure would discard that backing pixmap.
            return method(owner, *args, **kwargs)

        # Commit a pending resize before WM_SETREDRAW temporarily removes the
        # native WS_VISIBLE flag. Otherwise Tk can lose the resize/map request.
        window.update_idletasks()

        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.HRGN, wintypes.UINT]
        handle = user32.GetAncestor(window.winfo_id(), 2)
        if not user32.IsWindowVisible(handle):
            return method(owner, *args, **kwargs)
        window._hdm_paint_depth = 1
        user32.SendMessageW(handle, 0xB, False, 0)  # WM_SETREDRAW
        try:
            return method(owner, *args, **kwargs)
        finally:
            try:
                # Drain geometry and Tk display work, never queued mouse/key events.
                # Nested presentation callbacks remain inside this same transaction.
                window.update_idletasks()
            finally:
                user32.SendMessageW(handle, 0xB, True, 0)
                user32.RedrawWindow(handle, None, None, 0x185)  # INVALIDATE | ERASE | ALLCHILDREN | UPDATENOW
                window._hdm_paint_depth = 0
    return change


def apply_window_theme(window, theme):
    """Match the Windows title bar to the selected application theme when supported."""
    import os
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes
    user32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    handle = user32.GetAncestor(window.winfo_id(), 2)
    dark = ctypes.c_int(theme == "dark")
    for attribute in (20, 19):
        if dwm.DwmSetWindowAttribute(handle, attribute, ctypes.byref(dark), ctypes.sizeof(dark)) == 0:
            break


def redraw_window(window):
    """Invalidate native child surfaces after changing themes or overlapping pages."""
    surface = getattr(window, "_hdm_preferences_surface", None)
    if surface is not None and surface.winfo_ismapped():
        return
    import os
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.HRGN, wintypes.UINT]
    handle = user32.GetAncestor(window.winfo_id(), 2)
    # Invalidate all children and the frame, suppressing background erasure.
    # Tk paints its widgets on idle. Erasing and forcing WM_PAINT synchronously
    # exposes blank child surfaces before those Tk draws have run.
    user32.RedrawWindow(handle, None, None, 0x4A1)


def apply_checkbox_style(root, style, theme):
    """Keep native checkbox behavior while drawing a rounded box and a real checkmark."""
    from importlib.resources import files
    images = getattr(root, "_hdm_checkbox_images", {})
    element = f"HDM.{theme}.Check.indicator"
    if element not in style.element_names():
        folder = files("hngoos_dm")/"assets/icons"
        for state in ("on", "off", "on-disabled", "off-disabled"):
            images[theme, state] = tk.PhotoImage(master=root, file=str(folder/f"checkbox-{theme}-{state}.png"))
        root._hdm_checkbox_images = images
        style.element_create(element, "image", images[theme, "off"],
                             ("disabled", "selected", images[theme, "on-disabled"]),
                             ("disabled", images[theme, "off-disabled"]), ("selected", images[theme, "on"]))
    layout = [("Checkbutton.padding", {"sticky": "nswe", "children": [
        (element, {"side": "left", "sticky": "w"}),
        ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
            ("Checkbutton.label", {"sticky": "nswe"})]})]})]
    for name in ("TCheckbutton", "Card.TCheckbutton"):
        style.layout(name, layout)
        style.configure(name, padding=(0, 2))


TRANSLATIONS = {
    "Không thể mở trang tiện ích. Hãy nhập opera://extensions vào thanh địa chỉ trình duyệt.":
        "Could not open the extensions page. Enter opera://extensions in the browser address bar.",
    "Kết nối HDM": "Connect HDM",
    "Đã kết nối tiện ích với HDM.": "Extension connected to HDM.",
    "Chọn thư mục tiện ích đã giải nén": "Choose the extracted extension folder",
    "Chọn thư mục HDM chứa manifest.json sau khi giải nén.":
        "Choose the extracted HDM folder containing manifest.json.",
    "B1: Mở trang tiện ích của trình duyệt:": "Step 1: Open the browser extensions page:",
    "B2: Bật Chế độ nhà phát triển (Developer mode).": "Step 2: Enable Developer mode.",
    "B3: Giải nén HDM-Browser-Extension.zip có sẵn cùng HDM vào một thư mục cố định.":
        "Step 3: Extract HDM-Browser-Extension.zip included with HDM to a permanent folder.",
    "B4: Chọn Tải tiện ích đã giải nén (Load unpacked), rồi chọn thư mục chứa manifest.json.":
        "Step 4: Click Load unpacked, then select the folder containing manifest.json.",
    "B5: Bấm Kết nối HDM bên dưới và chọn lại thư mục vừa giải nén.":
        "Step 5: Click Connect HDM below and select the extracted folder again.",
    "B6: Mở cài đặt tiện ích HDM, bấm Bật chuyển lượt tải sang HDM và xác nhận quyền.":
        "Step 6: Open the HDM extension settings, click Enable download capture and accept the permission prompt.",
    "Chép đường dẫn": "Copy folder path",
    "Nếu trang tiện ích chưa mở, nhập {page} vào thanh địa chỉ trình duyệt.":
        "If the extensions page did not open, enter {page} in the browser address bar.",
    "Sau khi cài, bấm Bật chuyển lượt tải sang HDM và xác nhận quyền trong trình duyệt.":
        "After installation, click Enable download capture and accept the browser permission prompt.",
    "Định dạng video không được hỗ trợ.": "Unsupported video format.",
    "Cần FFmpeg để ghép video và âm thanh.": "FFmpeg is required to merge video and audio.",
    "Lưu tại:": "Save as:", "Gốc": "Original",
    "Đặt lại mặc định": "Reset to default", "Tệp đã bị xóa": "File deleted", "Xóa": "Remove",
    "Đang quét": "Scanning", "0 phát hiện": "0 detected", "Có rủi ro": "Risk", "Nguy hiểm": "Danger", "Lỗi quét": "Scan error", "Dừng": "Stop",
    "Hệ thống": "System",
    "Thu xuống khay hệ thống khi đóng cửa sổ": "Minimize to the system tray when closing the window",
    "Tắt máy sau khi tải xong": "Shut down after downloads finish",
    "Hỗ trợ": "Support", "Thông tin": "Info",
    "Tệp:": "File:",
    "Phiên bản hiện tại: {version}": "Current version: {version}",
    "Không có bản cập nhật mới.": "No updates available.",
    "Liên hệ": "Contact",
    "Tải tệp, video và âm thanh với tối đa 32 kết nối, hỗ trợ tiếp tục tải và kiểm tra an toàn.":
        "Download files, video and audio with up to 32 connections, resumable transfers and safety checks.",
    "Đang chuẩn bị tiện ích…": "Preparing browser extension…",
    "Tiện ích đã sẵn sàng tại {path}.": "Extension ready at {path}.",
    "Trong trình duyệt: bật Chế độ dành cho nhà phát triển, chọn Tải tiện ích đã giải nén rồi dán đường dẫn thư mục bên dưới.":
        "In the browser, enable Developer mode, choose Load unpacked and paste the folder path below.",
    "Bản thử nghiệm chưa có bộ kết nối trình duyệt.": "The development browser bridge has not been built.",
    "Thư mục tiện ích không được là liên kết.": "The extension folder cannot be a symbolic link.",
    "Gói tiện ích không hợp lệ.": "Invalid extension package.",
    "Danh sách tải xuống": "Download list",
    "Tự động xóa tệp không còn trên máy khỏi danh sách tải": "Automatically remove missing files from the download list",
    "Tự động xóa mục tải thành công khỏi danh sách": "Automatically remove completed downloads from the list",
    "Tự động thử lại lượt tải bị lỗi mạng": "Automatically retry downloads after network failures",
    "Chỉ xóa mục trong danh sách, không xóa tệp trên máy.": "Only list entries are removed; downloaded files are kept.",
    "Cập nhật": "Updates",
    "Nguồn không có âm thanh tương thích với định dạng này. Hãy chọn định dạng khác.":
        "The source has no compatible audio for this format. Choose another format.",
    "Kiểm tra cập nhật tự động": "Automatically check for updates",
    "Cài đặt bản cập nhật tự động": "Automatically install updates",
    "Kiểm tra mỗi 6 giờ. Chỉ cài bản đã xác minh khi không có tác vụ đang chạy.":
        "Check every 6 hours. Install verified updates only when no tasks are running.",
    "Có bản cập nhật HDM {version}.": "HDM {version} is available.",
    "Không thể cập nhật tự động: {error}": "Automatic update failed: {error}",
    "Đã tải và xác minh bản cập nhật. Cài khi HDM rảnh hoặc mở Kiểm tra cập nhật.":
        "Update downloaded and verified. Install when HDM is idle, or open Check for update.",
    "Mạng": "Network", "Proxy hệ thống": "System proxy", "Không dùng proxy": "No proxy",
    "Cấu hình thủ công": "Manual configuration", "Địa chỉ proxy": "Proxy address",
    "Ví dụ: http://127.0.0.1:8080. Áp dụng cho kết nối tải mới; không đổi proxy của hệ điều hành.":
        "Example: http://127.0.0.1:8080. Applies to new download connections; system proxy settings are unchanged.",
    "Đã lưu cấu hình mạng.": "Network settings saved.", "Cấu hình proxy không hợp lệ.": "Invalid proxy configuration.",
    "Nhập proxy HTTP(S) dạng http://máy-chủ:cổng, không kèm tài khoản hoặc đường dẫn.":
        "Enter an HTTP(S) proxy as http://host:port, without credentials or a path.",
    "Khôi phục cài đặt mặc định": "Restore default settings", "Đặt lại": "Reset",
    "Đặt lại thiết lập HDM? Tệp, lịch sử tải và khóa dịch vụ được giữ nguyên.":
        "Reset HDM settings? Files, download history and service keys will be kept.",
    "Tiếp tục trong trình duyệt nếu hủy tải trong HDM": "Resume in browser if cancelled in HDM",
    "Không bắt tải khi giữ phím Insert": "Skip capture while holding Insert",
    "Phím Insert cần quyền truy cập trang của tiện ích. Tải lại trang sau khi bật tích hợp.":
        "Insert bypass requires extension access to websites. Reload the page after enabling integration.",
    "Sửa lỗi nhận diện và tải video khi các trang web thay đổi.":
        "Fix video detection and downloads when websites change.",
    "Đang cập nhật bộ tải video…": "Updating video downloader…",
    "Không thể cập nhật bộ tải video: {error}": "Video downloader update failed: {error}",
    "Đã xác minh và cập nhật bộ tải video {version}.": "Video downloader {version} verified and updated.",
    "Bộ tải video đang được cập nhật. Hãy chờ hoàn tất.": "The video downloader is being updated. Wait for it to finish.",
    "Tệp bộ tải video đang được sử dụng hoặc không có quyền ghi. Hãy chờ tác vụ kết thúc rồi thử lại.":
        "The video downloader file is in use or cannot be written. Wait for active tasks to finish and try again.",
    "Bộ tải video cập nhật riêng hiện dành cho Windows.": "Standalone video downloader updates are currently available on Windows.",
    "Nguồn chính thức chưa có digest SHA-256 cho tài sản; không tự cập nhật.":
        "The official release has no SHA-256 digest for this asset; the update was rejected.",
    "Tệp yt-dlp vượt kích thước được công bố.": "The yt-dlp download exceeds the published size.",
    "yt-dlp không khớp mã SHA-256 được GitHub công bố.": "The yt-dlp file does not match the SHA-256 published by GitHub.",
    "Cài tiện ích cho {browser}": "Install extension for {browser}",
    "Các trình duyệt Chromium khác": "Other Chromium browsers", "Mở trang tiện ích": "Open extensions page",
    "Trình duyệt không được hỗ trợ.": "Unsupported browser.",
    "Chưa tìm thấy trình duyệt này trên máy. Hãy cài trình duyệt trước.":
        "This browser was not found on your computer. Install it first.",
    "1. Tải ZIP và giải nén vào thư mục cố định.\n2. Mở {page}, bật Chế độ dành cho nhà phát triển.\n3. Chọn Tải tiện ích đã giải nén và thư mục có manifest.json.\n4. Sao chép mã tiện ích, dán bên dưới và đăng ký kết nối.\n5. Mở tiện ích và chọn Kiểm tra kết nối.":
        "1. Download the ZIP and extract it to a permanent folder.\n2. Open {page} and enable Developer mode.\n3. Click Load unpacked and choose the folder with manifest.json.\n4. Copy the Extension ID, paste it below and register the connection.\n5. Open the extension and click Test connection.",
    "HDM đang mở với thư mục dữ liệu này. Hãy dùng cửa sổ hiện có.":
        "HDM is already open with this data folder. Use the existing window.",
    "Phiên bản phải có dạng x.y.z.": "The version must use the x.y.z format.",
    "Chưa cấu hình khóa công khai nhà phát hành; không chấp nhận cập nhật tự động.":
        "Publisher public key is not configured; automatic updates are unavailable.",
    "Manifest không hợp lệ.": "Invalid release manifest.", "Manifest chưa có tài sản phát hành.":
        "The manifest contains no release packages.", "Cập nhật yêu cầu HTTPS.": "Updates require HTTPS.",
    "Manifest và tag phát hành không khớp.": "The manifest and release tag do not match.",
    "Bản phát hành đã ký không có gói duy nhất phù hợp với nền tảng này.":
        "The signed release does not contain a unique package for this platform.",
    "Gói cài đặt không thuộc bản phát hành đã ký.": "The package is not part of the signed release.",
    "Tên tệp cập nhật không hợp lệ.": "Invalid update filename.",
    "Chữ ký cập nhật không hợp lệ; bản cập nhật bị từ chối.": "Invalid update signature; the update was rejected.",
    "Thông tin tệp cập nhật không hợp lệ.": "Invalid update package metadata.",
    "Manifest quá lớn.": "The release manifest is too large.",
    "Bản mới chưa có manifest ký số; không được cài tự động.":
        "The release has no signed manifest; automatic installation is unavailable.",
    "Gói cập nhật không còn khớp với bản phát hành đã ký.": "The update package no longer matches the signed release.",
    "Mã băm/kích thước bộ cài không khớp manifest đã ký.":
        "The installer hash or size does not match the signed manifest.",
    "Không có gói cập nhật cho nền tảng này.": "No update package is available for this platform.",
    "Bộ cài lớn hơn manifest đã ký.": "The installer exceeds the size in the signed manifest.",
    "Magnet cần có mã nhận diện torrent hợp lệ.": "The magnet URL must contain a valid torrent identifier.",
    "Thiếu manifest tiện ích đã ký": "Missing signed extension manifest",
    "Phiên bản phát hành không khớp": "Release version mismatch", "Gói tiện ích không hợp lệ": "Invalid extension package",
    "Tệp cookie Netscape": "Netscape cookie file", "Định dạng nguồn": "Source format",
    "Phần mở rộng": "Extension", "Độ phân giải": "Resolution", "Âm thanh": "Audio", "Kích thước": "Size",
    "Thư mục lưu": "Download folder", "Tích hợp trình duyệt": "Browser integration", "Nâng cao": "Advanced",
    "Bỏ qua tên miền": "Skip domains", "Bỏ qua loại tệp": "Skip file types",
    "Chỉ bắt loại tệp": "Only capture file types", "Kích thước tối thiểu (MB)": "Minimum size (MB)",
    "Đã lưu. Tiện ích đồng bộ trong vòng một phút khi trình duyệt đang mở.":
        "Saved. The extension syncs within one minute while the browser is open.",
    "Cài tiện ích HDM và cấp quyền Tải xuống để bật bắt tải tự động.":
        "Install the HDM extension and grant Downloads permission to enable automatic capture.",
    "Cài tiện ích…": "Install extension…",
    "Chuyển lượt tải từ trình duyệt sang HDM": "Send browser downloads to HDM",
    "Bắt đầu tải mà không cần xác nhận": "Start downloads without confirmation",
    "Ngăn cách bằng dấu phẩy. Để trống để không giới hạn; 0 MB nhận mọi kích thước.":
        "Separate entries with commas. Leave blank for no restriction; 0 MB accepts all sizes.",
    "Áp dụng": "Apply", "Nếu HDM không nhận được lượt tải, trình duyệt tự tiếp tục tải.":
        "If HDM cannot accept a download, the browser resumes it automatically.",
    "Bấm Kiểm tra cạnh tệp đã tải để chọn quét trên máy hoặc tra VirusTotal.":
        "Click Check next to a downloaded file to run a local scan or look it up on VirusTotal.",
    "Quét lại": "Scan again", "Quét tệp trực tiếp trên máy bằng Windows Defender.":
        "Scan the file locally with Windows Defender.",
    "Độc hại": "Malicious", "Đáng ngờ": "Suspicious", "Không phát hiện": "Undetected",
    "Không có dấu hiệu gây hại": "Harmless", "Hết thời gian": "Timeout", "Quét thất bại": "Failure",
    "Không hỗ trợ loại tệp": "Unsupported file type", "Chưa rõ": "Unknown",
    "Hết thời gian xác nhận": "Confirmed timeout",
    "{malicious} độc hại · {suspicious} đáng ngờ / {count} bộ quét":
        "{malicious} malicious · {suspicious} suspicious / {count} engines",
    "Nhập khóa API VirusTotal của bạn (64 ký tự thập lục phân).":
        "Enter your VirusTotal API key (64 hexadecimal characters).",
    "Địa chỉ dịch vụ VirusTotal không đáng tin cậy.": "Untrusted VirusTotal endpoint.",
    "Tệp gửi lên VirusTotal phải có kích thước từ 1 byte đến 650 MB.":
        "VirusTotal uploads must be between 1 byte and 650 MB.",
    "Tệp thay đổi trong lúc gửi. Hãy quét lại.": "File changed during upload. Scan again.",
    "Khóa API VirusTotal bị từ chối hoặc không có quyền truy cập.":
        "VirusTotal API key rejected or access unavailable.",
    "Đã đạt giới hạn yêu cầu VirusTotal. Hãy đợi trước khi kiểm tra lại.":
        "VirusTotal rate limit reached. Wait before checking again.",
    "Yêu cầu VirusTotal thất bại (HTTP {code}).": "VirusTotal request failed (HTTP {code}).",
    "Phản hồi VirusTotal vượt giới hạn kích thước.": "VirusTotal response exceeds the size limit.",
    "SHA-256 không hợp lệ.": "Invalid SHA-256.", "Cần xác nhận trước khi gửi tệp.":
        "File upload requires explicit consent.",
    "Tệp thay đổi sau khi kiểm tra. Hãy quét lại trước khi gửi.":
        "File changed after checking. Scan again before upload.",
    "Mã phân tích không hợp lệ.": "Invalid analysis identifier.", "Chưa có kết quả phân tích.":
        "Analysis not available yet.",
    "Thiết lập trình duyệt không hợp lệ": "Invalid browser preferences",
    "Tùy chọn bắt tải phải là bật hoặc tắt": "Capture options must be booleans",
    "Cho phép tối đa 100 ngoại lệ bắt tải": "At most 100 capture exceptions are allowed",
    "Ngoại lệ bắt tải phải là văn bản": "Capture exceptions must be strings",
    "Ngoại lệ bắt tải không hợp lệ": "Invalid capture exception",
    "Kích thước bắt tải tối thiểu không hợp lệ": "Invalid minimum capture size",
    "Đã lưu: {path}": "Saved: {path}", "Không thể cập nhật: {error}": "Update failed: {error}",
    "Có HDM {version} · {size} MB\nChữ ký nhà phát hành đã được xác minh.":
        "HDM {version} available · {size} MB\nPublisher signature verified.",
    "Đang tải bản cập nhật…": "Downloading update…",
    "Hãy tạm dừng hoặc hoàn tất các tác vụ trước khi cài cập nhật.":
        "Pause or finish active tasks before installing the update.",
    "Bản mới đã sẵn sàng trong thư mục cập nhật. Đóng HDM rồi chạy tệp AppImage.":
        "The update is ready in this folder. Close HDM, then run the AppImage.",
    "Hoàn tất cài đặt trong cửa sổ hệ thống, sau đó mở lại HDM.":
        "Finish installation in the system window, then restart HDM.",
    "Chỉ nhận đường dẫn HTTP hoặc HTTPS hợp lệ.": "Enter a valid HTTP or HTTPS URL.",
    "Không đặt tài khoản/mật khẩu trực tiếp trong URL.": "Do not put usernames or passwords directly in the URL.",
    "URL chứa ký tự điều khiển.": "The URL contains control characters.",
    "Định dạng có thể thực thi hoặc chứa mã": "The format can execute or contain code",
    "Tên tệp có ký tự điều hướng văn bản": "The filename contains text direction controls",
    "Tên tệp có nhiều đuôi, đuôi cuối có thể thực thi": "The filename has multiple extensions ending in an executable type",
    "Chọn dịch vụ hợp lệ và mã SHA-256 đủ 64 ký tự.": "Choose a valid service and a 64-character SHA-256 hash.",
    "Không tìm thấy Windows Defender trên máy này.": "Windows Defender was not found on this computer.",
    "Tệp thực thi Windows (MZ)": "Windows executable (MZ)", "Tệp thực thi Linux (ELF)": "Linux executable (ELF)",
    "Tệp nhị phân macOS hoặc Java": "macOS or Java binary", "Tệp script có thể thực thi": "Executable script",
    "An toàn cao: chương trình chưa có chữ ký Windows hợp lệ":
        "High security: the program has no valid Windows signature",
    "Tệp nén vượt giới hạn kiểm tra; cần quét riêng": "Archive exceeds inspection limits; a separate scan is required",
    "Tệp nén chứa đường dẫn/tên Windows không an toàn hoặc liên kết tượng trưng":
        "Archive contains unsafe Windows paths or filenames, or symbolic links",
    "Tệp nén có tỷ lệ giải nén bất thường": "Archive has an unusual compression ratio",
    "ZIP có mật khẩu, chưa kiểm tra được nội dung": "Password-protected ZIP; contents have not been inspected",
    "Đã hết ngân sách kiểm tra tệp nén": "Archive inspection limit reached",
    "Còn các dấu hiệu khác trong tệp nén; đã giới hạn báo cáo": "More archive indicators exist; report limit reached",
    "Cấu trúc ZIP/Office bị hỏng hoặc không đọc được": "ZIP or Office structure is corrupt or unreadable",
    "Tệp nén chứa mã/lối tắt rủi ro: {name}": "Archive contains risky code or shortcuts: {name}",
    "Không đọc được thành phần ZIP; cần mật khẩu đúng hoặc bộ quét chuyên dụng":
        "Cannot read ZIP entry; a correct password or a specialized scanner is required",
    "Defender phát hiện rủi ro hoặc chưa hoàn tất quét; cần kiểm tra trước khi mở":
        "Defender detected a risk or did not finish scanning; review before opening",
    "Tệp nén chứa chương trình Windows: {name}": "Archive contains a Windows program: {name}",
    "Tệp nén lồng nhau vượt giới hạn kiểm tra": "Nested archive exceeds inspection limits",
    "Dán link mới. Phần cũ chỉ dùng lại khi ETag mạnh và kích thước trùng.":
        "Paste the new URL. Existing data is reused only when a strong ETag and size match.",
    "Thay link": "Replace URL", "Khôi phục tệp cách ly": "Restore quarantined file",
    "Hẹn giờ": "Schedule", "Nhập ngày giờ trên máy: YYYY-MM-DD HH:MM": "Enter local date and time: YYYY-MM-DD HH:MM",
    "Link đám mây": "Cloud URL", "Dán link chia sẻ tệp công khai": "Paste a public file sharing URL",
    "Tiếp quản": "Take over", "Dán URL tải trực tiếp. Tệp gốc được giữ lại; toàn bộ phần cũ sẽ được xác minh.":
        "Paste a direct download URL. The original file is kept; all existing data will be verified.",
    "Nhập API key của bạn (chỉ dùng cho tác vụ này)": "Enter your API key (used only for this task)",
    "JWT token nếu dịch vụ yêu cầu đăng nhập (có thể để trống)": "JWT token if sign-in is required (optional)",
    "ZIP có mật khẩu?": "Password-protected ZIP?",
    "Nếu ZIP có mật khẩu, nhập mật khẩu (có thể để trống)": "Enter the ZIP password, if any (optional)",
    "Nhật ký bảo vệ thư mục": "Folder protection log", "Đã hủy tắt máy tự động.": "Automatic shutdown cancelled.",
    "Lưu website thành PDF / ảnh": "Save websites as PDF / images",
    "Đổi nơi lưu — giữ phần đã tải, tự tiếp tục": "Change destination — keep downloaded data and resume",
    "Báo cáo danh sách": "Batch report", "Chọn video": "Choose video", "Lưu MP4": "Save MP4",
    "Đang chuyển video sang MP4…": "Converting video to MP4…",
    "Chọn cookies.txt do bạn chủ động xuất": "Choose a cookies.txt file you exported",
    "Đã chọn tệp cookie cho lượt video tiếp theo. Không chia sẻ tệp này.":
        "Cookie file selected for the next media download. Do not share this file.",
    "Nhật ký — {name}": "Log — {name}", "Lưu tại: {path}": "Save to: {path}",
    "Chọn .crdownload/.part đã dừng trong trình duyệt": "Choose a paused browser .crdownload or .part file",
    "Chọn phim để tìm phụ đề tiếng Việt": "Choose a movie to find Vietnamese subtitles",
    "Kiểm tra tệp / ZIP / RAR / 7z / chữ ký Windows": "Inspect file / ZIP / RAR / 7z / Windows signature",
    "Đã tắt theo dõi thư mục tải.": "Download folder monitoring disabled.",
    "Theo dõi tệp mới/sửa đổi; tệp rủi ro được đổi đuôi .chuakiemtra":
        "Monitor new or modified files; risky files get the .chuakiemtra extension",
    "Đợi tác vụ video kết thúc trước khi cập nhật bộ tải.": "Wait for media tasks to finish before updating the downloader.",
    "TỆP CÁCH LY": "QUARANTINED FILE", "LÝ DO": "REASONS", "Tính SHA-256": "Calculate SHA-256",
    "Đang tính SHA-256…": "Calculating SHA-256…", "Chọn tệp để quét với Defender": "Choose a file to scan with Defender",
    "Đang quét bằng Windows Defender…": "Scanning with Windows Defender…",
    "Đã yêu cầu chuyển nơi lưu; lượt đang tải sẽ tiếp tục sau khi chuyển.":
        "Destination change requested; active downloads resume after moving.",
    "Thư mục cha để tạo thư mục giải nén mới": "Parent folder for a new extraction folder",
    "Kiểm tra sơ bộ": "Preliminary checks", "Chọn một tệp cách ly trước.": "Select a quarantined file first.",
    "Đường dẫn cách ly không hợp lệ.": "Invalid quarantine path.", "Xóa tệp cách ly": "Delete quarantined file",
    "Thư mục lưu trang": "Web page destination folder", "Đã hẹn tắt máy sau 60 giây. Bấm Hủy trong Công cụ để hủy.":
        "Shutdown scheduled in 60 seconds. Use Cancel scheduled shutdown in Preferences to cancel.",
    "Tôi hiểu rủi ro khi khôi phục tệp này": "I understand the risks of restoring this file",
    "Tên tệp gốc đã tồn tại. Hãy đổi tên hoặc di chuyển tệp đó trước.":
        "The original filename already exists. Rename or move that file first.",
    "Đã khôi phục theo yêu cầu người dùng": "Restored at the user's request", "Khôi phục tên gốc": "Restore original name",
    "Hãy chọn thời điểm trong tương lai.": "Choose a time in the future.",
    "Đã xuất lịch sử (không chứa URL có token): {path}": "History exported (URLs with tokens excluded): {path}",
    "Đã tải phụ đề khớp mã phim: {path}": "Matching subtitles downloaded: {path}",
    "Đang bảo vệ tệp mới trong: {path}": "Protecting new files in: {path}",
    "Đã xác minh và cập nhật yt-dlp {version}": "Verified and updated yt-dlp {version}",
    "Tôi hiểu rủi ro khi khôi phục tên gốc của tệp được chọn":
        "I understand the risks of restoring the selected file's original name",
    "Cần tích ô hiểu rủi ro trước khi khôi phục.": "Acknowledge the risks before restoring.",
    "Tên gốc đã tồn tại; không ghi đè.": "The original name already exists; it will not be overwritten.",
    "Xóa vĩnh viễn tệp này?\n{path}": "Permanently delete this file?\n{path}",
    "Xóa tệp cách ly…": "Delete quarantined file…",
    "Mỗi dòng: link | tên tệp. Trang được mở bằng phiên Edge riêng, không lấy tài khoản đang đăng nhập.":
        "One row: URL | filename. Pages open in an isolated Edge session without your signed-in accounts.",
    "Lưu ảnh PNG thay vì PDF": "Save PNG images instead of PDF", "Lưu trang": "Save page",
    "Chọn nơi lưu và bắt đầu…": "Choose destination and start…", "Khay hệ thống": "System tray",
    "Đã đăng ký: {path}": "Registered: {path}", "Có tệp rủi ro đã được cách ly.": "Risky files have been quarantined.",
    "Đã chuyển xong: {path}": "Conversion complete: {path}",
    "Đã tiếp quản và tiếp tục phần còn lại.": "Partial download imported and resumed.",
    "Đã khôi phục theo yêu cầu": "Restored on request", "Đã tính xong SHA-256": "SHA-256 calculated",
    "Mã kết quả: {code}\n{stdout}\n{stderr}": "Result code: {code}\n{stdout}\n{stderr}",
    "Đã nhận link video từ trình duyệt; chọn chất lượng rồi tải.": "Video URL received from the browser; choose quality and download.",
    "Đã giải nén: {path}": "Extracted: {path}", "Đã lưu phiếu: {path}": "Shipping label saved: {path}",
    "Lỗi {name}: {error}": "Error {name}: {error}",
    "Chưa thấy dấu hiệu trong phạm vi kiểm tra; không chứng minh tệp sạch.":
        "No indicators found within inspection limits; this does not certify the file is safe.",
    "Lưu tệp từ trình duyệt": "Save browser download",
    "Tiền tố tên tệp (sẽ thêm 001, 002… và giữ đuôi)": "Filename prefix (adds 001, 002… and keeps the extension)",
    "Mỗi lần nhập tối đa 500 dòng.": "Import up to 500 rows at a time.",
    "Sửa link": "Edit URL", "Đường dẫn HTTP/HTTPS": "HTTP/HTTPS URL", "Sửa tên": "Edit filename",
    "Danh sách chưa có link hợp lệ.": "The list contains no valid URLs.",
    "Đã thêm {count} lượt tải; có thể xuất báo cáo từng dòng trong Công cụ.":
        "Added {count} downloads; a per-row report is available in Preferences.",
    "Dòng": "Row", "Đã tải": "Downloaded", "Tổng": "Total", "Danh sách": "Batch list",
    "Danh sách chưa được thêm đầy đủ; chưa bắt đầu tải.": "The batch was not fully added; downloads have not started.",
    "Cắt / ghép / nén video, nhạc": "Trim / merge / compress video and audio",
    "Che thông tin PDF — xóa thật, xuất bản raster": "Redact PDF — remove content and export a raster copy",
    "Torrent — chọn tệp tải, dừng chia sẻ sau hoàn tất": "Torrent — select files and stop sharing on completion",
    "Mở lại torrent đã lưu": "Reopen saved torrent", "Cắt nhanh": "Fast trim", "Cắt chính xác": "Precise trim",
    "Ghép": "Merge", "Nén MP4": "Compress MP4", "Đổi MP4": "Convert to MP4",
    "Tách MP3": "Extract MP3", "Tách M4A": "Extract M4A", "Thêm tệp": "Add files",
    "Lên": "Move up", "Xuống": "Move down", "Bỏ tệp": "Remove file",
    "Tệp gốc được giữ nguyên.": "Original files are kept.", "Đang xử lý…": "Processing…",
    "Bắt đầu xử lý": "Start processing", "Hủy tác vụ": "Cancel task",
    "Chọn PDF cần xóa thông tin": "Choose a PDF to redact", "Trang trước": "Previous page", "Trang sau": "Next page",
    "Bỏ vùng cuối": "Undo last region", "Xuất PDF đã xóa…": "Export redacted PDF…",
    "Dán magnet, hoặc để trống rồi bấm OK để chọn tệp .torrent": "Paste a magnet URL, or leave blank and click OK to choose a .torrent file",
    "Đang chờ metadata…": "Waiting for metadata…", "Tải các tệp đã chọn": "Download selected files",
    "Chưa có torrent đã lưu.": "No saved torrents.", "Chọn video hoặc nhạc": "Choose video or audio",
    "Bắt đầu (giây)": "Start (seconds)", "Kết thúc (giây)": "End (seconds)",
    "Dung lượng đích (MB)": "Target size (MB)", "Thư mục tải torrent": "Torrent download folder",
    "Xử lý video và âm thanh": "Video and audio processing",
    "Cắt nhanh bám keyframe. Cắt chính xác mã hóa lại. Ghép giữ khung hình nguồn lớn nhất, chuẩn hóa 30fps/AAC.\nNén theo dung lượng đích; đầu ra lớn hơn bản gốc sẽ bị bỏ.":
        "Fast trim follows keyframes. Precise trim re-encodes. Merge keeps the largest source frame and normalizes to 30fps/AAC.\nCompression targets the selected size; outputs larger than the original are discarded.",
    "Giá trị": "Value", "Thời gian và dung lượng phải là số.": "Time and size must be numbers.",
    "Kéo chuột khoanh vùng cần xóa. Xuất PDF raster mới; văn bản, tệp đính kèm và lớp ẩn của bản gốc không được sao chép.":
        "Drag to select regions to remove. Export a new raster PDF without the original text, attachments or hidden layers.",
    "Chọn tệp bằng Ctrl/Shift. Tệp có đuôi thực thi không được chọn mặc định; hãy kiểm tra trước khi tải.":
        "Select files using Ctrl/Shift. Executable files are not selected by default; review them before downloading.",
    "Mở và tiếp tục…": "Open and resume…", "Đã xuất bản xóa thông tin:\n{path}": "Redacted copy exported:\n{path}",
    "Hoàn tất, đã dừng chia sẻ": "Complete, sharing stopped", "Tiến độ": "Progress", "máy ngang hàng": "peers",
    "Trang {page}/{count} · {regions} vùng xóa": "Page {page}/{count} · {regions} redacted regions",
    "Tệp": "File", "Trạng thái": "Status", "Tốc độ": "Speed",
    "Bình thường": "Normal", "URL": "URL", "Thuộc tính": "Properties", "Xong": "Done",
    "Kiểm tra dấu hiệu rủi ro và cách ly tệp đáng ngờ. Kết hợp Windows Defender khi có sẵn; không bảo đảm phát hiện mọi mối đe dọa.":
        "Check for risk indicators and quarantine suspicious files. Use Windows Defender when available; no check detects every threat.",
    "Tra cứu chỉ gửi mã băm, không gửi nội dung tệp.\nKhôi phục tệp cách ly: trong bảng tải, bấm … → Khôi phục tên gốc…":
        "Lookups send only the hash, not file contents.\nTo restore a quarantined file, click … → Restore original name… in the downloads list.",
    "Tự chia thư mục theo loại tệp": "Organize downloads into folders by file type",
    "Ưu tiên tải": "Prioritize downloads", "Kiểm tra": "Check",
    "Tiếng Việt": "Vietnamese", "Tiếng Anh": "English", "Khóa API": "API key",
    "Lấy khóa API": "Get API key",
    "Chất lượng": "Quality", "Tốt nhất": "Best available",
    "Không lấy được tên tệp từ nguồn. Hãy thử lại hoặc kiểm tra quyền truy cập.":
        "Could not retrieve the filename. Retry or check access to the source.",
    "Tùy chọn": "Options", "Quay lại": "Back", "Xóa khỏi danh sách": "Remove from list",
    "Xóa tệp…": "Delete file…", "Xóa vĩnh viễn các tệp sau?": "Permanently delete these files?",
    "Không lấy được tiêu đề nguồn. Bạn có thể sửa tên tệp hoặc thêm cookie.":
        "Could not retrieve the source title. Edit the filename or add cookies.",
    "Dán link để tải tệp trực tiếp, link lưu trữ đám mây, video, MP3/M4A và torrent từ nguồn được hỗ trợ.":
        "Paste a link to download files, cloud storage links, video, MP3/M4A and torrents from supported sources.",
    "Giao diện": "Appearance", "Sáng": "Light", "Tối": "Dark",
    "Chưa có tệp trong mục này": "No downloads in this category",
    "Dán liên kết · nhấn Enter": "Paste a link · press Enter", "Link tệp": "File link",
    "Link đã thay đổi; nhấn Enter để nhận diện lại.": "Link changed; press Enter to detect it again.",
    "Chọn thư mục lưu trước khi tải.": "Choose a destination before downloading.",
    "Xem thông tin và bấm Tải xuống để bắt đầu.": "Review the details and click Download to start.",
    "Kiểm tra an toàn": "Check Safety", "Bộ quét": "Engine", "Kết quả": "Result", "Phát hiện": "Detection",
    "Đang kiểm tra trên máy…": "Running local checks…", "Chưa quét bằng VirusTotal.": "Not checked with VirusTotal.",
    "Nhiều bộ quét · phát hiện mã độc, mã độc tống tiền và virus": "Multiple engines · malware, ransomware and virus detection",
    "Kiểm tra VirusTotal": "Check with VirusTotal", "Gửi tệp để quét mới…": "Submit file for a new scan…",
    "Lấy kết quả quét": "Get scan results", "Mở trang VirusTotal": "Open VirusTotal",
    "Khóa chỉ giữ trong phiên này. Tra mã băm không gửi nội dung tệp.":
        "The key stays in memory for this session. Hash lookups do not upload file contents.",
    "Không có bộ quét nào bảo đảm phát hiện mọi mối đe dọa.": "No scanner can guarantee detection of every threat.",
    "Tệp đã được di chuyển hoặc xóa.": "The file was moved or deleted.",
    "Tệp thay đổi trong lúc kiểm tra; hãy quét lại.": "The file changed during checks. Scan it again.",
    "Cần kiểm tra: ": "Needs review: ",
    "Chưa phát hiện dấu hiệu trong phạm vi kiểm tra.": "No indicators found within the scope of these checks.",
    "Đang tra kết quả nhiều bộ quét…": "Looking up multi-engine results…",
    "VirusTotal chưa có báo cáo. Bạn có thể gửi tệp để quét mới.":
        "VirusTotal has no report yet. You can submit the file for a new scan.",
    "Gửi toàn bộ tệp này lên VirusTotal?\nTệp có thể được chia sẻ với các đối tác bảo mật. Không gửi tệp riêng tư.":
        "Upload this entire file to VirusTotal?\nIt may be shared with security partners. Do not submit private files.",
    "Đang gửi tệp để quét…": "Uploading the file for scanning…",
    "Đã gửi. Đang chờ các bộ quét trả kết quả…": "Submitted. Waiting for scan engines…",
    "Đang chờ quét; chưa có kết luận.": "Scan pending; no verdict is available yet.",
    "Phát hiện mã độc": "Threat detections", "Chưa bộ quét nào phát hiện trong báo cáo này": "No engine detections in this report",
    "Thời điểm báo cáo: ": "Report time: ", "Báo cáo không có kết quả từ bộ quét.": "No engine results are available in this report.",
    "Tải xuống": "Download", "Video & nhạc": "Video & audio", "An toàn": "Safe",
    "Trình duyệt": "Browser", "Công cụ": "Tools",
    "Nhập / Xuất": "Import / Export", "Tiện ích trình duyệt": "Browser extension",
    "Ngôn ngữ": "Language", "Liên hệ hỗ trợ": "Contact support", "Báo lỗi": "Report",
    "Tham gia Discord": "Join Discord", "Giới thiệu": "About", "Thoát": "Quit",
    "Thư mục tải mặc định": "Default download folder", "Tệp gốc": "Original file",
    "Video / nhạc": "Video / audio", "Để trống để dùng tiêu đề gốc.": "Leave empty to use the original title.",
    "Số kết nối tùy nguồn. Tệp tải về được kiểm tra trước khi hoàn tất.":
        "Connections depend on the source. Downloaded files are checked before completion.",
    "Tải tiện ích (.zip)": "Download extension (.zip)", "Đang tải tiện ích…": "Downloading extension…",
    "1. Tải ZIP và giải nén vào thư mục cố định.\n2. Mở chrome://extensions hoặc edge://extensions, bật Chế độ dành cho nhà phát triển.\n3. Chọn Tải tiện ích đã giải nén và thư mục có manifest.json.\n4. Sao chép mã tiện ích, dán bên dưới và đăng ký kết nối.\n5. Mở tiện ích và chọn Kiểm tra kết nối.":
        "1. Download the ZIP and extract it to a permanent folder.\n2. Open chrome://extensions or edge://extensions and enable Developer mode.\n3. Click Load unpacked and choose the folder with manifest.json.\n4. Copy the Extension ID, paste it below and register the connection.\n5. Open the extension and click Test connection.",
    "Đang chờ": "Queued", "Đang tải": "Downloading", "Tạm dừng": "Pause",
    "Đang xác minh": "Verifying", "Hoàn tất": "Complete", "Cách ly": "Quarantined",
    "Lỗi": "Error", "Đã hẹn giờ": "Scheduled", "Tiếp tục": "Resume",
    "Đường dẫn": "Path", "Dán": "Paste", "Tên tệp": "Filename", "Luồng": "Connections",
    "Thêm lượt tải": "Add download", "Lưu tại": "Save to", "Chọn thư mục": "Choose folder",
    "Mã băm": "Checksum", "Link cách bởi dấu |": "Separate links with |",
    "Tùy chọn nâng cao  ▸": "Advanced options  ▸", "Thu gọn tùy chọn  ▾": "Hide options  ▾",
    "Nhập danh sách…": "Import list…", "Mở thư mục": "Open folder",
    "TÊN TỆP": "FILENAME", "TRẠNG THÁI": "STATUS", "TIẾN ĐỘ": "PROGRESS",
    "ĐÃ TẢI / TỔNG": "DOWNLOADED / TOTAL", "TỐC ĐỘ": "SPEED",
    "ĐANG TẢI": "DOWNLOADING", "HOÀN TẤT": "COMPLETED", "TỐC ĐỘ HIỆN TẠI": "CURRENT SPEED",
    "Bắt đầu lượt tải đầu tiên": "Start your first download",
    "Dán đường dẫn ở trên hoặc nhập danh sách từ bảng tính.": "Paste a URL above or import a spreadsheet list.",
    "Chọn một lượt tải để xem chi tiết. Bấm chuột phải để đổi link hoặc nơi lưu.":
        "Select a download for details. Right-click to change its link or folder.",
    "Sẵn sàng · dữ liệu tải được lưu trên máy của bạn": "Ready · download history stays on your computer",
    "Tải. Sắp xếp. Hoàn tất.": "Download. Organize. Done.",
    "Lưu video hoặc tách MP3": "Download video or extract MP3",
    "Dùng yt-dlp tùy chọn. Chỉ tải nội dung bạn có quyền truy cập; không hỗ trợ DRM.":
        "Uses optional yt-dlp support. Download content you can access; DRM is not supported.",
    "Độ cao tối đa": "Maximum resolution", "Cả danh sách phát": "Entire playlist",
    "Phụ đề vi/en": "VI/EN subtitles", "Chọn cookie do bạn xuất…": "Choose exported cookies…",
    "Tải video": "Download video", "Tải MP3": "Download MP3", "Tải M4A": "Download M4A",
    "Xem định dạng": "Show formats", "Dừng / bỏ link đang chọn": "Stop / clear selected link",
    "Lưu vào thư mục đã chọn ở thẻ Tải xuống.": "Saves to the folder selected in Downloads.",
    "Chuyển video sang MP4 H.264 / AAC": "Convert video to MP4 H.264 / AAC",
    "Cần FFmpeg trong PATH. Tệp gốc được giữ lại; thao tác có thể mất vài phút.":
        "Requires FFmpeg. Original files are kept; processing may take a few minutes.",
    "Chọn video để chuyển…": "Choose video to convert…",
    "Cắt / ghép / nén / tách nhạc…": "Trim / merge / compress / extract audio…",
    "Cập nhật yt-dlp từ nguồn chính thức…": "Update yt-dlp from the official source…",
    'Cài hỗ trợ video: pip install ".[media,processing]"\nTệp cookie là tùy chọn; app không tự đọc tài khoản trình duyệt.':
        'Video support: pip install ".[media,processing]"\nCookies are optional; browser accounts are not read automatically.',
    "Kiểm tra trước khi mở tệp": "Check files before opening",
    "Tệp thực thi, tài liệu macro, ký tự đảo chiều và tệp sai SHA-256 sẽ được đổi đuôi .chuakiemtra.\nĐây là kiểm tra sơ bộ, không phải phần mềm diệt virus. Tệp thông thường chưa được chứng nhận sạch.":
        "Executables, macro documents, reversed filenames and checksum mismatches are quarantined as .chuakiemtra.\nThese preliminary checks do not replace antivirus or certify that other files are safe.",
    "Tính SHA-256 của tệp…": "Calculate file SHA-256…",
    "Quét bằng Windows Defender…": "Scan with Windows Defender…",
    "Kiểm tra ZIP / chữ ký…": "Inspect ZIP / signature…",
    "Tra mã băm trên dịch vụ đã chọn": "Look up hash with selected service",
    "An toàn cao: cách ly chương trình chưa có chữ ký Windows hợp lệ":
        "High security: quarantine programs without a valid Windows signature",
    "Bật/tắt bảo vệ thư mục tải của trình duyệt…": "Toggle browser download folder protection…",
    "Xem nhật ký cách ly thư mục…": "View folder quarantine log…",
    "Tra cứu chỉ gửi mã băm trong URL tới dịch vụ đã chọn, không tải tệp lên.\nĐể khôi phục tệp cách ly: chọn lượt tải → chuột phải → Khôi phục tên gốc…":
        "Lookups send only the hash to the selected service; files are not uploaded.\nTo restore: select a download → right-click → Restore original name…",
    "Kết nối trình duyệt": "Browser connection",
    "Chrome / Edge / Brave / Cốc Cốc: nạp thư mục tiện ích ở chế độ nhà phát triển, sao chép mã tiện ích rồi đăng ký bên dưới. Quyền tùy chọn và bộ lọc được quản lý trong cửa sổ tiện ích.":
        "Load the extension folder in Developer mode, copy its ID, and register it below. Manage permissions and filters in the extension popup.",
    "Đăng ký kết nối cho tài khoản này": "Register connection for this account",
    "Dùng menu chuột phải “Tải bằng HDM” hoặc mở cửa sổ tiện ích để hiện nút tải phía trên video. Yêu cầu được lưu trên máy. Chuyển phiên đăng nhập từ tiện ích hiện chỉ hỗ trợ Windows, với mã hóa DPAPI. Trên macOS/Linux, dùng tệp cookie bạn tự chọn trong mục Video & nhạc.":
        "Use the Download with HDM context menu or the video button above the player. Requests stay local. Encrypted session transfer uses Windows DPAPI; on macOS/Linux choose an exported cookie file in Video & audio.",
    "Bộ lọc hỗ trợ quy tắc mạng, chặn tab quảng cáo đã nhận diện, chọn phần tử và thống kê. Dùng cửa sổ tiện ích để quản lý quyền, ngoại lệ và luồng HLS/DASH; một số cú pháp bộ lọc chưa được hỗ trợ.":
        "Filters support network rules, recognized ad tabs, element selection and statistics. Manage exceptions and HLS/DASH streams in the popup; some filter syntax is unsupported.",
    "Tài liệu và tác vụ bổ sung": "Documents and additional tools",
    "Che thông tin PDF bằng vùng kéo chuột…": "Redact PDF with selected regions…",
    "Lưu trang web thành PDF / ảnh…": "Save web pages as PDF / images…",
    "Cắt / ghép / nén video, nhạc…": "Trim / merge / compress video and audio…",
    "Giải mã link Drive / Dropbox / OneDrive / MediaFire…": "Resolve cloud storage links…",
    "Tiếp quản tệp trình duyệt tải dở…": "Resume a partial browser download…",
    "Torrent / magnet — chọn từng tệp…": "Torrent / magnet — select files…",
    "Mở lại torrent đã lưu…": "Reopen a saved torrent…",
    "Mở thư mục phiếu giao hàng…": "Open shipping labels folder…",
    "Giải nén ZIP sau khi kiểm tra…": "Check and extract ZIP…",
    "Tìm phụ đề Việt khớp tệp phim…": "Find matching Vietnamese subtitles…",
    "Xuất lịch sử tải CSV…": "Export download history as CSV…",
    "Kiểm tra bản cập nhật ký số…": "Check for update",
    "Xuất báo cáo danh sách từng dòng…": "Export batch completion report…",
    "Tự chia thư mục Video / Music / Images / Documents / Archives cho lượt tải mới":
        "Sort new downloads into Video / Music / Images / Documents / Archives",
    "Tự giải nén ZIP sau khi tải và kiểm tra an toàn thành công": "Extract ZIP after download and successful safety checks",
    "Thu xuống khay hệ thống khi đóng cửa sổ (dùng menu khay để thoát)": "Minimize to tray on close (use tray menu to quit)",
    "Tắt máy sau khi các lượt HTTP đang chờ đều hoàn tất (đếm ngược 60 giây)":
        "Shut down after pending HTTP downloads complete (60-second countdown)",
    "Hủy lệnh tắt máy đã hẹn": "Cancel scheduled shutdown", "Mở GitHub": "Open GitHub",
    "Tối đa": "Maximum", "Vừa (4 MB/s)": "Medium (4 MB/s)", "Nhẹ (512 KB/s)": "Light (512 KB/s)",
    "HDM là ứng dụng quản lý tải cho Windows, macOS và Linux, tích hợp các trình duyệt nhân Chromium.":
        "HDM manages downloads on Windows, macOS and Linux, with Chromium browser integration.",
    "Máy chủ không có ETag mạnh hoặc không cho tải theo Range sẽ dùng một luồng. Nếu không xác minh được nội dung cũ, ứng dụng tải lại từ đầu để tránh ghép sai tệp.":
        "Servers without strong ETags or byte ranges use one connection. Unverifiable partial content is downloaded again to avoid corrupt files.",
    "HDM giúp tải, quản lý và xử lý tệp trên máy của bạn. Các công cụ có điều kiện hỗ trợ riêng theo nền tảng, máy chủ và định dạng.":
        "Download, organize and process files locally. Tool support depends on your platform, source and file format.",
    "Biểu tượng dùng Morphicons kết hợp Lucide. Thiết kế giao diện tham khảo React Bits.":
        "Icons use Morphicons and Lucide. Interface design references React Bits.",
    "Tiếp tục tải": "Resume download", "Thay link tải…": "Replace download link…",
    "Đổi thư mục lưu…": "Change save folder…", "Đổi nơi lưu trong lúc tải…": "Move active download…",
    "Hẹn giờ tải…": "Schedule download…", "Chép SHA-256": "Copy SHA-256",
    "Khôi phục tên gốc…": "Restore original name…", "Cắt / ghép / nén…": "Trim / merge / compress…",
    "Nhật ký lượt tải…": "Download log…", "Đóng": "Close", "Hủy": "Cancel",
    "Tải bản cập nhật": "Download update", "Cài đặt bản cập nhật": "Install update",
    "Đang kiểm tra cập nhật…": "Checking for updates…",
    "Bạn đang dùng phiên bản mới nhất.": "You are up to date.",
    "Đã tải và xác minh bản cập nhật.": "Update downloaded and verified.",
    "Đã hủy tải bản cập nhật.": "Update download cancelled.", "Thử lại": "Retry",
    "Mở bộ cài": "Open installer", "Mở thư mục cập nhật": "Open updates folder",
    "Chung": "General", "Thiết lập": "Preferences", "Định dạng": "Format", "LUỒNG": "CONNECTIONS", "AN TOÀN": "SAFETY",
    "Tùy chọn tải": "Download preferences",
    "Kiểm tra cập nhật": "Check for update",
    "Dùng định dạng này": "Use this format",
    "Format ID chọn một luồng cụ thể; chọn Auto để tự ghép video và âm thanh.":
        "Format ID selects a specific stream. Leave it empty to combine video and audio automatically.",
    "Tự nhận link từ clipboard": "Detect links from clipboard",
    "Chọn native bridge": "Choose native messaging host",
    "Dán hai cột link / tên, rồi bấm Xem trước. Nhấp đúp một dòng để sửa.":
        "Paste URL and filename columns, then click Preview. Double-click a row to edit it.",
    "Link": "Link", "Mở tệp…": "Open file…", "Xem trước": "Preview", "Sửa dòng": "Edit row",
    "Đổi tên hàng loạt": "Rename in bulk", "Xóa dòng": "Remove row", "Bắt đầu tải": "Start downloads",
    "Dùng menu chuột phải “Tải bằng HDM” hoặc mở cửa sổ tiện ích để hiện nút tải phía trên video. Yêu cầu được lưu trên máy. Chuyển phiên đăng nhập từ tiện ích hiện chỉ hỗ trợ Windows, với mã hóa DPAPI. Trên macOS/Linux, chọn tệp cookie trong tùy chọn nâng cao.":
        "Use Download with HDM in the context menu or the extension popup to show a download button above videos. Requests stay local. Encrypted session transfer uses Windows DPAPI; on macOS/Linux, choose an exported cookie file.",
    "Khởi động cùng hệ điều hành": "Start HDM at sign-in",
    "Chỉ nhận link trên máy; chờ bạn bấm tải trước khi kết nối tới nguồn.":
        "Link detection stays local. HDM connects to the source only after you click Download.",
    "Cập nhật bộ tải video…": "Update media downloader…",
    "Tự quét bằng Windows Defender sau khi tải": "Scan completed downloads with Windows Defender",
    "Dùng link mới": "Use new link",
    "Có link mới trong clipboard. Giữ nguyên link bạn đang sửa.":
        "New clipboard link available. Your current URL has been kept.",
    "Đã nhận link từ clipboard · chọn định dạng và bấm tải.":
        "Clipboard link detected · choose a format and click Download.",
    "Đã nhận link từ clipboard · bấm tải để xem lựa chọn.":
        "Clipboard link detected · click Download to see options.",
    "Tệp gốc · tối đa 32 kết nối · kiểm tra an toàn sau tải":
        "Original file · up to 32 connections · safety checks after download",
    "Đã nhận link video/nhạc · chọn MP4, MP3 hoặc M4A rồi tải":
        "Video/audio link detected · choose MP4, MP3 or M4A and download",
    "Đã nhận magnet · chọn tệp cần tải trong bước tiếp theo":
        "Magnet detected · choose files in the next step",
    "Nhạc Spotify có DRM: không thể tải trực tiếp thành MP3.":
        "Spotify music is DRM-protected and cannot be downloaded directly as MP3.",
    "Chưa kiểm tra": "Not checked", "Chờ kiểm tra": "Pending checks",
    "Đang kiểm tra": "Checking", "Đã kiểm tra sơ bộ": "Preliminary checks",
    "Sơ bộ · Defender chưa quét": "Checks · Defender unavailable",
    "Sơ bộ + Defender": "Checks + Defender",
    "Link đã thay đổi; bấm tải lại để dùng link mới.": "The URL changed. Click Download again to use the new link.",
    "Đang nhận diện nguồn tải…": "Detecting download source…",
    "Đã thêm lượt tải; sẽ kiểm tra trước khi hoàn tất.": "Download added; safety checks run before completion.",
    "Đang có lượt tải video/nhạc. Hãy chờ hoặc tạm dừng lượt đó.":
        "A media download is active. Wait for it or pause it first.",
    "Tải nhanh": "Fast downloads", "Bảo vệ người dùng": "User protection",
    "Một nơi để tải": "One place to download", "Tiện ích hằng ngày": "Everyday essentials",
    "Giới hạn nguồn": "Source limitations",
    "Tối đa 32 kết nối, chia khối cho luồng đang rảnh; tự giảm khi nguồn giới hạn. Tạm dừng, tiếp tục, thử lại và thay link hết hạn.":
        "Up to 32 connections share queued chunks and back off when a source limits requests. Pause, resume, retry and replace expired links.",
    "Kiểm tra nội dung, tệp giả dạng, macro, tệp nén và mã băm. Cách ly tệp rủi ro; tích hợp quét Windows Defender khi có sẵn.":
        "Inspect content, disguised files, macros, archives and checksums. Quarantine risky files and scan with Windows Defender when available.",
    "Tự nhận link clipboard. Tải tệp trực tiếp, link lưu trữ đám mây, video, MP3/M4A và torrent từ nguồn được hỗ trợ.":
        "Recognize clipboard links. Download direct files, cloud links, video, MP3/M4A and torrents from supported sources.",
    "Nhập danh sách, hẹn giờ, đổi nơi lưu, giới hạn băng thông, chạy nền và tùy chọn khởi động cùng hệ điều hành.":
        "Import lists, schedule downloads, move files, limit bandwidth, run in the background and optionally start at sign-in.",
    "Số kết nối thực tùy máy chủ. Một số nguồn yêu cầu đăng nhập; nội dung DRM, gồm nhạc Spotify, không tải trực tiếp thành MP3. Kiểm tra sơ bộ không chứng nhận tệp sạch.":
        "Actual connections depend on the source. Some sites require sign-in; DRM-protected content, including Spotify music, cannot be downloaded directly as MP3. Preliminary checks do not certify a file as safe.",
}

PALETTES = {
    "dark": ("#121212", "#181818", "#eeeeee", "#a6a6a6", "#67d1f4"),
    "light": ("#f6f6f6", "#ffffff", "#222222", "#626262", "#087a9f"),
}
SEMANTIC_COLORS = {
    "dark": {"safe": "#4ade80", "risk": "#facc15", "danger": "#f87171"},
    "light": {"safe": "#15803d", "risk": "#a16207", "danger": "#b91c1c"},
}


def speed_color(speed, theme):
    if speed <= 0:
        return PALETTES[theme][3]
    level = "safe" if speed >= 10*1024**2 else "risk" if speed >= 1024**2 else "danger"
    return SEMANTIC_COLORS[theme][level]


DARK_COLORS = {
    '#121212': '#f6f6f6', '#181818': '#ffffff', '#eeeeee': '#222222',
    '#a6a6a6': '#626262', '#67d1f4': '#087a9f', '#272727': '#ececec',
    '#333333': '#e4e4e4', '#303030': '#e2e2e2', '#b6eaff': '#076581',
    '#3a3a3a': '#d0d0d0', '#383838': '#e0e0e0', '#343434': '#dddddd',
    '#6ee7b7': '#187a57', '#93c5fd': '#245caa',
}


class SlideSwitch(tk.Canvas):
    """Two-position thumb switch, also operable with Tab, Space and arrow keys."""

    def __init__(self, parent, labels, value, command, description):
        super().__init__(parent, width=94, height=32, highlightthickness=0, takefocus=True)
        self.labels, self.value, self.command = labels, bool(value), command
        self.description = description
        self.bind("<Button-1>", lambda _: self.toggle())
        self.bind("<space>", lambda _: self.toggle())
        self.bind("<Return>", lambda _: self.toggle())
        self.bind("<Left>", lambda _: self.toggle(False))
        self.bind("<Right>", lambda _: self.toggle(True))
        self.bind("<FocusIn>", lambda _: self.draw())
        self.bind("<FocusOut>", lambda _: self.draw())
        self.theme = "dark"
        self.draw()

    def toggle(self, value=None):
        self.value = not self.value if value is None else value
        self.draw()
        self.command(self.value)
        return "break"

    def draw(self):
        bg, panel, _text, muted, accent = PALETTES[self.theme]
        self.configure(background=bg)
        self.delete("all")
        self.create_polygon(16, 1, 78, 1, 93, 1, 93, 16, 93, 31, 78, 31,
                            16, 31, 1, 31, 1, 16, 1, 1, smooth=True, fill=panel,
                            outline=accent if self.focus_get() == self else muted)
        x = 48 if self.value else 3
        self.create_polygon(x+12, 4, x+30, 4, x+42, 4, x+42, 16, x+42, 28,
                            x+30, 28, x+12, 28, x, 28, x, 16, x, 4,
                            smooth=True, fill=accent, outline="", width=0)
        for index, label in enumerate(self.labels):
            self.create_text(25+44*index, 16, text=label, font=("Segoe UI", 9, "bold"),
                             fill=("white" if self.theme == "light" else "#10252f")
                             if index == int(self.value) else muted)


class Localizer:
    """Translate presentation text without rewriting filenames, URLs or control values."""

    def __init__(self, root, language="vi"):
        self.root, self.language = root, language
        self.variables = WeakKeyDictionary()
        self.reverse = {value: key for key, value in TRANSLATIONS.items()}

    def text(self, value):
        original = self.reverse.get(str(value), str(value))
        if original in TRANSLATIONS:
            return TRANSLATIONS[original] if self.language == "en" else original
        # Match only complete, catalogued messages. Captures are user/provider data,
        # so filenames, paths and detection names are never translated themselves.
        for vi, en, vi_pattern, en_pattern, fields in message_templates():
            for pattern in (vi_pattern, en_pattern):
                match = pattern.fullmatch(str(value))
                if match:
                    template = en if self.language == "en" else vi
                    values = dict(zip(fields, match.groups(), strict=True))
                    if "error" in values:
                        values["error"] = self.text(values["error"])
                    return template.format(**values)
        return str(value)

    def apply(self, parent=None):
        parent = parent or self.root
        for widget in parent.winfo_children():
            if isinstance(widget, tk.Toplevel) and not widget.overrideredirect():
                widget.title(self.text(widget.title()))
            if isinstance(widget, (ttk.Label, ttk.Button, ttk.Checkbutton, ttk.Radiobutton)) and getattr(widget, "translate_text", True):
                variable = widget.cget("textvariable")
                if variable:
                    if widget not in self.variables:
                        output = tk.StringVar(master=self.root)
                        source = str(variable)

                        def update(*_, source=source, output=output):
                            output.set(self.text(self.root.getvar(source)))

                        trace = self.root.register(update)
                        self.root.tk.call("trace", "add", "variable", source, "write", trace)
                        def cleanup(event, source=source, trace=trace, owner=widget):
                            if event.widget == owner:
                                self.root.tk.call("trace", "remove", "variable", source, "write", trace)
                                self.root.deletecommand(trace)
                                self.variables.pop(owner, None)
                        widget.bind("<Destroy>", cleanup, add="+")
                        self.variables[widget] = (output, update, trace)
                        widget.configure(textvariable=output)
                    self.variables[widget][1]()
                else:
                    widget.configure(text=self.text(widget.cget("text")))
            if isinstance(widget, ttk.Treeview):
                for column in widget.cget("columns"):
                    widget.heading(column, text=self.text(widget.heading(column, "text")))
            if isinstance(widget, ttk.Notebook):
                for tab in widget.tabs():
                    widget.tab(tab, text=self.text(widget.tab(tab, "text")))
            self.apply(widget)
            refresh_language = getattr(widget, "refresh_language", None)
            if callable(refresh_language):
                refresh_language()


@lru_cache(maxsize=1)
def message_templates():
    """Compile known formatted messages once, escaping all literal characters."""
    result = []
    for vi, en in TRANSLATIONS.items():
        if "{" not in vi:
            continue
        def compile_message(template):
            parts, fields = [], []
            for literal, field, _spec, _conversion in Formatter().parse(template):
                parts.append(re.escape(literal))
                if field is not None:
                    fields.append(field)
                    parts.append("(.*?)")
            return re.compile("".join(parts), re.DOTALL), fields
        vi_pattern, fields = compile_message(vi)
        en_pattern, en_fields = compile_message(en)
        if fields != en_fields:
            raise ValueError("Translation placeholders must have the same order")
        result.append((vi, en, vi_pattern, en_pattern, fields))
    return result


def recolor(parent, colors):
    """Update explicit colors as well as themed styles, including open dialogs."""
    if getattr(parent, "_hdm_shared_surface", False):
        # Its vector frame is replaced once, after layout and translation finish.
        return
    for option in ("background", "foreground", "insertbackground", "selectbackground",
                   "selectforeground", "highlightbackground", "highlightcolor"):
        if option in set(parent.keys()):
            old = str(parent.cget(option)).lower()
            if old in colors:
                parent.configure(**{option: colors[old]})
    if isinstance(parent, tk.Canvas):
        for item in parent.find_all():
            for option in ("fill", "outline"):
                try:
                    old = parent.itemcget(item, option).lower()
                    if old in colors:
                        parent.itemconfigure(item, **{option: colors[old]})
                except tk.TclError:
                    pass
    for widget in parent.winfo_children():
        recolor(widget, colors)
