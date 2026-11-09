# CLAUDE.md — Stock Market Research (Vàng & Chứng khoán Việt Nam)

> File điều khiển trung tâm của dự án. Mọi phiên làm việc, skill và agent phải tuân theo file này.
> Khi có mâu thuẫn giữa file này và yêu cầu tạm thời, hỏi lại người dùng trước khi làm.

## 1. Mục tiêu & bối cảnh

Dự án **nghiên cứu thị trường cá nhân**, phục vụ hai mục đích:
1. Theo dõi, hiểu biến động giá hằng ngày của vàng và một watchlist cổ phiếu/ETF Việt Nam.
2. Rèn tư duy đọc biểu đồ giá (price action, chỉ báo, khối lượng, mô hình giá) một cách có phương pháp.

Người dùng là **người mới** về tài chính → mọi nội dung phải dễ hiểu, có giải thích thuật ngữ, nhưng **không được đơn giản hóa đến mức sai**.

Sản phẩm là **một trang web tĩnh (HTML/JS)**, giao diện học theo bảng giá công khai (SSI iBoard, TCBS): gọn, chuyên nghiệp, dễ theo dõi. Về sau có thể thêm chế độ **Cơ bản ↔ Chuyên sâu**.

Đây **không phải** tư vấn đầu tư và không giao dịch thật. Không kết nối tài khoản môi giới, không đặt lệnh.

## 2. Watchlist (nguồn sự thật duy nhất: `config/watchlist.json`)

| Mã | Loại | Ghi chú |
|---|---|---|
| XAU/USD | Vàng thế giới | Biểu đồ tạm dùng GC=F (futures COMEX), **không phải spot** — xem mục 9 |
| SJC | Vàng miếng trong nước (thông tin phụ) | Giá mua/bán + độ chênh (premium) so với giá thế giới quy đổi. Chuỗi lịch sử tự tích lũy từ 2026-11-09 |
| FPT | Cổ phiếu – Công nghệ | |
| CMG | Cổ phiếu – Công nghệ | |
| VCB | Cổ phiếu – Ngân hàng | |
| TCB | Cổ phiếu – Ngân hàng | |
| GAS | Cổ phiếu – Dầu khí (khí) | |
| BSR | Cổ phiếu – Lọc hóa dầu | HOSE, niêm yết 2025-01-17 (VNDirect finfo, 2026-11-09); lịch sử trước ngày này cần kiểm tra |
| FUEVFVND | ETF (Diamond ETF) | Theo dõi chỉ số VN Diamond |
| E1VFVN30 | ETF (VN30) | Theo dõi chỉ số VN30 |

- Chỉ phân tích các mã trong watchlist. Thêm/bớt mã = sửa `config/watchlist.json`, không hard-code trong code.
- Tin tức chỉ được dùng nếu **có liên hệ nhân quả hợp lý** tới ít nhất một mã trong watchlist; nêu rõ kênh tác động (ví dụ: lãi suất → NIM ngân hàng → VCB/TCB).
- Chỉ số thị trường chung (VN-Index, VN30) và bối cảnh vĩ mô được dùng làm **ngữ cảnh**, không phải mã phân tích.

## 3. NGUYÊN TẮC BẮT BUỘC: không bịa, không phỏng đoán vô căn cứ

Đây là ràng buộc quan trọng nhất của dự án.

1. **Mọi số liệu** (giá, khối lượng, %, chỉ số vĩ mô, lãi suất, KQKD…) phải đến từ nguồn có thể truy vết. Lưu kèm: `source`, `url`, `fetched_at` (giờ Việt Nam, ISO 8601).
2. **Không có dữ liệu → ghi "Không có dữ liệu"**. Tuyệt đối không nội suy, không "ước chừng", không lấy số từ trí nhớ của model.
3. **Mọi sự kiện/tin tức** phải có nguồn (tên báo/cơ quan + link + ngày đăng). Ưu tiên nguồn gốc (NHNN, Tổng cục Thống kê, HOSE/HNX, công bố thông tin của doanh nghiệp, Bộ Công Thương, World Gold Council) hơn nguồn thứ cấp. Tin chỉ có một nguồn thứ cấp, chưa kiểm chứng → gắn nhãn *"chưa xác nhận"*.
4. **Tách bạch 3 tầng trong mọi báo cáo**, có nhãn rõ ràng:
   - **Sự kiện** (đã xảy ra, có nguồn) → **Suy luận** (kênh tác động, có cơ sở lý thuyết) → **Nhận định** (quan điểm, có mức độ tin cậy).
