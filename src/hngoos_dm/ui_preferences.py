"""Persistent presentation controls; localization never changes task input values."""

import tkinter as tk
from tkinter import ttk
from weakref import WeakKeyDictionary


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


TRANSLATIONS = {
    "Giao diện": "Appearance", "Sáng": "Light", "Tối": "Dark",
    "Chưa có tệp trong mục này": "No downloads in this category",
    "Dán liên kết · nhấn Enter": "Paste a link · press Enter", "Link tệp": "File link",
    "Link đã thay đổi; nhấn Enter để nhận diện lại.": "Link changed; press Enter to detect it again.",
    "Chọn thư mục lưu trước khi tải.": "Choose a destination before downloading.",
    "Xem thông tin và bấm Tải xuống để bắt đầu.": "Review the details and click Download to start.",
    "Kiểm tra an toàn": "Check Safety", "Bộ quét": "Engine", "Kết quả": "Result", "Phát hiện": "Detection",
    "Đang kiểm tra trên máy…": "Running local checks…", "Chưa quét bằng VirusTotal.": "Not checked with VirusTotal.",
    "Nhiều bộ quét · phát hiện mã độc, ransomware và virus": "Multiple engines · malware, ransomware and virus detection",
    "Kiểm tra VirusTotal": "Check with VirusTotal", "Gửi tệp để quét mới…": "Submit file for a new scan…",
    "Lấy API key": "Get API key",
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
    "Tải xuống": "Download", "Video & nhạc": "Video & audio", "An toàn": "Safety",
    "Trình duyệt": "Browser", "Công cụ": "Tools", "Thông tin": "Info",
    "Nhập / Xuất": "Import / Export", "Tiện ích trình duyệt": "Browser extension",
    "Ngôn ngữ": "Language", "Liên hệ hỗ trợ": "Contact support", "Báo lỗi": "Submit a bug report",
    "Tham gia Discord": "Join Discord", "Giới thiệu": "About", "Thoát": "Quit",
    "Thư mục tải mặc định": "Default download folder", "Tệp gốc": "Original file",
    "Video / nhạc": "Video / audio", "Để trống để dùng tiêu đề gốc.": "Leave empty to use the original title.",
    "Số kết nối tùy nguồn. Tệp tải về được kiểm tra trước khi hoàn tất.":
        "Connections depend on the source. Downloaded files are checked before completion.",
    "Tải tiện ích (.zip)": "Download extension (.zip)", "Đang tải tiện ích…": "Downloading extension…",
    "1. Tải ZIP và giải nén vào thư mục cố định.\n2. Mở chrome://extensions hoặc edge://extensions, bật Developer mode.\n3. Chọn Load unpacked và thư mục có manifest.json.\n4. Sao chép Extension ID, dán bên dưới và đăng ký kết nối.\n5. Mở tiện ích và chọn Test connection.":
        "1. Download the ZIP and extract it to a permanent folder.\n2. Open chrome://extensions or edge://extensions and enable Developer mode.\n3. Click Load unpacked and choose the folder with manifest.json.\n4. Copy the Extension ID, paste it below and register the connection.\n5. Open the extension and click Test connection.",
    "Đang chờ": "Queued", "Đang tải": "Downloading", "Tạm dừng": "Pause",
    "Kiểm tra": "Verifying", "Hoàn tất": "Complete", "Cách ly": "Quarantined",
    "Lỗi": "Error", "Đã hẹn giờ": "Scheduled", "Tiếp tục": "Resume",
    "Đường dẫn": "URL", "Dán": "Paste", "Tên tệp": "Filename", "Luồng": "Connections",
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
    "Chrome / Edge / Brave / Cốc Cốc: nạp thư mục browser-extension ở chế độ nhà phát triển, sao chép Extension ID rồi đăng ký bên dưới. Quyền tùy chọn và bộ lọc được quản lý trong popup extension.":
        "Load the extension folder in Developer mode, copy its ID, and register it below. Manage permissions and filters in the extension popup.",
    "Đăng ký kết nối cho tài khoản này": "Register connection for this account",
    "Dùng menu chuột phải “Tải bằng HDM” hoặc bấm popup để hiện nút tải phía trên video. Yêu cầu được lưu trên máy. Chuyển phiên đăng nhập từ tiện ích hiện chỉ hỗ trợ Windows, với mã hóa DPAPI. Trên macOS/Linux, dùng tệp cookie bạn tự chọn trong mục Video & nhạc.":
        "Use the Download with HDM context menu or the video button above the player. Requests stay local. Encrypted session transfer uses Windows DPAPI; on macOS/Linux choose an exported cookie file in Video & audio.",
    "Bộ lọc hỗ trợ quy tắc mạng, chặn tab quảng cáo đã nhận diện, chọn phần tử và thống kê. Dùng popup để quản lý quyền, ngoại lệ và luồng HLS/DASH; một số cú pháp bộ lọc chưa được hỗ trợ.":
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
    "dark": ("#121212", "#181818", "#eeeeee", "#a6a6a6", "#a78bfa"),
    "light": ("#f6f6f6", "#ffffff", "#222222", "#626262", "#6d28d9"),
}
DARK_COLORS = {
    '#121212': '#f6f6f6', '#181818': '#ffffff', '#eeeeee': '#222222',
    '#a6a6a6': '#626262', '#a78bfa': '#6d28d9', '#272727': '#ececec',
    '#333333': '#e4e4e4', '#303030': '#e2e2e2', '#d9c8ff': '#5828a0',
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
                             fill=("white" if self.theme == "light" else "#151020")
                             if index == int(self.value) else muted)


class Localizer:
    """Translate presentation text without rewriting filenames, URLs or control values."""

    def __init__(self, root, language="vi"):
        self.root, self.language = root, language
        self.variables = WeakKeyDictionary()
        self.reverse = {value: key for key, value in TRANSLATIONS.items()}

    def text(self, value):
        original = self.reverse.get(str(value), str(value))
        return TRANSLATIONS.get(original, original) if self.language == "en" else original

    def apply(self, parent=None):
        parent = parent or self.root
        for widget in parent.winfo_children():
            if isinstance(widget, (ttk.Label, ttk.Button, ttk.Checkbutton, ttk.Radiobutton)):
                variable = widget.cget("textvariable")
                if variable:
                    if widget not in self.variables:
                        output = tk.StringVar(master=self.root)
                        source = str(variable)

                        def update(*_, source=source, output=output):
                            output.set(self.text(self.root.getvar(source)))

                        trace = self.root.tk.call("trace", "add", "variable", source, "write",
                                                  self.root.register(update))
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


def recolor(parent, colors):
    """Update explicit colors as well as themed styles, including open dialogs."""
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
