# Chính sách bảo mật

## Phiên bản được duy trì

| Phiên bản | Chính sách |
| --- | --- |
| v0.1.0 / nhánh `main` | Nhận sửa lỗi bảo mật |

## Báo cáo riêng

Dùng [Report a vulnerability](https://github.com/hngoos/hngoos-download-manager/security/advisories/new) để gửi báo cáo riêng. Kèm phiên bản, các bước tái hiện với dữ liệu tự tạo, ảnh hưởng và cách giảm thiểu nếu có. Không đăng khai thác đang hoạt động lên issue công khai.

Không gửi mật khẩu, cookie, token, khóa ký, database lịch sử hoặc tệp cá nhân. Nếu cần một mẫu tệp rủi ro, mô tả trước và dùng dữ liệu tổng hợp; không đính kèm mã độc thật vào repo.

Dự án do cá nhân duy trì, chưa có cam kết thời gian phản hồi hoặc chương trình thưởng lỗi.

## Ranh giới tin cậy

| Thành phần | Biện pháp | Giới hạn |
| --- | --- | --- |
| HTTP/HTTPS | Xác thực TLS mặc định; Range/ETag/kích thước trước khi ghép; kiểm mã băm mong đợi | HTTP không mã hóa. Hash tự tính không chứng minh nguồn tệp an toàn |
| Mirror | Cần SHA-256 độc lập; sai hash thì tải lại nguồn chính | Không tin ETag giữa hai máy chủ khác nhau |
| Extension | Quyền cookie/host tùy chọn; kiểm cùng origin trước khi đọc cookie; nút trên trang cần sự kiện tin cậy | Website và extension không phải ranh giới sandbox cho ứng dụng native |
| Native host | Giao thức stdio giới hạn 128 KiB, kiểm URL/domain cookie; không nhận lệnh shell | OS/browser kiểm `allowed_origins`; không phòng được tài khoản Windows đã bị kiểm soát |
| Session | Mã hóa Windows DPAPI khi lưu vào inbox | Tiến trình cùng tài khoản Windows vẫn có thể giải mã |
| ZIP | Kiểm traversal, symlink, tên mơ hồ trên Windows, executable/macro, archive lồng nhau và giới hạn tài nguyên | Không phải bộ phân tích mã độc đầy đủ; RAR/7z chưa có độ phủ tương đương |
| PDF | Kiểm ngân sách pixel trước render; đầu ra che vùng là PDF raster mới | Mất khả năng tìm kiếm chữ; không thay thế việc xem lại vùng đã che |
| Cập nhật app | Khóa Ed25519 công khai ghim trong source; kiểm chữ ký/hash/kích thước trước nhận bộ cài | Chưa có Authenticode/uy tín SmartScreen; không tự chạy bộ cài |
| yt-dlp cập nhật riêng | Chỉ dùng release chính thức, bắt buộc có GitHub SHA-256 digest | Cần tin cậy nhà phát hành upstream và GitHub |

Ứng dụng không tự chạy tệp tải về. Đổi đuôi `.chuakiemtra` giảm nguy cơ mở nhầm nhưng không phải sandbox: đổi tên thủ công hoặc mở bằng công cụ khác vẫn có thể thực thi tệp. Quét Defender/AuthentiCode và tra hash là công cụ hỗ trợ, không phải chứng nhận tệp sạch.

<a id="du-lieu-cuc-bo"></a>

## Dữ liệu cục bộ

- `%LOCALAPPDATA%\HDM\downloads.sqlite3` chứa lịch sử, URL có thể có token, settings, sự kiện và inbox. Database và staging chưa được mã hóa toàn bộ.
- Phần HTTP tải dở mới ở `%LOCALAPPDATA%\HDM\staging\<job-id>`; app chỉ dùng lại khối khi có điều kiện xác minh phù hợp. Ứng dụng tiếp tục dùng thư mục dữ liệu có sẵn khi cần giữ lịch sử của lần cài trước.
- Cookie do extension gửi theo quyền bạn cấp được mã hóa DPAPI và xóa khỏi dữ liệu inbox đang dùng sau khi chấp nhận/hủy. Các bản SQLite/WAL/backup có thể còn dữ liệu đã mã hóa trước đó.
- Khi yt-dlp chạy, cookie được giải mã ra tệp tạm `hngoos-session-*` trong thư mục dữ liệu rồi xóa khi tác vụ kết thúc bình thường. Dừng cưỡng bức có thể để lại tệp tạm. Cookie do bạn tự xuất và chọn vẫn do bạn quản lý.
- FFmpeg/PDF/giải nén dùng staging tạm; tiến trình bị dừng đột ngột có thể để lại dữ liệu. Không gửi cả thư mục dữ liệu hoặc thư mục build vào báo cáo lỗi.

Không tự tải tệp cá nhân lên dịch vụ quét. Tra VirusTotal dùng hash; người dùng vẫn cần xem dịch vụ bên ngoài nào sẽ được mở/gọi. Video, website capture, phụ đề và cập nhật kết nối đến máy chủ tương ứng theo thao tác người dùng.

## Kiểm tra tự động

Workflow [Security](https://github.com/hngoos/hngoos-download-manager/actions/workflows/security.yml) quét secret trong Git, audit dependency Python và phân tích CodeQL cho Python/JavaScript. Dependabot theo dõi dependency và Actions. Các Actions được ghim commit; checkout không giữ credential trong cấu hình Git.

Xem [biên bản rà soát](docs/SECURITY_REVIEW.md) để biết phạm vi và kết quả cụ thể. Không có kết quả quét nào đảm bảo phần mềm an toàn tuyệt đối. Binary native như FFmpeg/PDFium và website bên ngoài vẫn cần cập nhật và kiểm thử riêng.
