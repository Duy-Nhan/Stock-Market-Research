# Báo cáo khảo sát nguồn dữ liệu (Giai đoạn 0)

- **Ngày khảo sát:** 2026-11-09 (thứ Hai), thực hiện lúc ~22:30–22:45 giờ VN, **sau khi thị trường đã đóng cửa**.
- **Cách làm:** gọi thật từng endpoint, kiểm tra số liệu chéo giữa các nguồn. Mã khảo sát lưu tại `pipeline/probes/probe_prices_2026-11-09.py` (chạy lại được, chỉ dùng thư viện chuẩn Python).
- **Giới hạn của đợt khảo sát (phải đọc):**
  1. Khảo sát lúc thị trường đóng cửa → **chưa đo được độ trễ trong phiên**. Cần đo lại vào phiên giao dịch kế tiếp (xem mục 6).
  2. **Chưa xác minh điều khoản sử dụng (ToS)** của bất kỳ nguồn nào. Tất cả endpoint dưới đây là **không chính thức/không có tài liệu công khai** (trừ vnappmob có tài liệu). Chỉ dùng cho nghiên cứu cá nhân; không phân phối lại dữ liệu thô.
  3. Python hệ thống trên máy là 3.9.6; chưa thử cài thư viện `vnstock` (yêu cầu phiên bản Python của nó chưa được kiểm tra). Pipeline giai đoạn 1 dự kiến gọi HTTP trực tiếp để giảm phụ thuộc.

## 1. Kết quả tổng hợp

| Nhu cầu | Nguồn chọn | Trạng thái | Ghi chú chính |
|---|---|---|---|
| OHLCV cổ phiếu/ETF/chỉ số VN | VNDirect dchart | **Đạt** | 10/10 mã trả dữ liệu; 1m ~1 năm; daily từ 2015 |
| Giá tham chiếu/trần/sàn, KL thỏa thuận, tên, sàn | VNDirect finfo | **Đạt** | Dùng host `api-finfo.vndirect.com.vn` |
| Dự phòng EOD cổ phiếu VN | Yahoo Finance (`.VN`) | **Đạt** | Giá đóng cửa khớp VNDirect 8/8 mã |
| Lịch sử vàng thế giới | Yahoo `GC=F` | **Đạt có điều kiện** | Là **hợp đồng tương lai COMEX, không phải spot** (mục 4) |
| Giá spot XAU/USD hiện tại | gold-api.com, Swissquote | Đạt | Chỉ giá hiện tại, không lịch sử |
| Lịch sử spot XAU/USD | Twelve Data (ứng viên) | **Chưa thử** | Cần người dùng đăng ký khóa miễn phí |
| Giá SJC | vnappmob | **Đạt có điều kiện** | Bên thứ ba; không có lịch sử → tự lưu hằng ngày (mục 5) |
| Tỷ giá USD/VND | Vietcombank XML | Đạt | Giới hạn 1 request/5 phút |
| Tin tức | RSS CafeF, VnExpress, Vietstock | **Đạt** | Báo Đầu tư cần kiểm tra lại |

## 2. VNDirect dchart (nguồn chính cho cổ phiếu VN)

`GET https://dchart-api.vndirect.com.vn/dchart/history?symbol=FPT&resolution=D&from=<unix>&to=<unix>`

