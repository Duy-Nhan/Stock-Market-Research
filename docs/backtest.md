# Backtest nhân quả của engine và các mô hình

> Sinh bởi `python -m pipeline.backtest --intraday` ngày **2026-11-09** (kết quả thô: `data/backtest/summary.json`, bản công khai cho giao diện: `site/data/backtest.json`). Engine **1.0**.
> Mục đích: đo xem các quy tắc có **lợi thế thật** so với đường cơ sở hay không — kể cả khi câu trả lời là "không". **Kết luận ngắn: không có bằng chứng về lợi thế dự báo.**

## 1. Cách đo

- Mỗi nến t (sau 260 nến khởi động), engine bỏ phiếu **chỉ bằng dữ liệu ≤ t** (có test nhân quả) rồi so với kết quả thực tế sau h nến: tăng nếu `C_{t+h}/C_t − 1 > τ`, giảm nếu `< −τ`, còn lại đi ngang; `τ = 0,25·ATR14_t·√h/C_t` (h = 1 cho phiên kế tiếp; h = 5 và 10 cho 1–2 tuần) — đúng quy ước chấm của sổ nhật ký.
- Dữ liệu: nến ngày đã điều chỉnh của 11 mã (8 mã theo dõi, VN-Index, VN30, GC=F), từ 2015 (hoặc từ ngày niêm yết) đến 2026-11-09; **không tinh chỉnh bất kỳ ngưỡng nào theo dữ liệu này**.
- **Đường cơ sở:** (1) *đoán độc lập*: độ chính xác kỳ vọng nếu dự đoán không liên quan đến kết quả, giữ nguyên tỷ lệ dự đoán của engine; (2) *luôn đoán nhóm phổ biến nhất*; (3) *động lượng ngây thơ*: đoán theo hướng 5 nến gần nhất.
- Khoảng tin cậy 95% là khoảng Wilson tính với **số mẫu độc lập hiệu dụng** = số nến / h (vì mẫu h > 1 chồng lấn) — vẫn là xấp xỉ.
- Đây là 3 lớp (tăng/đi ngang/giảm), nên đoán ngẫu nhiên đạt khoảng 1/3, **không phải 50%**.

## 2. Kết quả toàn bộ 11 mã (gộp)

| Khung / h | Số nến | Mẫu độc lập | Đúng (KTC 95%) | Cơ sở: đoán độc lập | Cơ sở: luôn đoán nhóm đông nhất | Vượt cơ sở độc lập |
|---|---|---|---|---|---|---|
| Phiên kế tiếp (h=1) | 23,798 | 23,798 | 35.3% (34.7–35.9%) | 34.2% | 34.9% | +1.1 điểm % |
| 1–2 tuần (h=5) | 23,754 | 4,750 | 34.7% (33.4–36.1%) | 33.9% | 38.7% | +0.9 điểm % |
| 1–2 tuần (h=10) | 23,699 | 2,369 | 35.0% (33.1–37.0%) | 34.0% | 39.9% | +1.1 điểm % |
| Động lượng ngây thơ (h=1) | 23,798 | 23,798 | 35.2% (34.6–35.8%) | 33.4% | 34.9% | +1.8 điểm % |
| Động lượng ngây thơ (h=5) | 23,754 | 4,750 | 34.6% (33.3–36.0%) | 33.8% | 38.7% | +0.8 điểm % |
| Động lượng ngây thơ (h=10) | 23,699 | 2,369 | 34.5% (32.6–36.4%) | 34.0% | 39.9% | +0.5 điểm % |

