# Tính năng và phạm vi hỗ trợ

[Trang chủ](../README.md) · [Hướng dẫn sử dụng](USAGE.md) · [Bảo mật](SECURITY.md)

Các mô tả dưới đây phản ánh chức năng đã triển khai trong v0.1.0, cùng điều kiện hỗ trợ và những phần chưa được nghiệm thu thực tế. Đây chưa phải bản hoàn tất mọi mục tiêu phát triển.

- **Tải HTTP/HTTPS 1–32 luồng**, hàng đợi hai tệp, chia khối cho luồng rảnh, tạm dừng/tiếp tục sau khi mở lại. Chỉ ghép nhiều phản hồi khi có Range và ETag mạnh; thiếu xác minh thì dùng một phản hồi hoặc tải lại.
- **Mirror có xác minh SHA-256**: cần mã băm độc lập do bạn cung cấp; loại mirror lỗi/kích thước sai. Nếu kết quả ghép sai hash, tải lại toàn bộ từ nguồn chính. Chưa định vị và chỉ tải lại riêng khối của mirror sai.
- Đổi link hết hạn khi đã dừng, giữ khối cũ nếu ETag mạnh/kích thước trùng. **Đổi nơi lưu trong lúc tải**: tự dừng ở biên đọc, chuyển dữ liệu dở và tiếp tục.
- **Tiếp quản `.crdownload`/`.part`**: giữ tệp gốc, xác minh *toàn bộ tiền tố liên tục* với máy chủ trước khi dùng lại; không chỉ kiểm 64 KB chồng lấn. Cần Range và ETag mạnh.
- Retry lỗi mạng/429/5xx. Giảm giới hạn kết nối theo host sau 429/503, lưu giới hạn qua lần mở app. Chưa tự tăng trở lại sau thời gian ổn định.
- Hẹn giờ theo thời gian trên máy; băng thông **Tối đa / Vừa 4 MB/s / Nhẹ 512 KB/s** dùng chung cho HTTP. Lượt hẹn giờ cần ứng dụng đang chạy.
- Dán hai cột từ Excel/Sheets; CSV/TXT/XLSX và hyperlink, tự đánh số tên, tự chia thư mục theo loại. Xuất lịch sử CSV không kèm URL/token, nhật ký từng lượt và bốn mã băm.
- **Video qua yt-dlp**: độ cao tối đa 360–2160p, MP3/M4A, playlist, phụ đề vi/en, xem format thực có. Có nút dừng; ưu tiên H.264/MP4 khi có format phù hợp. Không cam kết mọi chất lượng trên mọi trang.
- **Tiện ích Chromium MV3 và native messaging**: menu tải link/video, nút ở ngoài khung video, truyền yêu cầu bền vững qua SQLite; không mở HTTP server. Có kiểm thử Chromium → EXE bridge → inbox thật.
- Mặc định không đọc cookie. Khi người dùng bật **Dùng phiên đăng nhập** và cấp quyền của đúng trang, extension chuyển cookie phù hợp URL video; native host kiểm domain và mã hóa bằng **Windows DPAPI**. Khi tải, cookie tạm được giải mã cho yt-dlp rồi xóa. Chưa kiểm thử với tài khoản thật Facebook/Instagram/nhóm kín.
- **Bộ lọc quảng cáo thử nghiệm**: lấy trực tiếp EasyList/EasyPrivacy/ABPVN/uBlock badware, cập nhật mỗi 12 giờ khi trình duyệt chạy và đã cấp quyền. Bốn mức, allowlist vẫn giữ rule malware. Chỉ hỗ trợ quy tắc chặn miền rõ ràng, tối đa 4.500 rule; không tương đương uBlock Origin, chưa có chống popup/lớp phủ hoặc trình chọn phần tử.
- **Media FFmpeg**: chuyển MP4; cắt copy stream hoặc mã hóa chính xác; ghép có Lên/Xuống và chuẩn hóa video 720p/30fps/AAC; tách MP3/M4A; nén hai lượt và chỉ xuất nếu nhỏ hơn nguồn, không vượt mục tiêu. Đổi MP4 thử encoder Windows Media Foundation, lỗi thì dùng libx264. Bộ chọn chất lượng video không tự chọn format vượt độ cao tối đa.
- **An toàn sơ bộ**: MZ đội lốt tệp thường, đuôi rủi ro/đuôi kép, ký tự điều hướng; ZIP lồng nhau, lối tắt, macro Office, đường dẫn vượt thư mục, symlink và giới hạn chống giải nén quá mức. ZIP mã hóa không đọc được sẽ báo rõ, không coi đã quét sạch.
- Cách ly `.chuakiemtra`; khôi phục lượt HTTP cần checkbox hiểu rủi ro. Tính/đối chiếu MD5, SHA-1, SHA-256, SHA-512; gọi Defender và kiểm Authenticode. Tra VirusTotal bằng hash, không tải tệp lên.
- **Bảo vệ thư mục do bạn chọn**: theo dõi tệp mới/sửa đổi đã ổn định, bỏ qua file dở, kiểm tra và đổi đuôi tệp rủi ro. Không quét hồi tố toàn bộ tệp cũ.
- **Che PDF bằng vùng kéo chuột**: xuất PDF raster mới từ trang đã tô đen, không sao chép text/object/attachment gốc. Đổi lại PDF đầu ra mất văn bản tìm kiếm. Có kiểm thử xác nhận text nhạy cảm bị xóa và vùng chọn đen.
- Lưu website PDF/PNG theo danh sách, có URL và thời điểm lưu; mở phiên Edge/Chromium riêng. Resolver Drive/Dropbox/OneDrive và MediaFire công khai, không vượt khóa/quota.
- Torrent/magnet qua libtorrent, chọn từng tệp, bỏ chọn đuôi rủi ro mặc định, dừng seed khi thấy hoàn tất. Có fastresume và lịch sử mở lại; kiểm thử tải một phần trong mạng nội bộ → đóng → mở lại → hoàn tất và đối chiếu SHA-256. Chưa nghiệm thu torrent công khai nhiều GB.
- **Giao diện HDM**: sidebar, thống kê hàng đợi, tùy chọn nâng cao thu gọn, Morphicons/Lucide đóng gói cục bộ. Hiệu ứng desktop tôn trọng thiết lập giảm chuyển động Windows.
- **Lưu phiếu in thử nghiệm**: opt-in từng hostname bán hàng; HTML tĩnh ≤90 KB, dựng PDF không script/không request mạng, xếp theo sàn/ngày/mã đơn. Kiểm thử phiếu mẫu; chưa nghiệm thu tài khoản thật và mọi mẫu phiếu. Ảnh qua URL/iframe/cửa sổ in khác hostname có thể thiếu.
- **Tiếp quản lượt tải mới**: tùy chọn quyền downloads; tạm dừng, đợi native host kiểm nguồn và lưu inbox trước khi hủy lượt cũ; lỗi thì trình duyệt tiếp tục. Có Chromium E2E và unit tests thứ tự bàn giao. Gói Firefox đã kiểm thử tải tạm → native EXE, chưa ký AMO.
- Tìm phụ đề Việt theo hash OpenSubtitles với API key/token do bạn nhập, không tải bản chỉ đoán theo tên. Chưa kiểm thử dịch vụ với key thật.
- Giải nén ZIP có giới hạn và kiểm tra trước; tùy chọn thu xuống khay; một phiên cho mỗi database. Chống máy ngủ khi tải, tùy chọn tắt máy sau khi toàn bộ lịch sử HTTP hoàn tất với đếm ngược 60 giây và nút hủy.
- **Cập nhật ký Ed25519**: bản mới phải có manifest ký bởi khóa nhà phát hành được ghim trong app; kiểm SHA-256/kích thước bộ cài rồi mới nhận. Không tự chạy bộ cài. Đây là chữ ký manifest, **không phải chứng thư Authenticode/SmartScreen**.
- Nút cập nhật yt-dlp riêng từ release chính thức, bắt buộc có digest SHA-256 trong GitHub API. Không có digest thì từ chối thay vì bỏ kiểm tra.

