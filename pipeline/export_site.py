"""Xuất dữ liệu cho giao diện web vào site/data/ (JSON tĩnh, giao diện chỉ đọc — không tự tính chỉ báo).

  site/data/manifest.json          danh sách file, thời điểm tạo
  site/data/board.json             bảng giá: giá thực tế (finfo), tham chiếu/trần/sàn, KL, mini-chart, trạng thái xu hướng
  site/data/gold_domestic.json     SJC mua/bán + độ chênh so với giá thế giới quy đổi (theo tỷ giá mua và bán)
  site/data/<SYM>_<res>.json       nến + chỉ báo + cấu trúc giá (swing, đường xu hướng, vùng S/R, pivot), cột song song

Dùng:  python -m pipeline.export_site [--symbols FPT] [--res D 60 15 5 1]
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from . import gold
from .common import DATA, ROOT, VN_TZ, load_config, now_vn_iso, read_json, ts_to_vn_iso, write_json_atomic
from .build_indicators import PARAMS, is_partial
from .fetch_prices import RES_SECONDS
from .indicators import FIB_RATIOS, compute_all
from . import engine as eg
from .structure import SWING_K, daily_pivots

SITE_DATA = ROOT / "site" / "data"
from .journal import WINDOW as JOURNAL_WINDOW
KEEP = {"D": JOURNAL_WINDOW, "60": 600, "15": 600, "5": 600, "1": 2250}  # D dùng đúng cửa sổ của sổ nhật ký để nhận định hiển thị = nhận định đã phát hành
EXPORT_RES = ["D", "60", "15", "5", "1"]
IND_COLS = ["sma20", "sma50", "sma200", "ema9", "ema20", "ema50", "ema200", "macd", "macd_signal", "macd_hist",
            "adx14", "plus_di14", "minus_di14", "rsi14", "stoch_k", "stoch_d", "bb_mid", "bb_upper", "bb_lower",
            "bb_pct_b", "bb_bandwidth", "atr14", "vol_ma20", "obv", "vwap"]
PIVOT_COLS = ["P", "R1", "S1", "R2", "S2"]


def rnd(x: Any, nd: int = 4) -> Any:
    if x is None:
        return None
    x = float(x)
    return None if (math.isnan(x) or math.isinf(x)) else round(x, nd)


def instruments() -> Dict[str, Dict[str, Any]]:
    wl = load_config("watchlist.json")
    out: Dict[str, Dict[str, Any]] = {}
    for i in wl["instruments"]:
        if i["type"] in ("stock", "etf"):
            out[i["symbol"]] = {**i, "kind": "vn"}
        elif i["type"] == "gold_intl":
            out[i["symbol"]] = {**i, "kind": "gold"}
    for ix in wl["context_indices"]:
        out[ix["symbol"]] = {"symbol": ix["symbol"], "name": ix["name"], "type": "index", "kind": "vn", "sector": "Chỉ số"}
    return out


def clean(o: Any) -> Any:
    """Chuyển numpy -> kiểu thuần Python và NaN/inf -> None (JSON hợp lệ cho trình duyệt)."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return [clean(v) for v in o.tolist()]
    if isinstance(o, (np.floating, float)):
        return None if (math.isnan(float(o)) or math.isinf(float(o))) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def export_series(sym: str, res: str, ins: Dict[str, Any], now: float):
    src = read_json(DATA / "prices" / sym / f"{res}.json")
    if not src or not src["bars"]:
        return None, None
    kind = ins["kind"]
    df = pd.DataFrame(src["bars"], columns=["t", "o", "h", "l", "c", "v"])
    intraday = res != "D"
    day_key = [datetime.fromtimestamp(t, VN_TZ).strftime("%Y-%m-%d") for t in df["t"]]
    with_vol = bool(df["v"].sum() > 0)
    ind = compute_all(df, intraday=(intraday and kind == "vn"), with_volume=with_vol, day_key=day_key if intraday else None)
    for col in IND_COLS:
        if col not in ind:
            ind[col] = np.nan
    piv = None
    if kind == "vn" or res == "D":
        piv = daily_pivots(day_key, df["h"], df["l"], df["c"])
    keep = min(KEEP[res], len(df))
    off = len(df) - keep
    w = df.iloc[off:].reset_index(drop=True)
    wi = ind.iloc[off:].reset_index(drop=True)
    dec = 0 if (kind == "vn" and ins.get("type") != "index") else 2
    eng = eg.Engine(w, wi, kind=kind, dec=dec, intraday=intraday)  # cấu trúc, mô hình nến/giá và tín hiệu chỉ xét trong cửa sổ hiển thị
    st = eng.st
    sys_dir, sys_conf = eng.signal_arrays("next_session")
    partial = [is_partial(kind, res, int(t), now) for t in w["t"]]
    complete = [i for i, p in enumerate(partial) if not p]

    out: Dict[str, Any] = {
        "meta": {
            "symbol": sym, "name": ins.get("name", sym), "kind": kind, "resolution": res, "type": ins.get("type"),
            "source": src["meta"]["source"], "prices_fetched_at": src["meta"]["fetched_at"],
            "data_as_of": ts_to_vn_iso(int(w["t"].iloc[-1])), "generated_at": now_vn_iso(),
            "rows": len(w), "last_complete_index": complete[-1] if complete else None,
            "price_adjusted": kind == "vn" and ins.get("type") != "index" and "đã điều chỉnh",
            "is_futures": kind == "gold", "has_volume": with_vol,
            "volume_note": src["meta"].get("volume_semantics"),
            "unit": "đồng" if (kind == "vn" and ins.get("type") != "index") else ("USD/oz (GC=F, futures COMEX)" if kind == "gold" else "điểm"),
            "bar_label": "start", "bar_seconds": RES_SECONDS[res],
            "params": PARAMS, "swing_k": SWING_K, "fib_ratios": list(FIB_RATIOS),
            "structure_window_note": "Đường xu hướng/vùng S/R/swing chỉ xét trong cửa sổ hiển thị; mọi kết quả nhân quả (không dùng dữ liệu tương lai).",
        },
        "t": [int(x) for x in w["t"]],
        "o": [rnd(x) for x in w["o"]], "h": [rnd(x) for x in w["h"]], "l": [rnd(x) for x in w["l"]], "c": [rnd(x) for x in w["c"]],
        "v": [int(x) for x in w["v"]],
        "partial": partial,
        "trend_state": [None if np.isnan(x) else int(x) for x in st["trend_state"]],
        "swings": st["swings"], "trendlines": st["trendlines"], "zones": st["zones"],
        "candles": eng.candles, "chart_patterns": eng.charts,
        "sys_next": [None if np.isnan(x) else int(x) for x in sys_dir], "sys_next_conf": [None if np.isnan(x) else int(x) for x in sys_conf],
    }
    for col in IND_COLS:
        out[col] = [rnd(x) for x in wi[col]]
    for col in PIVOT_COLS:
        out[f"pv_{col}"] = [rnd(x) for x in piv[col][off:]] if piv else [None] * len(w)
    if intraday:
        sess: List[List[Any]] = []
        for i, t in enumerate(w["t"]):
            d = datetime.fromtimestamp(int(t), VN_TZ).strftime("%Y-%m-%d")
            if not sess or sess[-1][0] != d:
                sess.append([d, i, i])
            else:
                sess[-1][2] = i
        out["sessions"] = sess
    return clean(out), eng


