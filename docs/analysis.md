# Engine nhận định kỹ thuật top-down

> Phiên bản engine: **1.0** (đóng băng ngày 2026-11-09 khi phát hành các nhận định đầu tiên vào sổ nhật ký). Mã: `pipeline/engine.py`; test: `pipeline/tests/test_engine.py`.
> Mọi thay đổi quy tắc ở đây = nâng `ENGINE_VERSION`, ghi lại thay đổi và lý do, và **không** áp dụng hồi tố cho nhận định đã phát hành.

## 0. Đọc trước

- Engine là **một bộ quy tắc cố định theo thông lệ phân tích kỹ thuật**, không phải mô hình học từ dữ liệu và **không được tinh chỉnh theo dữ liệu của dự án**.
- **Bằng chứng thật về hiệu quả nằm ở [docs/backtest.md](backtest.md): trên dữ liệu lịch sử của 11 mã, các quy tắc này chưa vượt đường cơ sở nào.** Giao diện luôn hiển thị bằng chứng đó ngay dưới mỗi nhận định.
- Nhận định chưa tính tin tức/vĩ mô; bản tin (Giai đoạn 4) sẽ bổ sung và phải nêu rõ khi hai nguồn mâu thuẫn.
- Văn bản tiếng Việt trong nhận định được sinh từ mẫu câu điền **chính các giá trị đã tính**, nên mỗi câu truy được về một con số; không có đoạn văn nào do model "tự viết".

## 1. Khung phân tích

Với mỗi mã, tại **nến ngày hoàn tất gần nhất**, engine trả lời cho hai khung dự báo độc lập: `next_session` (nến ngày kế tiếp) và `1_2_weeks` (5 và 10 phiên). Thứ tự phân tích top-down (theo `docs/methodology.md` §4):

1. **Xu hướng** (khung ngày)  →  2. **Động lượng**  →  3. **Khối lượng**  →  4. **Cấu trúc giá** (mô hình nến/giá, hỗ trợ/kháng cự)  →  5. **Kịch bản + mức vô hiệu hóa**  →  6. **Kết luận + độ tin cậy**.

Mỗi nhóm trong 4 nhóm bỏ **một phiếu** `-1` (ủng hộ giảm), `0` (trung lập), `+1` (ủng hộ tăng) dựa trên giá trị chỉ báo cụ thể. Nhóm không có đủ dữ liệu (ví dụ không có khối lượng đáng tin cậy) được đánh dấu "không áp dụng" và **không tính** vào kết luận.

## 2. Phiếu bầu — khung `1_2_weeks` (theo xu hướng)

| Nhóm | Quy tắc phiếu |
|---|---|
| Xu hướng | Cộng ba dấu: (a) Dow (+1/−1/0, `docs/patterns.md` §3); (b) EMA20 so với EMA50; (c) giá đóng cửa so với EMA50. Tổng ≥ +2 → +1; ≤ −2 → −1; còn lại 0 |
| Động lượng | MACD histogram và RSI(14) − 50 (vùng chết ±2): phiếu = dấu chung nếu **cùng phía**, ngược lại 0 |
| Khối lượng | Trong 10 nến: giá và OBV cùng hướng → phiếu theo hướng đó (khối lượng xác nhận); khác hướng hoặc đi ngang → 0 |
| Cấu trúc giá | Cộng: mô hình giá **đã xác nhận** trong 20 nến gần nhất (theo hướng phá vỡ); nến Nhật có hướng ở nến hiện tại hoặc nến trước đó (sau xu hướng phù hợp, chưa thất bại); vị trí giá — sát hỗ trợ (≤ 1,0 ATR phía dưới, không sát kháng cự) = +1, sát kháng cự (≤ 1,0 ATR phía trên) = −1. Phiếu = dấu của tổng |

## 3. Phiếu bầu — khung `next_session` (ngắn hạn)

| Nhóm | Quy tắc phiếu |
|---|---|
| Xu hướng | Cộng ba dấu: giá so với EMA9; EMA9 so với EMA20; giá so với EMA20. Tổng ≥ +2 → +1; ≤ −2 → −1 |
| Động lượng (theo **chế độ ADX**) | ADX ≥ 25: theo chiều lực chi phối (+DI so với −DI). ADX < 20: hồi quy về trung bình — RSI ≤ 30 hoặc Stoch %K ≤ 20 (không đồng thời quá mua) → +1; RSI ≥ 70 hoặc %K ≥ 80 → −1. ADX trong [20, 25): 0 |
| Khối lượng | Nến vừa rồi có khối lượng ≥ 1,25× trung bình 20 nến → phiếu theo hướng nến (tăng/giảm); còn lại 0 |
| Cấu trúc giá | Như trên nhưng ngưỡng sát hỗ trợ/kháng cự 0,75 ATR, không xét mô hình giá, thêm Bollinger: đóng ngoài biên khi ADX < 25 (%B < 0 → +1; %B > 1 → −1) |

Cơ sở: ADX/DI (Wilder) để phân biệt thị trường có xu hướng với đi ngang; quá mua/quá bán và Bollinger là công cụ hồi quy khi **không** có xu hướng mạnh (Murphy). Đây là cách kết hợp thông dụng; **tính hiệu quả chưa được chứng minh** (xem backtest).

## 4. Hướng, độ tin cậy