**Đọc kết quả:**
- Engine đúng 35% (h=1), 34,7% (h=5), 35,0% (h=10): chỉ hơn mức "đoán độc lập" khoảng 1 điểm phần trăm và **thấp hơn** mức "luôn đoán nhóm đông nhất" ở khung 1–2 tuần (38,7% / 39,9%, do mẫu có xu hướng tăng dài hạn nên nhóm "tăng" đông nhất).
- Engine **không tốt hơn** "động lượng ngây thơ" (đoán theo hướng 5 nến trước): cùng mức ~35%. Nói cách khác bốn nhóm phiếu + cấu trúc giá không thêm thông tin có thể đo được.
- Khi engine dự đoán *tăng*, tỷ lệ thực sự tăng chỉ nhỉnh hơn tỷ lệ nền (h=1: 36,4% so với 34,4%; h=5: 39,3% so với 38,7%; h=10: 40,9% so với 39,9%). Khi dự đoán *giảm*, tỷ lệ giảm gần bằng nền (31,0% so với 30,6%; 31,3% so với 30,7%; 30,9% so với 30,1%) và tỷ lệ *tăng* thực tế sau dự đoán giảm còn cao hơn (34,6% ở h=1; 38,9% ở h=5): các tín hiệu "giảm" không có giá trị phân biệt rõ rệt.
- **Mức tin cậy "cao" không đáng tin hơn "thấp" một cách có ý nghĩa:**
  - next_session@h1: thấp 35.9% · trung bình 34.4% (33.2–35.6%) · cao 33.4% (31.3–35.5%). Ở h=1, mức cao còn thấp hơn mức thấp.
  - 1_2_weeks@h5: thấp 32.0% · trung bình 35.5% (32.9–38.1%) · cao 36.7% (34.5–38.9%). Mức cao nhỉnh hơn mức thấp nhưng vẫn không vượt cơ sở 'luôn đoán nhóm đông nhất' và khoảng tin cậy chồng lấn mức trung bình.
  - 1_2_weeks@h10: thấp 31.3% · trung bình 35.9% (32.2–39.6%) · cao 37.8% (34.7–41.0%). Mức cao nhỉnh hơn mức thấp nhưng vẫn không vượt cơ sở 'luôn đoán nhóm đông nhất' và khoảng tin cậy chồng lấn mức trung bình.

### Từng mã (độ chính xác và chênh so với cơ sở độc lập)

| Mã | h=1 đúng | h=1 vượt cơ sở | h=5 đúng | h=5 vượt cơ sở |
|---|---|---|---|---|
| XAUUSD | 34.7% | +1.0 điểm % | 34.8% | +0.7 điểm % |
| FPT | 33.8% | +0.4 điểm % | 35.2% | +0.8 điểm % |
| CMG | 38.6% | +1.8 điểm % | 33.8% | +0.3 điểm % |
| VCB | 35.0% | +0.7 điểm % | 34.6% | +1.0 điểm % |
| TCB | 33.3% | -0.5 điểm % | 33.3% | -0.5 điểm % |
| GAS | 33.5% | +0.1 điểm % | 33.0% | -0.4 điểm % |
| BSR | 35.9% | +1.8 điểm % | 37.3% | +3.6 điểm % |
| FUEVFVND | 36.2% | +0.9 điểm % | 31.2% | -2.5 điểm % |
| E1VFVN30 | 36.8% | +1.8 điểm % | 36.2% | +1.6 điểm % |
| VNINDEX | 36.0% | +3.0 điểm % | 36.3% | +1.9 điểm % |
| VN30 | 34.9% | +1.3 điểm % | 35.3% | +1.0 điểm % |

Chênh lệch từng mã dao động từ −2,5 đến +3,6 điểm phần trăm, **cùng cỡ với nhiễu lấy mẫu** (sai số chuẩn khoảng 1 điểm phần trăm cho mỗi mã ở h=1, lớn hơn ở h=5/10 do mẫu chồng lấn); với 11 mã × 2 khung, vài mã "trông" tốt có thể chỉ do may mắn khi thử nhiều lần.

## 3. Khung nội ngày — nến kế tiếp (chỉ để đánh giá chế độ replay)

Engine ở khung `next_session` áp dụng cho nến kế tiếp của các khung nội ngày (dữ liệu nến phút đã lưu, 11 mã gộp):

| Khung | Số nến | Đúng | Cơ sở: đoán độc lập | Vượt cơ sở |
|---|---|---|---|---|
| 60 phút | 7,338 | 35.5% | 35.2% | +0.3 điểm % |
| 15 phút | 22,966 | 32.8% | 33.5% | -0.7 điểm % |
| 5 phút | 52,129 | 34.0% | 34.3% | -0.3 điểm % |
| 1 phút | 62,785 | 39.6% | 39.3% | +0.3 điểm % |

**Chênh lệch trong khoảng ±0,7 điểm phần trăm: quy tắc ở khung nội ngày gần như ngẫu nhiên.** Do đó trong chế độ replay, "so sánh với hệ thống" là so sánh với một bộ quy tắc không có lợi thế đã đo được — **không** nên hiểu là hệ thống giỏi hơn người chơi.

## 4. Thống kê từng mô hình (mô tả)

