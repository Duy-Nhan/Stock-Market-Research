"""Backtest NHÂN QUẢ (walk-forward, không tinh chỉnh) của engine và của từng mô hình, trên dữ liệu đã lưu.

Mục đích: đo xem các quy tắc có lợi thế thật so với đường cơ sở hay không — kể cả khi kết quả là "không".
Quy ước chấm giống docs/methodology.md §3: ngưỡng τ_h = 0,25 · ATR14_t · √h / C_t; kết quả = tăng nếu C_{t+h}/C_t − 1 > τ_h,
giảm nếu < −τ_h, còn lại đi ngang. Dùng chuỗi giá đã điều chỉnh (nhất quán).
Giới hạn (ghi trong báo cáo): dữ liệu quá khứ của chính dự án; các quy tắc do người phân tích chọn theo thông lệ, KHÔNG tinh chỉnh theo
dữ liệu này, nhưng người viết đã biết đặc điểm chung của thị trường; mẫu chồng lấn (h>1); nhiều phép thử → có thể có kết quả "đẹp" do may mắn.

Dùng:  python -m pipeline.backtest [--intraday]   → data/backtest/summary.json
"""
from __future__ import annotations

import argparse
import math
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import engine as eg
from . import chart_patterns as cht
from .common import DATA, load_config, now_vn_iso, read_json, write_json_atomic
from .indicators import compute_all

WARMUP = 260
SYMS_ORDER = None


def wilson(k: int, n: int, z: float = 1.96) -> Optional[Tuple[float, float]]:
    if n <= 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return round(centre - half, 4), round(centre + half, 4)


def outcomes(c: np.ndarray, atr: np.ndarray, h: int) -> np.ndarray:
    """Kết quả tại nến t cho khung h nến: +1/-1/0; NaN nếu chưa có tương lai hoặc thiếu ATR."""
    n = len(c)
    out = np.full(n, np.nan)
    for t in range(n - h):
        if np.isnan(atr[t]) or c[t] <= 0:
            continue
        tau = 0.25 * atr[t] * math.sqrt(h) / c[t]
        r = c[t + h] / c[t] - 1
        out[t] = 1 if r > tau else (-1 if r < -tau else 0)
    return out


