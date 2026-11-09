import numpy as np
import pytest

from pipeline import indicators as ind
from pipeline import structure as st
from pipeline.common import DATA, read_json


def zigzag_uptrend(n_waves=8, wave=12, base=100.0, rise=2.0, amp=6.0):
    """Sóng tăng: đáy cao dần chính xác theo đường thẳng, đỉnh cao dần. Chỉ dùng để kiểm tra logic."""
    h, l, c = [], [], []
    for w in range(n_waves):
        lo = base + rise * w
        hi = lo + amp
        for j in range(wave):
            x = j / (wave - 1)
            price = lo + (hi - lo) * (1 - abs(2 * x - 1))  # tam giác: lo -> hi -> lo
            c.append(price)
            h.append(price + 0.2)
            l.append(price - 0.2 if (j not in (0, wave - 1)) else lo - 0.2 + 0.0)
    return np.array(h), np.array(l), np.array(c)


def test_trend_state_dow_logic():
    sw = [
        {"index": 5, "type": "low", "price": 10, "confirmed_at": 10},
        {"index": 12, "type": "high", "price": 20, "confirmed_at": 17},
        {"index": 20, "type": "low", "price": 12, "confirmed_at": 25},
        {"index": 28, "type": "high", "price": 25, "confirmed_at": 33},
    ]
    s = st.trend_state(40, sw)
    assert s[33] == 1.0  # đỉnh 25>20 và đáy 12>10
    assert np.isnan(s[24])  # trước đó chưa đủ 2 đỉnh
    sw2 = sw[:3] + [{"index": 28, "type": "high", "price": 15, "confirmed_at": 33}]
    assert st.trend_state(40, sw2)[33] == 0.0  # đáy cao dần nhưng đỉnh thấp dần -> hỗn hợp


def test_uptrend_line_detected_and_causal():
    h, l, c = zigzag_uptrend()
    atr = ind.atr(h, l, c, 14)
    res = st.analyze(h, l, c, atr, k=3)
    ups = [s for s in res["trendlines"] if s["kind"] == "up"]
    assert ups, "phải phát hiện đường xu hướng tăng"
    for s in ups:
        conf_second = s["i2"] + 3
        assert s["from"] >= conf_second, "đường chỉ được biết sau khi swing thứ hai đã xác nhận"
        assert s["p2"] > s["p1"]


@pytest.mark.parametrize("sym,res", [("FPT", "D"), ("XAUUSD", "D"), ("VCB", "60")])
def test_structure_no_lookahead_on_real_data(sym, res):
    p = DATA / "prices" / sym / f"{res}.json"
    if not p.exists():
        pytest.skip("chưa có dữ liệu")
    b = np.array(read_json(p)["bars"], dtype=float)[-500:]
    h, l, c = b[:, 2], b[:, 3], b[:, 4]
    atr = ind.atr(h, l, c, 14)
    full = st.analyze(h, l, c, atr)
    for cut in (250, 380, 480):
        part = st.analyze(h[:cut], l[:cut], c[:cut], atr[:cut])
        np.testing.assert_array_equal(np.nan_to_num(full["trend_state"][:cut], nan=9), np.nan_to_num(part["trend_state"], nan=9))
        key = lambda s: (s["kind"], s["i1"], s["i2"], s["from"])
        known_full = {key(s) for s in full["trendlines"] if s["from"] <= cut - 1}
        assert known_full == {key(s) for s in part["trendlines"]}, f"đường xu hướng lệch tại cut={cut}"
        zf = sorted(tuple(map(tuple, [e for e in z["hist"] if e[0] <= cut - 1])) for z in full["zones"] if any(e[0] <= cut - 1 for e in z["hist"]) and len([e for e in z["hist"] if e[0] <= cut - 1]) >= 2)
        zp = sorted(tuple(map(tuple, z["hist"])) for z in part["zones"])
        assert zf == zp, f"vùng S/R lệch tại cut={cut}"


def test_trendline_segments_do_not_use_future_break():
    """Đoạn đường có 'to' phải do nến i=to+1 phá/đổi, không phải thông tin tương lai: to >= from-1."""
    h, l, c = zigzag_uptrend()
    atr = ind.atr(h, l, c, 14)
    for s in st.analyze(h, l, c, atr, k=3)["trendlines"]:
        assert s["to"] is None or s["to"] >= s["from"] - 1


def test_zones_need_two_swings_and_cluster_by_atr():
    atr = np.full(100, 2.0)
    sw = [{"index": 10, "type": "high", "price": 100.0, "confirmed_at": 15},
          {"index": 40, "type": "high", "price": 100.8, "confirmed_at": 45},   # trong 0,5*ATR=1.0 -> cùng vùng
          {"index": 60, "type": "low", "price": 90.0, "confirmed_at": 65}]     # vùng riêng, chỉ 1 swing -> bị loại
    z = st.sr_zones(atr, sw)
    assert len(z) == 1 and z[0]["hist"][-1][2] == 2 and z[0]["hist"][-1][1] == pytest.approx(100.4)


def test_daily_pivots_use_previous_day_only():
    keys = ["d1", "d1", "d2", "d2", "d3"]
    h = [10, 12, 11, 13, 9]; l = [8, 9, 10, 11, 7]; c = [9, 11, 10.5, 12, 8]
    p = st.daily_pivots(keys, h, l, c)
    assert np.isnan(p["P"][0]) and np.isnan(p["P"][1])
    # d2 dùng H=12, L=8, C=11 của d1
    assert p["P"][2] == pytest.approx((12 + 8 + 11) / 3) and p["P"][3] == p["P"][2]
    # d3 dùng H=13, L=10, C=12 của d2
    assert p["P"][4] == pytest.approx((13 + 10 + 12) / 3)