- `net` = tổng phiếu các nhóm áp dụng. **Tăng** nếu `net ≥ 2`; **Giảm** nếu `net ≤ −2`; còn lại **Đi ngang/chưa rõ**.
- Độ tin cậy (confluence): **cao** = ≥ 3 nhóm cùng hướng và không nhóm nào ngược chiều; **trung bình** = ≥ 2 nhóm cùng hướng và ≤ 1 nhóm ngược chiều; **thấp** = còn lại (gồm mọi trường hợp "đi ngang"). Các nhóm mâu thuẫn được nêu rõ thay vì chọn một bên.
- "Độ tin cậy" ở đây chỉ là **mức đồng thuận của các nhóm quy tắc**, không phải xác suất đúng. Xác suất đúng thực tế được đo trong backtest và sổ nhật ký, và hiện chưa cho thấy mức tin cậy cao đáng tin hơn đáng kể.

## 5. Mức vô hiệu hóa và kịch bản

- **Mức vô hiệu hóa** (nếu có hướng): với nhận định tăng — mức cao nhất trong {đáy swing gần nhất, vùng hỗ trợ gần nhất} nằm dưới giá, cách giá ≥ 0,5 ATR và ≤ 4 ATR; không có thì dùng `giá − k·ATR` (k = 1,5 cho phiên kế tiếp, 2,0 cho 1–2 tuần). Đối xứng cho nhận định giảm.
- **Kịch bản chính/thay thế** được dựng từ hướng, mức vô hiệu hóa, vùng hỗ trợ/kháng cự gần nhất. Mức giá nêu là **vùng quan sát**, không phải mục tiêu giá.
- **Mục tiêu giá** chỉ xuất hiện khi có mô hình giá đã xác nhận cùng hướng, theo cách đo chiều cao mô hình (measured move), có ghi tên mô hình.
- **Luận điểm ngược chiều** = các nhóm bỏ phiếu ngược hướng kết luận. **Lưu ý** thêm: phân kỳ RSI (§6), ADX thấp ở khung 1–2 tuần, mô hình giá đang hình thành.

## 6. Phân kỳ RSI

Chỉ là cảnh báo (không bỏ phiếu): với hai swing đỉnh gần nhất đã xác nhận, nếu đỉnh sau cao hơn nhưng RSI tại đỉnh sau thấp hơn > 1 điểm → phân kỳ giảm (đối xứng cho đáy → phân kỳ tăng), chỉ xét khi swing sau được xác nhận trong 15 nến gần nhất (Wilder/Murphy mô tả phân kỳ; quy tắc định lượng là của dự án).

## 7. Nhân quả và kiểm thử

- Mọi phiếu tại nến i chỉ dùng dữ liệu ≤ i; test `test_signals_are_causal` so sánh tính trên toàn chuỗi với chuỗi cắt tại t.
- Nhận định hiển thị trên trang (`site/data/analysis.json`) dùng **cùng cửa sổ 900 nến ngày** với sổ nhật ký nên trùng với nhận định đã phát hành; backtest dùng toàn bộ lịch sử (cấu trúc giá có thể lệch nhẹ ở các vùng cũ hơn 900 nến — giới hạn đã biết).

## 8. Nhật ký dự đoán

- `python -m pipeline.journal issue|score|stats|all` (`pipeline/journal.py`). Nhận định đã phát hành **không bao giờ bị sửa/ghi đè**; chỉ thêm mục `evaluations`.
- Chống nhìn trước: chỉ phát hành khi nến tham chiếu **vừa hoàn tất** và chưa có nến mới bắt đầu (VN: tối đa 66 giờ sau 15:00 để gồm cuối tuần và chưa có nến phút của phiên sau; vàng GC=F: tối đa 4 giờ sau khi nến ngày kết thúc). Vì vậy: chạy `issue` cho cổ phiếu sau 15:15 giờ VN, và cho vàng ngay sau khi nến ngày GC=F kết thúc (~12:05 giờ VN, giờ nến theo Yahoo — cần kiểm chứng khi tự động hóa).
- Đánh giá: τ cố định lúc phát hành (`0,25·ATR14·√h/giá`, h = 1, 5, 10); giá đã điều chỉnh hiện tại ở cả hai đầu; gắn cờ `adjustment_event` nếu hệ số điều chỉnh của nến tham chiếu đã đổi.
- Thống kê (`data/predictions/summary.json`): tỷ lệ đúng kèm khoảng tin cậy 95% (Wilson) và cảnh báo `n < 30`. Mẫu ở khung 1–2 tuần chồng lấn nên số mẫu độc lập ít hơn số lượt chấm.

## 9. Giới hạn

- Chưa có cấu phần tin tức/vĩ mô; chưa có nhóm "tương quan liên thị trường" (ví dụ vàng ↔ USD, VN-Index ↔ cổ phiếu).
- Không có giá trị tuyệt đối nào trong các ngưỡng (0,25 ATR, 1,25× khối lượng, 25/20 ADX, 70/30 RSI…): đó là quy ước.
- Backtest dùng cùng dữ liệu mà người viết đã quan sát để thiết kế giao diện; dù quy tắc không được tinh chỉnh theo dữ liệu, kết quả chỉ nên coi là kiểm tra hợp lý, không phải bằng chứng về tương lai.
