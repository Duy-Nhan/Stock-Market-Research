"""Ảnh chụp (snapshot) các chuỗi không có lịch sử từ nguồn, và dữ liệu phiên từ finfo.

  data/snapshots/gold_spot.jsonl   giá spot XAU/USD hiện tại (gold-api.com, Swissquote)
  data/snapshots/sjc.jsonl         giá vàng miếng SJC mua/bán (qua vnappmob)
  data/snapshots/usdvnd.jsonl      tỷ giá USD/VND Vietcombank
  data/session/<SYMBOL>.json       finfo: tham chiếu/trần/sàn, KL khớp lệnh & thỏa thuận theo ngày

Snapshot được nối vào JSONL, bỏ qua bản ghi trùng mốc thời gian của nguồn.
Dùng:  python -m pipeline.fetch_snapshots [--only gold sjc usdvnd session] [--session-days 400]
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .common import DATA, VN_TZ, FetchError, get_json, http_get, load_config, now_vn_iso, write_json_atomic

GOLD_API = "https://api.gold-api.com/price/XAU"
SWISSQUOTE = "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD"
VNAPPMOB_KEY = "https://api.vnappmob.com/api/request_api_key?scope=gold"
VNAPPMOB_SJC = "https://api.vnappmob.com/api/v2/gold/sjc"
VCB_FX = "https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXML.aspx?b=10"
FINFO = "https://api-finfo.vndirect.com.vn/v4"


def append_jsonl(name: str, record: Dict[str, Any], dedupe_key: str) -> bool:
    """Nối record; trả False nếu đã có bản ghi cùng dedupe_key."""
    p = DATA / "snapshots" / f"{name}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and json.loads(line).get(dedupe_key) == record.get(dedupe_key):
                    return False
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return True


def snap_gold_spot() -> Dict[str, Any]:
    rec: Dict[str, Any] = {"fetched_at": now_vn_iso()}
    errs = []
    try:
        g = get_json(GOLD_API)
        rec["gold_api"] = {"price": g["price"], "source_updated_at": g.get("updatedAt")}
    except (FetchError, KeyError) as e:
        errs.append(f"gold_api: {e}")
    try:
        s = get_json(SWISSQUOTE)
        prime = next(x for x in s[0]["spreadProfilePrices"] if x["spreadProfile"] == "prime")
        rec["swissquote_prime"] = {"bid": prime["bid"], "ask": prime["ask"], "source_ts_ms": s[0]["ts"]}
    except (FetchError, KeyError, StopIteration, IndexError) as e:
        errs.append(f"swissquote: {e}")
    if errs:
        rec["errors"] = errs
    if "gold_api" not in rec and "swissquote_prime" not in rec:
        raise FetchError("; ".join(errs))
    key = (rec.get("swissquote_prime") or {}).get("source_ts_ms") or (rec.get("gold_api") or {}).get("source_updated_at")
    rec["dedupe"] = f"{key}"
    rec["added"] = append_jsonl("gold_spot", rec, "dedupe")
    return rec


def snap_sjc() -> Dict[str, Any]:
    key = get_json(VNAPPMOB_KEY)["results"]  # khóa hết hạn sau 15 ngày -> xin mới mỗi lần
    d = get_json(VNAPPMOB_SJC, headers={"Authorization": f"Bearer {key}"})["results"][0]
    rec = {
        "fetched_at": now_vn_iso(), "source": "vnappmob:/api/v2/gold/sjc (bên thứ ba, không phải SJC chính thức)",
        "source_datetime": int(d["datetime"]), "unit": "đồng/lượng",
        "buy_1l": float(d["buy_1l"]), "sell_1l": float(d["sell_1l"]),
        "buy_nhan1c": float(d["buy_nhan1c"]), "sell_nhan1c": float(d["sell_nhan1c"]),
    }
    rec["added"] = append_jsonl("sjc", rec, "source_datetime")
    return rec


def snap_usdvnd() -> Dict[str, Any]:
    root = ET.fromstring(http_get(VCB_FX).decode("utf-8-sig").strip())
    usd = next((e for e in root.findall("Exrate") if e.get("CurrencyCode") == "USD"), None)
    if usd is None:
        raise FetchError("Không thấy USD trong XML Vietcombank")
    num = lambda s: float(s.replace(",", ""))
    rec = {"fetched_at": now_vn_iso(), "source": "vietcombank:pXML", "source_datetime": root.findtext("DateTime"),
           "buy": num(usd.get("Buy")), "transfer": num(usd.get("Transfer")), "sell": num(usd.get("Sell")),
           "note": "Nguồn yêu cầu tối đa 1 request/5 phút"}
    rec["added"] = append_jsonl("usdvnd", rec, "source_datetime")
    return rec


def fetch_session(symbol: str, days: int) -> int:
    since = (datetime.now(VN_TZ) - timedelta(days=days)).strftime("%Y-%m-%d")
    rows: List[Dict[str, Any]] = []
    page = 1
    while True:
        j = get_json(f"{FINFO}/stock_prices?q=code:{symbol}~date:gte:{since}&sort=date&size=500&page={page}")
        rows += j["data"]
        if page >= j.get("totalPages", 1):
            break
        page += 1
    keep = ("date", "basicPrice", "ceilingPrice", "floorPrice", "open", "high", "low", "close", "adClose",
            "nmVolume", "ptVolume", "nmValue", "ptValue")
    out = [{k: r.get(k) for k in keep} for r in rows]
    write_json_atomic(DATA / "session" / f"{symbol}.json", {
        "meta": {"symbol": symbol, "source": "vndirect:finfo /v4/stock_prices", "price_unit": "nghìn đồng (giữ nguyên như nguồn)",
                 "fetched_at": now_vn_iso(), "rows": len(out), "since": since}, "rows": out})
    return len(out)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", choices=["gold", "sjc", "usdvnd", "session"], default=["gold", "sjc", "usdvnd", "session"])
    ap.add_argument("--session-days", type=int, default=400)
    args = ap.parse_args(argv)
    fails = 0
    jobs = {"gold": snap_gold_spot, "sjc": snap_sjc, "usdvnd": snap_usdvnd}
    for name in args.only:
        if name == "session":
            continue
        try:
            r = jobs[name]()
            print(f"[ok]   {name:7s} added={r.get('added')}  {({k: v for k, v in r.items() if k not in ('fetched_at', 'added', 'dedupe')})}")
        except (FetchError, KeyError, ValueError, ET.ParseError) as e:
            fails += 1
            print(f"[FAIL] {name}: {e}", file=sys.stderr)
    if "session" in args.only:
        wl = load_config("watchlist.json")
        for ins in wl["instruments"]:
            if ins["type"] in ("stock", "etf"):
                try:
                    n = fetch_session(ins["symbol"], args.session_days)
                    print(f"[ok]   session {ins['symbol']:9s} rows={n}")
                except (FetchError, KeyError) as e:
                    fails += 1
                    print(f"[FAIL] session {ins['symbol']}: {e}", file=sys.stderr)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
