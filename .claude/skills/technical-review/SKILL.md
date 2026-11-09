---
name: technical-review
description: Trình bày phân tích kỹ thuật top-down của một mã (ví dụ /technical-review FPT) dựa trên dữ liệu đã tính, kèm bằng chứng lịch sử. Dùng khi người dùng hỏi nhận định/xu hướng của một mã.
argument-hint: <mã trong watchlist>
---

Chỉ dùng dữ liệu đã tính của dự án — KHÔNG tự tính hay tự suy diễn con số:

1. Đảm bảo dữ liệu mới (skill `update-data`) nếu `prices_fetched_at` cũ.
2. Đọc `site/data/analysis.json` (mục `items[<mã>]`, cả hai khung `next_session` và `1_2_weeks`), `site/data/backtest.json` (`daily.pooled`) và `site/data/journal.json`.
3. Trình bày theo thứ tự top-down: xu hướng → động lượng → khối lượng → cấu trúc giá (mô hình nến/giá, hỗ trợ/kháng cự) → kịch bản chính/thay thế → mức vô hiệu hóa → luận điểm ngược chiều. Mỗi ý trích đúng giá trị chỉ báo có trong `groups[].text`/`evidence`.
4. BẮT BUỘC nêu: (a) độ tin cậy chỉ là mức đồng thuận của các nhóm quy tắc, không phải xác suất; (b) bằng chứng lịch sử từ backtest và câu "chưa vượt đường cơ sở" nếu đúng vậy; (c) nhận định chưa tính tin tức/vĩ mô; (d) với vàng: là GC=F futures; với cổ phiếu: giá đã điều chỉnh.
5. Không đưa mục tiêu giá/khuyến nghị mua bán; chỉ nêu "vùng quan sát" và "mục tiêu đo" khi engine cung cấp (kèm phương pháp).
