<div align="center">

![hngoos-download-manager — HDM](docs/assets/banner.svg)

**Tải tệp. Giữ tiến độ. Xử lý ngay trong HDM.**

[![Release](https://img.shields.io/github/v/release/hngoos/hngoos-download-manager?color=8b5cf6)](https://github.com/hngoos/hngoos-download-manager/releases/latest) [![Windows](https://img.shields.io/badge/Windows-10%20%2F%2011%20x64-0078d4)](#yêu-cầu-hệ-thống) [![License](https://img.shields.io/badge/License-Proprietary-64748b)](LICENSE)

[**Tải HDM v0.1.0 cho Windows**](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.0/HDM-Setup-0.1.0.exe) · [**Tải tiện ích trình duyệt**](https://github.com/hngoos/hngoos-download-manager/releases/latest/download/HDM-Browser-Extension.zip)

[Giới thiệu](#giới-thiệu) · [Ưu điểm](#ưu-điểm) · [Chức năng](#chức-năng) · [Cài đặt](#cài-đặt) · [Hướng dẫn sử dụng](docs/USAGE.md)

</div>

![Giao diện quản lý tải xuống của HDM v0.1.0](docs/screenshot.png)

## Giới thiệu

**hngoos-download-manager (HDM)** là ứng dụng quản lý tải xuống cho **Windows 10/11 64-bit**. HDM tập hợp tải tệp, video, âm thanh, danh sách từ bảng tính và các công cụ xử lý media, PDF trong cùng một giao diện tiếng Việt.

Bạn có thể dán một link để tải, nhập cả danh sách tài liệu, hoặc gửi link từ trình duyệt sang HDM. Sau khi tải, các thao tác cắt, ghép, nén, chuyển định dạng và kiểm tra tệp có sẵn trong ứng dụng.

**v0.1.0 là bản phát hành đầu tiên.** Các tính năng và điều kiện hỗ trợ được mô tả bên dưới; lưu phiếu bán hàng và lọc quảng cáo hiện ở mức thử nghiệm. Xem [phạm vi hỗ trợ chi tiết](docs/FEATURES.md) trước khi dùng cho công việc cần độ tin cậy cao.

## Ưu điểm

| Ưu điểm | Lợi ích khi sử dụng |
| --- | --- |
| **Giữ tiến độ tải** | Tạm dừng, tải tiếp khi mở lại ứng dụng và tự thử lại khi lỗi mạng, với máy chủ hỗ trợ xác minh phần đã tải. |
| **Giảm việc đổi tên thủ công** | Nhập hai cột link–tên từ bảng tính; tài liệu được đặt tên theo danh sách. |
| **Công cụ ngay trên máy** | Cắt, ghép, nén video, tách âm thanh và che PDF mà không cần gửi tệp lên website chuyển đổi. |
| **Kiểm tra trước khi mở** | Đối chiếu mã băm, nhận diện dấu hiệu rủi ro, cách ly tệp và gọi Windows Defender. |
| **Quyền trình duyệt tùy chọn** | Bạn quyết định trang nào được tích hợp và có cho phép dùng phiên đăng nhập hay không. |
| **Cài rồi sử dụng** | Bộ cài đã chứa ứng dụng và thành phần kết nối trình duyệt; không cần cài Python. |

## Chức năng

### Tải tệp và quản lý hàng đợi

- Tải HTTP/HTTPS với **1–32 luồng**, chia khối cho luồng rảnh và theo dõi tốc độ, tiến độ trong hàng đợi.
- Tạm dừng, tiếp tục sau khi mở lại HDM và tự thử lại khi kết nối gặp lỗi.
- Thay link hết hạn sau khi dừng; giữ dữ liệu cũ khi nguồn mới có đủ thông tin xác minh cùng nội dung.
- Đổi thư mục lưu khi đang tải; tiếp quản tệp `.crdownload` hoặc `.part` sau khi xác minh phần đã tải.
- Dùng nhiều nguồn mirror khi có SHA-256 độc lập để kiểm kết quả; giảm số kết nối khi máy chủ báo quá tải.
- Hẹn giờ và chọn băng thông **Tối đa / Vừa / Nhẹ**. Hẹn giờ cần HDM đang chạy.

Tải nhiều luồng và tiếp tục từ phần cũ phụ thuộc khả năng Range/ETag của máy chủ. HDM không ghép các phần chưa đủ điều kiện xác minh.

### Video và âm thanh

- Tải qua yt-dlp, chọn độ cao tối đa từ **360p đến 2160p**, xem các định dạng nguồn thực sự cung cấp.
- Lưu **MP3 / M4A**, danh sách phát và phụ đề khi nguồn hỗ trợ; ưu tiên H.264/MP4 nếu có định dạng phù hợp.
- Gửi yêu cầu từ tiện ích trình duyệt, dùng phiên đăng nhập theo quyền bạn chủ động cấp.
- Cập nhật yt-dlp riêng từ nguồn phát hành chính thức, có kiểm tra mã băm.

Chất lượng và khả năng tải phụ thuộc từng website, nội dung và quyền truy cập. HDM không vượt DRM; chưa nghiệm thu toàn bộ website hoặc video yêu cầu tài khoản riêng tư.

### Tải theo danh sách

- Dán hai cột **link | tên tệp** từ Excel hoặc Google Sheets.
- Mở **XLSX / CSV / TXT**, đọc hyperlink trong ô và tự đánh số khi thiếu tên.
- Xem trước, sửa tên, đổi tên hàng loạt và bỏ dòng trước khi tải; xuất báo cáo từng dòng sau khi xử lý.
- Phân loại thư mục theo loại tệp; xuất lịch sử CSV không kèm URL/token.
- Lưu danh sách trang web thành **PDF / PNG**, kèm nguồn và thời điểm lưu.

Ví dụ hai cột có thể dán vào cửa sổ nhập danh sách:

| Link | Tên tệp |
| --- | --- |
| `https://example.com/catalog.pdf` | `Danh-muc-san-pham.pdf` |
| `https://example.com/photo.jpg` | `Anh-san-pham-001.jpg` |

### Cắt, ghép và nén media

- Cắt nhanh bằng cách giữ nguyên luồng hoặc cắt chính xác bằng mã hóa lại.
- Ghép nhiều tệp, thay đổi thứ tự và chuẩn hóa video khi cần.
- Chuyển sang MP4, tách nhạc thành MP3/M4A.
- Nén video hai lượt theo dung lượng đích; chỉ xuất kết quả khi nhỏ hơn nguồn và không vượt mục tiêu.
- Thử bộ mã hóa Windows Media Foundation khi chuyển MP4, dùng bộ dự phòng khi không khả dụng.

### Kiểm tra tệp và xử lý PDF

- Tính hoặc đối chiếu **MD5, SHA-1, SHA-256, SHA-512**; tra VirusTotal, MetaDefender hoặc Kaspersky bằng hash mà không gửi tệp lên.
- Phát hiện một số dấu hiệu như chương trình đội lốt tài liệu, đuôi kép, ký tự điều hướng, macro và lối tắt trong ZIP.
- Cách ly bằng đuôi `.chuakiemtra`, hỗ trợ quét Windows Defender và xác nhận rủi ro khi khôi phục.
- Theo dõi tệp mới hoặc vừa sửa trong thư mục bạn chọn; giải nén ZIP có giới hạn, tùy chọn tự giải nén sau tải.
- Kiểm tra nội dung RAR/7z có giới hạn, nhận mật khẩu khi cần; chế độ an toàn cao đánh dấu chương trình chưa có chữ ký số hợp lệ.
- Che vùng PDF bằng kéo chuột và xuất PDF dạng ảnh mới, không giữ lớp chữ gốc trong đầu ra. Đổi lại, PDF mới mất khả năng tìm kiếm văn bản.

Kiểm tra sơ bộ và cách ly hỗ trợ giảm rủi ro; chúng không thay thế phần mềm chống mã độc. [Bảo mật](docs/SECURITY.md) · [Quyền riêng tư](docs/PRIVACY.md).

### Tích hợp trình duyệt

- Menu tải link/video và nút tải nằm ngoài khung video.
- Tùy chọn chuyển lượt tải HTTP/HTTPS mới từ trình duyệt sang HDM; khi không bàn giao được, trình duyệt tiếp tục xử lý.
- Một gói **Chromium Manifest V3** cho Chrome, Cốc Cốc, Edge, Brave và Opera; quyền website, cookie và tiếp quản lượt tải được cấp theo nhu cầu.
- Phát hiện luồng HLS/DASH trên trang đã cấp quyền, chọn luồng trong popup để gửi sang HDM.
- Bộ lọc quảng cáo thử nghiệm có bốn mức, danh sách cho phép từng trang, chặn tab từ miền quảng cáo đã biết và chọn phần tử để ẩn.

Bộ lọc chỉ dịch các quy tắc mạng tương thích, tối đa 4.500 quy tắc; chưa tương đương một engine lọc đầy đủ. Tiện ích hiện cài thủ công từ ZIP, chưa được phát hành trên Chrome Web Store.

### Tài liệu bán hàng và tiện ích khác

- Lưu bản in phiếu bán hàng theo **sàn / ngày / mã đơn** khi bạn bật quyền trên trang phù hợp. Tính năng đang thử nghiệm, cần kiểm lại PDF vì ảnh từ URL hoặc iframe có thể thiếu.
- Torrent/magnet: chọn từng tệp, lưu checkpoint, mở lại lượt tải và dừng chia sẻ khi hoàn tất.
- Xử lý link cloud công khai; với lượt HTTP mới, chỉ chuyển tệp tới đích sau khi tải xong.
- Chạy dưới khay hệ thống, chống máy ngủ khi tải và tùy chọn tắt máy khi hàng đợi HTTP hoàn tất, có đếm ngược để hủy.
- Tìm phụ đề Việt theo hash qua OpenSubtitles với API key/token do bạn cung cấp.
- Kiểm tra bản cập nhật bằng **chữ ký Ed25519**, đối chiếu hash và kích thước bộ cài trước khi nhận.

## Cài đặt

### Yêu cầu hệ thống

| Thành phần | Yêu cầu |
| --- | --- |
| Hệ điều hành | Windows 10 hoặc Windows 11, 64-bit |
| Môi trường chạy | Đã đóng gói trong bộ cài; không cần Python hoặc Node.js |
| Dung lượng trống | Đủ cho ứng dụng, tệp tải và dữ liệu tạm; lượt HTTP ghép khối có thể cần gần hai lần dung lượng tệp |
| Lưu website PDF/ảnh | Cần Edge đã cài hoặc trình duyệt Chromium tương thích được cấu hình trên máy |
| Tiện ích browser | Cài riêng từ ZIP nếu muốn gửi link từ trình duyệt |

### Chọn gói tải

| Gói | Khi nào cần? |
| --- | --- |
| [**HDM-Setup-0.1.0.exe**](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.0/HDM-Setup-0.1.0.exe) | **Tải gói này để cài HDM.** Đã có ứng dụng, bridge và thông báo giấy phép thư viện. |
| [**HDM-Browser-Extension.zip**](https://github.com/hngoos/hngoos-download-manager/releases/latest/download/HDM-Browser-Extension.zip) | Thêm tích hợp trình duyệt. Gói Chromium duy nhất, có `manifest.json` ngay trong thư mục giải nén. |

### Cài HDM trên Windows

1. Tải bộ cài từ các liên kết phía trên hoặc [Releases chính thức](https://github.com/hngoos/hngoos-download-manager/releases/latest).
2. Chạy `HDM-Setup-0.1.0.exe` và hoàn tất hướng dẫn cài đặt.
3. Mở **HDM**, dán URL, chọn thư mục lưu và số luồng, rồi chọn **Thêm lượt tải**.
4. Dùng menu chuột phải trên lượt tải để xem các thao tác phù hợp với tệp.

Mặc định, ứng dụng được cài tại `%LOCALAPPDATA%\Programs\HDM`. Bộ cài chưa ký Authenticode; đối chiếu nguồn phát hành và SHA-256 tại Releases khi cần xác minh. Chữ ký Ed25519 của cập nhật là cơ chế riêng, không thay thế chữ ký nhà phát hành Windows.

### Cài tiện ích trên Chrome / Edge / trình duyệt Chromium

1. Tải và giải nén `HDM-Browser-Extension.zip` vào thư mục cố định.
2. Mở trang quản lý tiện ích: `chrome://extensions` trên Chrome hoặc `edge://extensions` trên Edge. Với Cốc Cốc, Brave và Opera, mở mục quản lý tiện ích tương ứng.
3. Bật **Developer mode → Load unpacked**, chọn thư mục vừa giải nén có tệp `manifest.json`.
4. Sao chép **Extension ID**, mở **HDM → Trình duyệt**, đăng ký kết nối bằng ID đó.
5. Mở **Options** của tiện ích và kiểm tra kết nối. Chỉ cấp quyền website, cookie hoặc tiếp quản lượt tải khi bạn cần.

Giữ nguyên thư mục đã giải nén sau khi nạp tiện ích. HDM hỗ trợ các trình duyệt nhân Chromium từ phiên bản 120; luồng kết nối đã được kiểm thử trên Chromium thực tế. Cần kiểm lại theo phiên bản và chính sách của từng trình duyệt.

<details>
<summary><strong>Không kết nối được tiện ích hoặc không thấy video?</strong></summary>

Kiểm tra HDM đã được cài, đã đăng ký đúng Extension ID và đã cấp quyền cho website cần dùng. Thử nút kiểm tra kết nối trong Options trước khi gửi link. Với video, thử URL trang gốc và kiểm tra nội dung có yêu cầu đăng nhập hoặc DRM hay không.

Hướng dẫn theo từng tác vụ nằm trong [Hướng dẫn sử dụng](docs/USAGE.md); điều kiện hỗ trợ nằm trong [Tính năng và phạm vi](docs/FEATURES.md).

</details>

Repo công khai chứa tài liệu và hình ảnh giới thiệu HDM. `git clone` và hai gói **Source code** GitHub tự sinh chỉ tải những tài liệu này, không chứa mã nguồn ứng dụng. Người dùng cài HDM bằng hai gói phát hành phía trên. [Điều khoản sử dụng](LICENSE).