## Kiểm tra bảo mật

ZIP từ chối tên mơ hồ trên Windows (dấu chấm/khoảng trắng cuối, thiết bị dành riêng, ADS, bidi); tệp giải nén được gắn Mark of the Web khi hỗ trợ. Nút tải trên trang bỏ qua sự kiện do script tạo; cookie chỉ được đọc khi URL video cùng origin với trang nguồn. PDF được kiểm ngân sách pixel trước khi render.

## Dữ liệu và giới hạn

Lịch sử/URL ký số ở `%LOCALAPPDATA%\HDM\downloads.sqlite3`; phần HTTP tải dở mới ở `%LOCALAPPDATA%\HDM\staging\<job-id>`, lượt cũ vẫn đọc `<thư mục lưu>\.hngoos\<job-id>`. Tệp hoàn chỉnh mới được chuyển tới đích; khác ổ đĩa dùng `.tmp` và kiểm SHA-256 trước tên cuối. Không đăng database lên GitHub. Cookie từ extension chỉ được ghi dạng DPAPI, xóa khỏi inbox sau khi app nhận; file cookie bạn tự chọn được bạn quản lý. File cookie tạm được xóa khi tác vụ kết thúc, nhưng sự cố dừng cưỡng bức có thể để lại thư mục tạm cần dọn.

SHA-256 tự tính không chứng minh tệp sạch; chỉ mã băm mong đợi từ nguồn tin cậy giúp xác minh nội dung. Cách ly bằng đổi đuôi không phải sandbox. Xem [SECURITY](SECURITY.md).

Dung lượng tạm HTTP gần 2 lần kích thước tệp khi ghép; công cụ media/PDF có giới hạn riêng. Chưa có lưu đám mây hai giai đoạn cho video/torrent hoặc toàn bộ i18n. Lưu phiếu bán hàng hiện thử nghiệm. Chưa có chứng thư ký bộ cài Windows. Không vượt DRM, quyền truy cập hay khóa tải của chủ trang.
