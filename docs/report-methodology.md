# Phương pháp bản tin hằng ngày

> Giai đoạn 4 (2026-11-10). Mã: `pipeline/fetch_news.py`, `pipeline/factcheck.py`, `pipeline/build_report.py`; test: `pipeline/tests/test_factcheck.py`, `test_build_report.py`.

## 1. Quy trình

1. **Thu thập** — `python -m pipeline.fetch_news`: đọc RSS đã duyệt (`config/sources.json` → `news_sources.rss`), khử trùng lặp, gán nhãn sơ bộ theo từ khóa (`config/news_keywords.json`) vào `data/news/raw/<ngày>.json`. Chỉ lưu tiêu đề, link, giờ đăng, mô tả ngắn (≤ 240 ký tự). Văn bản bài báo đầy đủ chỉ được tải về `data/news/cache/` (không đưa vào repo) để người viết đọc và để kiểm chứng trích dẫn.
2. **Chọn tin & đọc bài gốc** — người viết (agent/người) chỉ dùng tin có **liên hệ nhân quả hợp lý** tới ít nhất một mã trong watchlist hoặc tới bối cảnh vĩ mô/vàng; phải mở và đọc bài gốc, không viết từ tiêu đề RSS.
3. **Viết bản tin** `reports/YYYY-MM-DD.md` (~2.000 từ; kiểm tra 1.800–2.200) kèm `…claims.json` (nguồn + câu trích nguyên văn) và `…outlook.json` (lập trường tin tức theo mã/khung).
4. **Kiểm chứng tự động + xuất bản** — `python -m pipeline.build_report YYYY-MM-DD`: chạy `factcheck`; chỉ khi đạt mới tạo `site/data/reports/…json`. Sau đó `python -m pipeline.journal issue-combined --report YYYY-MM-DD` phát hành nhận định kết hợp vào sổ nhật ký.
5. **Rà ngữ nghĩa độc lập** — xem §4.

## 2. Ba tầng nội dung (mỗi đoạn bắt buộc gắn một nhãn)

| Nhãn | Ý nghĩa | Quy tắc kiểm chứng tự động |
|---|---|---|
| `{fact}` Sự kiện | Điều đã xảy ra, có nguồn | **Mỗi câu** có ≥ 1 trích dẫn `[[cN]]`; câu trích có nguyên văn trong trang nguồn; **mọi con số trong câu phải xuất hiện trong câu trích** |
| `{data}` Số liệu dự án | Giá, % thay đổi, khối lượng, SJC, độ chênh, kết quả backtest | **Không gõ tay số nào**: chỉ dùng ô thay thế `{{px:FPT}}`, `{{pct:VNINDEX}}`, `{{gold:prem_lo}}`, `{{bt:…}}`… do mã điền từ `site/data` và `data/` |
| `{def}` Định nghĩa | Giải thích thuật ngữ cho người mới | Phải trích dẫn nguồn loại *definition* (Wikipedia hoặc nguồn chính thức) và câu trích có thật |
| `{infer}` Suy luận | Kênh tác động, cách hiểu | Số liệu chỉ từ trích dẫn/ô thay thế; cấm từ tuyệt đối |
| `{opinion}` Nhận định | Quan điểm của người viết | Như trên; không dùng "chắc chắn", "đảm bảo", "100%"… |
| `{note}` Ghi chú | Phương pháp, giới hạn, miễn trừ | Không chứa số liệu thị trường |

Các bước kiểm tra khác: tên miền nguồn nằm trong danh sách duyệt (`report_sources`); câu trích ≤ 40 từ; số từ; mọi ô thay thế giải được; outlook đủ mã × 2 khung và mỗi lập trường khác 0 có trích dẫn; cảnh báo nếu link tin không có trong dữ liệu RSS đã thu thập.

**Giới hạn của kiểm chứng tự động:** nó chứng minh "câu trích có thật trong trang gốc" và "số liệu trong câu không bịa", **không** chứng minh câu văn diễn giải đúng ý bài báo (ví dụ gán sai chủ thể). Đó là lý do cần bước §4.

## 3. Kết hợp nhận định kỹ thuật + tin tức

