"""Dựng bản tin: điền ô thay thế từ dữ liệu dự án → chạy factcheck → kết hợp nhận định kỹ thuật + tin tức → xuất JSON cho trang web.

Đầu vào (reports/):  YYYY-MM-DD.md  (nội dung có nhãn tầng), YYYY-MM-DD.claims.json (nguồn + câu trích), YYYY-MM-DD.outlook.json (lập trường tin tức)
Đầu ra:  site/data/reports/YYYY-MM-DD.json, site/data/reports/index.json, reports/YYYY-MM-DD.outlook.computed.json
Không xuất bản nếu factcheck có lỗi (trừ khi --allow-fail để xem thử, KHÔNG dùng khi đăng).

Dùng:  python -m pipeline.build_report 2026-11-09 [--no-fetch]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import factcheck as fc
from .common import DATA, ROOT, VN_TZ, load_config, now_vn_iso, read_json, write_json_atomic
from .engine import vn
from .fetch_news import article_text

REPORTS = ROOT / "reports"
SITE_REPORTS = ROOT / "site" / "data" / "reports"
CONF_RANK = {"low": 0, "medium": 1, "high": 2}
CONF_VI = {"low": "thấp", "medium": "trung bình", "high": "cao"}
DIR_VI = {1: "tăng", -1: "giảm", 0: "đi ngang"}
HORIZONS = ("next_session", "1_2_weeks")
HZ_VI = {"next_session": "phiên kế tiếp", "1_2_weeks": "1–2 tuần"}


def combine(engine_dir: int, engine_conf: str, stance: int) -> Dict[str, Any]:
    """Quy tắc kết hợp (docs/report-methodology.md §3): tối đa 'trung bình' vì chưa có bằng chứng lợi thế."""
    if engine_dir == 0 and stance == 0:
        return {"direction": 0, "confidence": "low", "relation": "both_neutral", "relation_vi": "cả hai trung lập"}
    if engine_dir != 0 and stance == engine_dir:
        return {"direction": engine_dir, "confidence": min(engine_conf, "medium", key=lambda c: CONF_RANK[c]), "relation": "agree", "relation_vi": "đồng thuận"}
    if engine_dir != 0 and stance == -engine_dir:
        return {"direction": 0, "confidence": "low", "relation": "conflict", "relation_vi": "MÂU THUẪN → trung lập"}
    if engine_dir == 0:
        return {"direction": stance, "confidence": "low", "relation": "news_only", "relation_vi": "chỉ tin tức nghiêng, kỹ thuật trung lập"}
    return {"direction": engine_dir, "confidence": "low", "relation": "tech_only", "relation_vi": "chỉ kỹ thuật nghiêng, tin tức trung lập"}


def pct_s(x: Optional[float], d: int = 1, signed: bool = False) -> str:
    if x is None:
        return "—"
    s = vn(abs(x) * 100 if False else x * 100, d)
    return (("+" if x > 0 else "") if signed else "") + s + "%"


class Resolver:
    def __init__(self, date: str):
        self.date = date
        self.board = {i["symbol"]: i for i in read_json(ROOT / "site" / "data" / "board.json")["items"]}
        self.gold = read_json(ROOT / "site" / "data" / "gold_domestic.json")
        self.analysis = read_json(ROOT / "site" / "data" / "analysis.json")["items"]
        self.bt = (read_json(DATA / "backtest" / "summary.json") or {}).get("daily", {}).get("pooled", {})
        self.journal = read_json(DATA / "predictions" / "summary.json", {})
        self.outlook_rows: List[Dict[str, Any]] = []

    def __call__(self, key: str) -> str:
        p = key.split(":")
        k = p[0]
        if k in ("px", "pct", "chg", "nm", "pt", "ref", "ceil", "floor"):
            it = self.board[p[1]]
            dec = 2 if (it["type"] == "index" or it["symbol"] == "XAUUSD") else 0
            if k == "px": return vn(it["last"], dec)
            if k == "ref": return vn(it["ref"], dec)
            if k == "ceil": return vn(it["ceiling"], 0)
            if k == "floor": return vn(it["floor"], 0)
            if k == "pct": return ("+" if it["pct"] > 0 else "") + vn(it["pct"], 2) + "%"
            if k == "chg": return ("+" if it["change"] > 0 else "") + vn(it["change"], dec)
            if k == "nm": return vn(it["nm_volume"], 0)
            if k == "pt": return vn(it["pt_volume"], 0)
        if k == "gold":
            g, f = self.gold, p[1]
            m = {"spot": vn(g["spot"]["xauusd"], 1), "sjc_buy_m": vn(g["sjc"]["buy"] / 1e6, 1), "sjc_sell_m": vn(g["sjc"]["sell"] / 1e6, 1),
                 "usd_buy": vn(g["usdvnd"]["buy"], 0), "usd_sell": vn(g["usdvnd"]["sell"], 0),
                 "prem_lo": vn(min(g["premium_pct_sjc_sell"].values()), 1) + "%", "prem_hi": vn(max(g["premium_pct_sjc_sell"].values()), 1) + "%",
                 "world_lo_m": vn(min(g["world_vnd_per_luong"].values()) / 1e6, 1), "world_hi_m": vn(max(g["world_vnd_per_luong"].values()) / 1e6, 1),
                 "spot_time": datetime.fromisoformat(g["spot"]["fetched_at"]).strftime("%H:%M ngày %d/%m"),
                 "sjc_time": datetime.fromisoformat(g["sjc"]["quoted_at"]).strftime("%H:%M ngày %d/%m"),
                 "gap_min": vn(g["input_time_gap_minutes"], 0)}
            return m[f]
        if k == "eng":
            a = self.analysis[p[1]]
            x = a["horizons"][p[2]]
            f = p[3]
            if f == "dir": return DIR_VI[x["direction"]]
            if f == "conf": return CONF_VI[x["confidence"]]
            if f == "asof": return datetime.strptime(a["asof_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            if f == "inval": return vn(x["invalidation"]["level"], 0 if p[1] not in ("XAUUSD", "VNINDEX", "VN30") else 2) if x["invalidation"] else "—"
        if k == "bt":
            x = self.bt[p[1]]
            f = p[2]
            if f == "acc": return vn(x["accuracy"] * 100, 1) + "%"
            if f == "indep": return vn(x["accuracy_if_independent"] * 100, 1) + "%"
            if f == "major": return vn(x["always_majority_accuracy"] * 100, 1) + "%"
            if f == "lo": return vn(x["accuracy_ci95_effective"][0] * 100, 1) + "%"
            if f == "hi": return vn(x["accuracy_ci95_effective"][1] * 100, 1) + "%"
            if f == "n": return vn(x["n"], 0)
        if k == "outlook":
            if p[1] == "list":  # outlook:list:<hz>:<relation>
                names = [r["symbol"] for r in self.outlook_rows if r["horizon"] == p[2] and r["relation"] == p[3]]
                return ", ".join(names) if names else "không có mã nào"
            r = next(x for x in self.outlook_rows if x["symbol"] == p[1] and x["horizon"] == p[2])
            return f"{DIR_VI[r['combined_direction']]} (tin cậy {CONF_VI[r['combined_confidence']]})"
        if k == "journal":
            return vn(self.journal.get({"issued": "predictions_issued", "scored": "evaluations_scored"}[p[1]], 0), 0)
        raise KeyError(key)


def compute_outlook(res: Resolver, outlook_doc: Dict[str, Any], claims: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    errs: List[str] = []
    rows: List[Dict[str, Any]] = []
    for sym in [i["symbol"] for i in load_config("watchlist.json")["instruments"] if i["type"] in ("stock", "etf", "gold_intl")]:
        a = res.analysis.get(sym)
        if not a:
            errs.append(f"thiếu phân tích kỹ thuật cho {sym}"); continue
        for hz in HORIZONS:
            st = (outlook_doc.get("stances", {}).get(sym, {}) or {}).get(hz)
            if st is None:
                errs.append(f"outlook thiếu lập trường tin tức cho {sym}/{hz}"); continue
            if st["stance"] != 0 and not st.get("claims"):
                errs.append(f"{sym}/{hz}: lập trường khác 0 nhưng không có trích dẫn")
            for c in st.get("claims", []):
                if c not in claims:
                    errs.append(f"{sym}/{hz}: claim {c} không tồn tại")
            if not st.get("channel"):
                errs.append(f"{sym}/{hz}: thiếu mô tả kênh tác động")
            x = a["horizons"][hz]
            comb = combine(x["direction"], x["confidence"], st["stance"])
            rows.append({"symbol": sym, "horizon": hz, "engine_direction": x["direction"], "engine_confidence": x["confidence"], "engine_asof": a["asof_date"],
                         "news_stance": st["stance"], "news_channel": st["channel"], "news_claims": st.get("claims", []),
                         "combined_direction": comb["direction"], "combined_confidence": comb["confidence"], "relation": comb["relation"], "relation_vi": comb["relation_vi"],
                         "invalidation": x["invalidation"]})
    return rows, errs


def render_blocks(md: str, res: Resolver, claims_doc: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    claims, sources = claims_doc["claims"], claims_doc["sources"]
    order: Dict[str, int] = {}

    def ref_no(sid: str) -> int:
        return order.setdefault(sid, len(order) + 1)

    out: List[Dict[str, Any]] = []
    for b in fc.parse_blocks(md):
        if b["type"] == "heading":
            out.append({"type": "heading", "level": b["level"], "text": b["text"]})
        elif b["type"] == "para":
            text, _ = fc.resolve_placeholders(b["text"], res)
            text = fc.CITE_RE.sub(lambda m: f"[^{ref_no(claims[m.group(1)]['source'])}]", text)
            out.append({"type": "para", "tier": b["tier"], "text": text, "bullet": b["bullet"]})
        elif b["type"] == "raw" and b["text"].strip() == "{{outlook_table}}":
            out.append({"type": "outlook_table"})
    refs = [{"n": n, **{k: sources[sid][k] for k in ("title", "outlet", "url", "kind", "published") if k in sources[sid]}} for sid, n in sorted(order.items(), key=lambda kv: kv[1])]
    return out, refs


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("date")
    ap.add_argument("--no-fetch", action="store_true", help="bỏ qua tải lại nguồn (CHỈ để thử cấu trúc; không dùng khi đăng)")
    ap.add_argument("--allow-fail", action="store_true")
    a = ap.parse_args(argv)
    md = (REPORTS / f"{a.date}.md").read_text(encoding="utf-8")
    claims_doc = json.loads((REPORTS / f"{a.date}.claims.json").read_text(encoding="utf-8"))
    outlook_doc = json.loads((REPORTS / f"{a.date}.outlook.json").read_text(encoding="utf-8"))
    res = Resolver(a.date)
    rows, oerrs = compute_outlook(res, outlook_doc, claims_doc["claims"])
    res.outlook_rows = rows
    idx = read_json(DATA / "news" / "index.json", {})
    result = fc.check(md, claims_doc, res, fetch_text=None if a.no_fetch else (lambda u: article_text(u)), known_links=set(idx))
    result["errors"] += oerrs
    result["ok"] = not result["errors"]
    print(f"Từ: {result['word_count']} | claims: {result['claims']} (đã xác minh trong nguồn: {result['claims_verified']}) | khối: {result['blocks']}")
    for w in result["warnings"]:
        print("  [cảnh báo]", w)
    for e in result["errors"]:
        print("  [LỖI]", e)
    if not result["ok"] and not a.allow_fail:
        print("FACTCHECK KHÔNG ĐẠT — không xuất bản.")
        return 1
    blocks, refs = render_blocks(md, res, claims_doc)
    meta = {k: v.strip() for k, v in re.findall(r"^(\w+):\s*(.+)$", md.split("---")[1] if md.startswith("---") else "", re.M)}
    doc = {"date": a.date, "title": meta.get("title", a.date), "asof": meta.get("asof"), "generated_at": now_vn_iso(), "word_count": result["word_count"],
           "factcheck": {"ok": result["ok"], "claims": result["claims"], "claims_verified": result["claims_verified"], "checked_at": now_vn_iso(),
                         "rules": "pipeline/factcheck.py", "warnings": result["warnings"]},
           "blocks": blocks, "refs": refs, "outlook": rows, "outlook_rule": "docs/report-methodology.md §3",
           "disclaimer": "Nội dung phục vụ nghiên cứu và học tập, không phải khuyến nghị đầu tư. Mọi quyết định đầu tư thuộc về người dùng."}
    write_json_atomic(SITE_REPORTS / f"{a.date}.json", doc)
    write_json_atomic(REPORTS / f"{a.date}.outlook.computed.json", {"date": a.date, "generated_at": now_vn_iso(), "rows": rows})
    index = [r for r in read_json(SITE_REPORTS / "index.json", []) if r["date"] != a.date]
    index.append({"date": a.date, "title": doc["title"], "word_count": doc["word_count"], "asof": doc["asof"], "factcheck_ok": result["ok"]})
    index.sort(key=lambda r: r["date"], reverse=True)
    write_json_atomic(SITE_REPORTS / "index.json", index)
    print(f"Đã xuất bản site/data/reports/{a.date}.json ({len(refs)} nguồn, {len(rows)} dòng nhận định)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
