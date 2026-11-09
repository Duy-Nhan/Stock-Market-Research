# Cấu trúc giá: swing, xu hướng, đường xu hướng, hỗ trợ/kháng cự

> Bản Giai đoạn 2 (2026-11-09). Cài đặt: `pipeline/structure.py`; test: `pipeline/tests/test_structure.py`.
> Phần A (mô hình nến) và Phần B (mô hình giá) ở cuối tài liệu — viết ở Giai đoạn 3.
> **Các hệ số (0,3 / 0,25 / 0,5 ATR, k = 5, lookback 250) là quy ước của người phân tích để có quy tắc định lượng lặp lại được; chúng không phải định luật và chưa được kiểm định thống kê.** Mọi nhận định dựa trên chúng phải nêu rõ điều này.

## 1. Nguyên tắc nhân quả (không nhìn trước tương lai)

Mọi kết quả tại nến i chỉ dùng: giá đến nến i và các swing đã **xác nhận** (`confirmed_at ≤ i`). Một swing tại nến j chỉ được xác nhận ở nến j + k. Do đó trên biểu đồ, dấu swing xuất hiện **trễ k nến** so với đỉnh/đáy thật — đúng như người giao dịch thực tế chỉ biết đó là đỉnh sau khi giá đã giảm k nến. Test (`test_structure_no_lookahead_on_real_data`) so sánh kết quả tính trên toàn chuỗi với tính trên chuỗi cắt tại t: phải trùng khớp. Nhờ đó chế độ replay chỉ cần hé lộ dần kết quả đã tính, không cần tính lại.

Giới hạn: đường xu hướng/vùng S/R/swing chỉ xét trong **cửa sổ hiển thị** (600 nến; 2.250 nến cho khung 1 phút) nên các swing cũ hơn cửa sổ không tham gia.

## 2. Swing (đỉnh/đáy cục bộ)

- Swing high tại nến i nếu `H_i` lớn hơn (chặt) `H` của k nến trước **và** k nến sau; swing low đối xứng với `L_i` nhỏ hơn chặt.
- k = 5 cho mọi khung (tham số `SWING_K`). Đỉnh bằng nhau (hòa) không tạo swing.
- Đây là khái niệm "swing point n nến" thông dụng; k lớn → ít swing hơn nhưng bền hơn.

## 3. Xu hướng theo Dow (`trend_state`)

Dùng hai đỉnh swing và hai đáy swing đã xác nhận gần nhất:
- **Tăng (+1):** đỉnh sau > đỉnh trước **và** đáy sau > đáy trước.
- **Giảm (−1):** đỉnh sau < đỉnh trước **và** đáy sau < đáy trước.
- **Hỗn hợp (0):** các trường hợp còn lại (gồm đi ngang, hoặc đang chuyển pha).
- **Chưa đủ dữ liệu (NaN):** chưa có hai đỉnh hoặc hai đáy.

Cơ sở: định nghĩa xu hướng tăng/giảm là chuỗi đỉnh–đáy cao dần/thấp dần trong Lý thuyết Dow (Murphy, *Technical Analysis of the Financial Markets*, chương về khái niệm xu hướng — chưa đối chiếu số trang). Dự án chỉ dùng tín hiệu **đỉnh–đáy**, chưa đòi hỏi xác nhận chéo giữa hai chỉ số hay khối lượng như Dow gốc. Trạng thái này thay đổi **trễ** vì phải chờ swing được xác nhận.

## 4. Đường xu hướng (`trendlines`)

