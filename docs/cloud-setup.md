# Thiết lập chạy tự động trên cloud (Giai đoạn 5)

> Soạn 2026-11-10. **Chưa có gì được đẩy lên mạng.** Các bước ghi "Người dùng" cần bạn tự làm; không bước nào lưu khóa API.

## 1. Kiến trúc

| Việc | Chạy ở đâu | Khi nào (giờ VN) | Cần LLM |
|---|---|---|---|
| Lấy giá/snapshot/tin, chỉ báo, phát hành + chấm nhận định kỹ thuật, test, commit dữ liệu | GitHub Actions `update-data.yml` | T2–T6 12:35 và 15:35 | Không |
| Dựng `site/data` từ dữ liệu + đăng GitHub Pages | GitHub Actions `deploy.yml` (gọi sau `update-data`, và khi có push vào `site/**`, `reports/**`) | ngay sau bước trên | Không |
| Viết bản tin, kiểm chứng, phát hành nhận định kết hợp | **Claude Code routine** (đám mây) | T2–T6 ~16:30 (sau khi dữ liệu 15:35 đã commit) | Có (routine) |

Lý do tách: phần dữ liệu/kỹ thuật là tất định, không cần LLM; chỉ phần viết bản tin cần LLM và dùng routine nên không phải quản lý khóa API trong repo.

## 2. Việc của người dùng

1. Repo GitHub: `Duy-Nhan/Stock-Market-Research`, **công khai** (quyết định 2026-11-10). Vì nguồn giá không chính thức và chưa xác minh ToS (`docs/data-sources.md`), chuỗi giá thô (`data/prices`, `data/session`) bị gitignore và chỉ lưu trong cache CI; repo chỉ chứa mã, bản tin, sổ nhật ký, snapshot SJC/vàng/tỷ giá và tin tức. **Lưu ý:** trang GitHub Pages vẫn hiển thị dữ liệu biểu đồ (cửa sổ nến) lấy từ các nguồn đó — việc này là phân phối lại ở mức hiển thị, rủi ro ToS vẫn còn, cần xác minh/xin phép nguồn trước khi coi là ổn định.
2. Gửi tôi URL repo. Tôi sẽ `git init`, commit và chuẩn bị đẩy lên (chỉ khi bạn đồng ý rõ ràng).
3. Repo → Settings → Pages → Source: **GitHub Actions**.
4. Repo → Settings → Actions → General → Workflow permissions: **Read and write**.
5. Tạo routine bằng `/schedule` (hoặc claude.ai/code/routines) trỏ vào repo, lịch T2–T6 16:30 giờ VN, dán nội dung ở §3. Bật cho phép push thẳng lên nhánh `main` (mặc định routine chỉ push nhánh `claude/*`; nếu không bật thì bạn phải merge tay mỗi ngày).
6. Kiểm tra môi trường routine truy cập được các trang báo trong `config/sources.json` (xem §4).

## 3. Lời nhắc (prompt) cho routine

```
Bạn đang chạy trong repo "Stock Market Research". Đọc CLAUDE.md, docs/report-methodology.md và .claude/skills/daily-report/SKILL.md, rồi thực hiện đúng quy trình /daily-report cho ngày giao dịch hôm nay (giờ Việt Nam, UTC+7).

Điều kiện tiên quyết (dừng và báo lỗi nếu không đạt, KHÔNG viết bản tin giả):
- Cài phụ thuộc: pip install -r requirements-ci.txt
- Giá thô KHÔNG nằm trong repo (repo công khai): chạy python -m pipeline.fetch_prices, python -m pipeline.fetch_snapshots --only session, python -m pipeline.build_indicators, rồi python -m pipeline.verify để kiểm tra nến ngày hôm nay. Nếu hôm nay không phải ngày giao dịch (không có nến ngày mới), dừng và ghi rõ lý do.
- Truy cập được các trang báo; nếu tải bài gốc thất bại thì KHÔNG dùng bài đó.

Quy trình: fetch_news → chọn tin có liên hệ nhân quả với watchlist → đọc BÀI GỐC → viết reports/<ngày>.md, .claims.json, .outlook.json → python -m pipeline.build_report <ngày> (phải đạt, không dùng --allow-fail) → rà ngữ nghĩa độc lập bằng một subagent riêng (người viết ≠ người kiểm; nó chỉ báo lỗi) → sửa theo lỗi → build_report lại → python -m pipeline.journal issue-combined --report <ngày>.

Ràng buộc: không bịa số liệu/sự kiện; mọi câu sự kiện có trích dẫn nguyên văn; nhận định xác suất hóa, nêu điều kiện vô hiệu; luôn nêu bằng chứng backtest "chưa vượt đường cơ sở". Không sửa engine, không sửa nhận định đã phát hành. Không commit data/news/cache.

Kết thúc: git add reports site/data/reports data/predictions data/news; commit "report: <ngày>"; push lên main. Trong tin nhắn cuối nêu: kết quả kiểm chứng tự động, các lỗi subagent rà báo và cách xử lý, những gì chưa kiểm chứng được.
```

## 4. Rủi ro đã biết (chưa kiểm chứng)

- **Mạng của routine:** môi trường đám mây có thể giới hạn tên miền ngoài. Cần thử một lần: tải bài từ vietstock.vn, vnexpress.net, cafef.vn, vneconomy.vn, en.wikipedia.org. Nếu bị chặn, cần thêm tên miền vào allowlist của môi trường routine.
- **IP cloud với nguồn giá:** VNDirect/Yahoo/vnappmob có thể chặn hoặc giới hạn IP của GitHub Actions. Chưa thử; lần chạy đầu của `update-data.yml` (workflow_dispatch) sẽ cho biết. Nếu fail thì workflow fail (không commit dữ liệu hỏng), không nội suy.
- **Giờ nến vàng GC=F:** cron 12:35 giờ VN dựa trên giả định nến ngày kết thúc ~12:05 giờ VN, chưa xác minh (theo giờ Yahoo thì nến ngày COMEX có thể kết thúc vào giờ khác). `journal.fresh_enough` từ chối phát hành nếu nến chưa hoàn tất nên chạy sai giờ chỉ gây bỏ lỡ, không gây sai.
- **Cache CI:** giá thô nằm trong `actions/cache` (bị xóa nếu 7 ngày không dùng hoặc vượt hạn mức 10 GB của repo). Khi mất cache, `fetch_prices` lấy lại toàn bộ cửa sổ từ nguồn (nến phút chỉ ~1 năm từ nguồn nên không mất gì mới). Dữ liệu không lấy lại được (SJC, vàng spot, tỷ giá, sổ nhật ký) được commit nên không phụ thuộc cache.
- **Lịch cron GitHub** có thể trễ vài phút đến vài chục phút khi tải cao; phiên bản trễ không ảnh hưởng tính đúng vì mọi bước đều idempotent và có kiểm tra độ mới.
- **Routine và nhận định bất biến:** hai nhận định đã phát hành ngày 2026-11-09 giữ nguyên; routine không được sửa/ghi đè bản ghi cũ.
- **Quyền riêng tư:** đã quét repo (2026-11-10), không có email/thông tin cá nhân. User-Agent của pipeline là chuỗi chung ("StockMarketResearch/0.1").