Với mỗi lần mô hình xuất hiện (nến) hoặc được xác nhận (mô hình giá), ghi nhận kết quả theo **hướng kỳ vọng của mô hình** sau h nến, đặt cạnh **tỷ lệ nền** (tần suất kết quả cùng hướng trên mọi nến). Mô hình giá: h = 5 và 10 nến sau nến xác nhận. Chỉ hiển thị các mô hình có n ≥ 25; mẫu nhỏ hơn có trong `summary.json` nhưng không đáng diễn giải.

| Mô hình | Hướng kỳ vọng | n | Đúng hướng (nền) — nến/5 nến đầu | Đúng hướng (nền) — 10 nến (mô hình giá) | Ghi chú vòng đời |
|---|---|---|---|---|---|
| Nhấn chìm giảm | giảm | 155 | 1 nến: 28% (31%), KTC 21.3–35.3% | 5 nến: 31% (31%), KTC 24.2–38.6% |  |
| Harami giảm | giảm | 36 | 1 nến: 25% (31%), KTC 13.8–41.1% | 5 nến: 22% (31%), KTC 11.7–38.1% |  |
| Nhấn chìm tăng | tăng | 68 | 1 nến: 40% (34%), KTC 28.9–51.6% | 5 nến: 38% (39%), KTC 27.6–50.1% |  |
| Harami tăng | tăng | 30 | 1 nến: 53% (34%), KTC 36.1–69.8% | 5 nến: 34% (39%), KTC 19.9–52.7% |  |
| Mây đen che phủ | giảm | 26 | 1 nến: 23% (31%), KTC 11.0–42.0% | 5 nến: 12% (31%), KTC 4.0–29.0% |  |
| Búa (Hammer) | tăng | 82 | 1 nến: 34% (34%), KTC 24.8–44.9% | 5 nến: 38% (39%), KTC 28.1–48.6% |  |
| Người treo cổ (Hanging man) | giảm | 141 | 1 nến: 40% (31%), KTC 32.0–48.0% | 5 nến: 35% (31%), KTC 27.4–42.9% |  |
| Búa ngược (Inverted hammer) | tăng | 92 | 1 nến: 45% (34%), KTC 34.8–54.7% | 5 nến: 41% (39%), KTC 31.1–50.9% |  |
| Sao băng (Shooting star) | giảm | 97 | 1 nến: 32% (31%), KTC 23.5–41.8% | 5 nến: 28% (31%), KTC 19.9–37.5% |  |
| Tam giác tăng — phá vỡ xuống | giảm | 53 | 5 nến: 25% (31%), KTC 14.9–37.6% | 10 nến: 15% (30%), KTC 7.8–27.1% | đạt mục tiêu đo 15, thất bại (fakeout) 12, còn lại 26 |
| Tam giác tăng — phá vỡ lên | tăng | 42 | 5 nến: 48% (39%), KTC 33.4–62.3% | 10 nến: 48% (40%), KTC 33.4–62.3% | đạt mục tiêu đo 15, thất bại (fakeout) 15, còn lại 12 |
| Tam giác giảm — phá vỡ xuống | giảm | 46 | 5 nến: 33% (31%), KTC 20.9–47.0% | 10 nến: 20% (30%), KTC 10.7–33.2% | đạt mục tiêu đo 9, thất bại (fakeout) 26, còn lại 11 |
| Tam giác giảm — phá vỡ lên | tăng | 67 | 5 nến: 37% (39%), KTC 26.7–49.3% | 10 nến: 43% (40%), KTC 32.1–55.2% | đạt mục tiêu đo 32, thất bại (fakeout) 9, còn lại 26 |
| Hai đáy (Double bottom) | tăng | 162 | 5 nến: 40% (39%), KTC 32.3–47.2% | 10 nến: 37% (40%), KTC 30.0–44.7% | đạt mục tiêu đo 80, thất bại (fakeout) 81, còn lại 1 |
| Hai đỉnh (Double top) | giảm | 113 | 5 nến: 23% (31%), KTC 16.4–31.8% | 10 nến: 29% (30%), KTC 21.0–37.5% | đạt mục tiêu đo 46, thất bại (fakeout) 63, còn lại 4 |
| Vai-đầu-vai (Head & shoulders) | giảm | 30 | 5 nến: 37% (31%), KTC 21.9–54.5% | 10 nến: 37% (30%), KTC 21.9–54.5% | đạt mục tiêu đo 12, thất bại (fakeout) 11, còn lại 7 |
| Vai-đầu-vai ngược | tăng | 27 | 5 nến: 26% (39%), KTC 13.2–44.7% | 10 nến: 52% (40%), KTC 34.0–69.3% | đạt mục tiêu đo 14, thất bại (fakeout) 12, còn lại 1 |
| Tam giác cân — phá vỡ xuống | giảm | 71 | 5 nến: 30% (31%), KTC 20.2–41.0% | 10 nến: 34% (30%), KTC 24.2–46.0% | đạt mục tiêu đo 8, thất bại (fakeout) 25, còn lại 38 |
| Tam giác cân — phá vỡ lên | tăng | 99 | 5 nến: 41% (39%), KTC 32.2–51.3% | 10 nến: 46% (40%), KTC 37.0–56.2% | đạt mục tiêu đo 20, thất bại (fakeout) 22, còn lại 57 |

