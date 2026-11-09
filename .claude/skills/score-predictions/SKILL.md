---
name: score-predictions
description: Phát hành nhận định mới vào sổ nhật ký (nếu đúng thời điểm), chấm các nhận định đã đến hạn bằng giá thật và cập nhật thống kê. Dùng khi người dùng muốn xem kết quả nhận định hoặc sau mỗi phiên.
---

1. Cập nhật dữ liệu trước (skill `update-data`, ít nhất bước 1–2).
2. `. .venv/bin/activate && python -m pipeline.journal all` — `issue` (chỉ phát hành khi nến tham chiếu vừa hoàn tất; cổ phiếu sau 15:15 giờ VN, vàng ngay sau khi nến ngày GC=F kết thúc), `score`, `stats`.
3. `python -m pipeline.export_site` để trang web hiển thị sổ nhật ký mới.
4. Báo cáo: số nhận định đã phát hành/đã chấm, tỷ lệ đúng KÈM khoảng tin cậy và đường cơ sở (`share_outcome_flat`), và nói rõ khi `n < 30` ("chưa đủ ý nghĩa thống kê"). Nêu cả những nhận định sai. Không sửa/xóa nhận định đã phát hành; không chấm lại theo luật mới (xem `docs/analysis.md` §8 và `docs/methodology.md`).
