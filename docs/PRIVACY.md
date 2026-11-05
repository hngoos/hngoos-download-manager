# Quyền riêng tư của HDM

[Trang chủ](../README.md) · [Hướng dẫn sử dụng](USAGE.md) · [Bảo mật](SECURITY.md)

Áp dụng cho hngoos-download-manager (HDM) v0.1.0 và tiện ích Chromium đi kèm. Cập nhật ngày 06/11/2026.

## Dữ liệu trên máy

HDM lưu lịch sử, URL nguồn, tên và đường dẫn tệp, tiến độ và tùy chọn trong thư mục dữ liệu của tài khoản Windows. URL tải có thể chứa token truy cập; hãy coi lịch sử là dữ liệu riêng tư. Tiện ích lưu thiết lập, danh sách trang cho phép và phần tử đã ẩn trong bộ nhớ cục bộ của trình duyệt. Các luồng video phát hiện được lưu tạm theo tab, giới hạn 30 luồng mỗi tab; khi đọc danh sách, mục quá 30 phút bị bỏ và khi đóng/chuyển trang, danh sách được xóa.

HDM không có dịch vụ thu thập lịch sử hay hệ thống quảng cáo của nhà phát triển. Ứng dụng và tiện ích không có cơ chế gửi phân tích sử dụng về máy chủ của HDM. Dữ liệu không được đưa lên repo GitHub.

## Kết nối tới bên thứ ba

- Tải tệp/video gửi yêu cầu tới website và máy chủ nội dung bạn chọn; chúng nhận địa chỉ IP và thông tin giao thức cần thiết. Khi tải luồng video từ trang, HDM có thể gửi origin của trang làm Referer, không kèm đường dẫn hoặc query của trang đó.
- Cập nhật ứng dụng và bộ tải video kết nối GitHub. Bộ lọc quảng cáo được lấy trực tiếp từ EasyList, EasyPrivacy, ABPVN và uBlock badware khi bạn cấp quyền.
- Tra mã băm mở VirusTotal, MetaDefender hoặc Kaspersky với SHA-256 của tệp, không tự tải nội dung tệp lên. Dịch vụ đó có chính sách riêng.
- Tìm phụ đề kết nối OpenSubtitles khi bạn sử dụng tính năng và cung cấp thông tin truy cập. Torrent kết nối các peer và dịch vụ mạng torrent; peer có thể thấy địa chỉ IP của bạn.

## Quyền của tiện ích Chromium

| Quyền | Mục đích |
| --- | --- |
| Native messaging | Gửi yêu cầu bạn chọn tới HDM trên cùng máy. |
| Context menus, active tab, scripting | Menu tải, nút video, chọn phần tử và lưu phiếu trên trang bạn cho phép. |
| Storage, alarms | Lưu thiết lập và hẹn cập nhật bộ lọc. |
| Declarative net request | Áp dụng quy tắc chặn mạng khi bạn bật bộ lọc và cấp quyền website. |
| Web request, web navigation | Nhận diện phản hồi HLS/DASH trên trang đã cấp quyền, dọn danh sách theo tab và xử lý tab quảng cáo từ miền đã biết. Không lưu header yêu cầu/phản hồi hay nội dung trang cho mục phát hiện luồng. |
| Truy cập website (tùy chọn) | Chỉ xin khi bạn bật tích hợp cho trang hoặc bật bộ lọc toàn cục. |
| Cookies (tùy chọn) | Dùng phiên đăng nhập cho yêu cầu video do bạn chọn, khi đã bật tùy chọn và cấp quyền đúng trang. |
| Downloads (tùy chọn) | Chuyển lượt tải mới sang HDM; giữ tải trong trình duyệt nếu bàn giao thất bại. |

Mặc định HDM không đọc cookie. Cookie chỉ được gửi khi URL video cùng origin với trang nguồn, được mã hóa Windows DPAPI khi chờ trong inbox của ứng dụng. Khi tải, yt-dlp sử dụng tệp cookie tạm dạng văn bản; HDM xóa tệp khi tác vụ kết thúc bình thường. Dừng cưỡng bức có thể để lại dữ liệu tạm. Tệp cookie bạn tự chọn vẫn do bạn quản lý.

Lưu phiếu là tính năng tùy chọn theo từng hostname bán hàng. Nội dung phiếu có thể có thông tin cá nhân khách hàng; HTML được chuyển tới ứng dụng trên máy, không gửi tới dịch vụ dựng PDF bên ngoài. HDM xóa HTML khỏi inbox sau khi xuất PDF thành công. Bạn tự quản lý PDF đã lưu.

## Xóa dữ liệu và liên hệ

Bạn có thể thu hồi quyền trong trang quản lý tiện ích, xóa dữ liệu tiện ích hoặc gỡ tiện ích. Đóng HDM rồi xóa dữ liệu tại `%LOCALAPPDATA%\HDM` để xóa lịch sử và bộ nhớ đệm; bản nâng cấp từ phiên bản cũ có thể tiếp tục dùng `%LOCALAPPDATA%\HngoosDM`. Việc này không tự xóa tệp bạn đã lưu ở thư mục khác. Hãy sao lưu dữ liệu cần giữ trước khi xóa.

Liên hệ nhà phát triển qua [GitHub của hngoos](https://github.com/hngoos) hoặc [Issues của HDM](https://github.com/hngoos/hngoos-download-manager/issues). Không đăng cookie, token, phiếu khách hàng hoặc lịch sử tải riêng tư vào issue công khai.
