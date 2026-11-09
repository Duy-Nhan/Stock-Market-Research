"""Kiểm chứng chất lượng dữ liệu đã tải (Giai đoạn 1). Ghi data/quality/report.json và in tóm tắt.

Các phép kiểm:
  A. dchart daily vs finfo: giá đóng cửa (x1000), khối lượng khớp lệnh.
  B. Giá điều chỉnh: finfo.adClose != close ở những ngày nào; dchart theo chuỗi nào.
  C. Nến phút: tổng KL các nến 1m trong ngày vs nmVolume; vị trí nến ATO/ATC; nhãn thời gian nến.
  D. Giá nến phút nằm trong [sàn, trần] của finfo.
  E. GC=F daily: khoảng nhảy open so với close phiên trước (dấu hiệu chuyển hợp đồng).
  F. Yahoo .VN vs dchart (đóng cửa 60 ngày gần nhất).
  G. Khoảng trống lịch ngày giao dịch (nghỉ lễ suy ra từ dữ liệu).
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from .common import DATA, VN_TZ, FetchError, get_json, load_config, now_vn_iso, read_json, write_json_atomic

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=3mo"


def vn_date(t: int) -> str:
    return datetime.fromtimestamp(t, VN_TZ).strftime("%Y-%m-%d")


def vn_hm(t: int) -> str:
    return datetime.fromtimestamp(t, VN_TZ).strftime("%H:%M")


def symbols() -> List[str]:
    return [i["symbol"] for i in load_config("watchlist.json")["instruments"] if i["type"] in ("stock", "etf")]


def check_daily_vs_finfo(sym: str) -> Dict[str, Any]:
    d = {vn_date(b[0]): b for b in read_json(DATA / "prices" / sym / "D.json")["bars"]}
    rows = read_json(DATA / "session" / f"{sym}.json")["rows"]
    n = close_diff = vol_diff = missing = 0
    worst: List[str] = []
    for r in rows:
        b = d.get(r["date"])
        if not b:
            missing += 1
            continue
        n += 1
        ref = (r["adClose"] if r.get("adClose") is not None else r["close"]) * 1000  # dchart là giá đã điều chỉnh
        if abs(b[4] - ref) > 1.5:
            close_diff += 1
            if len(worst) < 5:
                worst.append(f"{r['date']} dchart={b[4]} finfo_adClose={ref}")
        if abs(b[5] - r["nmVolume"]) > 0.5:
            vol_diff += 1
    return {"days_compared": n, "finfo_days_missing_in_dchart": missing, "close_mismatch": close_diff,
            "volume_vs_nmVolume_mismatch": vol_diff, "close_mismatch_examples": worst}


def check_adjusted(sym: str) -> Dict[str, Any]:
    rows = read_json(DATA / "session" / f"{sym}.json")["rows"]
    d = {vn_date(b[0]): b for b in read_json(DATA / "prices" / sym / "D.json")["bars"]}
    ev = [r for r in rows if r.get("adClose") is not None and abs(r["adClose"] - r["close"]) > 1e-6]
    out: Dict[str, Any] = {"days_where_adClose_differs_from_close": len(ev)}
    if ev:
        e = ev[0]
        b = d.get(e["date"])
        out["first_example"] = {"date": e["date"], "finfo_close": e["close"], "finfo_adClose": e["adClose"],
                                "dchart_close_x1000": b[4] if b else None}
        out["dchart_follows"] = None if not b else (
            "close (chưa điều chỉnh)" if abs(b[4] - e["close"] * 1000) < 0.5 else
            "adClose (đã điều chỉnh)" if abs(b[4] - e["adClose"] * 1000) < 0.5 else "không khớp cả hai")
    return out


def check_intraday(sym: str) -> Dict[str, Any]:
    bars = read_json(DATA / "prices" / sym / "1.json")["bars"]
    sess = {r["date"]: r for r in read_json(DATA / "session" / f"{sym}.json")["rows"]}
    by_day: Dict[str, List[List[float]]] = defaultdict(list)
    for b in bars:
        by_day[vn_date(b[0])].append(b)
    full_days = [k for k in sorted(by_day)][:-1]  # bỏ ngày cuối để loại nến dở dang
    ratios, out_of_band, band_checked = [], 0, 0
    first_hm: Dict[str, int] = defaultdict(int)
    last_hm: Dict[str, int] = defaultdict(int)
    atx = {"first_bar_share": [], "last_bar_share": []}
    for day in full_days + ([sorted(by_day)[-1]] if by_day else []):
        s = sess.get(day)
        if not s:
            continue
        vols = sum(b[5] for b in by_day[day])
        if s["nmVolume"]:
            ratios.append(vols / s["nmVolume"])
        first_hm[vn_hm(by_day[day][0][0])] += 1
        last_hm[vn_hm(by_day[day][-1][0])] += 1
        if s["nmVolume"]:
            atx["first_bar_share"].append(by_day[day][0][5] / s["nmVolume"])
            atx["last_bar_share"].append(by_day[day][-1][5] / s["nmVolume"])
        lo, hi = s["floorPrice"] * 1000, s["ceilingPrice"] * 1000
        for b in by_day[day]:
            band_checked += 1
            if not (lo - 0.5 <= b[3] and b[2] <= hi + 0.5):
                out_of_band += 1
    top = lambda dct: sorted(dct.items(), key=lambda kv: -kv[1])[:3]
    return {
        "days_compared": len(ratios),
        "sum_1m_volume_over_nmVolume": {"min": round(min(ratios), 4), "median": round(statistics.median(ratios), 4),
                                         "max": round(max(ratios), 4)} if ratios else None,
        "most_common_first_bar_hm": top(first_hm), "most_common_last_bar_hm": top(last_hm),
        "median_share_of_day_volume_in_first_bar": round(statistics.median(atx["first_bar_share"]), 4) if atx["first_bar_share"] else None,
        "median_share_of_day_volume_in_last_bar": round(statistics.median(atx["last_bar_share"]), 4) if atx["last_bar_share"] else None,
        "bars_checked_vs_floor_ceiling": band_checked, "bars_outside_floor_ceiling": out_of_band,
    }


def check_gold_gaps() -> Dict[str, Any]:
    bars = read_json(DATA / "prices" / "XAUUSD" / "D.json")["bars"]
    gaps = []
    for i in range(1, len(bars)):
        prev_c, o = bars[i - 1][4], bars[i][1]
        gaps.append((abs(o / prev_c - 1), vn_date(bars[i][0]), prev_c, o))
    gaps.sort(reverse=True)
    rets = [abs(bars[i][4] / bars[i - 1][4] - 1) for i in range(1, len(bars))]
    return {"bars": len(bars), "median_abs_daily_close_return_pct": round(100 * statistics.median(rets), 3),
            "median_abs_open_gap_pct": round(100 * statistics.median([g[0] for g in gaps]), 3),
            "top_open_gaps": [{"date": d, "prev_close": p, "open": o, "gap_pct": round(100 * g, 2)} for g, d, p, o in gaps[:8]]}


def check_yahoo(sym: str) -> Dict[str, Any]:
    j = get_json(YAHOO.format(sym=f"{sym}.VN"))["chart"]["result"][0]
    q = j["indicators"]["quote"][0]
    y = {vn_date(t): c for t, c in zip(j["timestamp"], q["close"]) if c}
    d = {vn_date(b[0]): b[4] for b in read_json(DATA / "prices" / sym / "D.json")["bars"]}
    # dung sai tương đối 0,5%: Yahoo làm tròn khác; chênh lớn hơn thường do Yahoo chỉ điều chỉnh tách/thưởng cổ phiếu, không điều chỉnh cổ tức tiền mặt (giả thuyết, chưa kiểm chứng)
    diffs = [(day, c, d[day]) for day, c in y.items() if day in d and abs(c / d[day] - 1) > 0.005]
    return {"days_compared": len([x for x in y if x in d]), "close_mismatch_rel_gt_0.5pct": len(diffs), "examples": diffs[:4]}


def check_calendar(sym: str = "FPT") -> Dict[str, Any]:
    days = [vn_date(b[0]) for b in read_json(DATA / "prices" / sym / "D.json")["bars"]]
    days = [x for x in days if x >= "2025-01-01"]
    ds = [datetime.strptime(x, "%Y-%m-%d") for x in days]
    gaps = [(days[i - 1], days[i], (ds[i] - ds[i - 1]).days) for i in range(1, len(ds)) if (ds[i] - ds[i - 1]).days > 3]
    weekend = [x for x, dt in zip(days, ds) if dt.weekday() >= 5]
    return {"trading_days_since_2025_01_01": len(days), "weekend_bars": weekend, "gaps_over_3_days": gaps}


def main() -> int:
    rep: Dict[str, Any] = {"generated_at": now_vn_iso(), "per_symbol": {}}
    for s in symbols():
        r: Dict[str, Any] = {}
        for name, fn in (("daily_vs_finfo", check_daily_vs_finfo), ("adjusted_prices", check_adjusted),
                         ("intraday_1m", check_intraday), ("yahoo_crosscheck", check_yahoo)):
            try:
                r[name] = fn(s)
            except (FetchError, KeyError, ValueError, TypeError, ZeroDivisionError) as e:
                r[name] = {"error": repr(e)}
        rep["per_symbol"][s] = r
    rep["gold_gc_f_gaps"] = check_gold_gaps()
    rep["calendar_FPT"] = check_calendar()
    write_json_atomic(DATA / "quality" / "report.json", rep, indent=1)
    import json
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
