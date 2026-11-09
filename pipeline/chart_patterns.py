"""Mô hình giá cổ điển từ swing đã xác nhận: Double top/bottom, Head & Shoulders (và ngược), Tam giác (tăng/giảm/cân).

Cơ sở lý thuyết: Edwards & Magee, *Technical Analysis of Stock Trends*; Murphy, *Technical Analysis of the Financial
Markets* (chương mô hình giá đảo chiều và tiếp diễn). Cách đo mục tiêu (measured move) theo mô tả trong các sách này.
Quy tắc định lượng + hệ số: docs/patterns.md §B — hệ số là QUY ƯỚC của người phân tích.

Nhân quả: mỗi mô hình có `formed_at` (nến sớm nhất có thể biết), `confirmed_at`, `invalidated_at`, `expired_at`,
`failed_at`, `target_hit_at` là các CHỈ SỐ NẾN; giao diện/engine chỉ dùng sự kiện có chỉ số <= nến hiện tại.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

TOL_TOP = 1.0          # hai đỉnh/đáy "bằng nhau" nếu lệch <= 1,0 ATR
MIN_DEPTH = 2.0        # độ sâu (đỉnh - đáy giữa) >= 2 ATR (Double top/bottom)
MIN_PRIOR = 3.0        # xu hướng trước mô hình: >= 3 ATR trong 60 nến
MIN_GAP, MAX_GAP = 8, 120
HS_HEAD = 1.0          # đầu cao hơn vai >= 1 ATR
HS_SHOULDER_TOL = 1.5  # hai vai lệch nhau <= 1,5 ATR
HS_TROUGH_DEPTH = 1.5  # hai đáy giữa thấp hơn vai thấp >= 1,5 ATR
HS_MAX_SPAN = 150
BREAK_ATR = 0.25       # đóng cửa vượt đường cổ/biên quá 0,25 ATR mới tính là phá vỡ
EXPIRE = 60            # quá 60 nến sau khi hình thành mà chưa phá vỡ -> hết hạn
FAIL_WINDOW = 10       # sau phá vỡ, nếu trong 10 nến đóng cửa quay lại phía cũ (qua đường cổ) -> thất bại (fakeout)
TRI_WINDOW = 100
TRI_MIN_SPAN = 15
TRI_FLAT = 0.75        # biên "phẳng" nếu thay đổi ròng <= 0,75 ATR
TRI_SLOPE = 1.0        # biên "dốc" nếu thay đổi ròng >= 1,0 ATR
TRI_START_HEIGHT = 3.0
TRI_CONVERGE = 0.7     # bề rộng cuối <= 70% bề rộng đầu
VOL_CONFIRM = 1.25     # khối lượng nến phá vỡ >= 1,25 × trung bình 20 nến coi là "có khối lượng xác nhận" (quy ước)

LABELS = {
    "double_top": "Hai đỉnh (Double top)", "double_bottom": "Hai đáy (Double bottom)",
    "head_shoulders": "Vai-đầu-vai (Head & shoulders)", "inverse_head_shoulders": "Vai-đầu-vai ngược",
    "ascending_triangle": "Tam giác tăng", "descending_triangle": "Tam giác giảm", "symmetrical_triangle": "Tam giác cân",
}


def _line(i1: int, p1: float, i2: int, p2: float, x: float) -> float:
    return p1 if i2 == i1 else p1 + (p2 - p1) / (i2 - i1) * (x - i1)


def _lifecycle_reversal(pat: Dict[str, Any], h, l, c, atr, vr, top: bool) -> None:
    """Chạy vòng đời cho mô hình đảo chiều có đường cổ `neckline` (có thể nghiêng) và mức vô hiệu `extreme`."""
    n = len(c)
    nk = pat["neckline"]
    sign = -1 if top else 1   # top: phá xuống (sign=-1); bottom: phá lên (+1)
    formed = pat["formed_at"]
    extreme = pat["invalid_level"]
    broke = None
    for j in range(pat["points"][-1]["index"] + 1, min(n, formed + EXPIRE + 1)):
        if np.isnan(atr[j]):
            continue
        neck = _line(nk["i1"], nk["p1"], nk["i2"], nk["p2"], j)
        if top:
            if c[j] > extreme + BREAK_ATR * atr[j]:
                pat["invalidated_at"] = max(j, formed); return
            if c[j] < neck - BREAK_ATR * atr[j]:
                broke = j; break
        else:
            if c[j] < extreme - BREAK_ATR * atr[j]:
                pat["invalidated_at"] = max(j, formed); return
            if c[j] > neck + BREAK_ATR * atr[j]:
                broke = j; break
    if broke is None:
        if formed + EXPIRE <= n - 1:
            pat["expired_at"] = formed + EXPIRE
        return
    pat["confirmed_at"] = max(broke, formed)
    pat["breakout_index"] = broke
    pat["breakout_vol_ratio"] = None if vr is None or np.isnan(vr[broke]) else round(float(vr[broke]), 2)
    pat["volume_confirmed"] = None if pat["breakout_vol_ratio"] is None else pat["breakout_vol_ratio"] >= VOL_CONFIRM
    height = pat["height"]
    neck_at_break = _line(nk["i1"], nk["p1"], nk["i2"], nk["p2"], broke)
    pat["target"] = neck_at_break + sign * height  # đo theo chiều cao mô hình (measured move)
    for j in range(max(broke, formed) + 1, n):
        neck = _line(nk["i1"], nk["p1"], nk["i2"], nk["p2"], j)
        back = (c[j] > neck + BREAK_ATR * atr[j]) if top else (c[j] < neck - BREAK_ATR * atr[j])
        hit = (l[j] <= pat["target"]) if top else (h[j] >= pat["target"])
        if hit and pat.get("target_hit_at") is None:
            pat["target_hit_at"] = j
            return
        if j - max(broke, formed) <= FAIL_WINDOW and back and pat.get("failed_at") is None:
            pat["failed_at"] = j
            return


def _double(h, l, c, atr, vr, swings, top: bool) -> List[Dict[str, Any]]:
    n = len(c)
    pts = sorted([s for s in swings if s["type"] == ("high" if top else "low")], key=lambda s: s["index"])
    out: List[Dict[str, Any]] = []
    for s1, s2 in zip(pts[:-1], pts[1:]):
        g = s2["index"] - s1["index"]
        if not (MIN_GAP <= g <= MAX_GAP) or s2["confirmed_at"] >= n:
            continue
        a = atr[s2["confirmed_at"]]
        if np.isnan(a) or abs(s1["price"] - s2["price"]) > TOL_TOP * a:
            continue
        seg = slice(s1["index"] + 1, s2["index"])
        if top:
            mid_i = s1["index"] + 1 + int(np.argmin(l[seg])); neck = float(l[mid_i])
            ext = max(s1["price"], s2["price"]); depth = min(s1["price"], s2["price"]) - neck
            lo = max(0, s1["index"] - 60); prior = c[s1["index"]] - np.min(l[lo:s1["index"] + 1])
        else:
            mid_i = s1["index"] + 1 + int(np.argmax(h[seg])); neck = float(h[mid_i])
            ext = min(s1["price"], s2["price"]); depth = neck - max(s1["price"], s2["price"])
            lo = max(0, s1["index"] - 60); prior = np.max(h[lo:s1["index"] + 1]) - c[s1["index"]]
        if depth < MIN_DEPTH * a or prior < MIN_PRIOR * a:
            continue
        avg = (s1["price"] + s2["price"]) / 2
        pat = {"type": "double_top" if top else "double_bottom", "label": LABELS["double_top" if top else "double_bottom"],
               "bias": -1 if top else 1,
               "points": [{"index": s1["index"], "price": s1["price"]}, {"index": mid_i, "price": neck}, {"index": s2["index"], "price": s2["price"]}],
               "neckline": {"i1": s1["index"], "p1": neck, "i2": s2["index"], "p2": neck},
               "invalid_level": ext, "height": abs(avg - neck), "formed_at": s2["confirmed_at"],
               "confirmed_at": None, "invalidated_at": None, "expired_at": None, "failed_at": None, "target_hit_at": None, "target": None}
        _lifecycle_reversal(pat, h, l, c, atr, vr, top)
        out.append(pat)
    return out


def _head_shoulders(h, l, c, atr, vr, swings, top: bool) -> List[Dict[str, Any]]:
    n = len(c)
    pts = sorted([s for s in swings if s["type"] == ("high" if top else "low")], key=lambda s: s["index"])
    out: List[Dict[str, Any]] = []
    for a_, b_, c_ in zip(pts[:-2], pts[1:-1], pts[2:]):
        if c_["confirmed_at"] >= n or c_["index"] - a_["index"] > HS_MAX_SPAN:
            continue
        if min(b_["index"] - a_["index"], c_["index"] - b_["index"]) < 5:
            continue
        at = atr[c_["confirmed_at"]]
        if np.isnan(at):
            continue
        pa, pb, pc = a_["price"], b_["price"], c_["price"]
        if top:
            if pb < max(pa, pc) + HS_HEAD * at or abs(pa - pc) > HS_SHOULDER_TOL * at:
                continue
            s1 = slice(a_["index"] + 1, b_["index"]); s2 = slice(b_["index"] + 1, c_["index"])
            t1i = a_["index"] + 1 + int(np.argmin(l[s1])); t2i = b_["index"] + 1 + int(np.argmin(l[s2]))
            t1p, t2p = float(l[t1i]), float(l[t2i])
            if min(pa, pc) - max(t1p, t2p) < HS_TROUGH_DEPTH * at:
                continue
            lo = max(0, a_["index"] - 60); prior = c[a_["index"]] - np.min(l[lo:a_["index"] + 1])
            ext = pb
        else:
            if pb > min(pa, pc) - HS_HEAD * at or abs(pa - pc) > HS_SHOULDER_TOL * at:
                continue
            s1 = slice(a_["index"] + 1, b_["index"]); s2 = slice(b_["index"] + 1, c_["index"])
            t1i = a_["index"] + 1 + int(np.argmax(h[s1])); t2i = b_["index"] + 1 + int(np.argmax(h[s2]))
            t1p, t2p = float(h[t1i]), float(h[t2i])
            if min(t1p, t2p) - max(pa, pc) < HS_TROUGH_DEPTH * at:
                continue
            lo = max(0, a_["index"] - 60); prior = np.max(h[lo:a_["index"] + 1]) - c[a_["index"]]
            ext = pb
        if prior < MIN_PRIOR * at or t2i == t1i:
            continue
        neck_at_head = _line(t1i, t1p, t2i, t2p, b_["index"])
        name = "head_shoulders" if top else "inverse_head_shoulders"
        pat = {"type": name, "label": LABELS[name], "bias": -1 if top else 1,
               "points": [{"index": a_["index"], "price": pa}, {"index": t1i, "price": t1p}, {"index": b_["index"], "price": pb},
                          {"index": t2i, "price": t2p}, {"index": c_["index"], "price": pc}],
               "neckline": {"i1": t1i, "p1": t1p, "i2": t2i, "p2": t2p},
               "invalid_level": ext, "height": abs(pb - neck_at_head), "formed_at": c_["confirmed_at"],
               "confirmed_at": None, "invalidated_at": None, "expired_at": None, "failed_at": None, "target_hit_at": None, "target": None}
        _lifecycle_reversal(pat, h, l, c, atr, vr, top)
        out.append(pat)
    return out


def _triangles(h, l, c, atr, vr, swings) -> List[Dict[str, Any]]:
    n = len(c)
    sw = sorted(swings, key=lambda s: (s["confirmed_at"], s["index"]))
    highs: List[Dict[str, Any]] = []
    lows: List[Dict[str, Any]] = []
    ptr = 0
    out: List[Dict[str, Any]] = []
    open_p: Optional[Dict[str, Any]] = None
    for i in range(n):
        while ptr < len(sw) and sw[ptr]["confirmed_at"] <= i:
            (highs if sw[ptr]["type"] == "high" else lows).append(sw[ptr]); ptr += 1
        a = atr[i]
        # 1) xử lý mô hình đang mở
        if open_p is not None:
            p = open_p
            up_l, lo_l = p["upper"], p["lower"]
            u = _line(up_l["i1"], up_l["p1"], up_l["i2"], up_l["p2"], i); lw = _line(lo_l["i1"], lo_l["p1"], lo_l["i2"], lo_l["p2"], i)
            if not np.isnan(a) and p["confirmed_at"] is None:
                if c[i] > u + BREAK_ATR * a or c[i] < lw - BREAK_ATR * a:
                    up = c[i] > u + BREAK_ATR * a
                    p["confirmed_at"] = i; p["breakout_dir"] = 1 if up else -1; p["breakout_index"] = i
                    p["breakout_vol_ratio"] = None if vr is None or np.isnan(vr[i]) else round(float(vr[i]), 2)
                    p["volume_confirmed"] = None if p["breakout_vol_ratio"] is None else p["breakout_vol_ratio"] >= VOL_CONFIRM
                    p["target"] = (u + p["height"]) if up else (lw - p["height"])
                    p["bound_at_break"] = u if up else lw
                elif u <= lw or i - p["formed_at"] >= EXPIRE:
                    p["expired_at"] = i; open_p = None
            elif p["confirmed_at"] is not None and i > p["confirmed_at"]:
                bl = up_l if p["breakout_dir"] == 1 else lo_l
                bound = _line(bl["i1"], bl["p1"], bl["i2"], bl["p2"], i)
                hit = (h[i] >= p["target"]) if p["breakout_dir"] == 1 else (l[i] <= p["target"])
                back = (c[i] < bound - BREAK_ATR * a) if p["breakout_dir"] == 1 else (c[i] > bound + BREAK_ATR * a)
                if hit:
                    p["target_hit_at"] = i; open_p = None
                elif i - p["confirmed_at"] <= FAIL_WINDOW and back and not np.isnan(a):
                    p["failed_at"] = i; open_p = None
                elif i - p["confirmed_at"] > FAIL_WINDOW + 20:
                    open_p = None
        # 2) tìm mô hình mới (chỉ khi chưa có mô hình chưa xác nhận đang mở)
        if np.isnan(a):
            continue
        hs = [s for s in highs if s["index"] >= i - TRI_WINDOW]
        ls = [s for s in lows if s["index"] >= i - TRI_WINDOW]
        if len(hs) < 2 or len(ls) < 2:
            continue
        hA, hB, lA, lB = hs[-2], hs[-1], ls[-2], ls[-1]
        start = min(hA["index"], lA["index"]); span = i - start
        if span < TRI_MIN_SPAN:
            continue
        ident = (hA["index"], hB["index"], lA["index"], lB["index"])
        if open_p is not None and open_p["_ident"] == ident:
            continue
        if open_p is not None and open_p["confirmed_at"] is not None:
            continue  # đang theo dõi sau phá vỡ, chưa tìm mô hình mới
        su = (hB["price"] - hA["price"]) / (hB["index"] - hA["index"]); sl = (lB["price"] - lA["price"]) / (lB["index"] - lA["index"])
        L = max(hB["index"], lB["index"]) - start
        net_up, net_lo = su * L, sl * L
        u0 = hA["price"] + su * (start - hA["index"]); l0 = lA["price"] + sl * (start - lA["index"])
        u1 = hA["price"] + su * (i - hA["index"]); l1 = lA["price"] + sl * (i - lA["index"])
        h0, h1 = u0 - l0, u1 - l1
        if h0 < TRI_START_HEIGHT * a or h1 <= 0 or h1 > TRI_CONVERGE * h0:
            continue
        kind = None
        if abs(net_up) <= TRI_FLAT * a and net_lo >= TRI_SLOPE * a:
            kind = "ascending_triangle"
        elif abs(net_lo) <= TRI_FLAT * a and net_up <= -TRI_SLOPE * a:
            kind = "descending_triangle"
        elif net_up <= -TRI_SLOPE * a and net_lo >= TRI_SLOPE * a:
            kind = "symmetrical_triangle"
        if kind is None:
            continue
        if open_p is not None:
            open_p["superseded_at"] = i
        pat = {"type": kind, "label": LABELS[kind], "bias": {"ascending_triangle": 1, "descending_triangle": -1}.get(kind, 0),
               "points": [{"index": s["index"], "price": s["price"]} for s in (hA, hB, lA, lB)],
               "upper": {"i1": hA["index"], "p1": hA["price"], "i2": hB["index"], "p2": hB["price"]},
               "lower": {"i1": lA["index"], "p1": lA["price"], "i2": lB["index"], "p2": lB["price"]},
               "height": h0, "formed_at": i, "confirmed_at": None, "invalidated_at": None, "expired_at": None, "failed_at": None,
               "target_hit_at": None, "target": None, "superseded_at": None, "_ident": ident}
        out.append(pat); open_p = pat
    for p in out:
        p.pop("_ident", None)
    return out


def detect(h, l, c, atr, vol_ratio: Optional[Sequence[float]], swings: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    h, l, c, atr = (np.asarray(x, dtype=float) for x in (h, l, c, atr))
    vr = None if vol_ratio is None else np.asarray(vol_ratio, dtype=float)
    res: List[Dict[str, Any]] = []
    res += _double(h, l, c, atr, vr, swings, True)
    res += _double(h, l, c, atr, vr, swings, False)
    res += _head_shoulders(h, l, c, atr, vr, swings, True)
    res += _head_shoulders(h, l, c, atr, vr, swings, False)
    res += _triangles(h, l, c, atr, vr, swings)
    return sorted(res, key=lambda p: (p["formed_at"], p["type"]))


def status_at(p: Dict[str, Any], i: int) -> Optional[str]:
    """Trạng thái tại nến i, chỉ dùng sự kiện có chỉ số <= i. None nếu chưa hình thành."""
    if p["formed_at"] > i:
        return None
    for key, name in (("invalidated_at", "invalidated"), ("expired_at", "expired"), ("superseded_at", "superseded")):
        if p.get(key) is not None and p[key] <= i and (p.get("confirmed_at") is None or p[key] <= p["confirmed_at"]):
            return name
    if p["confirmed_at"] is not None and p["confirmed_at"] <= i:
        if p.get("target_hit_at") is not None and p["target_hit_at"] <= i:
            return "target_hit"
        if p.get("failed_at") is not None and p["failed_at"] <= i:
            return "failed"
        return "confirmed"
    return "forming"