Kết quả đo được:
- 10/10 mã (FPT, CMG, VCB, TCB, GAS, BSR, FUEVFVND, E1VFVN30, VNINDEX, VN30) trả `s: "ok"`.
- Độ sâu dữ liệu (đo trên FPT): daily từ 2015-11-27 (2.733 nến); 1m ≈ 1 năm (29.594 nến từ 2025-10-31); 5m 6.026 nến cùng giai đoạn; 60m từ 2024-05-31 (700 nến). Độ sâu thực tế có thể lớn hơn; các con số trên bị giới hạn bởi cửa sổ yêu cầu tôi đã dùng cho 1m/5m (400 ngày).
- Nến phút chạy từ **09:15 đến 14:45** (nến cuối 14:45 là phiên ATC). Phù hợp với cấu trúc phiên ATO 9:00–9:15 · liên tục · ATC 14:30–14:45 mà các nguồn thứ cấp đưa ra; **quy chế chính thức của HOSE vẫn cần xác minh** (mục 6).
- **Đơn vị giá: nghìn đồng** (FPT đóng cửa `51.0` = 51.000 đồng; khớp Yahoo `51000.0`). Pipeline bắt buộc chuẩn hóa. Chỉ số VN giữ nguyên điểm.
- **Khối lượng chỉ gồm khớp lệnh, không gồm thỏa thuận.** Bằng chứng: VCB ngày 2026-11-09, dchart `v = 2.985.600` trùng khớp tuyệt đối với `nmVolume` của finfo; finfo ghi thêm `ptVolume = 600.000` (thỏa thuận). Yahoo ghi 3.597.556, xấp xỉ nmVolume + ptVolume (3.585.600; chênh ~0,3%, chưa giải thích được phần chênh). Khi phân tích khối lượng phải nêu rõ "khối lượng khớp lệnh".
- Smoke test giới hạn tần suất: 20 request liên tiếp trong 3,0 giây đều thành công (chưa phải kiểm tra tải; chưa biết ngưỡng chặn).

**Rủi ro:** API không chính thức, có thể thay đổi/chặn mà không báo. Giảm thiểu: cache dữ liệu đã lấy vào `data/prices/`, chỉ gọi phần còn thiếu, có nguồn dự phòng EOD (Yahoo).

## 3. VNDirect finfo (metadata và snapshot phiên)

- `GET https://api-finfo.vndirect.com.vn/v4/stocks?q=code:FPT,...` → tên pháp lý, sàn (`floor`), ngày niêm yết, thuộc rổ VN30.
- `GET https://api-finfo.vndirect.com.vn/v4/stock_prices?q=code:VCB~date:2026-11-09` → `basicPrice` (tham chiếu), `ceilingPrice`, `floorPrice`, `nmVolume`, `ptVolume`, `nmValue`, `ptValue`...
  - Ví dụ VCB 2026-11-09: tham chiếu 53,6 · trần 57,3 · sàn 49,85 (nghìn đồng). Tỷ lệ trần/tham chiếu = 57,3/53,6 = 1,069 → phù hợp biên độ ±7% sau làm tròn theo bước giá; **chưa xác nhận biên độ từ quy chế chính thức**.
- Host `finfo-api.vndirect.com.vn` lỗi kết nối khi thử; `api-finfo.vndirect.com.vn` hoạt động.
- Phát hiện đã xác minh từ nguồn này: **cả 8 mã đều niêm yết HOSE**; BSR niêm yết từ 2025-01-17 và thuộc rổ VN30 (finfo). FUEVFVND, E1VFVN30 là chứng chỉ quỹ ETF (`type: ETF`).

## 4. Vàng thế giới — vấn đề XAU/USD spot vs GC=F

- Yahoo **không còn** cung cấp `XAUUSD=X` (HTTP 404, "symbol may be delisted").
- Yahoo `GC=F` hoạt động, có volume (1m ~7 ngày, 5m ~60 ngày, 1h ~730 ngày, 1d ≥10 năm), nhưng đây là **hợp đồng tương lai vàng COMEX (đang là hợp đồng Dec 2026)**, không phải giá spot. Cùng thời điểm khảo sát: GC=F ≈ 4.126,7 USD/oz; spot từ gold-api.com ≈ 4.120,9 và Swissquote bid/ask ≈ 4.119,9/4.120,5. Chênh lệch ~6 USD là một ví dụ về basis (chênh futures–spot), thay đổi theo thời gian và còn có **bước nhảy khi chuyển hợp đồng (roll)** trong chuỗi liên tục — cách Yahoo ghép chuỗi chưa được xác minh.
- Chênh lệch giữa hai lần đọc không cùng giây nên con số trên chỉ minh họa, không dùng làm số liệu basis.