- **Nguồn A (kỹ thuật):** engine cố định (`docs/analysis.md`), tại nến ngày hoàn tất gần nhất; hướng ∈ {tăng, giảm, đi ngang} + mức tin cậy ∈ {thấp, trung bình, cao}.
- **Nguồn B (tin tức):** lập trường của người viết cho từng mã và từng khung: `+1` nghiêng tăng, `0` trung lập/trái chiều/không có tin riêng, `−1` nghiêng giảm — **kèm kênh tác động bằng lời và các trích dẫn đã kiểm chứng**; lập trường khác 0 mà không có trích dẫn bị từ chối. Không có tin riêng ⇒ `0` (không suy đoán).
- **Quy tắc kết hợp (cài trong `build_report.combine`, có test):**
  1. Cả hai trung lập → **đi ngang**, tin cậy thấp.
  2. Cùng hướng (khác 0) → hướng đó; tin cậy = min(tin cậy kỹ thuật, **trung bình**).
  3. Ngược hướng → **đi ngang**, tin cậy thấp, gắn nhãn "MÂU THUẪN" (mâu thuẫn được nêu rõ, không chọn một bên).
  4. Chỉ một nguồn nghiêng hướng → hướng đó, tin cậy **thấp**.
- Độ tin cậy kết hợp **không bao giờ vượt "trung bình"**: vì quy tắc kỹ thuật chưa vượt đường cơ sở (`docs/backtest.md`) và chưa có bằng chứng rằng đánh giá tin tức có giá trị dự báo.
- Với vàng: nhận định kỹ thuật dùng nến ngày hoàn tất gần nhất của GC=F (có thể cũ hơn ngày bản tin vài ngày); bảng nhận định luôn ghi ngày nến.
- **Kiểm chứng ngoài mẫu:** nhận định kết hợp được phát hành vào sổ nhật ký với `basis = "engine+news"` (id có hậu tố `_news`), chấm cùng quy tắc τ như nhận định thuần kỹ thuật; thống kê `by_basis` cho biết liệu thêm tin tức có cải thiện hay không. Chỉ có ý nghĩa khi đủ mẫu (n ≥ 30).

## 4. Rà ngữ nghĩa độc lập (người viết ≠ người kiểm)

- Sau khi `build_report` đạt, một **agent kiểm chứng riêng** (`.claude/agents/fact-checker.md`) hoặc người dùng đọc từng câu `{fact}`/`{def}` và đối chiếu với trang gốc: chủ thể, hướng (tăng/giảm), đơn vị, thời điểm, mức độ ("mạnh", "nhẹ") có đúng ý bài báo không. Agent này chỉ **báo lỗi**, không sửa nội dung.
- **Bản tin 2026-11-09 — đã rà độc lập (2026-11-10)** bằng một agent riêng (quy trình của `fact-checker`; người viết ≠ người kiểm), đọc 49/49 câu trích và 12 lập trường tin tức đối chiếu với 20 nguồn trong cache. Kết quả: **0 lỗi sai sự thật**, nhưng có 4 nhóm diễn đạt mạnh hơn nguồn và nhiều chỗ thiếu ngữ cảnh. Đã sửa trong bản tin:
  1. Vàng: bỏ cách dựng hai chuyên gia thành hai phe "bất đồng" (nguồn cho thấy kịch bản giảm của Blue Line là có điều kiện và chính ông cũng kỳ vọng đây có thể là đợt thanh lọc cuối).
  2. Lập trường −1 cho FPT/GAS/FUEVFVND/E1VFVN30 (phiên kế tiếp) dựa vào số liệu ETF *ước tính* (nguồn nói tác động có thể trải nhiều phiên) và áp lực bán đã diễn ra → kênh tác động nay ghi rõ là suy luận của người viết; ACBS được trích đủ hai vế (giải ngân thăm dò quanh 1.700–1.720; giảm tỷ trọng nếu mất 1.700).
  3. VCB: bỏ chữ "nhẹ" (nguồn nêu 18,4 tỷ đồng, ước tính); TCB: bỏ nhãn "quy mô nhỏ".
  4. Định nghĩa "ký quỹ" lệch ngữ cảnh (Wikipedia nói về collateral chung, bài nói về dư nợ margin) và "P/E" không xuất hiện trong thân bài → thay bằng "độ rộng thị trường" và "cổ phiếu thưởng" (có trong bài).
  Sửa thêm: hai số khối ngoại bán ròng (805,41 tỷ HOSE theo Vietstock; "gần 800 tỷ" theo VnExpress) nay nêu rõ nguồn; ghi "toàn thị trường" cho 354/304; ghi nguồn gốc cho số vĩ mô (KIS, VnDirect); điều kiện trong phát biểu của ông Trump; BSR: bổ sung việc đã vượt kế hoạch điều chỉnh và kế hoạch mới vẫn thấp hơn dự báo; Brent hiện xấp xỉ mức bình quân quý III của BSR; ghi tên báo gốc cho các bài CafeF đăng lại (Thanh Niên Việt, An ninh tiền tệ, Tiền phong). Để giữ khoảng 1.800–2.200 từ, bỏ các đoạn ít liên quan tới danh mục (kết quả bầu cử Mỹ, số quỹ ETF, tỷ giá trung tâm, so sánh chênh lệch SJC của báo chí).
  **Giới hạn của lượt rà:** đọc bản cache (không kiểm lại trang trực tuyến), không kiểm số liệu `{{...}}` do mã điền, Vietstock (s1) chỉ đọc phần liên quan.