def evaluate(pred: np.ndarray, out: np.ndarray, conf: Optional[np.ndarray], h_overlap: int, start: int) -> Dict[str, Any]:
    m = ~np.isnan(pred) & ~np.isnan(out)
    m[:start] = False
    p, o = pred[m].astype(int), out[m].astype(int)
    n = int(m.sum())
    if n == 0:
        return {"n": 0}
    base = {k: float((o == k).mean()) for k in (-1, 0, 1)}
    predd = {k: float((p == k).mean()) for k in (-1, 0, 1)}
    acc = float((p == o).mean())
    indep = sum(predd[k] * base[k] for k in (-1, 0, 1))  # độ chính xác kỳ vọng nếu dự đoán độc lập với kết quả
    neff = max(1, n // max(1, h_overlap))
    res: Dict[str, Any] = {
        "n": n, "n_effective": neff, "accuracy": round(acc, 4), "accuracy_ci95_effective": wilson(int(round(acc * neff)), neff),
        "base_rate": {"down": round(base[-1], 4), "flat": round(base[0], 4), "up": round(base[1], 4)},
        "pred_share": {"down": round(predd[-1], 4), "flat": round(predd[0], 4), "up": round(predd[1], 4)},
        "accuracy_if_independent": round(indep, 4), "lift_vs_independent": round(acc - indep, 4),
        "always_flat_accuracy": round(base[0], 4), "always_majority_accuracy": round(max(base.values()), 4),
    }
    for name, k in (("up", 1), ("down", -1)):
        sel = p == k
        res[f"precision_{name}"] = {"n": int(sel.sum()), "hit": round(float((o[sel] == k).mean()), 4) if sel.any() else None,
                                    "opposite": round(float((o[sel] == -k).mean()), 4) if sel.any() else None,
                                    "base": round(base[k], 4)}
    if conf is not None:
        byc = {}
        for name, lv in (("low", 0), ("medium", 1), ("high", 2)):
            cm = conf[m] == lv
            nn = int(cm.sum())
            kk = int((p[cm] == o[cm]).sum()) if nn else 0
            ne = max(1, nn // max(1, h_overlap))
            byc[name] = {"n": nn, "n_effective": ne, "accuracy": round(float((p[cm] == o[cm]).mean()), 4) if nn else None,
                         "accuracy_ci95_effective": wilson(int(round(kk / nn * ne)), ne) if nn else None,
                         "directional_share": round(float((p[cm] != 0).mean()), 4) if nn else None,
                         "directional_accuracy": (round(float((p[cm & (p != 0)] == o[cm & (p != 0)]).mean()), 4) if (cm & (p != 0)).any() else None),
                         "directional_n": int((cm & (p != 0)).sum())}
        res["by_confidence"] = byc
    return res


def load_df(sym: str, res: str, last: Optional[int] = None) -> Optional[pd.DataFrame]:
    src = read_json(DATA / "prices" / sym / f"{res}.json")
    if not src or not src["bars"]:
        return None
    b = np.array(src["bars"], dtype=float)
    if last:
        b = b[-last:]
    return pd.DataFrame(b, columns=["t", "o", "h", "l", "c", "v"])


def instruments() -> List[Tuple[str, str]]:
    wl = load_config("watchlist.json")
    out = [(i["symbol"], "gold" if i["type"] == "gold_intl" else "vn") for i in wl["instruments"] if i["type"] in ("stock", "etf", "gold_intl")]
    out += [(i["symbol"], "vn") for i in wl["context_indices"]]
    return out


def pattern_stats(engines: Dict[str, "eg.Engine"]) -> Dict[str, Any]:
    """Thống kê mô tả: sau khi mô hình xuất hiện, hướng kỳ vọng có xảy ra không (so với tỷ lệ nền của cùng hướng)?"""
    agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"n": 0, "h1": [0, 0, 0], "h5": [0, 0, 0], "exp": 0})
    base_counts = {h: {-1: 0, 0: 0, 1: 0} for h in (1, 5, 10)}
    outs = {}
    for sym, e in engines.items():
        for h in (1, 5, 10):
            o = outcomes(e.c, e.atr, h)
            outs[(sym, h)] = o
            for v in (-1, 0, 1):
                base_counts[h][v] += int(np.nansum(o[WARMUP:] == v))
    # nến
    for sym, e in engines.items():
        for r in e.candles:
            if r["dir"] == 0:
                continue
            a = agg["candle:" + r["name"]]
            a["exp"] = r["dir"]; a["label"] = r["label"]
            for h, key in ((1, "h1"), (5, "h5")):
                o = outs[(sym, h)][r["index"]]
                if np.isnan(o):
                    continue
                a[key][0 if o == r["dir"] else (1 if o == -r["dir"] else 2)] += 1
            a["n"] += 1
    # mô hình giá: tính từ nến xác nhận
    for sym, e in engines.items():
        for p in e.charts:
            if p["confirmed_at"] is None:
                continue
            dir_ = p.get("breakout_dir", p["bias"]) if p["type"].endswith("triangle") else p["bias"]
            if not dir_:
                continue
            kname = p["type"] + (":" + ("up" if dir_ > 0 else "down") if p["type"].endswith("triangle") else "")
            a = agg["chart:" + kname]
            a["exp"] = dir_; a["label"] = p["label"] + (" — phá vỡ " + ("lên" if dir_ > 0 else "xuống") if p["type"].endswith("triangle") else "")
            j = p["confirmed_at"]
            for h, key in ((5, "h1"), (10, "h5")):  # với mô hình giá: h1 := 5 nến, h5 := 10 nến
                o = outs[(sym, h)][j]
                if np.isnan(o):
                    continue
                a[key][0 if o == dir_ else (1 if o == -dir_ else 2)] += 1
            a["n"] += 1
            st = a.setdefault("lifecycle", {"target_hit": 0, "failed": 0, "other": 0, "volume_confirmed": 0, "volume_known": 0})
            if p.get("target_hit_at") is not None:
                st["target_hit"] += 1
            elif p.get("failed_at") is not None:
                st["failed"] += 1
            else:
                st["other"] += 1
            if p.get("volume_confirmed") is not None:
                st["volume_known"] += 1
                st["volume_confirmed"] += int(bool(p["volume_confirmed"]))
    out: Dict[str, Any] = {}
    for key, a in sorted(agg.items()):
        row: Dict[str, Any] = {"label": a["label"], "expected_dir": a["exp"], "n": a["n"]}
        kind = key.split(":")[0]
        hmap = (("h1", 1, "1_bar"), ("h5", 5, "5_bar")) if kind == "candle" else (("h1", 5, "5_bar"), ("h5", 10, "10_bar"))
        for k, h, lab in hmap:
            hit, opp, flat = a[k]
            nn = hit + opp + flat
            base = base_counts[h][a["exp"]] / max(1, sum(base_counts[h].values()))
            row[lab] = {"n": nn, "hit": round(hit / nn, 4) if nn else None, "opposite": round(opp / nn, 4) if nn else None,
                        "flat": round(flat / nn, 4) if nn else None, "base_rate_same_dir": round(base, 4),
                        "hit_ci95": wilson(hit, nn)}
        if "lifecycle" in a:
            row["lifecycle"] = a["lifecycle"]
        out[key] = row
    return {"patterns": out, "base_rates": {f"h{h}": {("down" if k == -1 else "flat" if k == 0 else "up"): round(v / max(1, sum(base_counts[h].values())), 4) for k, v in base_counts[h].items()} for h in base_counts}}