- **Đường tăng:** nối hai đáy swing đã xác nhận, đáy sau cao hơn đáy trước. **Đường giảm:** nối hai đỉnh swing, đỉnh sau thấp hơn.
- Ứng viên: mọi cặp trong `MAX_SWINGS_FOR_LINES = 8` swing cùng loại gần nhất.
- **Hợp lệ** (tại nến i) nếu **không có nến đóng cửa nào** từ swing đầu đến nến i vượt qua đường quá `BREAK_ATR × ATR_i` (0,25 ATR) về phía phá vỡ (dưới đường tăng/trên đường giảm).
- **Số lần chạm:** số swing cùng loại (từ swing đầu trở đi) nằm cách đường ≤ `TOUCH_ATR × ATR_i` (0,3 ATR); luôn ≥ 2 (hai swing tạo đường).
- **Chọn đường:** nhiều lần chạm nhất → swing thứ hai gần nhất → khoảng cách giữa hai swing dài nhất.
- Mỗi đường có vòng đời `[from, to]`: bắt đầu khi đường lần đầu được chọn (không sớm hơn lúc swing thứ hai được xác nhận), kết thúc khi bị phá hoặc có đường khác được chọn. Số chạm lưu theo thời gian (`touches_hist`), không dùng thông tin tương lai.
- Hiển thị: từ swing đầu đến nến hiện tại, **không kéo dài vào tương lai**.
- Lưu ý khoa học: việc chọn "đường tốt nhất" trong nhiều ứng viên thiên về cặp khớp quá khứ; độ chính xác dự báo của đường xu hướng chưa được kiểm định ở dự án này (sẽ đánh giá bằng nhật ký dự đoán).

## 5. Vùng hỗ trợ / kháng cự (`zones`)

- Duyệt swing theo thời điểm xác nhận; gộp (tham lam) vào vùng gần nhất nếu giá cách **tâm vùng** ≤ `ZONE_ATR × ATR` (0,5 ATR, ATR tại nến xác nhận); nếu không có vùng nào gần → tạo vùng mới.
- Tâm vùng = trung bình giá các swing trong vùng. Cần **≥ 2 swing** mới coi là vùng.
- Giao diện chỉ hiện vùng mà swing gần nhất không quá 250 nến, và tối đa 2 vùng trên giá + 2 vùng dưới giá gần nhất. Vùng nằm trên giá hiển thị là kháng cự, nằm dưới giá là hỗ trợ (một vùng có thể đổi vai trò khi giá vượt qua).
- Tham số `ZONE_HALF_ATR` (0,25 ATR) lưu để dùng cho bề rộng vùng; giao diện hiện tại chỉ vẽ đường tâm vùng.

## 6. Pivot theo ngày

Pivot cổ điển từ cao/thấp/đóng của **ngày giao dịch trước** (gộp tất cả nến cùng ngày VN): xem công thức tại `docs/indicators.md` §5. Giao diện vẽ các mức của ngày hiện tại. Với GC=F chỉ cung cấp ở khung ngày (giao dịch gần 24 giờ nên "ngày trước" theo giờ VN không có ý nghĩa rõ ràng trong khung nội ngày).

## 7. Fibonacci retracement trên giao diện

Hai swing đã xác nhận gần nhất ngược loại (một đỉnh, một đáy) → a là swing sớm hơn, b là swing muộn hơn; mức = `b − r·(b − a)` với r ∈ {0,236; 0,382; 0,5; 0,618; 0,786}. Công thức nằm ở `docs/indicators.md` §5; giao diện tự áp dụng từ danh sách swing và tỷ lệ trong `meta.fib_ratios`.

## 8. Phần A — Mô hình nến Nhật (`pipeline/candle_patterns.py`)

Mô tả hình dạng nến theo Nison (*Japanese Candlestick Charting Techniques*), được **định lượng** như dưới đây. Ký hiệu: thân = |C−O|, biên độ = H−L, bóng trên = H−max(O,C), bóng dưới = min(O,C)−L.

