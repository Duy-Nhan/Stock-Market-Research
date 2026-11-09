# Phương pháp luận

> Bản nháp Giai đoạn 0. Cụ thể hóa các nguyên tắc ở CLAUDE.md mục 3–5. Khi mâu thuẫn, CLAUDE.md thắng.

## 1. Hai khung thời gian dự báo (người dùng chọn trên giao diện)

| Tùy chọn | Mô tả | Dữ liệu chính | Điều kiện đánh giá đúng/sai |
|---|---|---|---|
| **Phiên kế tiếp** | Hướng giá đóng cửa phiên giao dịch kế tiếp so với giá đóng cửa hôm nay | Nến 1D + nội ngày gần nhất, tin hôm nay | So giá đóng cửa phiên kế tiếp với ngưỡng đã ghi (xem §3) |
| **1–2 tuần** | Xu hướng chủ đạo trong 5–10 phiên giao dịch kế tiếp | Nến 1D (và tuần nếu đủ dữ liệu), tin vĩ mô/doanh nghiệp | So giá đóng cửa sau 5 và sau 10 phiên với ngưỡng đã ghi |

Với XAU/USD và GC=F giao dịch gần như liên tục, "phiên" được định nghĩa bằng nến 1D theo lịch của nguồn dữ liệu; cần ghi rõ quy ước múi giờ cắt ngày.

Mỗi nhận định có `horizon: "next_session" | "1_2_weeks"`; hai nhận định độc lập, có thể khác chiều (ví dụ ngắn hạn giảm trong xu hướng tăng).

## 2. Cấu trúc một nhận định (schema)

```json
{
  "id": "2026-11-10_FPT_next_session",
  "symbol": "FPT",
  "issued_at": "2026-11-09T15:30:00+07:00",
  "horizon": "next_session",
  "direction": "up | down | sideways",
  "confidence": "low | medium | high",
  "reference_close": 51000,
  "tau": 0.0084,
  "invalidation": "đóng cửa dưới 50.000",
  "evidence": [{"indicator": "RSI14", "value": 52.1, "reading": "..."}],
  "counter_arguments": ["..."],
  "data_as_of": "2026-11-09T14:45:00+07:00",
  "sources": ["..."]
}
```

Quy tắc: `evidence` chỉ chứa giá trị đã tính bởi pipeline; không có trường trống bị bỏ qua mà không giải thích.

## 3. Định nghĩa đúng/sai (để nhật ký dự đoán đánh giá được)

Phải cố định **trước khi** đưa ra nhận định, không điều chỉnh sau:
- `up`: giá đóng cửa tại thời điểm kết thúc horizon > `reference_close × (1 + τ)`.
- `down`: < `reference_close × (1 − τ)`.
- `sideways`: nằm trong ±τ.
- **Ngưỡng τ (người dùng đồng ý nguyên tắc ngày 2026-11-09):** τ gắn với biến động riêng của từng mã bằng ATR(14) tại thời điểm phát hành nhận định:
  - Phiên kế tiếp (h = 1): `τ = 0,25 · ATR14 / reference_close`.
  - **Cập nhật 2026-11-09:** người dùng đã đồng ý hệ số `√h` bên dưới.
  - 1–2 tuần (h = 5 và h = 10 phiên): `τ_h = 0,25 · ATR14 · √h / reference_close`. **Phần √h** (giả định phương sai biến động tăng xấp xỉ tuyến tính theo thời gian, như mô hình bước ngẫu nhiên) là đề xuất của người phân tích và **đã được người dùng đồng ý** (2026-11-09); đây vẫn là một xấp xỉ, thực tế biến động có thể tự tương quan.
  - Hệ số 0,25 là lựa chọn quy ước, không có "giá trị đúng" tuyệt đối; τ được **ghi vào bản ghi nhận định ngay khi phát hành** (trường `tau`), không tính lại sau này.
  - Với XAU/USD (GC=F) dùng cùng công thức trên nến ngày của GC=F.