5. **Nhận định phải xác suất hóa, không tuyệt đối.** Dùng "nghiêng về tăng/giảm/đi ngang", kèm mức tin cậy (Thấp/Trung bình/Cao), **điều kiện vô hiệu hóa** (ví dụ: "nhận định sai nếu đóng cửa dưới 95.000"), và các luận điểm ngược chiều. Cấm các cụm như "chắc chắn", "đảm bảo", "100%".
6. **Mọi nhận định kỹ thuật phải dẫn chiếu giá trị chỉ báo cụ thể** đã tính được (ví dụ: "RSI(14)=68,2; giá trên EMA20 và EMA50; MACD histogram dương 3 phiên liên tiếp"). Không nhận định "cảm tính".
7. **Định nghĩa thuật ngữ** phải lấy từ nguồn uy tín (giáo trình, SSC/HOSE/NHNN, Investopedia, CFA Institute…) và ghi nguồn. Không tự chế định nghĩa. Khi định nghĩa có tranh cãi giữa các trường phái, nói rõ.
8. **Không đưa mục tiêu giá/khuyến nghị mua-bán** trừ khi suy ra được bằng phương pháp ghi rõ (ví dụ: đo mô hình theo chiều cao, Fibonacci từ swing xác định, ATR). Phải nêu phương pháp và giả định.
9. **Dữ liệu cũ phải hiển thị là cũ.** Nếu nguồn trễ (delayed) hoặc lỗi, UI phải hiện huy hiệu "Dữ liệu trễ X phút / lần cập nhật cuối", không giả làm real-time.
10. **"Mô phỏng real-time" ≠ giả dữ liệu.** Mô phỏng nghĩa là *phát lại (replay) hoặc cập nhật dần dữ liệu thật*. Cấm sinh giá ngẫu nhiên để làm đẹp biểu đồ. Nếu dùng dữ liệu mẫu để dev/test, đặt trong `data/fixtures/` và UI phải gắn watermark "DỮ LIỆU MẪU".
11. **Dữ liệu nhạy cảm theo thời gian** (luật giao dịch, giờ phiên, biên độ giá, chu kỳ thanh toán) có thể đã đổi — luôn xác minh từ nguồn chính thức hiện hành trước khi viết vào báo cáo/UI, ghi ngày xác minh.
12. Khi không chắc → **nói không chắc** và nêu cách kiểm chứng, đừng che giấu.
13. **Giá cổ phiếu/ETF từ nguồn là giá ĐÃ ĐIỀU CHỈNH** (xác minh 2026-11-09). Luôn ghi chú khi hiển thị giá quá khứ; trần/sàn/tham chiếu lấy từ finfo (giá thực tế). Khối lượng = khớp lệnh (không gồm thỏa thuận); khối lượng nến phút chỉ tham khảo. Chi tiết: `docs/data-quality.md`.
14. **Vàng thế giới trong dự án là GC=F (futures COMEX), không phải spot XAU/USD.** Mọi biểu đồ/nhận định vàng phải nêu rõ.

## 4. Chức năng 1 — Bản tin & nhận định thị trường

**Tần suất:** mỗi ngày giao dịch. Đề xuất 2 mốc:
- **Bản sáng (~08:00 giờ VN)**: tin qua đêm + tin trong nước, bối cảnh trước phiên.
- **Tổng kết chiều (sau ~15:00)**: diễn biến phiên, đối chiếu với nhận định buổi sáng, cập nhật nhận định cho phiên kế tiếp.

**Quy trình (pipeline):**
1. **Thu thập** tin từ nguồn đã duyệt (mục 8) → lưu thô vào `data/news/raw/YYYY-MM-DD.json` (tiêu đề, nguồn, link, thời điểm đăng, trích đoạn ngắn — không sao chép nguyên văn bài báo).
2. **Lọc & gán nhãn**: tin liên quan mã nào, kênh tác động, chiều tác động (tích cực/tiêu cực/trung tính), mức độ quan trọng.
3. **Kiểm chứng**: đối chiếu số liệu quan trọng với nguồn gốc; loại tin trùng, tin quảng cáo, tin đồn.
4. **Viết báo cáo** (~2000 từ, tiếng Việt, giọng văn tin tức/blog dễ đọc) theo cấu trúc dưới.
5. **Nhận định xu hướng** dựa trên báo cáo vừa viết (mục 4.2).
6. **Review** bởi agent kiểm chứng (mục 7) trước khi xuất bản.

