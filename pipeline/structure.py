"""Cấu trúc giá: trạng thái xu hướng (Dow), đường xu hướng, vùng hỗ trợ/kháng cự, pivot theo ngày.

Mọi kết quả đều NHÂN QUẢ (causal): thông tin dùng tại nến i chỉ gồm các swing đã xác nhận (confirmed_at <= i)
và dữ liệu giá đến nến i. Nhờ vậy chế độ replay chỉ cần "hé lộ" kết quả đến nến hiện tại mà không nhìn trước tương lai.
Quy tắc và tham số: docs/patterns.md (các hệ số 0,3 / 0,25 / 0,5 ATR là quy ước của người phân tích, không phải định luật).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .indicators import swings as find_swings

SWING_K = 5
TOUCH_ATR = 0.3      # một swing "chạm" đường xu hướng nếu cách đường <= 0,3 ATR
BREAK_ATR = 0.25     # đường bị phá nếu có nến đóng cửa vượt qua đường > 0,25 ATR
ZONE_ATR = 0.5       # gộp swing vào cùng vùng nếu cách tâm vùng <= 0,5 ATR
ZONE_HALF_ATR = 0.25  # nửa bề rộng vùng hiển thị = 0,25 ATR (tại thời điểm xác nhận)
MAX_SWINGS_FOR_LINES = 8


def _state_from(sh: List[float], sl: List[float]) -> float:
    if len(sh) < 2 or len(sl) < 2:
        return np.nan
    hh, hl = sh[-1] > sh[-2], sl[-1] > sl[-2]
    lh, ll = sh[-1] < sh[-2], sl[-1] < sl[-2]
    if hh and hl:
        return 1.0
    if lh and ll:
        return -1.0
    return 0.0


def trend_state(n: int, swing_list: Sequence[Dict[str, Any]]) -> np.ndarray:
    """+1: đỉnh sau cao hơn VÀ đáy sau cao hơn (xu hướng tăng theo Dow); -1: cả hai thấp dần; 0: hỗn hợp; NaN: chưa đủ swing."""
    by_conf: Dict[int, List[Dict[str, Any]]] = {}
    for s in swing_list:
        by_conf.setdefault(int(s["confirmed_at"]), []).append(s)
    out = np.full(n, np.nan)
    hs: List[float] = []
    ls: List[float] = []
    for i in range(n):
        for s in sorted(by_conf.get(i, []), key=lambda x: x["index"]):
            (hs if s["type"] == "high" else ls).append(s["price"])
        out[i] = _state_from(hs, ls)
    return out


def _line_y(x1: int, p1: float, x2: int, p2: float, xs: np.ndarray) -> np.ndarray:
    return p1 + (p2 - p1) / (x2 - x1) * (xs - x1)


def _best_line(kind: str, pts: List[Tuple[int, float]], close: np.ndarray, i: int, atr_i: float):
    """Chọn đường tốt nhất trong các cặp swing (kind='up': nối các đáy cao dần; 'down': nối các đỉnh thấp dần)."""
    best = None
    for a in range(len(pts)):
        for b in range(a + 1, len(pts)):
            (x1, p1), (x2, p2) = pts[a], pts[b]
            if x2 <= x1 or (kind == "up" and p2 <= p1) or (kind == "down" and p2 >= p1):
                continue
            xs = np.arange(x1, i + 1)
            y = _line_y(x1, p1, x2, p2, xs)
            c = close[x1:i + 1]
            broken = (c < y - BREAK_ATR * atr_i).any() if kind == "up" else (c > y + BREAK_ATR * atr_i).any()
            if broken:
                continue
            touches = sum(1 for (xs_, ps_) in pts if xs_ >= x1 and abs(ps_ - _line_y(x1, p1, x2, p2, np.array([xs_]))[0]) <= TOUCH_ATR * atr_i)
            key = (touches, x2, x2 - x1)
            if best is None or key > best[0]:
                best = (key, (x1, p1, x2, p2), touches)
    return best


def trendline_segments(close: np.ndarray, atr: np.ndarray, swing_list: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Vòng đời các đường xu hướng. Mỗi đoạn hiệu lực cho nến i trong [from, to] (to=None: còn hiệu lực đến nến cuối).
    touches_hist: [[i, số lần chạm]] — số chạm tại thời điểm i (không dùng thông tin tương lai)."""
    n = len(close)
    conf = sorted(swing_list, key=lambda s: (s["confirmed_at"], s["index"]))
    highs: List[Tuple[int, float]] = []
    lows: List[Tuple[int, float]] = []
    ptr = 0
    segs: List[Dict[str, Any]] = []
    open_seg: Dict[str, Optional[Dict[str, Any]]] = {"up": None, "down": None}
    for i in range(n):
        while ptr < len(conf) and conf[ptr]["confirmed_at"] <= i:
            s = conf[ptr]
            (highs if s["type"] == "high" else lows).append((int(s["index"]), float(s["price"])))
            ptr += 1
        a = atr[i]
        for kind, pts in (("up", lows), ("down", highs)):
            cur = open_seg[kind]
            best = None if np.isnan(a) or len(pts) < 2 else _best_line(kind, pts[-MAX_SWINGS_FOR_LINES:], close, i, float(a))
            if best is None:
                if cur is not None:
                    cur["to"] = i - 1
                    open_seg[kind] = None
                continue
            line, touches = best[1], best[2]
            if cur is not None and (cur["i1"], cur["i2"]) == (line[0], line[2]):
                if cur["touches_hist"][-1][1] != touches:
                    cur["touches_hist"].append([i, touches])
                continue
            if cur is not None:
                cur["to"] = i - 1
            seg = {"kind": kind, "i1": line[0], "p1": line[1], "i2": line[2], "p2": line[3],
                   "from": i, "to": None, "touches_hist": [[i, touches]]}
            segs.append(seg)
            open_seg[kind] = seg
    return segs


