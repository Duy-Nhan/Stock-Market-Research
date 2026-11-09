"""Đối chiếu chỉ báo với TA-Lib trên DỮ LIỆU THẬT đã tải (data/prices) + kiểm tra tính chất toán học.

Dữ liệu nhân tạo ở đây chỉ dùng để kiểm tra logic từng hàm (không bao giờ hiển thị cho người dùng).
"""
import numpy as np
import pytest

from pipeline import indicators as ind
from pipeline.common import DATA, read_json

talib = pytest.importorskip("talib")

SYMBOLS = ["FPT", "VCB", "GAS", "XAUUSD"]


def load(sym, res="D", last=1500):
    p = DATA / "prices" / sym / f"{res}.json"
    if not p.exists():
        pytest.skip(f"chưa có dữ liệu {p}")
    b = np.array(read_json(p)["bars"], dtype=float)[-last:]
    return {k: b[:, i] for i, k in enumerate(("t", "o", "h", "l", "c", "v"))}


def close_enough(mine, ref, start, rtol=1e-6, atol=1e-8):
    m, r = mine[start:], ref[start:]
    ok = ~np.isnan(r)
    assert ok.sum() > 100
    assert not np.isnan(m[ok]).any(), "chỉ báo của ta có NaN ở nơi TA-Lib đã có giá trị"
    np.testing.assert_allclose(m[ok], r[ok], rtol=rtol, atol=atol)


@pytest.mark.parametrize("sym", SYMBOLS)
def test_sma_ema_match_talib(sym):
    d = load(sym)
    for n in (9, 20, 50, 200):
        close_enough(ind.sma(d["c"], n), talib.SMA(d["c"], n), 0)
        close_enough(ind.ema(d["c"], n), talib.EMA(d["c"], n), 0)


@pytest.mark.parametrize("sym", SYMBOLS)
def test_rsi_atr_match_talib(sym):
    d = load(sym)
    close_enough(ind.rsi(d["c"], 14), talib.RSI(d["c"], 14), 0)
    close_enough(ind.atr(d["h"], d["l"], d["c"], 14), talib.ATR(d["h"], d["l"], d["c"], 14), 0)


@pytest.mark.parametrize("sym", SYMBOLS)
def test_adx_matches_talib(sym):
    d = load(sym)
    # TA-Lib khởi tạo tổng DM/TR bằng n-1 giá trị đầu, ta dùng trung bình n giá trị đầu (như ATR/RSI);
    # sai khác khởi tạo phải triệt tiêu theo hệ số (1-1/14)^k nên so sánh sau 300 nến.
    a = ind.adx(d["h"], d["l"], d["c"], 14)
    close_enough(a["plus_di"], talib.PLUS_DI(d["h"], d["l"], d["c"], 14), 300)
    close_enough(a["minus_di"], talib.MINUS_DI(d["h"], d["l"], d["c"], 14), 300)
    close_enough(a["adx"], talib.ADX(d["h"], d["l"], d["c"], 14), 300)


@pytest.mark.parametrize("sym", SYMBOLS)
def test_bollinger_matches_talib(sym):
    d = load(sym)
    up, mid, lo = talib.BBANDS(d["c"], 20, 2, 2, 0)
    b = ind.bollinger(d["c"], 20, 2)
    close_enough(b["upper"], up, 0)
    close_enough(b["mid"], mid, 0)
    close_enough(b["lower"], lo, 0)


@pytest.mark.parametrize("sym", SYMBOLS)
def test_stochastic_matches_talib_when_range_nonzero(sym):
    d = load(sym)
    k, dd = talib.STOCH(d["h"], d["l"], d["c"], 14, 3, 0, 3, 0)
    s = ind.stochastic(d["h"], d["l"], d["c"], 14, 3, 3)
    close_enough(s["k"], k, 0, rtol=1e-6, atol=1e-6)
    close_enough(s["d"], dd, 0, rtol=1e-6, atol=1e-6)


@pytest.mark.parametrize("sym", SYMBOLS)
def test_obv_matches_talib(sym):
    d = load(sym)
    close_enough(ind.obv(d["c"], d["v"]), talib.OBV(d["c"], d["v"]), 0)


