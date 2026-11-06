# Chuẩn bị phát hành Chrome Web Store

Tài liệu dành cho người duy trì; không phân phối cùng gói tiện ích. Chỉ hỗ trợ Chromium MV3, tối thiểu 120.

- Gói nộp: `dist/HDM-Browser-Extension.zip`; manifest nằm ở gốc, không gồm source ứng dụng, tests, npm metadata hay công cụ phát triển.
- Tên: Hngoos Download Manager. Viết tắt: HDM. Phiên bản: 0.1.2.
- Mục đích chính: kết nối thao tác tải tệp/video trên trình duyệt với ứng dụng HDM trên Windows. Các công cụ lọc nội dung và lưu phiếu là tùy chọn.
- Mô tả ngắn: Gửi link và video tới HDM trên Windows, tiếp quản lượt tải tùy chọn và phát hiện luồng HLS/DASH.
- Trang chủ: https://github.com/hngoos/hngoos-download-manager
- Chính sách riêng tư: https://github.com/hngoos/hngoos-download-manager/blob/main/docs/PRIVACY.md
- Giải thích quyền và luồng dữ liệu: xem PRIVACY.md. Mã tiện ích được đóng gói cục bộ; danh sách lọc tải về là dữ liệu quy tắc DNR, không phải mã thực thi từ xa.

Trước khi nộp: cần tài khoản Chrome Web Store Developer của chủ sản phẩm, hoàn tất xác minh và phí đăng ký theo yêu cầu hiện hành của Google, thêm ảnh chụp tiện ích thực tế, điền khai báo dữ liệu theo hành vi thực tế và giải thích từng quyền. Đính kèm hướng dẫn cài HDM cho người duyệt, URL bộ cài chính thức và các bước kiểm kết nối. Không khai báo là đã phát hành khi chưa được duyệt.

Sau khi được Google cấp extension ID ổn định, đăng ký ID đó trong native-host manifest của HDM. Gói ZIP cài thủ công có thể có ID khác theo đường dẫn; không giả định ID store từ bản unpacked. Kiểm tra lại các giới hạn/điều khoản cửa hàng trước khi nộp. Chrome Web Store không tự phát hành tiện ích lên cửa hàng Edge hoặc Opera.
