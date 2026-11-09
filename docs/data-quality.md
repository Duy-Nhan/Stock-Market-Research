# Báo cáo chất lượng dữ liệu (Giai đoạn 1)

- **Ngày chạy:** 2026-11-09, sau phiên (≈22:45–23:00 giờ VN). Mã kiểm tra: `pipeline/verify.py`; kết quả thô: `data/quality/report.json` (chạy lại được).
- **Phạm vi:** 8 mã cổ phiếu/ETF (nến ngày 273 phiên gần nhất đối chiếu finfo; nến 1 phút 61 phiên gần nhất), 2 chỉ số, vàng `GC=F`.
- **Giới hạn:** chưa đo độ trễ trong phiên (script sẵn: `pipeline/probes/latency_probe.py`); dữ liệu cloud/IP chưa thử.

## 1. Phát hiện quan trọng nhất: giá VNDirect dchart là giá ĐÃ ĐIỀU CHỈNH

- Đối chiếu nến ngày dchart với finfo: **0 lệch** giữa `close` của dchart và `adClose` (giá điều chỉnh) của finfo trên 273 phiên × 8 mã (dung sai 1,5 đồng). Ngược lại, so với `close` (giá thực tế đã khớp) thì lệch ở 6/8 mã.
- Số phiên có `adClose ≠ close` trong 273 phiên: FPT 237 · CMG 70 · VCB 198 · TCB 265 · GAS 238 · BSR 211 · FUEVFVND 0 · E1VFVN30 0.
- Hệ số điều chỉnh ở ngày gần nhất có chênh (adClose/close): TCB 0,667 (2026-10-28) · FPT 0,909 (2026-09-18) · GAS 0,972 (2026-09-21) · BSR 0,989 (2026-08-10) · VCB 0,992 (2026-07-22) · CMG 0,909 (2026-01-13). Các hệ số này **phù hợp với** việc điều chỉnh theo sự kiện doanh nghiệp (cổ tức/thưởng cổ phiếu), nhưng **chưa đối chiếu loại sự kiện cụ thể** — không được khẳng định loại sự kiện trong báo cáo khi chưa có công bố gốc.
- **Nến phút cũng bị điều chỉnh:** ở FPT, 25 ngày có nến nằm ngoài [sàn, trần] thực tế (từ 2026-08-12 đến 2026-09-18) và ngày cuối cùng đó trùng đúng ngày cuối cùng có `adClose ≠ close`; TCB tương tự (53 ngày, đến 2026-10-28). Các mã khác: 0 nến ngoài biên.
- **Hệ quả:**
  1. Lịch sử bị **tính lại hồi tố** mỗi khi có sự kiện mới. Pipeline đã xử lý: mỗi lần chạy so sánh phần chồng lấn với bản đã lưu; nếu lệch > 0,01% thì lấy lại toàn bộ cửa sổ (ghi `refetch_reason` trong meta). Test chạy tăng dần ngày 2026-11-09 không phát hiện điều chỉnh mới (đúng kỳ vọng).
  2. **Chỉ báo/biểu đồ dùng chuỗi đã điều chỉnh** (nhất quán, không có bước nhảy do sự kiện doanh nghiệp). Giá hiển thị trong quá khứ có thể không phải giá đã giao dịch thực tế và không khớp đơn vị yết giá; UI replay phải ghi chú "giá đã điều chỉnh" và **chỉ vẽ trần/sàn thực tế cho những ngày không bị điều chỉnh**.
  3. Giá tham chiếu/trần/sàn của một ngày lấy từ finfo (giá thực tế đã niêm yết), không lấy từ chuỗi dchart.

## 2. Nhãn thời gian nến phút