**4.1 Cấu trúc báo cáo (`reports/YYYY-MM-DD.md` + JSON cho UI)**
1. Tóm tắt nhanh (5 gạch đầu dòng, đọc 30 giây).
2. Bức tranh vĩ mô trong nước (lãi suất, tỷ giá, lạm phát, chính sách, dòng vốn ngoại).
3. Vàng (XAU/USD và bối cảnh liên quan).
4. Chứng khoán theo nhóm: Ngân hàng (VCB, TCB) · Công nghệ (FPT, CMG) · Dầu khí (GAS, BSR) · ETF (FUEVFVND, E1VFVN30).
5. Lịch sự kiện sắp tới (công bố số liệu, họp, KQKD, ngày GDKHQ…) — chỉ liệt kê sự kiện có nguồn.
6. **Hộp "Kiến thức cho người mới"**: 2–4 thuật ngữ có xuất hiện trong bài hôm nay, định nghĩa ngắn + nguồn.
7. Nhận định xu hướng (4.2).
8. Nguồn tham khảo & miễn trừ trách nhiệm.

Độ dài mục tiêu 1.800–2.200 từ. Mỗi nhận xét nhân quả phải nêu kênh tác động; không viết câu rỗng kiểu "thị trường có thể biến động".

**4.2 Nhận định xu hướng sắp tới** — cho **từng mã** + thị trường chung:
- Hướng: Tăng / Giảm / Đi ngang · **Hai khung thời gian độc lập, người dùng chọn trên giao diện: "Phiên kế tiếp" và "1–2 tuần"** (định nghĩa đúng/sai và schema trong `docs/methodology.md`).
- Mức tin cậy + lý do chính (tối đa 3) + rủi ro ngược chiều (tối đa 2).
- Điều kiện vô hiệu hóa.
- Kết hợp **hai nguồn**: (a) bản tin cơ bản/vĩ mô hôm nay, (b) kết quả phân tích kỹ thuật mới nhất (chức năng 2). Nếu hai nguồn mâu thuẫn, nói rõ mâu thuẫn thay vì chọn một.

## 5. Chức năng 2 — Biểu đồ giá mô phỏng real-time & phân tích kỹ thuật

**Hiển thị (mỗi mã):**
- Biểu đồ nến (candlestick), chọn khung: 1m / 5m / 15m / 1h / 1D (tùy nguồn dữ liệu cung cấp được).
- Khối lượng giao dịch (cột volume + đường MA volume).
- Đường xu hướng và hỗ trợ/kháng cự **tính bằng thuật toán có tài liệu** (swing high/low theo fractal hoặc ZigZag với tham số ghi rõ), không vẽ tay tùy ý.
- Nhận diện mô hình giá dựa trên quy tắc định lượng (mục 5.2), hiển thị kèm mức độ tin cậy của nhận diện.
- Chỉ báo kỹ thuật (mục 5.1), bật/tắt được.
- Thanh thông tin kiểu bảng giá: giá, +/- , %, giá trần/sàn/tham chiếu (với cổ phiếu), KL, cao/thấp ngày, trạng thái dữ liệu (live/delayed/replay).

**Chế độ dữ liệu:**
- **Live/Delayed**: lấy dữ liệu thật theo nguồn có thể truy cập; hiển thị độ trễ thật.
- **Replay (mô phỏng real-time)**: phát lại nến phút của một phiên đã qua theo từng nến (tốc độ 1x/5x/20x, tạm dừng, tua), để người dùng **tập đọc biểu đồ và dự đoán trước khi nến kế tiếp hiện ra**, sau đó so sánh với phân tích của hệ thống. Đây là tính năng cốt lõi cho mục tiêu học tập.

**5.1 Chỉ báo kỹ thuật (bộ cơ bản; mỗi chỉ báo có công thức & tham số chuẩn ghi trong `docs/indicators.md`)**
- Xu hướng: SMA/EMA (9, 20, 50, 200), MACD (12,26,9), ADX(14)
- Động lượng: RSI(14), Stochastic (14,3,3)
- Biến động: Bollinger Bands (20,2), ATR(14)
- Khối lượng: Volume + MA(20), OBV; VWAP (nội phiên)
- Hỗ trợ/kháng cự: pivot point, swing high/low, Fibonacci retracement từ swing xác định

Chỉ báo tính ở **một nơi duy nhất** (module dùng chung, có unit test đối chiếu với giá trị tham chiếu từ thư viện đã kiểm chứng như TA-Lib / pandas-ta). UI và báo cáo dùng chung kết quả này để số liệu không bao giờ lệch nhau.