def export_board(ins_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    latest_dates = set()
    for sym, ins in ins_map.items():
        d = read_json(DATA / "prices" / sym / "D.json")
        if not d:
            continue
        bars = d["bars"]
        closes = [b[4] for b in bars[-31:]]
        it: Dict[str, Any] = {"symbol": sym, "name": ins.get("name", sym), "type": ins.get("type"), "sector": ins.get("sector"),
                              "exchange": ins.get("exchange"), "spark": [rnd(x) for x in closes]}
        sess = read_json(DATA / "session" / f"{sym}.json")
        if sess and sess["rows"]:
            r = sorted(sess["rows"], key=lambda x: x["date"])[-1]
            latest_dates.add(r["date"])
            it.update(last=rnd(r["close"] * 1000, 2), ref=rnd(r["basicPrice"] * 1000, 2), ceiling=rnd(r["ceilingPrice"] * 1000, 2),
                      floor=rnd(r["floorPrice"] * 1000, 2), nm_volume=r["nmVolume"], pt_volume=r["ptVolume"], date=r["date"],
                      price_basis="giá thực tế (finfo)")
        else:
            last, prev = bars[-1], bars[-2]
            it.update(last=rnd(last[4]), ref=rnd(prev[4]), date=datetime.fromtimestamp(last[0], VN_TZ).strftime("%Y-%m-%d"),
                      nm_volume=last[5] if ins["kind"] == "vn" else None,
                      price_basis="GC=F futures COMEX (không phải spot)" if ins["kind"] == "gold" else "điểm số")
        if it.get("last") is not None and it.get("ref"):
            it["change"] = rnd(it["last"] - it["ref"], 4)
            it["pct"] = rnd(100 * (it["last"] / it["ref"] - 1), 3)
        ex = read_json(SITE_DATA / f"{sym}_D.json")
        if ex:
            ts = [x for x in ex["trend_state"] if x is not None]
            it["trend_state_d"] = ex["trend_state"][-1]
            it["trend_basis"] = "Dow: đỉnh/đáy swing xác nhận gần nhất (khung ngày)"
        items.append(it)
    return {"generated_at": now_vn_iso(), "latest_session_date": max(latest_dates) if latest_dates else None, "items": items}


def export_analysis(engines_d: Dict[str, Any]) -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    for sym, (eng, o) in engines_d.items():
        i = o["meta"]["last_complete_index"]
        if i is None or np.isnan(eng.atr[i]):
            continue
        items[sym] = {"asof_index": i, "asof_t": o["t"][i], "asof_date": datetime.fromtimestamp(o["t"][i], VN_TZ).strftime("%Y-%m-%d"),
                      "last_bar_partial": o["meta"]["rows"] - 1 > i, "name": o["meta"]["name"], "is_futures": o["meta"]["is_futures"],
                      "price_adjusted": bool(o["meta"]["price_adjusted"]),
                      "horizons": {hz: eng.explain(i, hz) for hz in eg.HORIZONS}}
    return clean({"generated_at": now_vn_iso(), "engine_version": eg.ENGINE_VERSION, "rules_doc": "docs/analysis.md",
                  "disclaimer": "Số liệu và nhận định theo quy tắc cố định, không phải khuyến nghị đầu tư. Xem bằng chứng lịch sử trong backtest.json.",
                  "items": items})


def export_journal_and_backtest() -> None:
    rows: List[Dict[str, Any]] = []
    pdir = DATA / "predictions"
    for p in sorted(pdir.glob("????-??-??.json")):
        for x in read_json(p)["predictions"]:
            rows.append({k: x[k] for k in ("id", "symbol", "horizon", "asof_date", "issued_at", "direction", "direction_vi", "confidence", "tau",
                                           "reference_close_actual", "invalidation", "evaluations", "engine_version")})
    summ = read_json(pdir / "summary.json", {})
    write_json_atomic(SITE_DATA / "journal.json", clean({"generated_at": now_vn_iso(), "summary": summ, "recent": rows[-120:]}))
    bt = read_json(DATA / "backtest" / "summary.json")
    if bt:
        write_json_atomic(SITE_DATA / "backtest.json", clean(bt))


def parse_vcb_dt(s: str) -> Optional[str]:
    try:
        return datetime.strptime(s, "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=VN_TZ).isoformat()
    except (ValueError, TypeError):
        return None


def last_jsonl(name: str) -> Optional[Dict[str, Any]]:
    p = DATA / "snapshots" / f"{name}.jsonl"
    if not p.exists():
        return None
    rows = [json.loads(x) for x in open(p, encoding="utf-8") if x.strip()]
    return rows[-1] if rows else None


def export_gold_domestic() -> Dict[str, Any]:
    sjc, fx, spot = last_jsonl("sjc"), last_jsonl("usdvnd"), last_jsonl("gold_spot")
    out: Dict[str, Any] = {"generated_at": now_vn_iso(), "warnings": []}
    if not (sjc and fx and spot):
        out["warnings"].append("Thiếu ảnh chụp SJC/tỷ giá/giá spot — chưa tính được độ chênh.")
        return out
    sjc_iso = ts_to_vn_iso(sjc["source_datetime"])
    spot_price = (spot.get("gold_api") or {}).get("price")
    if spot_price is None and spot.get("swissquote_prime"):
        q = spot["swissquote_prime"]
        spot_price = (q["bid"] + q["ask"]) / 2
    out["sjc"] = {"buy": sjc["buy_1l"], "sell": sjc["sell_1l"], "unit": "đồng/lượng", "quoted_at": sjc_iso, "source": sjc["source"]}
    out["usdvnd"] = {"buy": fx["buy"], "sell": fx["sell"], "transfer": fx["transfer"], "quoted_at": parse_vcb_dt(fx["source_datetime"]), "source": fx["source"]}
    out["spot"] = {"xauusd": spot_price, "fetched_at": spot["fetched_at"],
                   "source": "gold-api.com" if spot.get("gold_api") else "swissquote", "unit": "USD/oz (spot)"}
    w_buy = gold.world_price_vnd_per_luong(spot_price, fx["buy"])
    w_sell = gold.world_price_vnd_per_luong(spot_price, fx["sell"])
    out["world_vnd_per_luong"] = {"at_usdvnd_buy": round(w_buy), "at_usdvnd_sell": round(w_sell)}
    out["premium_pct_sjc_sell"] = {"at_usdvnd_buy": round(100 * gold.premium(sjc["sell_1l"], spot_price, fx["buy"]), 2),
                                   "at_usdvnd_sell": round(100 * gold.premium(sjc["sell_1l"], spot_price, fx["sell"]), 2)}
    gap_min = abs(datetime.fromisoformat(spot["fetched_at"]).timestamp() - sjc["source_datetime"]) / 60
    out["input_time_gap_minutes"] = round(gap_min)
    if gap_min > 30:
        out["warnings"].append(f"Giá SJC và giá vàng thế giới lệch thời điểm ~{round(gap_min)} phút; độ chênh chỉ mang tính tham khảo.")
    out["formula"] = "premium = SJC_bán / (XAUUSD × USDVND × 37,5 / 31,1034768) − 1; hiển thị khoảng theo tỷ giá Vietcombank mua và bán"
    out["history_note"] = "Chuỗi giá SJC tự tích lũy từ 2026-11-09; nguồn không cung cấp lịch sử."
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="*")
    ap.add_argument("--res", nargs="*", default=EXPORT_RES, choices=EXPORT_RES)
    args = ap.parse_args(argv)
    ins_map = instruments()
    targets = {k: v for k, v in ins_map.items() if not args.symbols or k in args.symbols}
    now = time.time()
    files: List[Dict[str, Any]] = []
    engines_d: Dict[str, Any] = {}
    for sym, ins in targets.items():
        for res in args.res:
            o, eng = export_series(sym, res, ins, now)
            if o is None:
                print(f"[skip] {sym} {res}")
                continue
            if res == "D":
                engines_d[sym] = (eng, o)
            fn = f"{sym}_{res}.json"
            write_json_atomic(SITE_DATA / fn, o)
            size = (SITE_DATA / fn).stat().st_size
            files.append({"file": fn, "symbol": sym, "resolution": res, "rows": o["meta"]["rows"], "bytes": size})
            print(f"[ok]   {fn:20s} rows={o['meta']['rows']:5d} {size // 1024:5d} KB  lines={len(o['trendlines'])} zones={len(o['zones'])}")
    write_json_atomic(SITE_DATA / "board.json", export_board(ins_map))
    write_json_atomic(SITE_DATA / "analysis.json", export_analysis(engines_d))
    export_journal_and_backtest()
    write_json_atomic(SITE_DATA / "gold_domestic.json", export_gold_domestic())
    write_json_atomic(SITE_DATA / "manifest.json", {"generated_at": now_vn_iso(), "files": files})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