- Đánh giá thống kê: báo cáo kèm **số mẫu**; với số mẫu nhỏ (ví dụ < 30 nhận định mỗi nhóm) tỷ lệ đúng không có ý nghĩa thống kê và UI phải nói rõ. So sánh với đường cơ sở (ví dụ luôn dự đoán "tăng" hoặc "đi ngang") để biết nhận định có giá trị gia tăng hay không.

## 4. Khung phân tích kỹ thuật top-down

Theo CLAUDE.md mục 5.3. Khác biệt theo horizon:
- **Phiên kế tiếp:** trọng tâm là cấu trúc nến gần nhất, vị trí trong dải Bollinger, vùng hỗ trợ/kháng cự gần, khối lượng so với MA20, động lượng ngắn (RSI, Stochastic), mức trần/sàn (cổ phiếu VN).
- **1–2 tuần:** trọng tâm là xu hướng 1D/tuần, EMA20/50, MACD, ADX, mô hình giá lớn, mốc sự kiện sắp tới (KQKD, họp chính sách) có nguồn.

Quy tắc đồng thuận (confluence): `high` chỉ khi ≥ 3 nhóm độc lập (xu hướng, động lượng, khối lượng, cấu trúc giá) cùng chiều **và** không có tín hiệu ngược chiều đáng kể; mâu thuẫn → `low` hoặc "trung lập". Các nhóm cùng đo một thứ (ví dụ RSI và Stochastic) tính là một nhóm.

## 5. Kết hợp tin tức và kỹ thuật

- Tin tức/vĩ mô quyết định **bối cảnh và rủi ro sự kiện**; kỹ thuật cho **vị trí và mức giá**.
- Khi hai bên mâu thuẫn: trình bày cả hai, hạ độ tin cậy, không "chọn" một bên để câu chuyện trơn tru.
- Mọi liên hệ nhân quả tin → giá phải nêu kênh (ví dụ: giá dầu → biên lợi nhuận lọc dầu → BSR), có cơ sở lý thuyết/dữ liệu; nếu chỉ là tương quan quan sát được thì ghi rõ là tương quan.

## 6. Replay (mô phỏng real-time)

- Phát lại nến 1m/5m của một phiên đã qua từ dữ liệu thật.
- **Không rò rỉ tương lai:** tại thời điểm replay t, UI và phân tích chỉ được dùng nến ≤ t, mọi swing/mô hình chỉ hiện sau khi đã xác nhận (xem `docs/indicators.md` §5–6).
- Chế độ "đoán trước": người dùng ghi dự đoán hướng nến/khung kế tiếp, hệ thống chấm sau khi nến hiện ra và so với phân tích của hệ thống tại cùng thời điểm.

## 7. Tự động hóa trên cloud (quyết định ngày 2026-11-09: chạy tự động trên cloud)

Tách thành hai phần, vì bản chất khác nhau:

1. **Pipeline dữ liệu & chỉ báo (xác định, không cần LLM):** GitHub Actions theo lịch.
   - Giờ phiên VN (UTC+7) ≈ 02:00–07:45 UTC; cron của GitHub chạy theo UTC. Đề xuất chạy sau đóng cửa khoảng 15:15 VN (≈ 08:15 UTC), thứ Hai–thứ Sáu. Lịch của GitHub có thể bị trễ vài phút đến lâu hơn lúc tải cao; workflow phải idempotent (chạy lại không làm hỏng dữ liệu).
   - Chạy ngày nghỉ lễ: pipeline phải nhận biết không có phiên (không có nến mới) và không tạo dữ liệu giả.
   - Lưu ý GitHub (cần xác minh khi cấu hình): workflow theo lịch trong repo không hoạt động trong thời gian dài có thể bị tự tắt; commit dữ liệu hằng ngày thường giữ repo hoạt động.
   - Xác nhận thật sự bằng một lần chạy workflow trước khi coi là đạt (IP cloud có thể bị chặn bởi nguồn; xem `docs/data-sources.md` §6.8).