**5.2 Mô hình giá**
- Nến Nhật (theo Nison): doji, hammer/hanging man, shooting star, engulfing, morning/evening star, harami… — quy tắc định lượng (tỷ lệ thân/bóng) và **bối cảnh xu hướng trước đó** bắt buộc (hammer chỉ có nghĩa sau xu hướng giảm).
- Mô hình giá cổ điển (theo Edwards & Magee, Murphy): double top/bottom, head & shoulders, tam giác, cờ/cờ đuôi nheo, kênh giá, breakout/fakeout.
- Mỗi mô hình phải có: điều kiện xác nhận, mức vô hiệu hóa, và **kỳ vọng khối lượng** (ví dụ: breakout hợp lệ cần volume tăng). Không xác nhận đủ điều kiện → gắn nhãn "đang hình thành / chưa xác nhận", không báo như đã hoàn thành.

**5.3 Nhận định phiên hôm nay (khung phân tích bắt buộc, theo thứ tự top-down)**
1. **Bối cảnh khung lớn** (1D): xu hướng chính, vị trí so với MA50/MA200, vùng hỗ trợ/kháng cự lớn.
2. **Xu hướng & động lượng**: EMA, MACD, ADX, RSI (có phân kỳ hay không).
3. **Khối lượng**: xác nhận hay phân kỳ với giá; so với MA volume 20.
4. **Mô hình giá/nến** đang hiện diện.
5. **Kịch bản**: kịch bản chính (xác suất định tính) + kịch bản thay thế + mức vô hiệu hóa + vùng giá quan sát.
6. **Kết luận ngắn** một câu + mức tin cậy.

Nguyên tắc: đa số tín hiệu phải **đồng thuận (confluence)** mới nâng độ tin cậy; tín hiệu mâu thuẫn → kết luận "trung lập/chờ xác nhận". Phải nêu hạn chế (ví dụ: ít dữ liệu, thanh khoản thấp của ETF, phiên ATO/ATC).

**5.4 Sổ nhật ký dự đoán (rất nên có)**
- Mỗi nhận định lưu vào `data/predictions/` (mã, ngày, hướng, khung thời gian, mức tin cậy, mức vô hiệu hóa, lý do).
- Sau khi hết khung thời gian, tự đối chiếu với giá thật → ghi đúng/sai và bài học. Hiển thị thống kê tỷ lệ đúng (kèm số mẫu) trên UI. Đây là cách duy nhất để biết nhận định có thật sự có giá trị hay không, và để luyện tư duy.
- Không tô hồng: ghi cả dự đoán sai.

## 6. Kiến trúc kỹ thuật (đề xuất, chốt trước khi code)

```
Stock Market Research/
├── CLAUDE.md
├── config/
│   ├── watchlist.json        # danh sách mã, loại, sàn, nguồn dữ liệu
│   └── sources.json          # nguồn tin & nguồn giá được duyệt
├── data/
│   ├── prices/               # OHLCV theo mã & khung (JSON/CSV), có metadata nguồn
│   ├── news/raw|curated/
│   ├── predictions/
│   └── fixtures/             # dữ liệu mẫu cho test (luôn gắn nhãn)
├── reports/                  # báo cáo hằng ngày YYYY-MM-DD
├── pipeline/                 # Python: lấy dữ liệu, tính chỉ báo, nhận diện mô hình
│   ├── fetch_prices.py
│   ├── fetch_news.py
│   ├── indicators.py
│   ├── patterns.py
│   └── tests/
├── site/                     # web tĩnh: index.html, assets, JS
│   ├── index.html            # Tổng quan + bản tin
│   ├── chart.html            # Biểu đồ & replay
│   └── ...
├── docs/                     # indicators.md, patterns.md, glossary.md, methodology.md
└── .claude/
    ├── agents/
    └── skills/
```

