"""Đo độ trễ dữ liệu TRONG PHIÊN của VNDirect dchart (chạy vào phiên giao dịch, giờ VN 09:00–14:45).

Mỗi `--interval` giây gọi dchart nến 1m của các mã và ghi vào data/quality/latency_<ngày>.jsonl:
  - thời điểm gọi (now), nhãn nến cuối (t_last), độ trễ = now - t_last
  - nến cuối có KL bao nhiêu; số nến của ngày hôm nay
Sau phiên, chạy `python -m pipeline.probes.latency_probe --summary` để xem trung vị/tối đa độ trễ.

Kết quả đo mới là bằng chứng để quyết định UI hiển thị "trễ X phút" — không đoán.
Dùng:  python -m pipeline.probes.latency_probe --symbols FPT VCB BSR --interval 60 --minutes 120
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime

from ..common import DATA, VN_TZ, FetchError, get_json

DCHART = "https://dchart-api.vndirect.com.vn/dchart/history?symbol={s}&resolution=1&from={f}&to={t}"


def probe(symbols, interval, minutes):
    day = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    out = DATA / "quality" / f"latency_{day}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    end = time.time() + minutes * 60
    while time.time() < end:
        now = int(time.time())
        for s in symbols:
            rec = {"now": now, "symbol": s}
            try:
                j = get_json(DCHART.format(s=s, f=now - 3 * 3600, t=now), retries=1)
                if j.get("s") == "ok" and j["t"]:
                    rec.update(t_last=j["t"][-1], lag_s=now - j["t"][-1], v_last=j["v"][-1], bars_returned=len(j["t"]))
                else:
                    rec["status"] = j.get("s")
            except FetchError as e:
                rec["error"] = str(e)[:120]
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        time.sleep(interval)


def summary():
    day = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    p = DATA / "quality" / f"latency_{day}.jsonl"
    rows = [json.loads(x) for x in open(p, encoding="utf-8")]
    lags = [r["lag_s"] for r in rows if "lag_s" in r]
    print(f"{len(rows)} lần đo, {len(lags)} có dữ liệu, {len(rows) - len(lags)} lỗi/không dữ liệu")
    if lags:
        print(f"độ trễ (giây): trung vị={statistics.median(lags):.0f} p90={sorted(lags)[int(0.9 * len(lags)) - 1]} max={max(lags)}")
        print("Lưu ý: nhãn nến = thời điểm bắt đầu nến; trễ tối thiểu hợp lệ ≈ 0–60s nếu nến đang chạy dở được trả về.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="*", default=["FPT", "VCB", "BSR", "E1VFVN30"])
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--minutes", type=int, default=120)
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    summary() if a.summary else probe(a.symbols, a.interval, a.minutes)
