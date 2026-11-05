# Rà soát bảo mật — 2026-11-05

Đây là ghi nhận tự rà soát cho bản 0.1.0, không phải pentest độc lập hoặc chứng nhận an toàn. Phạm vi gồm mã Python/extension, đường đi tệp ZIP/PDF, quyền cookie, dependency, Git history và workflow phát hành.

## Kết quả và sửa đổi

| Hạng mục | Kết quả / thay đổi |
| --- | --- |
| Secret trong Git | Gitleaks 8.30.1 quét 10 commit trước đợt sửa, không tìm thấy secret; workflow quét lại khi push/PR |
| Dependency | pip-audit và npm audit không phát hiện lỗ hổng đã biết trong môi trường kiểm tra 0.1.0; package HDM editable được kiểm bằng review/test, không có dữ liệu advisory trên PyPI |
| Tên ZIP trên Windows | Bổ sung từ chối đuôi chấm/khoảng trắng, thiết bị dành riêng kể cả superscript, ADS, bidi, absolute/traversal; test các tên bị bỏ sót trước đó |
| Tệp giải nén | Gắn Mark of the Web trên hệ thống hỗ trợ; vẫn không tự chạy đầu ra |
| Nút tải trên website | Bỏ qua click do script tạo; kiểm thử Chromium phân biệt click giả và thao tác người dùng |
| Cookie website khác | Không đọc/gửi cookie khi URL video khác origin trang nguồn; test JavaScript cả hai nhánh |
| PDF bất thường | Kiểm số pixel dự kiến trước renderer; test từ chối trang rất lớn mà không gọi render |
| Chuỗi cung ứng CI | Actions ghim commit, checkout không giữ credential, Dependabot đề xuất cập nhật |
| Phiếu in | Dựng HTML tĩnh trong browser tách biệt: JavaScript tắt, CSP khóa nguồn và route chặn mạng; test phiếu chứa script/iframe/ảnh mạng |
| Bàn giao browser | Native host kiểm URL/kích thước và lưu yêu cầu trước khi hủy lượt cũ; test native host lỗi thì trình duyệt tải tiếp |
| Kiểm tra liên tục | Workflow Security chạy Gitleaks, pip-audit, npm audit và CodeQL Python/JavaScript |

Các kết quả quét chỉ phản ánh mã/dependency ở thời điểm chạy. Không đưa số lượng tests hoặc badge CI vào cam kết “an toàn 100%”. Dependency có binary native cần theo dõi advisory và phiên bản upstream riêng; pip-audit không chứng minh binary FFmpeg/PDFium không có lỗ hổng.

## Vệ sinh repository

Source, test, tài liệu và icon SVG/PNG đã sinh được theo dõi bằng Git. Bộ cài, môi trường ảo, node_modules, database và công cụ cục bộ không được đưa vào repository. Không viết lại Git history hoặc xóa test để làm đẹp số liệu.

Giữ source, test và tài liệu theo thư mục hiện có. File build nằm trong `dist/` và `build/`, công cụ cục bộ nằm trong `tools/`, đều bị Git bỏ qua. Extension phát hành dùng danh sách file runtime cho phép; `test/` và `package.json` không nằm trong ZIP/bộ cài.

`.gitignore` được bổ sung mẫu khóa ký/chứng thư, DPAPI, cookie và file tải dở. Ignore không xóa secret đã commit: nếu có lộ khóa, cần thu hồi/đổi khóa trước khi xử lý lịch sử.

## Phần còn cần theo dõi

- Bộ cài Windows chưa có Authenticode; manifest Ed25519 không thay thế chứng thư này.
- Cookie tạm có thể còn lại sau dừng cưỡng bức; dữ liệu lịch sử/staging chưa mã hóa toàn bộ. DPAPI không bảo vệ trước malware chạy cùng tài khoản Windows.
- Chưa kiểm thử mọi website/tài khoản, archive format, GPU hoặc tải nhiều GB khi mất nguồn.
- App và thư viện native chạy với quyền tài khoản người dùng; kiểm tra đuôi/MZ/ZIP không phải antivirus hoặc sandbox.
- Nghiệm thu đầy đủ bộ lọc quảng cáo, phát hành Chrome Web Store, video riêng tư và phiếu trên tài khoản sàn thật còn trong lộ trình. Tiện ích chỉ hỗ trợ Chromium, cài thủ công từ ZIP.

Xem [Vulnerability reporting](VULNERABILITY_REPORTING.md) để báo lỗ hổng và hiểu ranh giới tin cậy.