- **Frontend:** HTML/CSS/JS thuần (hoặc framework nhẹ), **TradingView Lightweight Charts** (mã nguồn mở) cho nến/volume/đường chỉ báo. Không phụ thuộc server; đọc JSON tĩnh do pipeline sinh ra.
- **Pipeline:** Python. Chạy thủ công lúc đầu; sau đó tự động hóa theo lịch (GitHub Actions cron hoặc `/schedule`) và commit dữ liệu mới.
- **Deploy:** GitHub Pages / Cloudflare Pages / Netlify (tĩnh, miễn phí).
- **Nguồn giá (đã khảo sát ngày 2026-11-09, chi tiết trong `docs/data-sources.md`, cấu hình trong `config/sources.json`):**
  - Cổ phiếu/ETF/chỉ số VN: **VNDirect dchart** (chính; nến 1m ~1 năm, daily từ 2015; giá tính bằng *nghìn đồng*; khối lượng **chỉ khớp lệnh, không gồm thỏa thuận**), **VNDirect finfo** (tham chiếu/trần/sàn, metadata), **Yahoo `.VN`** (dự phòng EOD).
  - Vàng thế giới: **Yahoo `GC=F`** (lịch sử, là futures COMEX), snapshot spot từ gold-api.com/Swissquote. `XAUUSD=X` không còn khả dụng trên Yahoo.
  - SJC: **vnappmob** (bên thứ ba, khóa 15 ngày tự cấp, **không có lịch sử**); `sjc.com.vn` chặn bot bằng Cloudflare và dự án không vượt rào.
  - Tỷ giá USD/VND: XML Vietcombank (giới hạn 1 request/5 phút).
  - Tất cả đều là endpoint **không chính thức**, chưa xác minh ToS → chỉ dùng cho nghiên cứu cá nhân, không phân phối lại dữ liệu thô, luôn có cache và xử lý lỗi khi nguồn sập. Thư viện `vnstock` chưa được thử (Python máy hiện tại là 3.9.6); pipeline gọi HTTP trực tiếp để giảm phụ thuộc.
- **Múi giờ:** toàn bộ thời gian lưu ở ISO 8601 có offset; hiển thị giờ Việt Nam (UTC+7). XAU/USD giao dịch gần 24/5, cổ phiếu VN theo phiên (xác minh giờ phiên hiện hành từ HOSE/HNX).
- **Giao diện:** nền sáng/tối, bố cục bảng giá 3 vùng (watchlist trái · biểu đồ giữa · phân tích/tin phải), mật độ thông tin gọn, màu theo quy ước VN (tím = trần, xanh lơ = sàn, vàng = tham chiếu, xanh lá = tăng, đỏ = giảm). Responsive. Dùng skill `dataviz` + `artifact-design` khi dựng UI nếu xuất bản dạng Artifact.
- **Chế độ Cơ bản/Chuyên sâu (dự phòng cho tương lai):** thiết kế dữ liệu sẵn để bật thêm — Cơ bản: nến + MA + volume + tóm tắt "đang tăng/giảm" bằng ngôn ngữ đơn giản; Chuyên sâu: toàn bộ chỉ báo, mô hình, thông số. Không khóa cứng giao diện vào một mức.

## 7. Đề xuất Agent (đặt tại `.claude/agents/`)

| Agent | Vai trò | Quyền/Công cụ | Ghi chú |
|---|---|---|---|
| `news-collector` | Thu thập & lọc tin theo watchlist, gán nhãn kênh tác động | WebSearch, WebFetch, Read, Write | Chỉ ghi `data/news/`; không viết nhận định |
| `fact-checker` | **Kiểm chứng độc lập**: đối chiếu số liệu, link, ngày, định nghĩa; từ chối báo cáo nếu có câu không có nguồn | Read, WebFetch, WebSearch | **Chạy sau cùng, không sửa nội dung, chỉ báo lỗi**. Gác cổng chống bịa đặt |
| `market-analyst` | Viết báo cáo ~2000 từ + nhận định xu hướng cơ bản | Read, Write | Chỉ dùng dữ liệu đã được duyệt trong `data/` |
| `technical-analyst` | Phân tích kỹ thuật theo khung 5.3 từ dữ liệu đã tính | Read, Bash (chạy pipeline) | Mỗi kết luận dẫn số liệu chỉ báo |
| `data-engineer` | Viết/bảo trì pipeline lấy giá, tính chỉ báo, test | Read, Write, Edit, Bash | Bắt buộc có test đối chiếu |
| `frontend-builder` | Dựng giao diện web, biểu đồ, replay | Read, Write, Edit, Bash | Theo quy tắc UI ở mục 6 |

Nguyên tắc: **người viết ≠ người kiểm**. `fact-checker` luôn tách riêng khỏi `market-analyst` và `technical-analyst`.

## 8. Đề xuất Skill (đặt tại `.claude/skills/`)

| Skill | Mục đích |
|---|---|
| `/daily-report` | Chạy trọn quy trình: thu thập → lọc → viết → kiểm chứng → xuất bản báo cáo ngày |
| `/technical-review <mã>` | Chạy khung phân tích 5.3 cho một mã, ghi vào nhật ký dự đoán |
| `/update-data` | Cập nhật giá/khối lượng, tính lại chỉ báo, báo lỗi nguồn |
| `/fact-check <file>` | Kiểm chứng một báo cáo/đoạn nội dung, trả danh sách câu thiếu nguồn |
| `/score-predictions` | Đối chiếu dự đoán đã đến hạn với giá thực, cập nhật thống kê |
| `/glossary-add <thuật ngữ>` | Thêm định nghĩa vào `docs/glossary.md` kèm nguồn |

