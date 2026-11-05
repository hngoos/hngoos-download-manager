# Nghiệm thu tương đương chức năng

Lộ trình phát triển hngoos-download-manager (HDM). Bảng dưới phân biệt tính năng đã kiểm chứng với phần đang phát triển hoặc cần nghiệm thu thực tế.

| Nhóm | Đã có và được kiểm tra | Còn thiếu / chưa được nghiệm thu |
| --- | --- | --- |
| Tải nhanh | Range/ETag, 1–32 workers, resume qua database, retry, mirror SHA-256 và giữ khối nguồn chính khi fallback, giảm/tăng lại giới hạn host, kiểm dung lượng đĩa trước tải, hẹn giờ, bandwidth, đổi nơi lưu khi chạy, tiếp quản toàn bộ tiền tố đã xác minh | Resume không ETag mạnh; định vị từng khối sai trong nhóm mirror; thử tải nhiều GB và ngắt nguồn |
| Video/nhạc | yt-dlp, chất lượng tối đa, MP3/M4A, playlist/subtitle options, xem format; phát hiện HLS/DASH theo URL/MIME, bỏ một số quảng cáo rõ ràng; extension/nút ngoài video; phiên đăng nhập opt-in mã hóa DPAPI; cập nhật extractor có digest | Chưa nghiệm thu 1.800 trang hoặc tài khoản thật Facebook/Instagram; story/slideshow không có workflow riêng; phân biệt mọi preroll; chưa nghiệm thu mọi extractor/chất lượng thực tế |
| Danh sách | TSV/CSV/TXT/XLSX/hyperlink, preview/sửa/đổi tên hàng loạt/báo cáo từng dòng, đánh số, website PDF/PNG có nguồn/thời điểm qua Chromium thật | Tự giải quyết cookie/đăng nhập cho web capture |
| Bán hàng | PDF redaction raster; lưu phiếu in HTML tĩnh opt-in, kiểm thử PDF mẫu và chặn script/network | Lưu phiếu thử nghiệm: ảnh URL/iframe/CSS ngoài/hostname cửa sổ in có thể thiếu; cần nghiệm thu tài khoản có quyền và từng dạng phiếu |
| Xử lý media | FFmpeg convert/cut/extract/concat thực, ghép giữ khung hình lớn nhất; kiểm duration; nén hai lượt, chỉ xuất nếu nhỏ hơn nguồn và không vượt dung lượng đích | Nghiệm thu nén trên bộ video đa dạng; hardware encoder cần test trên card thật; đọc DVD menu |
| An toàn | MZ, nhiều đuôi, bidi, ZIP/macro/nested/traversal/symlink, giới hạn tài nguyên, bốn mã băm, Defender/AuthentiCode, guard thư mục opt-in với restore checkbox/xóa, DPAPI cookie, RAR/7z mã hóa có giới hạn, chế độ an toàn cao, hướng dẫn bộ cài chính thức, ba dịch vụ tra hash | RAR/7z lồng nhau, giải nén tạm mọi archive có mật khẩu; nghiệm thu bộ cài giả mạo đa dạng |
| Chặn quảng cáo | Compiler quy tắc mạng tương thích, không dịch rule không hiểu, bốn mức, allowlist giữ malware, fetch gốc/12 giờ, bộ quy tắc thử nghiệm có tests, chặn popup/lớp phủ từ miền đã biết, chọn phần tử và thống kê tùy quyền | Không phải engine ABP/uBlock đầy đủ; 4.500 rule; chưa nghiệm thu mọi lớp phủ/quảng cáo hoặc kiểm tra không phá ngân hàng/thanh toán trên toàn mạng |
| Tiện ích | Torrent selection, tải thực loopback/checkpoint/reopen/SHA-256, no-seed monitor; cloud resolver; HTTP/media staging cục bộ và chuyển đích sau hoàn tất; phân loại; tray; ZIP extraction/tự giải nén tùy chọn; OpenSubtitles hash; cập nhật Ed25519; chống ngủ khi tải, tắt máy opt-in có đếm ngược và hủy | Staging cho torrent; full English; chế độ sleep khi xong; proxy; tự tìm phụ đề theo queue; signed installer certificate |
| Trình duyệt | Chromium thật → native EXE → inbox; không mở HTTP server; file/video request opt-in; Chromium takeover/fallback E2E; gói Chromium MV3 duy nhất | Phát hành Chrome Web Store; một hộp lưu trên mọi cấu hình; Alt bypass; bắt tất cả link; cross-browser account/site acceptance |

## Cải tiến có bằng chứng

- **Tiếp quản tệp dở**: xác minh toàn bộ tiền tố trước khi dùng lại, phát hiện trường hợp phần đầu hỏng nhưng 64 KB cuối vẫn trùng. Đổi lại cần thêm băng thông để xác minh phần cũ.
- **Mirror**: bắt buộc mã SHA-256 độc lập thay vì tin ETag của hai máy chủ khác nhau. Khi sai hash, chỉ xuất tệp sau khi đã tải lại/kiểm tra nguồn chính. Giữ khối nguồn chính, tải lại khối có nguồn mirror khi kết quả ghép sai hash.
- **Native messaging**: không mở máy chủ HTTP localhost; Chrome kiểm origin extension theo native-host manifest. Các request được deduplicate và lưu bền vững.
- **PDF redaction**: dựng đầu ra từ trang raster đã xóa pixel; không mang theo text/object/attachment gốc. Đổi lại mất khả năng tìm kiếm text trong PDF đầu ra.
- **Cập nhật app**: khóa Ed25519 công khai ghim trong source; tests từ chối sửa payload, thiếu chữ ký và khóa lạ. Digest bộ cài được kiểm sau khi tải.

## Phần cần dữ liệu thực để nghiệm thu

Tài khoản và quyền truy cập hợp lệ cho video riêng tư, group/story và phiếu sàn; API key OpenSubtitles; cấu hình GPU/driver; chứng thư Authenticode nếu muốn ký bộ cài Windows. Không yêu cầu đưa mật khẩu/cookie/API key lên issue công khai hoặc GitHub source.

Không sao chép mã hoặc tài sản gốc. Trạng thái chỉ chuyển sang hoàn thành sau khi đường đi người dùng và đầu ra được kiểm chứng; có thư viện hoặc có nút chưa đủ.