**Phương án đề xuất (cần người dùng chốt):**
- **A (mặc định, không cần đăng ký):** biểu đồ vàng dùng `GC=F`, **gắn nhãn rõ "Vàng COMEX (GC=F) – hợp đồng tương lai"**, đồng thời tự lưu ảnh chụp giá spot từ gold-api/Swissquote mỗi lần chạy để dần có chuỗi spot riêng và theo dõi basis.
- **B (chính xác hơn):** đăng ký khóa miễn phí Twelve Data (8 credit/phút, 800 credit/ngày theo trang hỗ trợ của họ) để lấy lịch sử XAU/USD spot; lưu khóa trong GitHub Secrets. Chi phí credit của `time_series` cho XAU/USD cần xác minh trước.

## 5. SJC và tỷ giá

- `sjc.com.vn` bảo vệ bằng Cloudflare ("Just a moment…") → **không truy cập tự động được; dự án không vượt rào.**
- **vnappmob** (bên thứ ba, có tài liệu): `GET /api/v2/gold/sjc` với khóa Bearer lấy từ `/api/request_api_key?scope=gold`.
  - Khóa cấp tự động; JWT có hạn **15 ngày** (giải mã: exp − iat = 1.296.000 s) → pipeline xin khóa mới mỗi lần chạy.
  - Mẫu phản hồi (mốc 2026-11-09 ~15:00 giờ VN, field `datetime` = 1794211207): `buy_1l = 138.200.000`, `sell_1l = 141.200.000` đồng/lượng.
  - **Không có lịch sử:** gọi với `?date=2026-11-06` vẫn trả đúng bản ghi mới nhất. Do đó chuỗi giá SJC phải được **tự tích lũy bằng ảnh chụp hằng ngày từ hôm nay**; không thể backfill nếu không có nguồn khác. Cần thông báo rõ trên UI ("dữ liệu SJC bắt đầu từ 2026-11-09").
  - Độ tin cậy của dữ liệu so với bảng giá niêm yết chính thức của SJC **chưa được đối chiếu**; cần đối chiếu thủ công với trang SJC vài ngày đầu.
- **Premium (độ chênh trong nước − thế giới)**, công thức dự kiến:
  `premium = SJC_bán / (XAUUSD × USDVND × 37,5 / 31,1034768) − 1`
  trong đó 1 lượng = 37,5 g (đơn vị vàng miếng Việt Nam) và 1 troy ounce = 31,1034768 g (định nghĩa chuẩn). Tỷ giá USD/VND lấy từ XML Vietcombank (ghi rõ dùng giá bán/chuyển khoản/mua). Giá XAUUSD dùng là spot nếu có, nếu không thì ghi rõ GC=F và chấp nhận sai số basis. Hai hằng số quy đổi cần đối chiếu với nguồn chính thức khi viết `docs/methodology.md` cuối cùng.

## 6. Việc phải làm / xác minh tiếp (đưa vào Giai đoạn 1)

**Tiến độ cuối Giai đoạn 1 (2026-11-09):**