@pytest.mark.parametrize("sym", SYMBOLS)
def test_macd_converges_to_talib(sym):
    """TA-Lib khởi tạo EMA nhanh/chậm hơi khác ở đoạn đầu; sai khác phải triệt tiêu sau giai đoạn hội tụ."""
    d = load(sym)
    m, s, h = talib.MACD(d["c"], 12, 26, 9)
    mine = ind.macd(d["c"], 12, 26, 9)
    close_enough(mine["macd"], m, 300, rtol=1e-5, atol=1e-6)
    close_enough(mine["signal"], s, 300, rtol=1e-5, atol=1e-6)
    close_enough(mine["hist"], h, 300, rtol=1e-4, atol=1e-5)


# ---------------------------------------------------------------- không nhìn trước tương lai
@pytest.mark.parametrize("sym", ["FPT", "XAUUSD"])
def test_no_lookahead_truncation(sym):
    """Tính trên toàn chuỗi và trên chuỗi cắt tại t phải cho cùng giá trị tại t."""
    import pandas as pd
    d = load(sym, last=700)
    df = pd.DataFrame({k: d[k] for k in ("o", "h", "l", "c", "v")})
    full = ind.compute_all(df)
    for cut in (260, 400, 650):
        part = ind.compute_all(df.iloc[:cut].reset_index(drop=True))
        a, b = full.iloc[cut - 1].to_numpy(dtype=float), part.iloc[cut - 1].to_numpy(dtype=float)
        np.testing.assert_allclose(a, b, rtol=1e-9, atol=1e-9, equal_nan=True, err_msg=f"lệch tại cut={cut}")


# ---------------------------------------------------------------- logic từng hàm
def test_swings_confirmation_lag_and_ties():
    h = np.array([1, 2, 3, 2, 1, 2, 5, 5, 1, 0.0])
    l = h - 0.5
    sw = ind.swings(h, l, k=2)
    highs = [s for s in sw if s["type"] == "high"]
    assert [s["index"] for s in highs] == [2]  # đỉnh 5-5 hòa nhau: so sánh chặt nên không là swing
    assert all(s["confirmed_at"] == s["index"] + 2 for s in sw)


def test_swings_not_visible_before_confirmation():
    rng = np.random.default_rng(0)
    h = np.cumsum(rng.normal(size=300)) + 100
    l = h - 1
    known_full = {(s["index"], s["type"]) for s in ind.swings(h, l, 2) if s["confirmed_at"] <= 200}
    known_cut = {(s["index"], s["type"]) for s in ind.swings(h[:201], l[:201], 2)}
    assert known_full == known_cut


def test_vwap_resets_each_day():
    h = np.array([10, 12, 20, 22.0]); l = h - 2; c = h - 1; v = np.array([1, 3, 2, 2.0])
    out = ind.vwap_intraday(h, l, c, v, ["a", "a", "b", "b"])
    tp = (h + l + c) / 3
    assert out[0] == pytest.approx(tp[0])
    assert out[1] == pytest.approx((tp[0] * 1 + tp[1] * 3) / 4)
    assert out[2] == pytest.approx(tp[2])  # reset sang ngày mới


def test_pivots_and_fib():
    p = ind.pivots(110, 90, 100)
    assert p["P"] == pytest.approx(100) and p["R1"] == pytest.approx(110) and p["S1"] == pytest.approx(90)
    assert p["R2"] == pytest.approx(120) and p["S2"] == pytest.approx(80)
    f = ind.fib_retracement(100, 200)  # sóng tăng 100 -> 200
    assert f["0.5"] == pytest.approx(150) and f["0.618"] == pytest.approx(200 - 61.8)


def test_rsi_extremes():
    up = np.arange(1, 60, dtype=float)
    assert ind.rsi(up, 14)[-1] == pytest.approx(100.0)
    assert ind.rsi(up[::-1].copy(), 14)[-1] == pytest.approx(0.0)


def test_stochastic_flat_range_is_nan_not_signal():
    x = np.full(40, 5.0)
    s = ind.stochastic(x, x, x)
    assert np.isnan(s["k"]).all()