2. **Viết bản tin & nhận định (cần LLM):** chạy bằng Claude Code routine (skill `/schedule`) hoặc workflow gọi Claude API — **chưa chọn**, quyết định ở Giai đoạn 4 (cần biết chi phí, nơi lưu khóa, cách đọc dữ liệu từ repo). Trước khi bật tự động, bản chạy tay phải qua `fact-checker` ít nhất vài lần.

## 7a. Độ chênh vàng SJC (quyết định 2026-11-09)

Tỷ giá USD/VND dùng **cả hai loại: mua và bán** của Vietcombank; giao diện hiển thị **khoảng** (hai số) thay vì một số duy nhất. Độ chênh tính theo giá SJC **bán ra** (giá người mua vàng phải trả) so với giá vàng thế giới spot quy đổi. Luôn hiển thị thời điểm của từng đầu vào; cảnh báo khi giá SJC và giá thế giới lệch thời điểm > 30 phút (ví dụ ngoài giờ giao dịch).

## 7b. Giá điều chỉnh (xác minh ở Giai đoạn 1 — xem `docs/data-quality.md` §1)

- Nguồn giá cổ phiếu/ETF (VNDirect dchart) trả giá **đã điều chỉnh** theo sự kiện doanh nghiệp và **tính lại toàn bộ lịch sử** khi có sự kiện mới.
- Quyết định: mọi chỉ báo, mô hình giá và biểu đồ dùng **một chuỗi điều chỉnh nhất quán** (tránh bước nhảy giả do sự kiện doanh nghiệp làm méo chỉ báo như MA, RSI, ATR).
- Hệ quả bắt buộc: (1) giá quá khứ hiển thị có thể khác giá đã giao dịch; ghi chú "giá đã điều chỉnh" trên UI; (2) mức trần/sàn/tham chiếu của một ngày lấy từ finfo (giá thực tế), chỉ vẽ cho ngày không bị điều chỉnh; (3) `reference_close` của nhận định là giá đóng cửa thực tế tại thời điểm phát hành, còn đánh giá đúng/sai phải so với **giá đã điều chỉnh tới cùng thời điểm quan sát** để không bị lệch nếu có sự kiện doanh nghiệp xảy ra giữa chừng — chi tiết cách xử lý ở Giai đoạn 3 (ngày giao dịch không hưởng quyền trong khung dự báo cần được gắn cờ/loại khỏi thống kê).
- Nhật ký dự đoán: lưu cả `reference_close` thực tế lẫn hệ số điều chỉnh tại thời điểm phát hành.

## 8. Các giả định và giới hạn đã biết (cập nhật dần)

- Phân tích kỹ thuật là công cụ xác suất; độ tin cậy thống kê của nhiều mô hình giá hạn chế (Bulkowski cung cấp thống kê cho mô hình giá; cần dẫn số liệu cụ thể từ nguồn khi dùng trong báo cáo, không dùng con số nhớ từ trí nhớ).
- Dữ liệu miễn phí có thể trễ, thiếu, hoặc đổi cấu trúc; mọi báo cáo ghi `data_as_of`.
- **Quyết định 2026-11-09: giữ toàn bộ nguồn miễn phí.** XAU/USD dùng GC=F (futures COMEX) cho biểu đồ và nhận định; không dùng Twelve Data. Mọi nhận định vàng phải nêu rõ đây là futures, không phải spot. Ảnh chụp spot (gold-api/Swissquote) được lưu song song để theo dõi basis.
- Khối lượng nến phút chỉ mang tính tham khảo (`docs/data-quality.md` §3); kết luận khối lượng dựa trên nến ngày.
- Giá SJC chỉ có từ ngày bắt đầu lưu snapshot (2026-11-09 trở đi nếu pipeline chạy ngay).
