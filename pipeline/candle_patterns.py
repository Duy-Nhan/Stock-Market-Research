"""Mô hình nến Nhật (theo mô tả của Nison) với quy tắc định lượng + bối cảnh xu hướng trước đó.

Quy tắc và hệ số: docs/patterns.md §A. Hệ số là QUY ƯỚC của người phân tích (không phải định luật).
Mọi phát hiện tại nến i chỉ dùng nến <= i (nhân quả). Trạng thái xác nhận/thất bại dùng nến i+1 và được đánh dấu bằng
chỉ số của nến đó (confirmed_at / failed_at) để giao diện chỉ hiển thị khi đã tới nến đó.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

TREND_N = 10        # đo xu hướng trước mô hình trên 10 nến
TREND_ATR = 3.0     # xu hướng tăng/giảm nếu giá đóng cửa thay đổi >= 3 ATR trong 10 nến
MIN_RANGE_ATR = 0.5  # nến phải có biên độ >= 0,5 ATR để tránh nhiễu
LONG_BODY_ATR = 0.7  # "nến thân dài": thân >= 0,7 ATR và >= 60% biên độ

LABELS = {
    "doji": "Doji", "hammer": "Búa (Hammer)", "hanging_man": "Người treo cổ (Hanging man)",
    "inverted_hammer": "Búa ngược (Inverted hammer)", "shooting_star": "Sao băng (Shooting star)",
    "bullish_engulfing": "Nhấn chìm tăng", "bearish_engulfing": "Nhấn chìm giảm",
    "bullish_harami": "Harami tăng", "bearish_harami": "Harami giảm",
    "piercing_line": "Xuyên thấu (Piercing line)", "dark_cloud_cover": "Mây đen che phủ",
    "morning_star": "Sao mai (Morning star)", "evening_star": "Sao hôm (Evening star)",
}


def trend_into(c: np.ndarray, atr: np.ndarray) -> np.ndarray:
    """trend[j]: xu hướng kết thúc tại nến j (gồm j): +1 nếu c[j]-c[j-N] >= 3·ATR[j]; -1 nếu <= -3·ATR[j]; 0 còn lại; NaN nếu thiếu dữ liệu."""
    n = len(c)
    out = np.full(n, np.nan)
    for j in range(TREND_N, n):
        if np.isnan(atr[j]):
            continue
        d = c[j] - c[j - TREND_N]
        out[j] = 1.0 if d >= TREND_ATR * atr[j] else (-1.0 if d <= -TREND_ATR * atr[j] else 0.0)
    return out


def detect(o, h, l, c, atr, vol_ratio: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
    o, h, l, c, atr = (np.asarray(x, dtype=float) for x in (o, h, l, c, atr))
    n = len(c)
    body = np.abs(c - o)
    rng = h - l
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    tr = trend_into(c, atr)
    out: List[Dict[str, Any]] = []

    def long_candle(j: int, bearish: Optional[bool]) -> bool:
        if np.isnan(atr[j]) or rng[j] <= 0:
            return False
        col_ok = True if bearish is None else ((c[j] < o[j]) if bearish else (c[j] > o[j]))
        return bool(col_ok and body[j] >= LONG_BODY_ATR * atr[j] and body[j] >= 0.6 * rng[j])

    def add(i: int, name: str, direction: int, start: int, invalid: Optional[float]) -> None:
        rec: Dict[str, Any] = {"index": i, "name": name, "label": LABELS[name], "dir": direction, "start": start,
                               "trend_before": None if np.isnan(tr[start - 1]) else int(tr[start - 1]),
                               "invalid_level": invalid, "confirmed_at": None, "failed_at": None,
                               "vol_ratio": None if vol_ratio is None or np.isnan(vol_ratio[i]) else round(float(vol_ratio[i]), 2)}
        if direction != 0 and i + 1 < n:  # nến kế tiếp quyết định xác nhận/thất bại
            if direction > 0:
                if c[i + 1] < invalid:
                    rec["failed_at"] = i + 1
                elif c[i + 1] > c[i]:
                    rec["confirmed_at"] = i + 1
            else:
                if c[i + 1] > invalid:
                    rec["failed_at"] = i + 1
                elif c[i + 1] < c[i]:
                    rec["confirmed_at"] = i + 1
        out.append(rec)

    for i in range(TREND_N + 2, n):
        if np.isnan(atr[i]) or rng[i] <= 0:
            continue
        a = atr[i]
        # ---- một nến
        t1 = tr[i - 1]
        if rng[i] >= MIN_RANGE_ATR * a:
            if body[i] <= 0.1 * rng[i] and min(upper[i], lower[i]) >= 0.2 * rng[i]:
                add(i, "doji", 0, i, None)
            hammer_shape = lower[i] >= 2 * body[i] and lower[i] >= 0.6 * rng[i] and upper[i] <= 0.1 * rng[i]
            star_shape = upper[i] >= 2 * body[i] and upper[i] >= 0.6 * rng[i] and lower[i] <= 0.1 * rng[i]
            if hammer_shape and t1 == -1:
                add(i, "hammer", 1, i, float(l[i]))
            if hammer_shape and t1 == 1:
                add(i, "hanging_man", -1, i, float(h[i]))
            if star_shape and t1 == -1:
                add(i, "inverted_hammer", 1, i, float(l[i]))
            if star_shape and t1 == 1:
                add(i, "shooting_star", -1, i, float(h[i]))
        # ---- hai nến
        t2 = tr[i - 2]
        p, q = i - 1, i
        mid_p = (o[p] + c[p]) / 2
        if t2 == -1:
            if c[p] < o[p] and c[q] > o[q] and o[q] <= c[p] and c[q] >= o[p] and body[q] > body[p] and body[q] >= 0.5 * a:
                add(i, "bullish_engulfing", 1, p, float(min(l[p], l[q])))
            if long_candle(p, True) and c[q] > o[q] and body[q] <= 0.5 * body[p] and max(o[q], c[q]) <= o[p] and min(o[q], c[q]) >= c[p]:
                add(i, "bullish_harami", 1, p, float(min(l[p], l[q])))
            if long_candle(p, True) and c[q] > o[q] and o[q] <= c[p] and mid_p < c[q] < o[p]:
                add(i, "piercing_line", 1, p, float(min(l[p], l[q])))
        if t2 == 1:
            if c[p] > o[p] and c[q] < o[q] and o[q] >= c[p] and c[q] <= o[p] and body[q] > body[p] and body[q] >= 0.5 * a:
                add(i, "bearish_engulfing", -1, p, float(max(h[p], h[q])))
            if long_candle(p, False) and c[q] < o[q] and body[q] <= 0.5 * body[p] and max(o[q], c[q]) <= c[p] and min(o[q], c[q]) >= o[p]:
                add(i, "bearish_harami", -1, p, float(max(h[p], h[q])))
            if long_candle(p, False) and c[q] < o[q] and o[q] >= c[p] and o[p] < c[q] < mid_p:
                add(i, "dark_cloud_cover", -1, p, float(max(h[p], h[q])))
        # ---- ba nến
        t3 = tr[i - 3]
        s1, s2, s3 = i - 2, i - 1, i
        if t3 == -1 and long_candle(s1, True) and body[s2] <= 0.3 * body[s1] and max(o[s2], c[s2]) < c[s1] and c[s3] > o[s3] and c[s3] > (o[s1] + c[s1]) / 2 and body[s3] >= 0.5 * a:
            add(i, "morning_star", 1, s1, float(min(l[s1], l[s2], l[s3])))
        if t3 == 1 and long_candle(s1, False) and body[s2] <= 0.3 * body[s1] and min(o[s2], c[s2]) > c[s1] and c[s3] < o[s3] and c[s3] < (o[s1] + c[s1]) / 2 and body[s3] >= 0.5 * a:
            add(i, "evening_star", -1, s1, float(max(h[s1], h[s2], h[s3])))
    return out
