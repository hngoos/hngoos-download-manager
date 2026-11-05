# Kiến trúc HDM v0.1.0

## Phân lớp

```text
Tkinter desktop (app.py)
  ├── DownloadManager (engine.py)
  │     ├── urllib + TLS mặc định
  │     ├── ThreadPoolExecutor: 2 jobs, mỗi job 1–32 workers
  │     ├── SQLite job/chunk state (store.py)
  │     └── SHA-256 + triage (safety.py)
  ├── CSV/TXT/XLSX (batch.py)
  └── yt-dlp / FFmpeg (media.py, tùy chọn)
```

UI chỉ đọc metadata định kỳ. Worker không chạm Tkinter; cập nhật giao diện qua queue. Mỗi thao tác database mở kết nối riêng, dùng transaction và WAL.

## Quy tắc HTTP

1. Probe bằng GET `Range: bytes=0-0`, `Accept-Encoding: identity`.
2. Kiểm tra 206 và `Content-Range` đúng chính xác, ghi kích thước/ETag.
3. Khi có ETag mạnh, chia tệp thành khối tối thiểu 1 MiB và dùng hàng đợi chung để worker rảnh lấy khối tiếp theo. Gửi `If-Match` ở mỗi yêu cầu.
4. Xác minh response status, ETag, Content-Range và số byte. Lỗi xác minh dừng job, không xuất tệp hoàn tất.
5. Hoàn tất khối: flush, fsync, đánh dấu trong SQLite. Khối dở không được đánh dấu và sẽ được tải lại.
6. Tiếp tục chỉ khi ETag mạnh và tổng kích thước trùng. Nếu không, bỏ khối cũ và tạo kế hoạch tải mới. Máy chủ không có validator mạnh chỉ dùng một phản hồi toàn tệp.
7. Ghép tệp trong thư mục staging cùng ổ đĩa; tính SHA-256 và kiểm tra sơ bộ trước khi xuất. Đổi tên không ghi đè trên Windows. Mỗi job có staging riêng nên các tên trùng không chung dữ liệu.

Mirror chỉ được dùng khi có SHA-256 độc lập do người dùng cung cấp. Mỗi nguồn được probe và kiểm riêng; không giả định ETag giữa các host giống nhau chứng minh cùng nội dung. Sai hash đầu ra thì bỏ kế hoạch ghép và tải lại từ nguồn chính. `policy.py` chia ngân sách băng thông và giảm giới hạn host sau 429/503.

## Khôi phục và dừng

`downloading`, `queued`, `verifying` được đổi thành `paused` khi mở ứng dụng. Tắt app yêu cầu worker dừng. Yêu cầu mạng đang chờ có thể cần tối đa timeout 15 giây (theo từng lần đọc) để thoát. Tệp/khối chỉ dùng lại khi metadata và kích thước hợp lệ. Không có bảo đảm khôi phục khi người dùng sửa trực tiếp dữ liệu staging.

File lock do hệ điều hành giữ ngăn hai phiên ứng dụng mở cùng thư mục dữ liệu. Khóa tự giải phóng khi tiến trình thoát hoặc bị dừng.

## Ranh giới an toàn

App nhận URL do chính người dùng nhập và có thể truy cập địa chỉ mạng nội bộ để tải từ NAS. Không có HTTP server lắng nghe cổng mạng. Không nhận lệnh thực thi qua URL hoặc shell. FFmpeg và Defender được gọi bằng danh sách đối số, không qua shell. Tệp rủi ro không tự thực thi, không tự khôi phục. Đầu ra HTTP và tệp được khôi phục cố gắng gắn Mark of the Web trên NTFS; FAT/exFAT và một số ổ mạng không hỗ trợ.

Các luồng HTTP, yt-dlp, FFmpeg và giải nén cố gắng gắn Mark of the Web. Manifest cập nhật dùng Ed25519; bộ cài chưa có chứng thư Authenticode. Xem [chính sách bảo mật](VULNERABILITY_REPORTING.md) cho các giới hạn còn lại.

## Trình duyệt và phiên đăng nhập

Extension MV3 gửi yêu cầu qua `HDMBridge.exe` bằng stdio. Browser kiểm `allowed_origins` trong native manifest; host kiểm framing/kích thước/action/URL rồi ghi inbox SQLite. App đọc inbox và dùng sự kiện UI để tiếp nhận. Không mở HTTP listener.

Quyền cookie và host là tùy chọn. Sự kiện nút tải do script tạo bị bỏ qua; cookie chỉ được lấy khi URL video cùng origin với trang nguồn. Native host kiểm cookie thuộc domain URL, mã hóa DPAPI trước khi lưu. App chỉ giải mã tạm cho tác vụ video gắn đúng URL, rồi xóa file khi tác vụ kết thúc bình thường.

## Các mô-đun công cụ

| Mô-đun | Trách nhiệm |
| --- | --- |
| `media.py`, `processing.py` | Tải yt-dlp và subprocess FFmpeg có staging/cancel |
| `pdf_tools.py`, `capture.py` | Che PDF raster có giới hạn pixel; web capture bằng profile riêng |
| `safety.py`, `guard.py`, `extraction.py` | Kiểm tệp/ZIP, bảo vệ thư mục và giải nén có giới hạn |
| `torrent.py`, `cloud.py`, `subtitles.py` | Các adapter công cụ tùy chọn |
| `vault.py`, `updater.py`, `toolchain.py` | DPAPI, kiểm cập nhật Ed25519, yt-dlp có digest |
| `diagnostics.py` | Chạy kiểm tra thành phần ngay trong EXE phát hành |

Các thư viện nặng được import tại điểm sử dụng; lõi HTTP không bắt buộc cài toàn bộ extras. Công cụ có quyền đọc/ghi như tài khoản Windows đang chạy; chúng không nằm trong sandbox riêng.