| # | Việc | Trạng thái |
|---|---|---|
| 1 | Đo độ trễ trong phiên | **Chưa** — cần phiên giao dịch; script sẵn `pipeline/probes/latency_probe.py` (chạy 2026-11-10) |
| 2 | Quy chế HOSE từ nguồn chính thức | **Một phần** — chưa lấy được văn bản HOSE/UBCKNN; trang SSI (thứ cấp) ghi ATO 9:00–9:15, liên tục 9:15–11:30 và 13:00–14:30, ATC 14:30–14:45, biên độ ±7% (cổ phiếu, CCQ ETF), bước giá 10/50/100 đồng (cổ phiếu) và 10 đồng (ETF), T+2; **không ghi ngày hiệu lực**. Khớp với dữ liệu: nến phút chỉ có ở 09:15–11:29, 13:00–14:29, 14:45; trần/sàn VCB 57,3/49,85 khớp ±7% làm tròn theo bước giá. Vẫn cần văn bản gốc |
| 3 | Lịch nghỉ lễ | **Xong** — suy từ dữ liệu, không hard-code (`docs/data-quality.md` §7) |
| 4 | Giá điều chỉnh | **Xong** — dchart là giá điều chỉnh (`docs/data-quality.md` §1) |
| 5 | Chuỗi liên tục GC=F | **Không kết luận được** (`docs/data-quality.md` §6) |
| 6 | Đối chiếu SJC | **Một phần** — khớp với một trang tổng hợp bên thứ ba; chưa có nguồn chính thức |
| 7 | Điều khoản sử dụng (ToS) | **Chưa** |
| 8 | Chạy từ IP cloud | **Chưa** — cần repo/GitHub Actions |
| 9 | RSS Báo Đầu tư | **Chưa** (để Giai đoạn 4) |

Danh sách gốc (giữ để đối chiếu):

1. **Đo độ trễ trong phiên** (thứ Ba 2026-11-10, 09:15–14:45): gọi dchart nến 1m mỗi phút, so thời gian nến cuối với giờ thực, đo độ trễ và tính đầy đủ của nến.
2. **Xác minh quy chế hiện hành từ nguồn chính thức** (HOSE/UBCKNN): giờ phiên, biên độ ±7% đối với cổ phiếu/chứng chỉ quỹ, bước giá, chu kỳ thanh toán. Hiện chỉ có các nguồn thứ cấp (blog/sàn môi giới), và các nguồn này **không thống nhất** về giờ khớp lệnh liên tục buổi chiều.
3. **Lịch nghỉ lễ:** không hard-code; suy ra ngày giao dịch từ việc có/không có nến trong dữ liệu, đối chiếu thông báo HOSE.
4. **Điều chỉnh giá (cổ tức, tách cổ phiếu):** chưa kiểm tra dchart trả giá chưa điều chỉnh hay đã điều chỉnh. finfo có trường `adClose`, `adOpen`... gợi ý có cả giá điều chỉnh; cần kiểm tra trước khi tính chỉ báo dài hạn (MA200).
5. **Chuỗi liên tục GC=F:** kiểm tra khoảng nhảy khi roll hợp đồng trong dữ liệu daily.
6. **Đối chiếu SJC** với bảng giá chính thức trong vài ngày.
7. **Đọc điều khoản sử dụng** của VNDirect, Yahoo, vnappmob, gold-api.com và quyết định phạm vi dùng (cá nhân/nghiên cứu).
8. **Chạy từ môi trường cloud:** IP của GitHub Actions có thể bị chặn bởi một số nguồn; phải thử chạy thật trong workflow trước khi coi là đạt.
9. **Báo Đầu tư RSS:** kiểm tra cấu trúc feed.

## 7. Tin tức (RSS)

Đã đọc được tiêu đề và thời gian đăng:

| Feed | Số item | Mục mới nhất lúc khảo sát |
|---|---|---|
| CafeF – Thị trường chứng khoán | 50 | 2026-11-09 22:18 |
| VnExpress – Kinh doanh | 60 | 2026-11-09 19:46 |
| Vietstock – Cổ phiếu | 20 | 2026-11-09 20:30 |
| Báo Đầu tư – Tài chính chứng khoán | (chưa phân tích được) | — |

RSS chỉ cho tiêu đề/mô tả ngắn. Với tin quan trọng, agent phải mở bài gốc để đọc đầy đủ trước khi kết luận. Việc đọc tin từ trang nguồn gốc (NHNN, Cục Thống kê, HOSE...) cần kiểm tra từng trang ở Giai đoạn 4.