Nên tạo skill sau khi có phiên bản chạy tay đầu tiên ổn định, tránh đóng gói quy trình chưa được kiểm chứng.

**Nguồn tin được duyệt ban đầu (`config/sources.json`, người dùng có quyền thêm/bớt):**
- *Nguồn gốc:* NHNN (sbv.gov.vn), Tổng cục Thống kê (nso.gov.vn), HOSE, HNX, UBCKNN (ssc.gov.vn), Bộ Công Thương, Bộ Tài chính, trang IR/công bố thông tin của doanh nghiệp.
- *Báo chuyên ngành:* CafeF, Vietstock, VnEconomy, Báo Đầu tư, Thời báo Tài chính VN, VnExpress Kinh doanh, Tuổi Trẻ, Thanh Niên (mục kinh tế).
- *Vàng/quốc tế (làm bối cảnh):* World Gold Council, Fed, các nguồn tin tài chính quốc tế uy tín; giá vàng trong nước từ SJC/DOJI/PNJ nếu được thêm.

## 9. Quyết định đã chốt (2026-11-09) và việc còn mở

**Đã chốt:**
1. **Vàng:** thêm **giá SJC** (mua/bán) và độ chênh so với giá thế giới quy đổi làm thông tin phụ. XAU/USD vẫn là mã chính; bản tin vàng phải nêu cả yếu tố quốc tế (Fed, USD, lợi suất Mỹ) vì đây là yếu tố giải thích chính cho giá vàng.
2. **Khảo sát nguồn dữ liệu bằng thử nghiệm thật:** đã thực hiện (`docs/data-sources.md`).
3. **Mức "real-time":** chấp nhận phương án miễn phí = *replay phiên đã qua + cập nhật định kỳ/sau phiên*. Tick-by-tick trực tiếp để phát triển sau (cần nguồn trả phí/broker API). UI không được giả danh real-time; luôn hiện trạng thái và độ trễ thật.
4. **Chạy tự động trên cloud:** pipeline dữ liệu bằng GitHub Actions theo lịch; phần viết bản tin (cần LLM) chọn cơ chế ở Giai đoạn 4 (`docs/methodology.md` §7).
5. **Khung dự báo:** cả hai — "phiên kế tiếp" và "1–2 tuần", người dùng chọn trên UI.

**Chốt thêm (2026-11-09, đầu Giai đoạn 1):**
6. **Giữ toàn bộ nguồn miễn phí.** Vàng thế giới dùng `GC=F` (futures) có gắn nhãn; không đăng ký Twelve Data.
7. **Ngưỡng chấm đúng/sai τ gắn với ATR(14)** (`0,25·ATR14/giá` cho phiên kế tiếp). Phần mở rộng `√h` cho khung 1–2 tuần là đề xuất của tôi, chưa được duyệt riêng (`docs/methodology.md` §3).

**Chốt thêm (2026-11-09, đầu Giai đoạn 2):**
8. Hệ số `√h` cho τ của khung 1–2 tuần: **đồng ý**.
9. Độ chênh SJC hiển thị theo **cả tỷ giá USD/VND mua và bán** (một khoảng).
10. Làm hết các giai đoạn rồi **deploy một lần** (không deploy giữa chừng; deploy là hành động công khai nên vẫn cần xác nhận trước khi thực hiện).

**Nguyên tắc rút ra từ Giai đoạn 3 (bắt buộc):**
11. **Mọi nhận định kỹ thuật đi kèm bằng chứng lịch sử** (backtest + sổ nhật ký) và câu "chưa vượt đường cơ sở" khi đúng như vậy. Không bao giờ trình bày nhận định như dự báo đáng tin khi số liệu chưa chứng minh.
12. **Engine đóng băng theo phiên bản.** Sửa quy tắc = nâng `ENGINE_VERSION` + ghi lý do; nhận định đã phát hành không bị sửa hay chấm lại theo luật mới. Không tinh chỉnh ngưỡng theo kết quả backtest (sẽ thành data-snooping).
13. Phát hành nhận định chỉ ngay sau khi nến tham chiếu hoàn tất (`journal.fresh_enough`): cổ phiếu sau 15:15 giờ VN; vàng GC=F ngay sau khi nến ngày kết thúc (~12:05 giờ VN, cần kiểm chứng giờ nến Yahoo khi tự động hóa). Hôm nay (2026-11-09) vàng bị bỏ qua vì đã có nến mới đang chạy.