- Nến phút tồn tại ở: 09:15–11:29, 13:00–14:29 và **14:45**; **không có** ở 11:30, 12:xx, 14:30–14:44. Suy ra **nhãn = thời điểm bắt đầu nến** (nến 11:29 phủ 11:29–11:30; nến 13:00 là phút đầu buổi chiều), và nến **14:45 là kết quả phiên ATC** (giai đoạn 14:30–14:45 không có nến liên tục).
- Nến 14:45 chiếm khối lượng trung vị 5–10% cả ngày ở các cổ phiếu (FPT 5,8%; VCB 6,1%; TCB 10,3%; GAS 5,2%; BSR 5,7%), phù hợp vai trò của phiên ATC. Với ETF thấp hơn (FUEVFVND 2,2%; E1VFVN30 1,9%).
- Nến 09:15 chiếm khối lượng trung vị khoảng 0,9–1,6% cả ngày (E1VFVN30 4,7%). **Chưa xác định** nến này gộp kết quả ATO (09:00–09:15) hay chỉ là phút khớp liên tục đầu tiên → chưa kết luận gì về ATO từ nến phút.
- Quy tắc áp dụng: nến t chỉ hoàn tất khi `now ≥ t + độ dài khung` (cài trong `build_indicators.is_partial`); nến ngày VN hoàn tất sau 15:00 giờ VN. Phép xấp xỉ có chủ đích: nến 14:45 coi là hoàn tất sau 1 khung.
- Chỉ số VN-Index/VN30 có nến đến ~15:05 (khác cổ phiếu) — hiểu theo cách công bố của nguồn, chưa xác minh nguyên nhân.

## 3. Khối lượng

| Phép đối chiếu | Kết quả |
|---|---|
| dchart daily `v` so với finfo `nmVolume` (khớp lệnh) | Khớp tuyệt đối ở phần lớn phiên; lệch ở 1–7/273 phiên mỗi mã, mức lệch nhỏ (≤ ~2,5%), **cùng một số ngày ở nhiều mã** (2026-11-02, 10-12, 10-09, 08-11…) → nguyên nhân hệ thống, **chưa xác định** (nghi giao dịch lô lẻ — chưa kiểm chứng) |
| Tổng KL các nến 1m trong ngày / `nmVolume` | Trung vị = 1,00 ở cả 8 mã, nhưng có phiên lệch: FPT 0,92–1,05 · VCB 0,93–1,13 · TCB 0,98–1,07 · GAS 0,86–1,16 · BSR 0,95–1,09 · FUEVFVND 0,95–1,07 · E1VFVN30 0,89–1,10 · **CMG 0,83–1,43** |
| Thỏa thuận (`ptVolume`) | Không có trong dchart (đã xác nhận ở Giai đoạn 0) |

Kết luận: **khối lượng nến phút chỉ mang tính tham khảo** (sai lệch tới ±10–40% ở một số phiên so với tổng ngày); mọi kết luận về khối lượng (xác nhận breakout, phân kỳ…) nên dựa trên khối lượng ngày. Ghi rõ "khối lượng khớp lệnh".

## 4. Mã ít thanh khoản: nến phút thưa

Phút không có giao dịch **không có nến** (CMG: 5.656 nến 1m trong 61 phiên so với ~13.700 của FPT; FUEVFVND 6.723; E1VFVN30 9.550). Không điền nến giả. Chỉ báo nội phiên (EMA, RSI…) trên các mã này được tính trên các nến *có giao dịch*, khoảng cách thời gian không đều → ý nghĩa của "n nến" khác với mã thanh khoản cao; UI/phân tích phải nêu điều này, và ưu tiên khung 15m/60m/ngày cho CMG, FUEVFVND, E1VFVN30.

## 5. Đối chiếu Yahoo `.VN` (nến ngày, 63 phiên)

- Lệch > 0,5%: FPT 0 · FUEVFVND 0 · E1VFVN30 0 · CMG 1 · VCB 1 · TCB 1 · BSR 2 · **GAS 28**.
- Cả CMG, VCB, TCB đều lệch đúng một ngày **2026-09-09** (nghi dữ liệu Yahoo ngày đó, chưa xác minh).
- GAS lệch ~2,8% trong nhiều phiên gần đây: trùng với hệ số điều chỉnh 0,972 của dchart. **Phù hợp với giả thuyết** Yahoo không điều chỉnh cổ tức tiền mặt trong trường `close` (chưa kiểm chứng) → Yahoo `.VN` chỉ dùng dự phòng và phải kiểm tra chênh trước khi thay thế dchart.

## 6. Vàng GC=F

