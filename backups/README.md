# Thư mục Sao lưu (Backups Directory)

Thư mục này được sử dụng để lưu trữ các bản sao lưu (backup) cấu hình và cơ sở dữ liệu của công cụ.

## Cơ chế hoạt động
- Khi bạn nhấn nút **Sao Lưu Profile Hiện Tại** trong phần mềm, hộp thoại chọn nơi lưu file sẽ mặc định mở tại thư mục `backups/` này.
- Các bản sao lưu sẽ được nén dưới dạng tệp tin `.zip` với tên định dạng: `backup_<Tên_Profile>_<Thời_gian>.zip`.
- Thư mục này đã được cấu hình đặc biệt trong tệp `.gitignore` để đảm bảo Git sẽ luôn theo dõi (track) và đẩy các tệp sao lưu này lên Repository GitHub khi bạn cập nhật code.

## Nội dung tệp sao lưu (.zip)
Mỗi tệp sao lưu chứa:
1. `config.json`: File cấu hình tài khoản, luồng chạy, các tùy chọn giao diện.
2. `history.db`: File SQLite lưu lịch sử bình luận, lịch sử đăng bài, các bài viết đã quét.
3. `metadata.json`: Lưu thông tin metadata như tên profile gốc, phiên bản và thời gian sao lưu.