**Quyết định 2026-11-10:** các hướng cải thiện kỹ thuật (ngoài engine v1.0) chuyển vào giai đoạn phát triển/mở rộng sau; hiện chỉ làm tiếp các giai đoạn còn lại rồi deploy một lần.

**Còn mở:**
- Cơ chế gọi LLM để tự động hóa việc viết bản tin trên cloud (Giai đoạn 5; **đã chọn 2026-11-10: dùng Claude Code routine**, người dùng tự tạo repo GitHub và đăng trang);
- Độ trễ trong phiên (script sẵn, chạy trong phiên 2026-11-10); quy chế HOSE từ văn bản gốc; điều khoản sử dụng các nguồn; chạy thử từ IP cloud; loại tỷ giá USD/VND dùng tính premium SJC; nguyên nhân chênh khối lượng ngày. Danh sách và trạng thái: `docs/data-sources.md` §6, `docs/data-quality.md` §10.

## 10. Lộ trình làm việc đề xuất

- **Giai đoạn 0 — Nền tảng: ✅ hoàn thành bản nháp (2026-11-09).** Đã có `config/watchlist.json`, `config/sources.json`, `docs/data-sources.md`, `docs/methodology.md`, `docs/indicators.md`, mã khảo sát tại `pipeline/probes/`. Chờ người dùng duyệt các mục "Còn mở" ở mục 9.
- **Giai đoạn 1 — Dữ liệu & chỉ báo: ✅ hoàn thành phần cốt lõi (2026-11-09).** Có: `pipeline/` (fetch_prices, fetch_snapshots, indicators, build_indicators, gold, verify), 43 test đạt (đối chiếu TA-Lib trên dữ liệu thật), dữ liệu 8 mã + 2 chỉ số + GC=F, `docs/data-quality.md`. Chưa làm: đo độ trễ trong phiên, workflow cloud, ToS. Chạy: `. .venv/bin/activate && python -m pipeline.fetch_prices && python -m pipeline.fetch_snapshots && python -m pipeline.export_site && python -m pytest pipeline/tests`.
- **Giai đoạn 2 — Biểu đồ: ✅ hoàn thành (2026-11-09), chạy cục bộ, chưa deploy.** Trang `site/index.html` (bố cục 3 vùng: bảng giá · biểu đồ · số liệu), nến + khối lượng + EMA/Bollinger/VWAP/Pivot/Fibonacci, RSI/MACD/Stoch/ADX, swing, xu hướng Dow, đường xu hướng và vùng S/R theo thuật toán có tài liệu (`docs/patterns.md`), thẻ SJC + độ chênh, chế độ Cơ bản/Chuyên sâu, sáng/tối, mobile, **replay** (phát lại phiên, đoán nến kế, chấm theo τ, thống kê lưu trên trình duyệt). Dữ liệu cho giao diện: `python -m pipeline.export_site` → `site/data/`. Xem thử: `python3 -m http.server 8765 -d site`. Kiểm thử giao diện: `tests/e2e/smoke.js` (Playwright). Chưa làm (để Giai đoạn 3): mô hình nến/giá, nhận định kỹ thuật tự động, so sánh lượt đoán với hệ thống.
- **Giai đoạn 3 — Phân tích kỹ thuật tự động: ✅ hoàn thành (2026-11-09), chạy cục bộ, chưa deploy.** Có: mô hình nến Nhật (`candle_patterns.py`), mô hình giá cổ điển (`chart_patterns.py`), engine top-down 4 nhóm phiếu cho 2 khung (`engine.py`, đóng băng v1.0), **backtest nhân quả** (`backtest.py` → `docs/backtest.md`), **sổ nhật ký dự đoán** (`journal.py`; 16 nhận định đầu tiên phát hành 2026-11-09, chấm từ phiên kế tiếp), giao diện hiển thị nhận định + bằng chứng lịch sử + sổ nhật ký + so sánh lượt đoán replay với hệ thống. Tài liệu: `docs/analysis.md`, `docs/patterns.md` (phần A/B), `docs/backtest.md`. **Kết quả backtest: các quy tắc chưa vượt đường cơ sở nào (đúng ~35% trên bài toán 3 lớp, ngang "động lượng ngây thơ" và ngang mức đoán độc lập; nội ngày gần như ngẫu nhiên). Giao diện phải luôn hiển thị điều này cạnh nhận định.** Chạy: `python -m pipeline.journal all && python -m pipeline.export_site`; backtest: `python -m pipeline.backtest --intraday`.
- **Giai đoạn 4 — Bản tin: ✅ hoàn thành (2026-11-10), chạy cục bộ, chưa deploy.** Có: `fetch_news.py` (8 RSS, lọc từ khóa, tải bài gốc để đọc/kiểm chứng), `factcheck.py` (gác cổng chống bịa: câu trích phải có nguyên văn trong trang gốc, số liệu trong câu phải có trong trích dẫn, số liệu thị trường chỉ qua ô thay thế do mã điền), `build_report.py` (kết hợp kỹ thuật + tin tức theo quy tắc cố định, xuất `site/data/reports/`), tab "Bản tin & nhận định" trên trang, bản tin đầu tiên 2026-11-09 (~2.160 từ, 49/49 câu trích khớp trang gốc), phát hành 16 nhận định kết hợp (`basis = engine+news`) vào sổ nhật ký, agent `fact-checker`, skill `/daily-report`. Tài liệu: `docs/report-methodology.md`. **Đã rà ngữ nghĩa độc lập (2026-11-10, agent riêng):** 0 lỗi sai sự thật, 4 nhóm diễn đạt mạnh hơn nguồn đã sửa, errata ghi trong `docs/report-methodology.md` §4 (nhận định đã phát hành giữ nguyên theo nguyên tắc bất biến).
- **Giai đoạn 5 — Hoàn thiện & deploy:** giao diện bảng giá, tự động hóa theo lịch, chế độ Cơ bản/Chuyên sâu.