- **Bối cảnh xu hướng trước mô hình** (Nison nhấn mạnh mô hình đảo chiều chỉ có nghĩa sau xu hướng phù hợp): xu hướng tăng nếu C thay đổi ≥ +3·ATR trong 10 nến trước nến đầu của mô hình; giảm nếu ≤ −3·ATR; không đạt = không có bối cảnh → **mô hình đảo chiều không được báo**.
- Nến phải có biên độ ≥ 0,5·ATR (loại nhiễu). "Nến thân dài": thân ≥ 0,7·ATR và ≥ 60% biên độ.
- **Doji:** thân ≤ 10% biên độ và cả hai bóng ≥ 20% biên độ (trung lập, không có hướng).
- **Búa (hammer)** sau xu hướng giảm / **Người treo cổ (hanging man)** sau xu hướng tăng: bóng dưới ≥ 2·thân và ≥ 60% biên độ; bóng trên ≤ 10% biên độ.
- **Búa ngược (inverted hammer)** sau xu hướng giảm / **Sao băng (shooting star)** sau xu hướng tăng: bóng trên ≥ 2·thân và ≥ 60% biên độ; bóng dưới ≤ 10% biên độ.
- **Nhấn chìm (engulfing):** nến thứ hai ngược màu và thân thứ hai bao trọn thân nến thứ nhất (`O₂ ≤ C₁`, `C₂ ≥ O₁` cho nhấn chìm tăng), thân thứ hai lớn hơn thân thứ nhất và ≥ 0,5·ATR.
- **Harami:** nến thứ nhất thân dài ngược chiều xu hướng; nến thứ hai thân ≤ 50% thân thứ nhất và nằm trọn trong thân thứ nhất.
- **Xuyên thấu (piercing line) / Mây đen che phủ (dark cloud cover):** nến thứ nhất thân dài; nến thứ hai mở cửa vượt ra ngoài đóng cửa nến thứ nhất theo hướng xu hướng (nới lỏng so với "gap" của Nison vì dữ liệu cổ phiếu VN có phiên ATO) và đóng cửa vượt quá điểm giữa thân nến thứ nhất nhưng chưa vượt mở cửa của nó.
- **Sao mai (morning star) / Sao hôm (evening star):** nến thứ nhất thân dài theo xu hướng; nến thứ hai thân ≤ 30% thân nến thứ nhất, thân nằm hẳn dưới (sao mai) hoặc trên (sao hôm) đóng cửa nến thứ nhất; nến thứ ba ngược màu, đóng cửa vượt điểm giữa thân nến thứ nhất, thân ≥ 0,5·ATR.
- **Xác nhận / thất bại** (chỉ dùng nến kế tiếp): mô hình tăng — *xác nhận* nếu nến kế tiếp đóng cửa cao hơn đóng cửa của nến mô hình; *thất bại* nếu nến kế tiếp đóng cửa dưới đáy mô hình (mức vô hiệu); còn lại "chưa xác nhận". Mô hình giảm đối xứng.
- Chưa triển khai: ba chú lính trắng/ba con quạ đen, các mô hình nến hiếm khác.

## 9. Phần B — Mô hình giá cổ điển (`pipeline/chart_patterns.py`)

Hình dạng theo Edwards & Magee và Murphy; cách đo mục tiêu theo chiều cao mô hình (measured move). Tất cả dựng từ swing đã xác nhận (k = 5) nên mô hình chỉ được biết ở nến `formed_at` (sau khi swing cuối được xác nhận). Mỗi mô hình có vòng đời với các **chỉ số nến** `formed_at` → `confirmed_at` | `invalidated_at` | `expired_at` | `superseded_at` → `target_hit_at` | `failed_at`. Chỉ sự kiện có chỉ số ≤ nến hiện tại mới được hiển thị.

