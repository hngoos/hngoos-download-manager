# Hướng dẫn sử dụng

[Trang chủ](../README.md) · [Chi tiết tính năng](FEATURES.md) · [Bảo mật](../SECURITY.md)

## Cài trên Windows

1. Mở [Releases](https://github.com/hngoos/hngoos-download-manager/releases/latest), tải `HDM-Setup-<version>.exe`.
2. Chạy bộ cài; mặc định cài cho tài khoản hiện tại tại `%LOCALAPPDATA%\Programs\HDM`.
3. Mở **hngoos-download-manager**, chọn thư mục lưu và dán URL để thêm lượt tải.

Bộ cài chứa sẵn ứng dụng, bridge và giấy phép thư viện. Cài extension là thao tác riêng, hướng dẫn bên dưới. Không cần cài Python. Repo công khai chỉ phân phối tài liệu và hai gói tải, không cung cấp mã nguồn ứng dụng.

Bộ cài chưa ký Authenticode, nên Windows có thể hiển thị cảnh báo về nhà phát hành. Kiểm tra nguồn phát hành và SHA-256; không tắt công cụ bảo vệ của Windows.

## Xác minh SHA-256

Mã SHA-256 của từng gói được hiển thị tại Releases. Chạy lệnh sau và so sánh mã của đúng tên bộ cài:

```powershell
Get-FileHash .\HDM-Setup-<version>.exe -Algorithm SHA256
```

Thay `<version>` bằng phiên bản đã tải. Bộ cập nhật bên trong app còn kiểm manifest Ed25519 trong dữ liệu phát hành bằng khóa công khai được ghim trong ứng dụng, rồi kiểm hash và kích thước bộ cài. Tự so hash không thay thế bước kiểm chữ ký.

## Tải tệp

Dán URL HTTP/HTTPS, nhập tên nếu muốn, chọn nơi lưu và số luồng, rồi chọn **Thêm lượt tải**. Dùng **Tạm dừng** / **Tiếp tục** để điều khiển hàng đợi. Các thao tác theo tệp nằm trong menu chuột phải.

Mã băm và mirror nằm trong **Tùy chọn nâng cao**. Ba ô phía trên hiển thị lượt đang tải, số tệp hoàn tất và tổng tốc độ HTTP. Icon chuyển trạng thái tuân theo tùy chọn giảm hiệu ứng của Windows.

Lượt HTTP mới tải vào bộ nhớ đệm tại `%LOCALAPPDATA%\HDM\staging`, sau khi hoàn tất mới chuyển tới thư mục đã chọn. Khi khác ổ đĩa, app chép vào tên `.tmp`, kiểm SHA-256 rồi mới công bố tên cuối; phần mềm đồng bộ có thể nhìn thấy tệp `.tmp`. Video cũng tải và xử lý trong bộ nhớ đệm cục bộ trước khi chuyển tệp hoàn chỉnh tới đích; torrent vẫn dùng thư mục riêng của tác vụ.

Tiếp tục qua lần mở app cần máy chủ giữ nguyên ETag mạnh và kích thước. Đổi link hết hạn khi đã dừng; app chỉ giữ phần cũ khi xác minh được cùng nội dung. Mirror cần SHA-256 từ một nguồn độc lập đáng tin.

Muốn tiếp quản `.crdownload` hoặc `.part`, dừng tải trong trình duyệt trước, mở **Công cụ → Tiếp quản tệp trình duyệt tải dở**, rồi cung cấp URL trực tiếp. App giữ tệp gốc và xác minh toàn bộ tiền tố đã tải.

## Nhập danh sách

Dán hai cột từ Excel/Sheets hoặc mở CSV/TXT/XLSX:

```text
link | tên tệp
https://example.com/report.pdf | Báo cáo.pdf
https://example.com/photo.jpg | Ảnh sản phẩm.jpg
```

Không có tên thì app đánh số. XLSX hỗ trợ hyperlink của ô. Xem trước danh sách, bấm đúp để sửa dòng, chọn nhiều dòng để đổi tên hoặc bỏ dòng trước khi tải. Danh sách tối đa 500 dòng. Xuất báo cáo từng dòng từ Công cụ để đối chiếu thứ tự và trạng thái; báo cáo không kèm URL hay token.

## Video và phiên đăng nhập

Mở **Video & nhạc**, dán URL, chọn độ cao tối đa hoặc MP3/M4A rồi tải. Khả năng lấy video phụ thuộc extractor và quyền truy cập hợp lệ của bạn; không hỗ trợ DRM. Xử lý nội bộ bằng FFmpeg nằm trong **Công cụ**.

Mặc định app không đọc phiên đăng nhập. Chỉ bật **Dùng phiên đăng nhập** trong extension khi cần; quyền cookie được xin riêng theo website. Cookie chỉ được gửi cho yêu cầu cùng origin với trang nguồn, mã hóa bằng Windows DPAPI khi lưu trong inbox. Tác vụ yt-dlp cần cookie tạm ở dạng văn bản trong lúc chạy; xem [ranh giới dữ liệu](../SECURITY.md#du-lieu-cuc-bo).

## Kết nối trình duyệt Chromium

1. Cài HDM bằng bộ cài Windows.
2. Giải nén `HDM-Browser-Extension.zip`. Tại `chrome://extensions` / `edge://extensions`, bật Developer mode, Load unpacked thư mục vừa giải nén chứa `manifest.json`. Cũng có thể dùng thư mục `browser-extension` trong thư mục cài HDM.
3. Sao chép ID extension, mở thẻ **Trình duyệt** trong app và đăng ký native host. Chỉ ghi registry tài khoản hiện tại.
4. Mở Options của extension → Kiểm tra kết nối. Dùng menu chuột phải hoặc popup để tải.
5. Quyền lọc mạng và dùng phiên đăng nhập là tùy chọn, được xin riêng trong popup. Không bật session nếu bạn không muốn gửi cookie của trang được chọn tới ứng dụng trên máy.

Chromium đã được kiểm thử tải thật → native EXE → inbox và quay về trình duyệt khi native host lỗi. Bật **Tự chuyển lượt tải HTTP/HTTPS sang HDM** trong popup nếu muốn tiếp quản lượt tải mới; quyền downloads được xin riêng. URL cần truy cập được từ app và có kích thước phù hợp. Cookie, POST, blob và nguồn không xác minh được sẽ tiếp tục tải trong trình duyệt. Chrome/Edge/Brave/Cốc Cốc/Opera cần nghiệm thu thêm trên từng bản; thời điểm hộp lưu tùy trình duyệt/cấu hình.

Hỗ trợ Chrome, Cốc Cốc, Edge, Brave và Opera từ Chromium 120. Hiện cài thủ công; chưa có trang phát hành Chrome Web Store.

Trong popup, mục luồng video liệt kê HLS/DASH đã phát hiện trên trang được cấp quyền. Phát video trước rồi mở lại popup nếu danh sách trống. Nút chọn phần tử chỉ hoạt động khi bật chặn quảng cáo; nhấn Escape để hủy và dùng **Về mặc định cho trang này** để bỏ các phần tử đã ẩn.

## Phiếu giao hàng (thử nghiệm)

Tại trang bán hàng Shopee/Lazada/TikTok Shop được hỗ trợ, mở popup và bật **Tự lưu phiếu khi in** cho đúng trang. Khi trang phát sự kiện in, extension chuyển bản HTML tĩnh tới app; thao tác in thông thường vẫn tiếp tục. PDF được lưu tại `%LOCALAPPDATA%\HDM\invoices\<sàn>\<ngày>`, có mã đơn trong tên và nguồn/thời điểm trong trang. Mở từ **Công cụ → Mở thư mục phiếu giao hàng**.

Giới hạn 90 KB mỗi phiếu, không lấy ảnh qua mạng và không chạy script khi dựng PDF. Phiếu dùng ảnh barcode từ URL, stylesheet ngoài, iframe hoặc cửa sổ in ở hostname khác có thể thiếu nội dung; hãy kiểm tra PDF và dùng **Save as PDF** của trình duyệt khi cần. Đã kiểm thử phiếu mẫu; chưa nghiệm thu tài khoản thật trên từng sàn. App chỉ xóa HTML trong inbox sau khi xuất PDF thành công; tác vụ bị ngắt được thử lại khi mở app.

## Torrent và nén video

**Công cụ → Mở lại torrent đã lưu** khôi phục lựa chọn và các mảnh đã xác minh từ checkpoint. App lưu checkpoint định kỳ, khi tạm dừng và khi đóng; mở lại ở trạng thái dừng để bạn chủ động tiếp tục. Hoàn tất sẽ dừng chia sẻ tiếp.

Nén video dùng hai lượt libx264, tính dung lượng cho cả âm thanh và chi phí đóng gói. App chỉ xuất kết quả nếu nhỏ hơn nguồn và không vượt dung lượng đích; nếu mục tiêu quá thấp hoặc không đạt, tệp gốc được giữ nguyên. Có thể dừng ở cả hai lượt.
