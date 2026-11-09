"""Sổ nhật ký dự đoán (CLAUDE.md §5.4, docs/methodology.md §2–3, §7b).

  python -m pipeline.journal issue   # phát hành nhận định cho nến ngày hoàn tất gần nhất (idempotent, KHÔNG bao giờ ghi đè nhận định đã phát hành)
  python -m pipeline.journal score   # chấm các nhận định đã đến hạn bằng giá thật (thêm mục `evaluations`, không sửa phần phát hành)
  python -m pipeline.journal stats   # tổng hợp → data/predictions/summary.json
  python -m pipeline.journal all

Quy tắc chấm: ngưỡng τ cố định tại thời điểm phát hành; tăng nếu C_{t+h}/C_t − 1 > τ, giảm nếu < −τ, còn lại đi ngang.
C_t và C_{t+h} cùng lấy từ chuỗi giá đã điều chỉnh HIỆN TẠI để sự kiện doanh nghiệp xen giữa không làm sai lệch; vẫn gắn cờ
`adjustment_event` nếu hệ số điều chỉnh của nến tham chiếu đã đổi kể từ lúc phát hành (để loại khỏi thống kê nếu muốn).
Chống nhìn trước: chỉ phát hành khi nến tham chiếu vừa hoàn tất và chưa có nến mới bắt đầu (xem `fresh_enough`).
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import engine as eg
from .backtest import wilson
from .build_indicators import is_partial
from .common import DATA, ROOT, VN_TZ, load_config, now_vn_iso, read_json, write_json_atomic
from .indicators import compute_all

HORIZON_EVAL = {"next_session": [1], "1_2_weeks": [5, 10]}
WINDOW = 900
MAX_STALE_H = {"vn": 66.0, "gold": 4.0}   # giờ tối đa từ lúc nến tham chiếu hoàn tất (VN: gồm cuối tuần)
MIN_SAMPLE = 30


def vn_date(t: float) -> str:
    return datetime.fromtimestamp(t, VN_TZ).strftime("%Y-%m-%d")


def watch_instruments() -> List[Dict[str, Any]]:
    wl = load_config("watchlist.json")
    out = []
    for i in wl["instruments"]:
        if i["type"] in ("stock", "etf"):
            out.append({"symbol": i["symbol"], "kind": "vn", "type": i["type"], "name": i["name"]})
        elif i["type"] == "gold_intl":
            out.append({"symbol": i["symbol"], "kind": "gold", "type": i["type"], "name": i["name"]})
    return out


def load_daily(data_dir: Path, sym: str) -> Optional[pd.DataFrame]:
    src = read_json(data_dir / "prices" / sym / "D.json")
    if not src or not src["bars"]:
        return None
    return pd.DataFrame(np.array(src["bars"], dtype=float), columns=["t", "o", "h", "l", "c", "v"])


def complete_time(kind: str, t: float) -> float:
    """Thời điểm nến ngày t hoàn tất (xấp xỉ): VN = 15:00 giờ VN cùng ngày; vàng = t + 24h."""
    if kind == "vn":
        return datetime.fromtimestamp(t, VN_TZ).replace(hour=15, minute=0, second=0, microsecond=0).timestamp()
    return t + 86400


def last_complete_index(df: pd.DataFrame, kind: str, now: float) -> Optional[int]:
    for i in range(len(df) - 1, -1, -1):
        if not is_partial(kind, "D", int(df["t"].iloc[i]), now):
            return i
    return None


def fresh_enough(df: pd.DataFrame, idx: int, kind: str, now: float, data_dir: Path, sym: str) -> Tuple[bool, str]:
    if idx != len(df) - 1:
        return False, "đã có nến ngày mới hơn nến tham chiếu (nến mới đang chạy hoặc đã bắt đầu) — bỏ qua để tránh nhìn trước"
    age_h = (now - complete_time(kind, float(df["t"].iloc[idx]))) / 3600
    if age_h > MAX_STALE_H[kind]:
        return False, f"nến tham chiếu hoàn tất cách đây {age_h:.1f} giờ (> {MAX_STALE_H[kind]:g} giờ) — dữ liệu sau đó có thể đã biết, bỏ qua"
    if kind == "vn":
        m1 = read_json(data_dir / "prices" / sym / "1.json")
        if m1 and m1["bars"] and vn_date(m1["bars"][-1][0]) > vn_date(df["t"].iloc[idx]):
            return False, "đã có nến phút của phiên sau nến tham chiếu — bỏ qua để tránh nhìn trước"
    return True, ""


def build_prediction(sym: str, ins: Dict[str, Any], df: pd.DataFrame, full_ind: pd.DataFrame, idx: int, horizon: str,
                     now: float, fetched_at: Optional[str], data_dir: Path) -> Dict[str, Any]:
    lo = max(0, len(df) - WINDOW)
    d, ind = df.iloc[lo:].reset_index(drop=True), full_ind.iloc[lo:].reset_index(drop=True)
    e = eg.Engine(d, ind, kind=ins["kind"], dec=0 if (ins["kind"] == "vn" and ins["type"] != "index") else 2)
    i = idx - lo
    x = e.explain(i, horizon)
    c, a = float(e.c[i]), float(e.atr[i])
    taus = {str(h): round(0.25 * a * math.sqrt(h) / c, 6) for h in HORIZON_EVAL[horizon]}
    # giá thực tế (chưa điều chỉnh) của ngày tham chiếu từ finfo nếu có
    actual = None
    sess = read_json(data_dir / "session" / f"{sym}.json")
    if sess:
        for r in sess["rows"]:
            if r["date"] == vn_date(df["t"].iloc[idx]):
                actual = round(r["close"] * 1000, 2)
    return {
        "id": f"{vn_date(df['t'].iloc[idx])}_{sym}_{horizon}", "symbol": sym, "horizon": horizon,
        "issued_at": datetime.fromtimestamp(now, VN_TZ).replace(microsecond=0).isoformat(),
        "asof_date": vn_date(df["t"].iloc[idx]), "asof_bar_t": int(df["t"].iloc[idx]), "data_as_of_fetch": fetched_at,
        "direction": x["direction"], "direction_vi": x["direction_vi"], "confidence": x["confidence"], "confluence": x["confluence"],
        "tau": taus, "tau_rule": "0,25·ATR14·√h / giá đóng cửa tham chiếu (đã điều chỉnh)",
        "reference_close_adjusted": round(c, 4), "reference_close_actual": actual,
        "atr14": round(a, 4), "invalidation": x["invalidation"], "scenario_main": x["scenario_main"], "scenario_alt": x["scenario_alt"],
        "groups": [{k: g[k] for k in ("group", "group_vi", "vote", "reading", "text", "evidence", "na")} for g in x["groups"]],
        "counter_arguments": x["counter_arguments"], "notes": x["notes"], "levels": x["levels"],
        "price_basis": {"adjusted": ins["kind"] == "vn" and ins["type"] != "index", "futures": ins["kind"] == "gold"},
        "engine_version": eg.ENGINE_VERSION, "rules_doc": "docs/analysis.md", "basis": "engine", "evaluations": [],
    }


def day_file(data_dir: Path, asof: str) -> Path:
    return data_dir / "predictions" / f"{asof}.json"


def issue(now: Optional[float] = None, data_dir: Path = DATA, instruments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    now = time.time() if now is None else now
    created, skipped = [], []
    for ins in instruments or watch_instruments():
        sym = ins["symbol"]
        df = load_daily(data_dir, sym)
        if df is None or len(df) < 300:
            skipped.append((sym, "thiếu dữ liệu ngày")); continue
        idx = last_complete_index(df, ins["kind"], now)
        if idx is None:
            skipped.append((sym, "không có nến hoàn tất")); continue
        ok, why = fresh_enough(df, idx, ins["kind"], now, data_dir, sym)
        if not ok:
            skipped.append((sym, why)); continue
        full_ind = compute_all(df, with_volume=bool(df["v"].sum() > 0))
        if np.isnan(full_ind["atr14"].iloc[idx]):
            skipped.append((sym, "chưa đủ dữ liệu ATR")); continue
        meta = (read_json(data_dir / "prices" / sym / "D.json") or {}).get("meta", {})
        asof = vn_date(df["t"].iloc[idx])
        path = day_file(data_dir, asof)
        doc = read_json(path, {"asof_date": asof, "predictions": []})
        have = {p["id"] for p in doc["predictions"]}
        for hz in eg.HORIZONS:
            pid = f"{asof}_{sym}_{hz}"
            if pid in have:
                skipped.append((pid, "đã phát hành trước đó — không ghi đè")); continue
            doc["predictions"].append(build_prediction(sym, ins, df, full_ind, idx, hz, now, meta.get("fetched_at"), data_dir))
            created.append(pid)
        write_json_atomic(path, doc, indent=1)
    return {"created": created, "skipped": skipped}


def issue_combined(report_date: str, now: Optional[float] = None, data_dir: Path = DATA, instruments: Optional[List[Dict[str, Any]]] = None,
                   outlook_path: Optional[Path] = None) -> Dict[str, Any]:
    """Phát hành nhận định KẾT HỢP (kỹ thuật + tin tức) từ bản tin; id có hậu tố _news, basis = 'engine+news'. Cùng quy tắc chống nhìn trước và bất biến như `issue`."""
    now = time.time() if now is None else now
    comp = read_json(outlook_path or (ROOT / "reports" / f"{report_date}.outlook.computed.json"))
    if not comp:
        return {"created": [], "skipped": [("*", f"chưa có outlook của bản tin {report_date}")]}
    rows = {(r["symbol"], r["horizon"]): r for r in comp["rows"]}
    created, skipped = [], []
    for ins in instruments or watch_instruments():
        sym = ins["symbol"]
        df = load_daily(data_dir, sym)
        if df is None or len(df) < 300:
            skipped.append((sym, "thiếu dữ liệu ngày")); continue
        idx = last_complete_index(df, ins["kind"], now)
        if idx is None:
            skipped.append((sym, "không có nến hoàn tất")); continue
        ok, why = fresh_enough(df, idx, ins["kind"], now, data_dir, sym)
        if not ok:
            skipped.append((sym, why)); continue
        asof = vn_date(df["t"].iloc[idx])
        full_ind = compute_all(df, with_volume=bool(df["v"].sum() > 0))
        meta = (read_json(data_dir / "prices" / sym / "D.json") or {}).get("meta", {})
        path = day_file(data_dir, asof)
        doc = read_json(path, {"asof_date": asof, "predictions": []})
        have = {p["id"] for p in doc["predictions"]}
        for hz in eg.HORIZONS:
            r = rows.get((sym, hz))
            pid = f"{asof}_{sym}_{hz}_news"
            if r is None:
                skipped.append((pid, "bản tin không có dòng nhận định")); continue
            if pid in have:
                skipped.append((pid, "đã phát hành trước đó — không ghi đè")); continue
            if r["engine_asof"] != asof:
                skipped.append((pid, f"nến kỹ thuật của bản tin ({r['engine_asof']}) khác nến tham chiếu hiện tại ({asof})")); continue
            p = build_prediction(sym, ins, df, full_ind, idx, hz, now, meta.get("fetched_at"), data_dir)
            p["id"] = pid
            p["basis"] = "engine+news"
            p["engine_only"] = {"direction": p["direction"], "confidence": p["confidence"]}
            p["direction"] = r["combined_direction"]
            p["direction_vi"] = {1: "Tăng", -1: "Giảm", 0: "Đi ngang / chưa rõ"}[r["combined_direction"]]
            p["confidence"] = r["combined_confidence"]
            p["news"] = {"report_date": report_date, "stance": r["news_stance"], "channel": r["news_channel"], "claims": r["news_claims"],
                         "relation": r["relation"], "relation_vi": r["relation_vi"]}
            p["rules_doc"] = "docs/report-methodology.md §3"
            if r["combined_direction"] != r["engine_direction"]:
                p["invalidation"] = None
                p["scenario_main"] = "Nhận định kết hợp khác với kết luận thuần kỹ thuật; xem kênh tác động tin tức."
                p["scenario_alt"] = ""
            doc["predictions"].append(p)
            created.append(pid)
        write_json_atomic(path, doc, indent=1)
    return {"created": created, "skipped": skipped}


def score(now: Optional[float] = None, data_dir: Path = DATA, instruments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    now = time.time() if now is None else now
    kinds = {i["symbol"]: i["kind"] for i in (instruments or watch_instruments())}
    cache: Dict[str, Optional[pd.DataFrame]] = {}
    newly = 0
    pending = 0
    for path in sorted((data_dir / "predictions").glob("????-??-??.json")):
        doc = read_json(path)
        changed = False
        for p in doc["predictions"]:
            sym = p["symbol"]
            if sym not in cache:
                cache[sym] = load_daily(data_dir, sym)
            df = cache[sym]
            if df is None:
                continue
            kind = kinds.get(sym, "vn")
            ts = df["t"].to_numpy()
            where = np.flatnonzero(np.array([vn_date(t) for t in ts]) == p["asof_date"])
            if len(where) == 0:
                continue
            i0 = int(where[0])
            ref_now = float(df["c"].iloc[i0])
            ratio = ref_now / p["reference_close_adjusted"]
            done = {e["h"] for e in p["evaluations"]}
            for h in HORIZON_EVAL[p["horizon"]]:
                if h in done:
                    continue
                j = i0 + h
                if j >= len(df) or is_partial(kind, "D", int(ts[j]), now):
                    pending += 1
                    continue
                tau = p["tau"][str(h)]
                r = float(df["c"].iloc[j]) / ref_now - 1
                outcome = 1 if r > tau else (-1 if r < -tau else 0)
                p["evaluations"].append({
                    "h": h, "eval_date": vn_date(ts[j]), "scored_at": now_vn_iso(), "close_adjusted_at_scoring": round(float(df["c"].iloc[j]), 4),
                    "reference_close_adjusted_at_scoring": round(ref_now, 4), "return": round(r, 6), "tau": tau,
                    "outcome": outcome, "outcome_vi": {1: "tăng", -1: "giảm", 0: "đi ngang"}[outcome],
                    "correct": outcome == p["direction"], "adjustment_event": abs(ratio - 1) > 1e-4, "adjustment_ratio": round(ratio, 6)})
                changed = True; newly += 1
        if changed:
            write_json_atomic(path, doc, indent=1)
    return {"newly_scored_evaluations": newly, "still_pending": pending}


def stats(data_dir: Path = DATA) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    total_pred = 0
    first = last = None
    for path in sorted((data_dir / "predictions").glob("????-??-??.json")):
        for p in read_json(path)["predictions"]:
            total_pred += 1
            first = first or p["asof_date"]; last = p["asof_date"]
            for e in p["evaluations"]:
                rows.append({"basis": p.get("basis", "engine"), "symbol": p["symbol"], "horizon": p["horizon"], "h": e["h"], "direction": p["direction"], "confidence": p["confidence"],
                             "correct": e["correct"], "outcome": e["outcome"], "adj": e["adjustment_event"]})

    def agg(sel: List[Dict[str, Any]]) -> Dict[str, Any]:
        n = len(sel)
        k = sum(1 for r in sel if r["correct"])
        flat = sum(1 for r in sel if r["outcome"] == 0)
        return {"n": n, "correct": k, "accuracy": round(k / n, 4) if n else None, "ci95": wilson(k, n),
                "share_outcome_flat": round(flat / n, 4) if n else None, "enough_sample": n >= MIN_SAMPLE}

    out: Dict[str, Any] = {"generated_at": now_vn_iso(), "predictions_issued": total_pred, "first_asof": first, "last_asof": last,
                           "evaluations_scored": len(rows), "min_sample_for_meaning": MIN_SAMPLE,
                           "excluding_adjustment_events": agg([r for r in rows if not r["adj"]]), "overall": agg(rows),
                           "by_horizon": {}, "by_symbol": {}, "by_confidence": {}, "by_direction": {}, "by_basis": {}}
    for key, field in (("by_basis", lambda r: r["basis"]), ("by_horizon", lambda r: f"{r['horizon']}@h{r['h']}"), ("by_symbol", lambda r: r["symbol"]),
                       ("by_confidence", lambda r: r["confidence"]), ("by_direction", lambda r: {1: "up", -1: "down", 0: "flat"}[r["direction"]])):
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            groups.setdefault(field(r), []).append(r)
        out[key] = {k: agg(v) for k, v in sorted(groups.items())}
    out["note"] = ("Tỷ lệ đúng chỉ có ý nghĩa khi n ≥ 30 và phải so với đường cơ sở (share_outcome_flat = tỷ lệ kết quả 'đi ngang'; "
                   "xem thêm docs/backtest.md cho kết quả lịch sử). Mẫu chồng lấn ở khung 1–2 tuần.")
    write_json_atomic(data_dir / "predictions" / "summary.json", out, indent=1)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["issue", "issue-combined", "score", "stats", "all"])
    ap.add_argument("--report", help="ngày bản tin (YYYY-MM-DD) cho issue-combined")
    a = ap.parse_args(argv)
    if a.cmd in ("issue", "all"):
        r = issue()
        print(f"[issue] phát hành {len(r['created'])}: {r['created']}")
        for s, why in r["skipped"]:
            print(f"[issue] bỏ qua {s}: {why}")
    if a.cmd == "issue-combined" or (a.cmd == "all" and a.report):
        r = issue_combined(a.report)
        print(f"[issue-combined] phát hành {len(r['created'])}: {r['created']}")
        for s, why in r["skipped"]:
            print(f"[issue-combined] bỏ qua {s}: {why}")
    if a.cmd in ("score", "all"):
        print("[score]", score())
    if a.cmd in ("stats", "all"):
        s = stats()
        print(f"[stats] đã phát hành {s['predictions_issued']} nhận định, đã chấm {s['evaluations_scored']} lượt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
