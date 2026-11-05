<div align="center">

![hngoos-download-manager](docs/assets/banner.svg)

# HDM

### Trình quản lý tải xuống cho Windows

Tải tệp, lưu video, xử lý media và quản lý tài liệu trong một ứng dụng.

[![Release](https://img.shields.io/github/v/release/hngoos/hngoos-download-manager?color=8b5cf6)](https://github.com/hngoos/hngoos-download-manager/releases/latest)
[![Windows](https://img.shields.io/badge/Windows-10%20%2F%2011%20x64-0078d4)](https://github.com/hngoos/hngoos-download-manager/releases/latest)
[![License](https://img.shields.io/badge/License-Proprietary-64748b)](LICENSE)

[**Tải bộ cài Windows**](https://github.com/hngoos/hngoos-download-manager/releases/latest/download/HDM-Setup-0.1.0.exe) · [**Tải tiện ích browser**](https://github.com/hngoos/hngoos-download-manager/releases/latest/download/HDM-Browser-Extension.zip)

[Giới thiệu](#giới-thiệu) · [Ưu điểm](#ưu-điểm) · [Chức năng](#chức-năng) · [Cài đặt](#cài-đặt) · [Hướng dẫn](docs/USAGE.md)

</div>

![Giao diện HDM](docs/screenshot.png)

## Giới thiệu

**hngoos-download-manager**, viết tắt **HDM**, giúp bạn quản lý các lượt tải HTTP/HTTPS, tải video và âm thanh, nhập danh sách từ bảng tính, xử lý media và lưu tài liệu. Ứng dụng chạy trên **Windows 10/11 64-bit**, có giao diện tiếng Việt và lưu lịch sử tải trên máy.

## Ưu điểm

- **Giữ tiến độ tải:** tạm dừng, tiếp tục sau khi mở lại ứng dụng, tự thử lại khi lỗi mạng. Phần cũ chỉ được dùng lại khi máy chủ cung cấp đủ thông tin xác minh.
- **Làm việc theo danh sách:** dán hai cột link–tên từ Excel/Google Sheets hoặc nhập CSV/TXT/XLSX, giảm việc đổi tên từng tệp.
- **Xử lý ngay sau khi tải:** cắt, ghép, chuyển định dạng, nén video và tách âm thanh trong ứng dụng.
- **Kiểm tra trước khi mở:** đối chiếu mã băm, nhận diện dấu hiệu rủi ro và cách ly tệp đáng ngờ; hỗ trợ gọi Windows Defender.
- **Chủ động quyền riêng tư:** tích hợp trình duyệt theo quyền tùy chọn; không yêu cầu tạo tài khoản HDM.
- **Giao diện tập trung:** nền tối, thanh điều hướng rõ ràng, thống kê hàng đợi và biểu tượng Morphicons có chuyển động nhẹ.

## Chức năng

| Nhóm | Khả năng |
| --- | --- |
| **Tải tệp** | 1–32 luồng, hàng đợi, tạm dừng/tiếp tục, retry, mirror có SHA-256, thay link, đổi nơi lưu và bộ nhớ đệm HTTP cục bộ |
| **Danh sách** | Dán link–tên, nhập CSV/TXT/XLSX và hyperlink, đánh số và phân loại thư mục |
| **Video / âm thanh** | Chọn chất lượng tối đa, MP3/M4A, playlist, phụ đề qua yt-dlp |
| **Công cụ media** | Cắt nhanh hoặc chính xác, ghép, chuyển MP4, nén hai lượt theo dung lượng đích, tách nhạc |
| **PDF / website** | Che vùng nhạy cảm bằng PDF raster mới; lưu trang thành PDF/PNG có nguồn và thời điểm |
| **Kiểm tra tệp** | MD5/SHA-1/SHA-256/SHA-512, kiểm ZIP, phát hiện đuôi rủi ro, cách ly và Defender |
| **Trình duyệt** | Gửi link/video qua native messaging, tiếp quản tải HTTP/HTTPS tùy chọn, nút ngoài khung video, phiên đăng nhập theo quyền tùy chọn |
| **Phiếu giao hàng** | Lưu bản in theo sàn/ngày/mã đơn từ trang bán hàng được bật quyền; tính năng thử nghiệm |
| **Tiện ích** | Hẹn giờ, băng thông, torrent chọn tệp và lưu tiến độ, link cloud công khai, khay hệ thống và cập nhật có manifest ký số |

Điều kiện hỗ trợ phụ thuộc máy chủ và website. HDM không hỗ trợ nội dung DRM; kiểm tra tệp sơ bộ không thay thế phần mềm chống mã độc. Xem [hướng dẫn chức năng](docs/FEATURES.md) khi cần thông tin chi tiết.

## Cài đặt

### Bộ cài Windows

1. Mở [trang tải HDM](https://github.com/hngoos/hngoos-download-manager/releases/latest).
2. Tải tệp `HDM-Setup-<version>.exe` của phiên bản mới nhất.
3. Chạy bộ cài và mở **HDM**. Không cần cài Python.
4. Dán URL, chọn nơi lưu rồi thêm lượt tải.

Bộ cài chứa ứng dụng, bridge và thông báo giấy phép thư viện; không cần tải riêng các thành phần này. Bộ cài hiện chưa có chữ ký Authenticode. HDM xác minh cập nhật bằng manifest Ed25519 trong dữ liệu phát hành.

### Tiện ích trình duyệt

1. Tải và giải nén `HDM-Browser-Extension.zip` từ cùng release.
2. Mở trang quản lý extension của Chrome/Edge, bật **Developer mode → Load unpacked**, chọn thư mục **Chromium** trong gói đã giải nén.
3. Sao chép Extension ID, mở thẻ **Trình duyệt** trong HDM và đăng ký kết nối.
4. Kiểm tra kết nối trong Options của extension. Quyền dùng cookie là tùy chọn riêng.

Firefox dùng thư mục **Firefox** trong cùng gói: mở `about:debugging` → **This Firefox → Load Temporary Add-on**, chọn `Firefox/manifest.json`, rồi đăng ký Firefox trong HDM. Gói chưa ký AMO nên cần nạp lại sau khi khởi động lại Firefox.

Repo công khai chỉ chứa giới thiệu, hình ảnh và hướng dẫn. Mã nguồn ứng dụng không được công khai; `git clone` chỉ tải tài liệu. Hai gói tải chính là **bộ cài HDM** và **tiện ích trình duyệt** tại [Releases](https://github.com/hngoos/hngoos-download-manager/releases/latest).