def sr_zones(atr: np.ndarray, swing_list: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Vùng hỗ trợ/kháng cự: gom (tham lam) các swing có giá gần nhau (<= 0,5 ATR tại thời điểm xác nhận).
    hist: [[confirmed_at, tâm, số swing, nửa bề rộng, chỉ số swing gần nhất]] — thêm một mục mỗi khi vùng thay đổi.
    Giao diện chỉ hiển thị khi số swing >= 2 và swing gần nhất không quá cũ."""
    zones: List[Dict[str, Any]] = []
    for s in sorted(swing_list, key=lambda s: (s["confirmed_at"], s["index"])):
        ci = int(s["confirmed_at"])
        a = atr[ci] if ci < len(atr) else np.nan
        if np.isnan(a):
            continue
        tol = ZONE_ATR * a
        best, bd = None, None
        for z in zones:
            d = abs(z["_center"] - s["price"])
            if d <= tol and (bd is None or d < bd):
                best, bd = z, d
        if best is None:
            best = {"_prices": [], "_center": s["price"], "hist": []}
            zones.append(best)
        best["_prices"].append(float(s["price"]))
        best["_center"] = float(np.mean(best["_prices"]))
        best["hist"].append([ci, round(best["_center"], 4), len(best["_prices"]), round(ZONE_HALF_ATR * float(a), 4), int(s["index"])])
    return [{"hist": z["hist"]} for z in zones if len(z["hist"]) >= 2]


def daily_pivots(day_keys: Sequence[str], high, low, close) -> Dict[str, np.ndarray]:
    """Pivot cổ điển cho từng nến, tính từ H/L/C của NGÀY GIAO DỊCH TRƯỚC (gộp các nến cùng day_key)."""
    h, l, c = (np.asarray(x, dtype=float) for x in (high, low, close))
    n = len(h)
    out = {k: np.full(n, np.nan) for k in ("P", "R1", "S1", "R2", "S2")}
    days: List[str] = []
    agg: Dict[str, List[float]] = {}
    for i, k in enumerate(day_keys):
        if k not in agg:
            days.append(k)
            agg[k] = [h[i], l[i], c[i]]
        else:
            agg[k][0] = max(agg[k][0], h[i])
            agg[k][1] = min(agg[k][1], l[i])
            agg[k][2] = c[i]
    prev: Dict[str, Optional[str]] = {days[j]: (days[j - 1] if j else None) for j in range(len(days))}
    for i, k in enumerate(day_keys):
        pk = prev[k]
        if pk is None:
            continue
        ph, pl, pc = agg[pk]
        p = (ph + pl + pc) / 3
        out["P"][i], out["R1"][i], out["S1"][i] = p, 2 * p - pl, 2 * p - ph
        out["R2"][i], out["S2"][i] = p + (ph - pl), p - (ph - pl)
    return out


def analyze(high, low, close, atr, k: int = SWING_K) -> Dict[str, Any]:
    h, l, c = (np.asarray(x, dtype=float) for x in (high, low, close))
    sw = find_swings(h, l, k)
    return {"swings": sw, "trend_state": trend_state(len(c), sw),
            "trendlines": trendline_segments(c, np.asarray(atr, dtype=float), sw),
            "zones": sr_zones(np.asarray(atr, dtype=float), sw)}
