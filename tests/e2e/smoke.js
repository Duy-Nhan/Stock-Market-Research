/* Kiểm thử giao diện (smoke test) bằng Playwright.
   Chạy:  npm i playwright && npx playwright install chromium
          python3 -m http.server 8765 -d site &   (sau khi chạy python -m pipeline.export_site)
          node tests/e2e/smoke.js
   Kiểm tra: không lỗi console, đổi mã/khung, chế độ cơ bản, replay không hé lộ nến tương lai, chấm lượt đoán, không tràn ngang trên mobile. */
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'http://localhost:8765/index.html';
let failed = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) failed++; };
(async () => {
  const b = await chromium.launch(); const errs = [];
  const mk = async (o) => { const p = await (await b.newContext(o)).newPage();
    p.on('console', m => { if (['error', 'warning'].includes(m.type())) errs.push(m.text()); });
    p.on('pageerror', e => errs.push('pageerror ' + e.message)); return p; };
  const p = await mk({ viewport: { width: 1440, height: 1000 } });
  await p.goto(BASE); await p.waitForSelector('.chart-main canvas');
  ok((await p.locator('#board tr[data-sym]').count()) >= 10, 'bảng giá có ≥ 10 dòng');
  for (const s of ['VCB', 'XAUUSD', 'E1VFVN30']) { await p.click(`tr[data-sym="${s}"]`); await p.waitForTimeout(500); ok((await p.textContent('#inst-head')).length > 10, 'đầu trang mã ' + s); }
  await p.click('tr[data-sym="VCB"]'); await p.waitForTimeout(600);
  const an = await p.textContent('#panel-analysis');
  ok(an.includes('Độ tin cậy') && an.includes('Bằng chứng lịch sử'), 'nhận định có độ tin cậy + bằng chứng lịch sử');
  ok(/Chưa vượt đường cơ sở nào|Vượt đường cơ sở/.test(an), 'kết luận so với đường cơ sở được sinh tự động');
  await p.click('#hz-seg button[data-hz="1_2_weeks"]'); await p.waitForTimeout(200);
  ok((await p.textContent('#panel-analysis')).includes('Sau 10 phiên'), 'khung 1–2 tuần hiển thị cả h=5 và h=10');
  ok((await p.textContent('#panel-journal')).includes('Đã phát hành'), 'sổ nhật ký hiển thị');
  await p.click('#res-seg button[data-res="1"]'); await p.waitForTimeout(700);
  ok((await p.textContent('#badges')).includes('Khối lượng nến phút chỉ tham khảo'), 'cảnh báo khối lượng nến phút');
  await p.click('#replay-toggle'); await p.waitForSelector('#rp-step'); await p.waitForTimeout(500);
  const day = await p.inputValue('#rp-day'); const [y, m, d] = day.split('-');
  const timeBefore = await p.textContent('#panel-time');
  ok(!timeBefore.includes(`${d}/${m}/${y}`), 'đầu replay: nến cuối thuộc phiên TRƯỚC (' + timeBefore + ')');
  ok((await p.textContent('#rp-status')).includes('0/'), 'đầu replay: 0 nến của phiên được hé lộ');
  for (let i = 0; i < 5; i++) await p.click('#rp-step');
  await p.click('#rp-up'); await p.waitForTimeout(200);
  const rr = await p.textContent('#rp-result');
  ok(/Đúng|Sai/.test(rr), 'có kết quả chấm lượt đoán');
  ok(rr.includes('hệ thống'), 'kết quả có so sánh với hệ thống');
  ok((await p.textContent('#rp-status')).includes('6/'), 'sau 5 bước + 1 lượt đoán: hé lộ 6 nến');
  await p.click('#replay-toggle'); await p.waitForTimeout(500);
  await p.click('#mode-basic'); await p.waitForTimeout(500);
  ok((await p.locator('.pane').count()) === 0, 'chế độ cơ bản: không có ô chỉ báo phụ');
  await p.click('#tab-news'); await p.waitForSelector('.nw-head h1'); await p.waitForTimeout(400);
  ok((await p.locator('.refs li').count()) >= 10, 'bản tin có danh sách nguồn');
  ok((await p.locator('.otable tbody tr').count()) >= 16, 'bản tin có bảng nhận định kết hợp');
  ok((await p.textContent('.fc-badge')).includes('Kiểm chứng'), 'bản tin hiển thị trạng thái kiểm chứng');
  ok((await p.locator('.tier.fact').count()) > 5 && (await p.locator('.tier.infer').count()) > 0, 'bản tin gắn nhãn tầng sự kiện/suy luận');
  const mo = await mk({ viewport: { width: 390, height: 844 } });
  await mo.goto(BASE); await mo.waitForSelector('.chart-main canvas');
  ok((await mo.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)) <= 0, 'mobile: không tràn ngang');
  ok(errs.length === 0, 'không có lỗi/cảnh báo console ' + JSON.stringify(errs));
  await b.close(); process.exit(failed ? 1 : 0);
})().catch(e => { console.error('LỖI', e); process.exit(1); });
