"""Chỉ báo kỹ thuật — triển khai theo docs/indicators.md (nguồn duy nhất cho công thức).

Quy ước:
  - Đầu vào là numpy array / pandas Series cùng độ dài, KHÔNG chứa NaN, sắp theo thời gian tăng dần.
  - Giá trị tại chỉ số t chỉ phụ thuộc dữ liệu ở chỉ số <= t (không nhìn trước tương lai).
  - Giai đoạn khởi tạo trả về NaN.
  - Làm mượt Wilder (RMA): A_t = (A_{t-1}*(n-1) + x_t)/n, khởi tạo bằng trung bình n giá trị đầu.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

FIB_RATIOS = (0.236, 0.382, 0.5, 0.618, 0.786)


def _arr(x) -> np.ndarray:
    return np.asarray(x, dtype=float)


# --------------------------------------------------------------------------- nền tảng
def sma(x, n: int) -> np.ndarray:
    return pd.Series(_arr(x)).rolling(n, min_periods=n).mean().to_numpy()


def ema(x, n: int) -> np.ndarray:
    """EMA, α = 2/(n+1), khởi tạo bằng SMA(n) của n giá trị đầu hợp lệ (bỏ qua NaN ở đầu mảng)."""
    x = _arr(x)
    out = np.full(len(x), np.nan)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) < n:
        return out
    s = valid[0]
    seed = s + n - 1
    out[seed] = x[s:seed + 1].mean()
    a = 2.0 / (n + 1)
    for i in range(seed + 1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def rma(x, n: int) -> np.ndarray:
    """Làm mượt Wilder; x có thể có NaN ở đầu (khởi tạo từ giá trị hợp lệ đầu tiên)."""
    x = _arr(x)
    out = np.full(len(x), np.nan)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) < n:
        return out
    s = valid[0]
    seed = s + n - 1
    out[seed] = x[s:seed + 1].mean()
    for i in range(seed + 1, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def true_range(high, low, close) -> np.ndarray:
    h, l, c = _arr(high), _arr(low), _arr(close)
    tr = np.full(len(c), np.nan)
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])])
    return tr


# --------------------------------------------------------------------------- xu hướng
def macd(close, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)  # ema() bỏ qua NaN đầu mảng -> khởi tạo từ MACD hợp lệ đầu tiên
    return {"macd": line, "signal": sig, "hist": line - sig}


def adx(high, low, close, n: int = 14) -> Dict[str, np.ndarray]:
    h, l = _arr(high), _arr(low)
    up = np.full(len(h), np.nan)
    dn = np.full(len(h), np.nan)
    up[1:] = h[1:] - h[:-1]
    dn[1:] = l[:-1] - l[1:]
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    plus_dm[0] = minus_dm[0] = np.nan
    atr_ = rma(true_range(high, low, close), n)
    pdi = 100 * rma(plus_dm, n) / atr_
    mdi = 100 * rma(minus_dm, n) / atr_
    with np.errstate(divide="ignore", invalid="ignore"):
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    return {"plus_di": pdi, "minus_di": mdi, "adx": rma(dx, n)}


# --------------------------------------------------------------------------- động lượng
def rsi(close, n: int = 14) -> np.ndarray:
    c = _arr(close)
    d = np.full(len(c), np.nan)
    d[1:] = np.diff(c)
    gain = np.where(d > 0, d, 0.0)
    loss = np.where(d < 0, -d, 0.0)
    gain[0] = loss[0] = np.nan
    ag, al = rma(gain, n), rma(loss, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(al == 0, 100.0, 100 - 100 / (1 + ag / al))
    out[np.isnan(ag) | np.isnan(al)] = np.nan
    return out


def stochastic(high, low, close, k: int = 14, smooth_k: int = 3, d: int = 3) -> Dict[str, np.ndarray]:
    """Slow stochastic. Nếu HH == LL (mẫu số 0) trả NaN (không phát tín hiệu), khác TA-Lib là trả 0."""
    h, l, c = pd.Series(_arr(high)), pd.Series(_arr(low)), _arr(close)
    hh, ll = h.rolling(k, min_periods=k).max().to_numpy(), l.rolling(k, min_periods=k).min().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = np.where(hh == ll, np.nan, 100 * (c - ll) / (hh - ll))
    slow_k = sma(raw, smooth_k)
    return {"k": slow_k, "d": sma(slow_k, d)}


# --------------------------------------------------------------------------- biến động
def bollinger(close, n: int = 20, k: float = 2.0) -> Dict[str, np.ndarray]:
    s = pd.Series(_arr(close))
    mid = s.rolling(n, min_periods=n).mean()
    sd = s.rolling(n, min_periods=n).std(ddof=0)  # độ lệch chuẩn tổng thể (chia N), như Bollinger/TA-Lib
    up, lo = mid + k * sd, mid - k * sd
    with np.errstate(divide="ignore", invalid="ignore"):
        pct_b = ((s - lo) / (up - lo)).to_numpy()
        bw = ((up - lo) / mid).to_numpy()
    return {"mid": mid.to_numpy(), "upper": up.to_numpy(), "lower": lo.to_numpy(), "pct_b": pct_b, "bandwidth": bw}


def atr(high, low, close, n: int = 14) -> np.ndarray:
    return rma(true_range(high, low, close), n)


# --------------------------------------------------------------------------- khối lượng
def obv(close, volume) -> np.ndarray:
    """OBV_0 = V_0 (quy ước của TA-Lib), sau đó cộng/trừ V theo chiều giá đóng cửa. Chỉ có ý nghĩa về xu hướng."""
    c, v = _arr(close), _arr(volume)
    out = np.empty(len(c))
    out[0] = v[0]
    for i in range(1, len(c)):
        out[i] = out[i - 1] + (v[i] if c[i] > c[i - 1] else -v[i] if c[i] < c[i - 1] else 0.0)
    return out


def vwap_intraday(high, low, close, volume, day_key) -> np.ndarray:
    """VWAP tích lũy, reset theo day_key (ví dụ ngày VN). Trả NaN khi tổng khối lượng tích lũy = 0."""
    tp = (_arr(high) + _arr(low) + _arr(close)) / 3
    v = _arr(volume)
    df = pd.DataFrame({"pv": tp * v, "v": v, "k": list(day_key)})
    cum = df.groupby("k")[["pv", "v"]].cumsum()
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(cum["v"] > 0, cum["pv"] / cum["v"], np.nan)


# --------------------------------------------------------------------------- hỗ trợ/kháng cự
def pivots(prev_high: float, prev_low: float, prev_close: float) -> Dict[str, float]:
    p = (prev_high + prev_low + prev_close) / 3
    return {"P": p, "R1": 2 * p - prev_low, "S1": 2 * p - prev_high,
            "R2": p + (prev_high - prev_low), "S2": p - (prev_high - prev_low)}


def swings(high, low, k: int = 2) -> List[Dict[str, float]]:
    """Swing high/low kiểu fractal: nến i là swing high nếu H_i > H của k nến trước VÀ k nến sau (so sánh chặt).
    Mỗi swing có 'confirmed_at' = i + k: chỉ được biết/vẽ từ nến đó trở đi (tránh nhìn trước tương lai)."""
    h, l = _arr(high), _arr(low)
    out: List[Dict[str, float]] = []
    for i in range(k, len(h) - k):
        nb = list(range(i - k, i)) + list(range(i + 1, i + k + 1))
        if all(h[i] > h[j] for j in nb):
            out.append({"index": i, "type": "high", "price": float(h[i]), "confirmed_at": i + k})
        if all(l[i] < l[j] for j in nb):
            out.append({"index": i, "type": "low", "price": float(l[i]), "confirmed_at": i + k})
    return sorted(out, key=lambda s: (s["index"], s["type"]))


def fib_retracement(price_a: float, price_b: float) -> Dict[str, float]:
    """Mức hồi từ a (đầu sóng) về b (cuối sóng): giá = b - ratio*(b - a). Ratio 0,5 là quy ước, không phải tỷ lệ Fibonacci."""
    return {f"{r:g}": price_b - r * (price_b - price_a) for r in FIB_RATIOS}


# --------------------------------------------------------------------------- gộp
def compute_all(df: pd.DataFrame, *, intraday: bool = False, with_volume: bool = True,
                day_key: Optional[List[str]] = None) -> pd.DataFrame:
    """df cần cột o,h,l,c,v. Trả DataFrame cùng chỉ số với các cột chỉ báo (tên theo docs/indicators.md)."""
    o, h, l, c, v = (df[k].to_numpy(dtype=float) for k in ("o", "h", "l", "c", "v"))
    out = pd.DataFrame(index=df.index)
    for n in (9, 20, 50, 200):
        out[f"sma{n}"] = sma(c, n)
        out[f"ema{n}"] = ema(c, n)
    m = macd(c)
    out["macd"], out["macd_signal"], out["macd_hist"] = m["macd"], m["signal"], m["hist"]
    a = adx(h, l, c)
    out["adx14"], out["plus_di14"], out["minus_di14"] = a["adx"], a["plus_di"], a["minus_di"]
    out["rsi14"] = rsi(c)
    st = stochastic(h, l, c)
    out["stoch_k"], out["stoch_d"] = st["k"], st["d"]
    bb = bollinger(c)
    for k in ("mid", "upper", "lower", "pct_b", "bandwidth"):
        out[f"bb_{k}"] = bb[k]
    out["atr14"] = atr(h, l, c)
    if with_volume:
        out["vol_ma20"] = sma(v, 20)
        out["obv"] = obv(c, v)
        if intraday and day_key is not None:
            out["vwap"] = vwap_intraday(h, l, c, v, day_key)
    return out