def run_daily() -> Dict[str, Any]:
    engines: Dict[str, eg.Engine] = {}
    per: Dict[str, Dict[str, Any]] = {}
    pooled: Dict[str, Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray]]] = {}
    for sym, kind in instruments():
        df = load_df(sym, "D")
        if df is None or len(df) < WARMUP + 50:
            continue
        ind = compute_all(df, with_volume=bool(df["v"].sum() > 0))
        e = eg.Engine(df, ind, kind=kind)
        engines[sym] = e
        per[sym] = {}
        for hz, hs in (("next_session", [1]), ("1_2_weeks", [5, 10])):
            d, cf = e.signal_arrays(hz, start=WARMUP)
            for h in hs:
                o = outcomes(e.c, e.atr, h)
                key = f"{hz}@h{h}"
                per[sym][key] = evaluate(d, o, cf, h, WARMUP)
                pooled.setdefault(key, ([], [], []))
                pooled[key][0].append(d[WARMUP:][~np.isnan(o[WARMUP:])]); pooled[key][1].append(o[WARMUP:][~np.isnan(o[WARMUP:])]); pooled[key][2].append(cf[WARMUP:][~np.isnan(o[WARMUP:])])
        print(f"[daily] {sym:9s} bars={len(df)}")
    ALL: Dict[str, Any] = {}
    for key, (ds, os_, cs) in pooled.items():
        d, o, cf = np.concatenate(ds), np.concatenate(os_), np.concatenate(cs)
        h = int(key.split("@h")[1])
        ALL[key] = evaluate(d, o, cf, h, 0)
    # baseline đơn giản để so sánh: "theo hướng 5 nến gần nhất" (momentum ngây thơ)
    naive: Dict[str, Any] = {}
    for h in (1, 5, 10):
        P, O = [], []
        for sym, e in engines.items():
            c = e.c
            p = np.full(len(c), np.nan)
            for t in range(WARMUP, len(c)):
                if np.isnan(e.atr[t]):
                    continue
                tau = 0.25 * e.atr[t] * math.sqrt(5) / c[t]
                r = c[t] / c[t - 5] - 1
                p[t] = 1 if r > tau else (-1 if r < -tau else 0)
            o = outcomes(c, e.atr, h)
            m = ~np.isnan(p) & ~np.isnan(o)
            P.append(p[m]); O.append(o[m])
        naive[f"h{h}"] = evaluate(np.concatenate(P), np.concatenate(O), None, h, 0)
    return {"per_symbol": per, "pooled": ALL, "naive_momentum_5bar": naive, "pattern_stats": pattern_stats(engines)}


def run_intraday() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for res, last in (("60", 3000), ("15", 4000), ("5", 5000), ("1", 6000)):
        P, O, C = [], [], []
        t0 = time.time()
        for sym, kind in instruments():
            df = load_df(sym, res, last)
            if df is None or len(df) < WARMUP + 100:
                continue
            ind = compute_all(df, with_volume=bool(df["v"].sum() > 0))
            e = eg.Engine(df, ind, kind=kind, intraday=True)
            d, cf = e.signal_arrays("next_session", start=WARMUP)
            o = outcomes(e.c, e.atr, 1)
            m = ~np.isnan(o[WARMUP:]) & ~np.isnan(d[WARMUP:])
            P.append(d[WARMUP:][m]); O.append(o[WARMUP:][m]); C.append(cf[WARMUP:][m])
        if P:
            out[res] = evaluate(np.concatenate(P), np.concatenate(O), np.concatenate(C), 1, 0)
        print(f"[intraday] {res} done in {time.time() - t0:.0f}s")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--intraday", action="store_true", help="cũng chạy khung nội ngày (chậm hơn)")
    args = ap.parse_args(argv)
    res = {"generated_at": now_vn_iso(), "engine_version": eg.ENGINE_VERSION, "warmup_bars": WARMUP, "daily": run_daily()}
    if args.intraday:
        res["intraday_next_bar"] = run_intraday()
    write_json_atomic(DATA / "backtest" / "summary.json", res, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
