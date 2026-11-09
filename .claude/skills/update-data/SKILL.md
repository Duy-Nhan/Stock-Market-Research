---
name: update-data
description: Cập nhật dữ liệu giá/snapshot của dự án, kiểm tra chất lượng, xuất dữ liệu cho trang web và chạy test. Dùng khi người dùng bảo "cập nhật dữ liệu", "chạy pipeline" hoặc trước khi phân tích.
---

Chạy trong thư mục dự án (đã có `.venv`):

1. `. .venv/bin/activate && python -m pipeline.fetch_prices` — in ra từng mã/khung; báo cáo mã nào `[FAIL]` hoặc có `ANOMALY` (không bỏ qua im lặng).
2. `python -m pipeline.fetch_snapshots` — vàng spot, SJC, USD/VND, dữ liệu phiên finfo. Nguồn tỷ giá giới hạn 1 request/5 phút.
3. `python -m pipeline.verify` rồi đọc `data/quality/report.json`: báo cáo bất thường mới so với `docs/data-quality.md`.
4. `python -m pipeline.export_site` để làm mới `site/data/`.
5. `python -m pytest pipeline/tests -q`.

Quy tắc: nếu nguồn lỗi/thiếu dữ liệu thì nói rõ, không nội suy. Không chạy `journal issue` ở đây (xem skill score-predictions). Ghi rõ thời điểm dữ liệu (`prices_fetched_at`) trong báo cáo cho người dùng.