Mỗi giai đoạn kết thúc bằng một bản chạy được, người dùng xem và duyệt trước khi sang giai đoạn tiếp.

## 11. Quy ước làm việc

- **Ngôn ngữ:** nội dung hiển thị và báo cáo bằng **tiếng Việt**; tên biến/file/code bằng tiếng Anh; giữ nguyên thuật ngữ quốc tế (RSI, MACD, breakout…) kèm giải thích tiếng Việt lần đầu.
- **Định dạng số:** theo quy ước Việt Nam khi hiển thị (1.234,56); lưu trữ dạng số chuẩn trong JSON. Giá cổ phiếu VN: đơn vị đồng (xác định rõ nếu nguồn trả về đơn vị nghìn đồng); XAU/USD: USD/oz.
- **Không hard-code** số liệu, mã, ngày vào HTML. Dữ liệu luôn đi qua JSON.
- **Test:** hàm tính chỉ báo và nhận diện mô hình phải có test; mọi thay đổi công thức phải cập nhật `docs/`.
- **Không thêm tính năng ngoài phạm vi** (giao dịch thật, đăng nhập, khuyến nghị mua bán) khi chưa được yêu cầu.
- **Báo cáo trung thực:** nếu nguồn lỗi, thiếu dữ liệu, test fail, hoặc bước nào bị bỏ qua → nói rõ trong báo cáo/commit/phản hồi, không im lặng bỏ qua.
- **Miễn trừ trách nhiệm** (hiển thị trên mọi trang): "Nội dung phục vụ nghiên cứu và học tập, không phải khuyến nghị đầu tư. Mọi quyết định đầu tư thuộc về người dùng."

## 12. Tài liệu tham khảo nền tảng (dùng để định nghĩa và kiểm chứng phương pháp)

- John J. Murphy — *Technical Analysis of the Financial Markets*
- Edwards & Magee — *Technical Analysis of Stock Trends*
- Steve Nison — *Japanese Candlestick Charting Techniques*
- J. Welles Wilder — *New Concepts in Technical Trading Systems* (RSI, ATR, ADX)
- Thomas Bulkowski — *Encyclopedia of Chart Patterns* (thống kê độ tin cậy của mô hình giá)
- CFA Institute — tài liệu Technical Analysis; Investopedia (định nghĩa tra cứu nhanh, có ghi nguồn)
- Quy chế giao dịch HOSE/HNX, quy định UBCKNN, văn bản NHNN (luật & quy định hiện hành của Việt Nam)

> Lưu ý khoa học: phân tích kỹ thuật là công cụ xác suất, không phải khoa học chính xác. Bulkowski và các nghiên cứu học thuật cho thấy nhiều mô hình chỉ có lợi thế thống kê nhỏ và phụ thuộc thị trường/giai đoạn. Do đó mọi nhận định trong dự án phải thể hiện đúng bản chất xác suất này (mục 3.5) và được kiểm chứng bằng nhật ký dự đoán (mục 5.4).