**Đọc kết quả:**
- Phần lớn mô hình **không** cho thấy tỷ lệ đúng hướng cao hơn nền một cách rõ rệt; nhiều khoảng tin cậy 95% chứa tỷ lệ nền.
- Một vài ô "trông tốt" (ví dụ búa ngược, phá vỡ lên của tam giác tăng) và một vài ô "trông tệ" (ví dụ Hai đỉnh đã xác nhận: sau 5 nến giá tăng nhiều hơn giảm — hướng **ngược** kỳ vọng) là điều **sẽ xảy ra do ngẫu nhiên** khi thử ~25 mô hình × 2 mốc thời gian (khoảng 1–3 kết quả "có ý nghĩa" ở mức 5% chỉ do may rủi). Không diễn giải riêng lẻ khi chưa lặp lại trên dữ liệu mới.
- Tỷ lệ **fakeout cao** ở các mô hình đảo chiều đã xác nhận (Hai đỉnh: thất bại 63 / đạt mục tiêu 46; Hai đáy: 81 / 80; Vai-đầu-vai: 11 / 12): việc "đóng cửa vượt đường cổ > 0,25 ATR" không đủ để coi mô hình là đáng tin theo định nghĩa này.
- Điều này **không** chứng minh các mô hình vô dụng nói chung — chỉ cho thấy **cách nhận diện cơ học này, trên chuỗi dữ liệu này, chưa chứng minh được lợi thế**. Các tài liệu kinh điển mô tả mô hình theo cách mang tính phán đoán trực quan hơn.

## 5. Giới hạn của backtest

1. Kiểm tra nội mẫu trên dữ liệu mà người xây dựng đã thấy; không thay thế kiểm tra ngoài mẫu. Sổ nhật ký (`docs/analysis.md` §8) là kiểm tra ngoài mẫu thật sự và mới bắt đầu 2026-11-09.
2. Mẫu chồng lấn (h > 1); khoảng tin cậy dùng mẫu hiệu dụng gần đúng.
3. Thử nhiều biến thể (3 khung × nhiều mô hình × nhiều mã) → rủi ro kết quả "đẹp" do may mắn; ở đây kết quả chung lại là "không có lợi thế" nên rủi ro này nghiêng về phía thận trọng.
4. Dùng giá đã điều chỉnh; không tính chi phí giao dịch, trượt giá, thanh khoản, giới hạn biên độ ±7%/ngày.
5. Backtest dùng cấu trúc giá tính trên **toàn bộ** lịch sử; engine thực tế dùng cửa sổ 900 nến — chênh nhẹ.
6. Dữ liệu 11 mã giai đoạn 2015–2026 ở một thị trường mới nổi có biên độ giá ±7% và nhiều biến động theo dòng tiền; kết quả không suy rộng cho thị trường/giai đoạn khác.

## 6. Hệ quả cho sản phẩm

- Giao diện luôn hiển thị bằng chứng này ngay dưới mỗi nhận định; câu "Chưa vượt đường cơ sở nào" được sinh tự động từ số liệu, không phải do con người viết tay.
- Nhận định vẫn hữu ích như **công cụ học đọc biểu đồ có kỷ luật** (mọi kết luận truy được về chỉ báo cụ thể, có mức vô hiệu hóa, được chấm công khai), **không** phải tín hiệu giao dịch.
- Hướng cải thiện (Giai đoạn sau, mỗi thay đổi nâng phiên bản engine và phải backtest lại): kết hợp tin tức/vĩ mô; thử các quy tắc có cơ sở học thuật rõ hơn (ví dụ động lượng theo khung dài, mean-reversion theo thanh khoản); đánh giá riêng từng mã thay vì gộp.