| Mô hình | Điều kiện hình thành | Xác nhận | Mức vô hiệu / hết hạn | Mục tiêu đo |
|---|---|---|---|---|
| Hai đỉnh / Hai đáy | Hai swing cùng loại liên tiếp cách nhau 8–120 nến, giá lệch ≤ 1,0 ATR; độ sâu giữa hai đỉnh ≥ 2 ATR; có xu hướng trước (≥ 3 ATR trong 60 nến) | Đóng cửa phá đường cổ (đáy/đỉnh giữa) > 0,25 ATR | Đóng cửa vượt đỉnh (đáy) cực trị > 0,25 ATR trước khi xác nhận; hết hạn sau 60 nến chưa phá | Đường cổ ∓ chiều cao (đỉnh trung bình − đường cổ) |
| Vai-đầu-vai (và ngược) | Ba swing cùng loại liên tiếp; đầu vượt hai vai ≥ 1 ATR; hai vai lệch ≤ 1,5 ATR; hai đáy giữa thấp hơn vai thấp ≥ 1,5 ATR; tổng ≤ 150 nến; có xu hướng trước | Đóng cửa phá đường cổ (nối hai đáy giữa, có thể nghiêng) > 0,25 ATR | Đóng cửa vượt đầu > 0,25 ATR; hết hạn 60 nến | Đường cổ tại điểm phá ∓ (đầu − đường cổ tại đầu) |
| Tam giác tăng / giảm / cân | Hai đỉnh + hai đáy swing gần nhất trong 100 nến; biên "phẳng" nếu thay đổi ròng ≤ 0,75 ATR, "dốc" nếu ≥ 1,0 ATR; tăng = trên phẳng + dưới dốc lên; giảm = dưới phẳng + trên dốc xuống; cân = trên dốc xuống + dưới dốc lên; bề rộng đầu ≥ 3 ATR và bề rộng hiện tại ≤ 70% | Đóng cửa vượt biên > 0,25 ATR (hướng phá vỡ do giá quyết định, không mặc định) | Hai biên cắt nhau hoặc hết hạn sau 60 nến; bị thay bằng cấu hình swing mới (`superseded`) | Biên bị phá ± bề rộng đầu |

- Sau xác nhận: `target_hit_at` nếu giá chạm mục tiêu; `failed_at` nếu trong 10 nến đóng cửa quay lại phía cũ của đường cổ/biên (fakeout).
- **Kỳ vọng khối lượng:** nến phá vỡ có khối lượng ≥ 1,25× trung bình 20 nến → ghi `volume_confirmed = true` (quy ước; Edwards & Magee nhấn mạnh khối lượng nên tăng khi phá vỡ lên). Chỉ ghi nhận, không phải điều kiện bắt buộc.
- Chưa triển khai: kênh giá, cờ/cờ đuôi nheo (flag/pennant), đáy/đỉnh tròn, nêm (wedge). Breakout/fakeout của vùng hỗ trợ/kháng cự: mới có dạng fakeout của đường cổ/biên mô hình giá.
- **Hạn chế quan trọng:** nhận diện mô hình bằng quy tắc định lượng mang tính chủ quan (dung sai, cách chọn swing). Các ngưỡng ở đây là quy ước; xem `docs/backtest.md` cho thống kê hiệu quả trên dữ liệu của dự án.

## 10. Tài liệu tham khảo


- Murphy, J. J. (1999). *Technical Analysis of the Financial Markets* — xu hướng, hỗ trợ/kháng cự, đường xu hướng (các chương đầu).
- Edwards, R. D. & Magee, J. — *Technical Analysis of Stock Trends* — đường xu hướng, hỗ trợ/kháng cự, mô hình giá đảo chiều và tiếp diễn.
- Nison, S. — *Japanese Candlestick Charting Techniques* — mô tả và bối cảnh của mô hình nến.
- Bulkowski, T. — *Encyclopedia of Chart Patterns* — thống kê hiệu quả mô hình giá (dự án KHÔNG dùng số liệu của sách; tự đo trong `docs/backtest.md`).
- *(Chưa đối chiếu số trang/phiên bản cụ thể; sẽ bổ sung khi các khái niệm này được trích dẫn trong báo cáo.)*
