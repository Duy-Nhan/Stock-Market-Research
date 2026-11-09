"""Tính chỉ báo từ data/prices và ghi data/indicators/<SYMBOL>_<res>.json (cột song song, NaN -> null).

Mỗi file có:
  meta: nguồn, tham số, thời điểm tính, chỉ số nến hoàn tất cuối cùng (last_complete_index)
  t, o, h, l, c, v, partial: mảng song song (partial=True: nến chưa hoàn tất — KHÔNG dùng để kết luận)
  <chỉ báo>: mảng song song
Chỉ giữ N nến cuối để file nhỏ; chỉ báo vẫn được tính trên TOÀN BỘ lịch sử rồi mới cắt (tránh sai do khởi tạo).

Dùng:  python -m pipeline.build_indicators [--symbols FPT] [--res D 60 15 5] [--keep 600]
"""
from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from .common import DATA, VN_TZ, load_config, now_vn_iso, read_json, write_json_atomic
from .fetch_prices import RES_SECONDS
from .indicators import compute_all

DEFAULT_RES = ["D", "60", "15", "5"]
PARAMS = {"sma_ema": [9, 20, 50, 200], "macd": [12, 26, 9], "adx": 14, "rsi": 14, "stoch": [14, 3, 3],
          "bollinger": [20, 2], "atr": 14, "vol_ma": 20}


def is_partial(kind: str, res: str, t: int, now: float) -> bool:
    """Nến t chưa hoàn tất? Nhãn nến = thời điểm BẮT ĐẦU nến.
    - VN, khung ngày: nến ngày hoàn tất sau 15:00 giờ VN của chính ngày đó (sau phiên ATC 14:45).
    - Khung còn lại: hoàn tất khi now >= t + độ dài khung. (Nến 14:45 ATC được coi là hoàn tất sau 1 khung; xấp xỉ có chủ đích.)
    - XAUUSD (GC=F): theo quy tắc t + độ dài khung."""
    if kind == "vn" and res == "D":
        d = datetime.fromtimestamp(t, VN_TZ)
        close_dt = d.replace(hour=15, minute=0, second=0, microsecond=0)
        return now < close_dt.timestamp()
    return now < t + RES_SECONDS[res]


def clean(v: Any) -> Any:
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def build_one(sym: str, res: str, kind: str, keep: int, now: float) -> Optional[Dict[str, Any]]:
    p = DATA / "prices" / sym / f"{res}.json"
    src = read_json(p)
    if not src or not src["bars"]:
        return None
    df = pd.DataFrame(src["bars"], columns=["t", "o", "h", "l", "c", "v"])
    intraday = res != "D"
    with_volume = bool(df["v"].sum() > 0)
    day_key = [datetime.fromtimestamp(t, VN_TZ).strftime("%Y-%m-%d") for t in df["t"]] if intraday else None
    vwap_ok = intraday and kind == "vn"  # VWAP chỉ cho cổ phiếu/ETF/chỉ số VN nội phiên (xem docs/indicators.md §4)
    ind = compute_all(df, intraday=vwap_ok, with_volume=with_volume, day_key=day_key)
    full = pd.concat([df, ind], axis=1)
    full["partial"] = [is_partial(kind, res, int(t), now) for t in full["t"]]
    tail = full.tail(keep)
    complete = [i for i, x in enumerate(tail["partial"]) if not x]
    out: Dict[str, Any] = {
        "meta": {
            "symbol": sym, "resolution": res, "generated_at": now_vn_iso(),
            "price_source_meta": src["meta"], "params": PARAMS,
            "rows": len(tail), "total_history_bars": len(full),
            "last_complete_index": complete[-1] if complete else None,
            "note": "Chỉ báo tính trên toàn bộ lịch sử rồi cắt N nến cuối. Nến partial=True chưa hoàn tất, không dùng để kết luận.",
        }
    }
    for col in tail.columns:
        out[col] = [clean(x.item() if hasattr(x, "item") else x) for x in tail[col]]
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="*")
    ap.add_argument("--res", nargs="*", default=DEFAULT_RES)
    ap.add_argument("--keep", type=int, default=600)
    args = ap.parse_args(argv)
    wl = load_config("watchlist.json")
    kinds: Dict[str, str] = {i["symbol"]: ("vn" if i["type"] in ("stock", "etf") else "gold")
                             for i in wl["instruments"] if i["type"] in ("stock", "etf", "gold_intl")}
    for ix in wl["context_indices"]:
        kinds[ix["symbol"]] = "vn"
    if args.symbols:
        kinds = {k: v for k, v in kinds.items() if k in args.symbols}
    import time
    now = time.time()
    for sym, kind in kinds.items():
        for res in args.res:
            r = build_one(sym, res, kind, args.keep, now)
            if r is None:
                print(f"[skip] {sym} {res}: chưa có dữ liệu")
                continue
            write_json_atomic(DATA / "indicators" / f"{sym}_{res}.json", r)
            print(f"[ok]   {sym:9s} {res:>2s} rows={r['meta']['rows']} last_complete_index={r['meta']['last_complete_index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