- 2.514 nến ngày; trung vị |lợi suất ngày| 0,51%; trung vị |khoảng nhảy mở cửa so với đóng cửa trước| 0,17%.
- Khoảng nhảy lớn nhất 2,4–3,5% (2020-03-16, 2016-11-14, 2026-06-12, 2024-08-01, 2019-06-20, 2026-03-23…). **Không thể phân biệt** bước nhảy do chuyển hợp đồng với biến động thị trường thật chỉ từ dữ liệu này. Chưa có kết luận về roll; cách xử lý: lưu giá spot hằng ngày song song và so sánh basis theo thời gian (Giai đoạn sau), dán nhãn "futures" trên mọi biểu đồ vàng.
- Nến 1h/5m/1m cuối cùng là nến đang chạy dở khi tải (gắn `partial`).
- **Phát hiện ở Giai đoạn 2:** Yahoo gắn thêm vào cuối mỗi chuỗi một "nến giả" mang giá hiện tại (O=H=L=C, khối lượng 0, thời gian có giây lẻ, ví dụ 22:39:05). Nếu giữ lại nó sẽ nằm vĩnh viễn trong chuỗi và làm méo biểu đồ/chỉ báo (đã thấy trên biểu đồ 15 phút). Pipeline nay loại mọi nến có giây lẻ (nến thật luôn tròn phút) và dọn cả nến giả đã lưu; có test.

## 7. Lịch giao dịch

- 459 phiên kể từ 2025-01-01 (FPT), **không có nến cuối tuần**. Các khoảng nghỉ > 3 ngày: 2025-01-24→02-03, 2025-04-04→04-08, 2025-04-29→05-05, 2025-08-29→09-03, 2025-12-31→2026-01-05, 2026-02-13→02-23, 2026-04-24→04-28, 2026-04-29→05-04, 2026-08-28→09-03. Hai khoảng ngày 2025-01-24→02-03 và 2026-02-13→02-23 là kỳ nghỉ Tết. Chưa đối chiếu từng kỳ nghỉ với thông báo chính thức; pipeline suy ngày giao dịch từ dữ liệu (không hard-code lịch).

## 8. Bất thường nhỏ được giữ nguyên (không sửa)

- GAS 2019-12-19: giá mở 57.516 thấp hơn giá thấp nhất 57.577 (~0,1%). VN-Index 2020-09-29: giá đóng 903,98 thấp hơn giá thấp nhất 904,69 (~0,08%). Nghi do làm tròn/điều chỉnh ở dữ liệu cũ. Pipeline đếm vào `meta.anomalies`, không sửa dữ liệu.

## 9. SJC

- Đối chiếu chéo 2026-11-09 ~22:40: trang tổng hợp webgia.com (bên thứ ba) ghi vàng SJC 1L–10L–1KG tại TP.HCM mua 13.820.000 / bán 14.120.000 đồng/**chỉ** → ×10 = 138,2 / 141,2 triệu đồng/lượng, **trùng** vnappmob. Cả hai đều là bên thứ ba, chưa phải bảng giá chính thức của SJC.
- Ví dụ độ chênh (minh họa, KHÔNG phải số liệu chính thức — mốc thời gian lệch nhau: giá SJC lúc ~15:00, giá vàng spot lúc ~22:50): với spot 4.119,3 USD/oz và SJC bán 141,2 triệu: premium ≈ 12,4% (tỷ giá mua 25.290), 12,3% (chuyển khoản 25.320), 10,6% (bán 25.700) → phải chọn và ghi rõ loại tỷ giá. Công thức và test: `pipeline/gold.py`.

## 10. Việc còn lại

1. Đo độ trễ trong phiên (2026-11-10) bằng `latency_probe`.
2. Xác định nguyên nhân chênh khối lượng ngày (lô lẻ?) và chênh nến phút.
3. Quyết định loại tỷ giá USD/VND dùng tính premium.
4. Chạy thử từ cloud (IP GitHub Actions).
5. Dung lượng lưu trữ: `data/prices` ≈ 14 MB và `data/indicators` ≈ 12 MB đã đủ lớn; commit hằng ngày các file JSON nến phút/5 phút sẽ phình repo. Đề xuất: không commit `data/indicators/` (sinh lại khi build), và chia nhỏ nến phút theo tháng ở giai đoạn tự động hóa.
