"""Lấy OHLCV, chuẩn hóa và lưu vào data/prices/<SYMBOL>/<res>.json.

Nguồn:
  - Cổ phiếu/ETF/chỉ số VN: VNDirect dchart (giá nghìn đồng -> nhân 1000; chỉ số giữ nguyên điểm).
  - XAUUSD: Yahoo GC=F (futures COMEX, KHÔNG phải spot) — meta ghi rõ.

Định dạng file: {"meta": {...}, "bars": [[t_unix, o, h, l, c, v], ...]} sắp theo t tăng dần.
Hợp nhất tăng dần: nến mới ghi đè nến cũ cùng t (để sửa nến đang chạy dở).
Mọi bất thường dữ liệu được ĐẾM và ghi vào meta.anomalies — không âm thầm loại bỏ.

Dùng:  python -m pipeline.fetch_prices [--symbols FPT VCB] [--res D 60 15 5 1] [--full]
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from .common import DATA, FetchError, get_json, load_config, now_vn_iso, read_json, ts_to_vn_iso, write_json_atomic

DCHART = "https://dchart-api.vndirect.com.vn/dchart/history"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={iv}&range={rg}"

# Số ngày lịch sử lấy ở lần đầu (giới hạn dung lượng repo). Nến phút chỉ giữ gần đây cho replay.
RETENTION_DAYS = {"D": 4000, "60": 900, "15": 400, "5": 400, "1": 90}
RES_SECONDS = {"D": 86400, "60": 3600, "15": 900, "5": 300, "1": 60}
YAHOO_MAP = {"D": ("1d", "10y"), "60": ("1h", "730d"), "15": ("15m", "60d"), "5": ("5m", "60d"), "1": ("1m", "7d")}
POLITE_SLEEP = 0.3


# ----------------------------------------------------------------------------- chuẩn hóa/kiểm tra
def normalize_dchart(payload: Dict[str, Any], multiplier: float) -> List[List[float]]:
    """dchart trả các mảng song song t,o,h,l,c,v. Nhân giá theo multiplier (nghìn đồng -> đồng)."""
    if payload.get("s") != "ok":
        if payload.get("s") == "no_data":
            return []
        raise FetchError(f"dchart trả trạng thái bất thường: {str(payload)[:150]}")
    n = len(payload["t"])
    for k in ("o", "h", "l", "c", "v"):
        if len(payload[k]) != n:
            raise FetchError(f"dchart: độ dài mảng '{k}' khác 't'")
    bars = []
    for i in range(n):
        o, h, l, c, v = (payload[k][i] for k in ("o", "h", "l", "c", "v"))
        bars.append([int(payload["t"][i]), round(o * multiplier, 4), round(h * multiplier, 4),
                     round(l * multiplier, 4), round(c * multiplier, 4), v])
    return bars


def normalize_yahoo(payload: Dict[str, Any]) -> Tuple[List[List[float]], Dict[str, Any]]:
    res = payload["chart"]["result"]
    if not res:
        raise FetchError(f"Yahoo không có dữ liệu: {payload['chart'].get('error')}")
    r = res[0]
    q = r["indicators"]["quote"][0]
    bars, dropped, synthetic = [], 0, 0
    for i, t in enumerate(r.get("timestamp") or []):
        o, h, l, c, v = (q[k][i] for k in ("open", "high", "low", "close", "volume"))
        if None in (o, h, l, c):  # Yahoo trả null cho phút không có giao dịch
            dropped += 1
            continue
        if int(t) % 60 != 0:  # Yahoo gắn thêm một "nến" giả mang giá hiện tại (O=H=L=C, KL=0, giây lẻ); nến thật luôn tròn phút
            synthetic += 1
            continue
        bars.append([int(t), round(o, 4), round(h, 4), round(l, 4), round(c, 4), v or 0])
    return bars, {"null_bars_skipped": dropped, "synthetic_quote_bars_dropped": synthetic, "yahoo_meta": {k: r["meta"].get(k) for k in (
        "symbol", "exchangeName", "instrumentType", "currency", "timezone", "dataGranularity")}}


def validate_bars(bars: List[List[float]]) -> Dict[str, Any]:
    """Đếm bất thường; không sửa dữ liệu."""
    a = {"non_monotonic_time": 0, "duplicate_time": 0, "high_below_low": 0, "ohlc_out_of_range": 0,
         "non_positive_price": 0, "negative_volume": 0, "zero_volume_bars": 0}
    examples: List[str] = []
    prev_t = None
    for t, o, h, l, c, v in bars:
        if prev_t is not None:
            if t == prev_t:
                a["duplicate_time"] += 1
            elif t < prev_t:
                a["non_monotonic_time"] += 1
        prev_t = t
        if h < l:
            a["high_below_low"] += 1
        if not (l <= o <= h and l <= c <= h):
            a["ohlc_out_of_range"] += 1
            if len(examples) < 5:
                examples.append(f"{ts_to_vn_iso(t)} o={o} h={h} l={l} c={c}")
        if min(o, h, l, c) <= 0:
            a["non_positive_price"] += 1
        if v is not None and v < 0:
            a["negative_volume"] += 1
        if not v:
            a["zero_volume_bars"] += 1
    return {"counts": a, "examples": examples}


def merge_bars(old: List[List[float]], new: List[List[float]]) -> List[List[float]]:
    d = {int(b[0]): b for b in old}
    for b in new:
        d[int(b[0])] = b  # nến mới thắng
    return [d[k] for k in sorted(d)]


# ----------------------------------------------------------------------------- lấy dữ liệu
def path_for(symbol: str, res: str):
    return DATA / "prices" / symbol / f"{res}.json"


def plan_window(existing: Optional[Dict[str, Any]], res: str, now: int, full: bool) -> int:
    """Trả về mốc 'from' (unix). Có dữ liệu cũ -> chỉ lấy phần mới, lùi lại để ghi đè nến dở dang."""
    horizon = now - RETENTION_DAYS[res] * 86400
    if full or not existing or not existing.get("bars"):
        return horizon
    last_t = existing["bars"][-1][0]
    overlap = max(2 * RES_SECONDS[res], 86400) if res != "D" else 5 * 86400
    return max(horizon, last_t - overlap)


def fetch_dchart_symbol(symbol: str, multiplier: float, res: str, full: bool) -> Dict[str, Any]:
    now = int(time.time())
    p = path_for(symbol, res)
    existing = read_json(p)
    frm = plan_window(existing, res, now, full)
    horizon = now - RETENTION_DAYS[res] * 86400
    url = f"{DCHART}?symbol={symbol}&resolution={res}&from={frm}&to={now}"
    new = normalize_dchart(get_json(url), multiplier)
    old = existing["bars"] if existing else []
    refetch_reason = None
    if old and not full:
        # dchart trả giá ĐÃ ĐIỀU CHỈNH theo sự kiện doanh nghiệp; khi có sự kiện mới, toàn bộ lịch sử cũ bị tính lại.
        # Nếu phần chồng lấn lệch so với bản đã lưu thì phải lấy lại toàn bộ để chuỗi không bị đứt gãy.
        oldmap = {b[0]: b for b in old[:-2]}  # bỏ 2 nến cuối (có thể là nến dở dang)
        mism = [b[0] for b in new if b[0] in oldmap and abs(b[4] / oldmap[b[0]][4] - 1) > 1e-4]
        if mism:
            refetch_reason = f"phát hiện điều chỉnh giá: {len(mism)} nến chồng lấn lệch (vd {ts_to_vn_iso(mism[0])})"
            new = normalize_dchart(get_json(f"{DCHART}?symbol={symbol}&resolution={res}&from={horizon}&to={now}"), multiplier)
            old = []
    bars = [b for b in merge_bars(old, new) if b[0] >= horizon]
    meta = {
        "symbol": symbol, "resolution": res, "source": "vndirect:dchart", "url_template": DCHART,
        "instrument_kind": "index" if multiplier == 1 else "vn_equity_or_etf",
        "price_unit_raw": "nghìn đồng" if multiplier != 1 else "điểm", "price_multiplier": multiplier,
        "price_unit_stored": "đồng" if multiplier != 1 else "điểm",
        "volume_semantics": "khối lượng khớp lệnh (không gồm thỏa thuận)",
        "price_adjustment": "ĐÃ ĐIỀU CHỈNH theo sự kiện doanh nghiệp tới thời điểm lấy (đối chiếu finfo adClose); lịch sử bị tính lại khi có sự kiện mới",
        "timestamp_semantics": "unix giây (UTC); nhãn = THỜI ĐIỂM BẮT ĐẦU nến (nến t hoàn tất khi now >= t + độ dài khung); xem docs/data-quality.md",
        "refetch_reason": refetch_reason,
        "fetched_at": now_vn_iso(), "new_bars_this_run": len(new),
        "bars_count": len(bars), "first_bar": ts_to_vn_iso(bars[0][0]) if bars else None,
        "last_bar": ts_to_vn_iso(bars[-1][0]) if bars else None,
        "anomalies": validate_bars(bars),
    }
    write_json_atomic(p, {"meta": meta, "bars": bars})
    return meta


def fetch_yahoo_gold(res: str, full: bool) -> Dict[str, Any]:
    symbol = "XAUUSD"
    iv, rg = YAHOO_MAP[res]
    p = path_for(symbol, res)
    existing = read_json(p)
    new, extra = normalize_yahoo(get_json(YAHOO.format(sym="GC=F", iv=iv, rg=rg)))
    bars = [b for b in merge_bars(existing["bars"] if existing else [], new) if b[0] % 60 == 0]  # dọn cả nến giả đã lưu trước đây
    meta = {
        "symbol": symbol, "resolution": res, "source": "yahoo:GC=F",
        "instrument_kind": "futures_comex_NOT_SPOT",
        "warning": "GC=F là hợp đồng tương lai vàng COMEX (front-month), không phải spot XAU/USD; có basis và có thể nhảy giá khi chuyển hợp đồng.",
        "price_unit_stored": "USD/oz", "volume_semantics": "khối lượng hợp đồng futures (không phải thanh khoản spot)",
        "fetched_at": now_vn_iso(), "new_bars_this_run": len(new), "bars_count": len(bars),
        "first_bar": ts_to_vn_iso(bars[0][0]) if bars else None, "last_bar": ts_to_vn_iso(bars[-1][0]) if bars else None,
        "anomalies": validate_bars(bars), **extra,
    }
    write_json_atomic(p, {"meta": meta, "bars": bars})
    return meta


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="*", help="mặc định: toàn bộ watchlist + chỉ số ngữ cảnh")
    ap.add_argument("--res", nargs="*", default=list(RETENTION_DAYS), choices=list(RETENTION_DAYS))
    ap.add_argument("--full", action="store_true", help="bỏ qua tăng dần, lấy lại toàn bộ cửa sổ")
    args = ap.parse_args(argv)

    wl = load_config("watchlist.json")
    targets: Dict[str, float] = {}  # symbol -> multiplier (dchart)
    for ins in wl["instruments"]:
        if ins["type"] in ("stock", "etf"):
            targets[ins["symbol"]] = 1000.0
    for ix in wl["context_indices"]:
        targets[ix["symbol"]] = 1.0
    include_gold = True
    if args.symbols:
        sel = set(args.symbols)
        targets = {k: v for k, v in targets.items() if k in sel}
        include_gold = "XAUUSD" in sel

    failures = 0
    for sym, mult in targets.items():
        for res in args.res:
            try:
                m = fetch_dchart_symbol(sym, mult, res, args.full)
                bad = {k: v for k, v in m["anomalies"]["counts"].items() if v and k != "zero_volume_bars"}
                print(f"[ok]   {sym:9s} {res:>2s}  bars={m['bars_count']:6d} +{m['new_bars_this_run']:<5d} last={m['last_bar']}"
                      + (f"  ANOMALY {bad}" if bad else ""))
            except FetchError as e:
                failures += 1
                print(f"[FAIL] {sym:9s} {res:>2s}  {e}", file=sys.stderr)
            time.sleep(POLITE_SLEEP)
    if include_gold:
        for res in args.res:
            try:
                m = fetch_yahoo_gold(res, args.full)
                bad = {k: v for k, v in m["anomalies"]["counts"].items() if v and k != "zero_volume_bars"}
                print(f"[ok]   XAUUSD    {res:>2s}  bars={m['bars_count']:6d} +{m['new_bars_this_run']:<5d} last={m['last_bar']} (GC=F futures)"
                      + (f"  ANOMALY {bad}" if bad else ""))
            except FetchError as e:
                failures += 1
                print(f"[FAIL] XAUUSD    {res:>2s}  {e}", file=sys.stderr)
            time.sleep(POLITE_SLEEP)
    print(f"Hoàn tất. Lỗi: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