- **Errata và tính bất biến:** các nhận định kết hợp đã phát hành vào sổ nhật ký trước lượt rà (FPT, TCB, VCB, GAS, BSR, vàng… theo `news.channel` cũ) được **giữ nguyên** (hướng, độ tin cậy, lời kênh tác động) và sẽ được chấm như đã phát hành; mô tả đã sửa chỉ xuất hiện trên trang bản tin, và bản tin có đoạn đính chính. Lập trường −1 của 4 mã nói trên được giữ vì đã phát hành, **không** vì được nguồn chứng minh; thống kê `by_basis` của sổ nhật ký sẽ cho biết thêm tin tức có giá trị hay không.

## 5. Định nghĩa thuật ngữ

- Mỗi bản tin có hộp "Kiến thức cho người mới" (2–4 thuật ngữ **xuất hiện trong bài hôm đó**), mỗi định nghĩa trích một câu nguyên văn từ nguồn mở có thể tải lại (hiện dùng Wikipedia; Investopedia chặn truy cập tự động nên không dùng được cho kiểm chứng). Lời giải thích tiếng Việt là diễn đạt lại của người viết, không phải bản dịch từng chữ.
- Wikipedia là nguồn tham khảo mở, **không** phải nguồn chính thức; thuật ngữ cần tính chuẩn mực pháp lý (biên độ, giờ phiên, thanh toán) phải dẫn văn bản của HOSE/UBCKNN (còn tồn đọng ở `docs/data-sources.md` §6).

## 6. Giới hạn đã biết

- Độ phủ nguồn: 8 feed RSS tin tức (CafeF ×2, VnExpress, Vietstock ×2, VnEconomy, Thanh Niên, Tuổi Trẻ, Báo Chính phủ); Báo Đầu tư tạm bỏ (RSS trả HTML). Chưa đọc trang gốc của NHNN, Cục Thống kê, HOSE, Fed (chỉ qua báo chí).
- Tin quốc tế dựa vào báo trong nước đăng lại (VnEconomy, CafeF…), chưa phải nguồn gốc (Reuters, Fed…).
- Lịch sự kiện trong nước (số liệu vĩ mô, giao dịch không hưởng quyền) chưa thu thập có hệ thống.
- Lập trường tin tức là phán đoán của người viết, có tính chủ quan dù đã được ràng buộc bằng trích dẫn và kênh tác động.
- Bản tin được viết thủ công (có hỗ trợ của AI) từ dữ liệu đã thu thập; việc tự động hóa trên cloud (Giai đoạn 5) cần quyết định cơ chế gọi LLM, cách quản lý khóa API và chi phí — **chưa chọn**.
