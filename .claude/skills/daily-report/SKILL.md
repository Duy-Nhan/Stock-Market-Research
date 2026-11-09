---
name: daily-report
description: Quy trình viết bản tin thị trường hằng ngày (~2000 từ) cho watchlist, có trích dẫn kiểm chứng tự động và nhận định kết hợp kỹ thuật + tin tức. Dùng khi người dùng bảo "viết bản tin hôm nay" hoặc /daily-report.
---

Đọc trước: `docs/report-methodology.md` (quy trình, 3 tầng nội dung, quy tắc kết hợp) và CLAUDE.md §3 (không bịa).

1. Cập nhật dữ liệu: skill `update-data`; sau 15:15 giờ VN mới có nến ngày hoàn tất. Chạy `python -m pipeline.journal issue` (nhận định kỹ thuật) rồi `python -m pipeline.export_site`.
2. Thu thập tin: `python -m pipeline.fetch_news`; liệt kê tin liên quan (lọc theo nhãn `tickers`/`themes` trong `data/news/raw/<ngày>.json`), **đọc bài gốc** (`python -m pipeline.fetch_news --article URL`) của những tin dùng được. Không dùng tin chưa đọc.
3. Viết `reports/<ngày>.md` theo mẫu bản tin gần nhất: mỗi đoạn có nhãn `{fact}|{data}|{def}|{infer}|{opinion}|{note}`; mọi số liệu thị trường dùng ô thay thế `{{...}}`; mọi câu sự kiện có `[[cN]]`; ~2000 từ; hộp "Kiến thức cho người mới" 2–4 thuật ngữ xuất hiện trong bài (định nghĩa dẫn từ nguồn có thể tải lại).
4. Tạo `reports/<ngày>.claims.json` (câu trích NGUYÊN VĂN ≤ 40 từ, chép đúng từ văn bản bài) và `reports/<ngày>.outlook.json` (lập trường −1/0/+1 cho mỗi mã × 2 khung, có kênh tác động và trích dẫn; không có tin riêng ⇒ 0).
5. `python -m pipeline.build_report <ngày>`: sửa đến khi đạt (không dùng --allow-fail khi đăng). Xử lý mọi cảnh báo.
6. Gọi agent `fact-checker` để rà ngữ nghĩa độc lập; sửa theo các lỗi nó báo rồi chạy lại bước 5.
7. `python -m pipeline.journal issue-combined --report <ngày>` rồi `python -m pipeline.export_site`.
8. Báo cáo cho người dùng: kết quả kiểm chứng, các lỗi đã bắt, những gì CHƯA kiểm chứng/không có nguồn, và nhắc rằng bằng chứng backtest chưa cho thấy lợi thế dự báo.
