"""Kiểm tra quy tắc nhận diện nến bằng các nến dựng tay (chỉ để kiểm tra logic, không hiển thị cho người dùng)."""
import numpy as np
import pytest

from pipeline import candle_patterns as cp
from pipeline import indicators as ind
from pipeline.common import DATA, read_json


def base_down(n=30, start=200.0, step=-2.0):
    """chuỗi nến giảm đều (thân nhỏ, biên độ ~2) làm bối cảnh xu hướng giảm."""
    o, h, l, c = [], [], [], []
    p = start
    for _ in range(n):
        o.append(p); c.append(p + step); h.append(p + 0.3); l.append(p + step - 0.3); p += step
    return o, h, l, c


def base_up(n=30, start=100.0, step=2.0):
    return base_down(n, start, step)


def run(o, h, l, c):
    atr = ind.atr(h, l, c, 14)
    return cp.detect(o, h, l, c, atr), atr


def names(res, i=None):
    return {r["name"] for r in res if i is None or r["index"] == i}


def test_hammer_only_after_downtrend_hanging_man_after_uptrend():
    o, h, l, c = base_down(); p = c[-1]
    # nến búa: thân nhỏ ở đỉnh, bóng dưới dài (>= 2 thân)
    o.append(p - 0.2); c.append(p + 0.1); h.append(p + 0.12); l.append(p - 3.5)
    res, _ = run(o, h, l, c)
    assert "hammer" in names(res, len(c) - 1) and "hanging_man" not in names(res)
    o, h, l, c = base_up(); p = c[-1]
    o.append(p - 0.2); c.append(p + 0.1); h.append(p + 0.12); l.append(p - 3.5)
    res, _ = run(o, h, l, c)
    assert "hanging_man" in names(res, len(c) - 1) and "hammer" not in names(res)


def test_hammer_shape_without_trend_is_not_reported():
    rng = np.random.default_rng(1)
    c = list(100 + np.cumsum(rng.normal(0, 0.2, 40)))  # đi ngang
    o = [x + 0.05 for x in c]; h = [x + 0.3 for x in c]; l = [x - 0.3 for x in c]
    p = c[-1]
    o.append(p - 0.2); c.append(p + 0.1); h.append(p + 0.12); l.append(p - 3.5)
    res, _ = run(o, h, l, c)
    assert "hammer" not in names(res) and "hanging_man" not in names(res)


def test_bullish_engulfing_and_confirmation_uses_next_bar():
    o, h, l, c = base_down(); p = c[-1]
    # nến giảm nhỏ rồi nến tăng nhấn chìm thân
    o.append(p + 0.2); c.append(p - 0.6); h.append(p + 0.3); l.append(p - 0.7)
    o.append(p - 0.8); c.append(p + 0.9); h.append(p + 1.0); l.append(p - 0.9)
    o.append(p + 0.9); c.append(p + 2.0); h.append(p + 2.1); l.append(p + 0.8)  # nến kế: đóng cao hơn -> xác nhận
    res, _ = run(o, h, l, c)
    e = [r for r in res if r["name"] == "bullish_engulfing"]
    assert e and e[0]["index"] == len(c) - 2 and e[0]["confirmed_at"] == len(c) - 1 and e[0]["failed_at"] is None


def test_bullish_engulfing_failure_when_next_close_below_pattern_low():
    o, h, l, c = base_down(); p = c[-1]
    o.append(p + 0.2); c.append(p - 0.6); h.append(p + 0.3); l.append(p - 0.7)
    o.append(p - 0.8); c.append(p + 0.9); h.append(p + 1.0); l.append(p - 0.9)
    o.append(p + 0.5); c.append(p - 2.0); h.append(p + 0.6); l.append(p - 2.1)  # đóng dưới đáy mô hình -> thất bại
    res, _ = run(o, h, l, c)
    e = [r for r in res if r["name"] == "bullish_engulfing"][0]
    assert e["failed_at"] == len(c) - 1 and e["confirmed_at"] is None


def test_morning_star_three_bars():
    o, h, l, c = base_down(); p = c[-1]
    o.append(p); c.append(p - 4.0); h.append(p + 0.1); l.append(p - 4.2)           # nến giảm dài
    o.append(p - 4.6); c.append(p - 4.5); h.append(p - 4.3); l.append(p - 4.9)    # sao nhỏ, thân dưới đóng cửa trước
    o.append(p - 4.4); c.append(p - 0.5); h.append(p - 0.3); l.append(p - 4.5)    # nến tăng dài qua điểm giữa thân nến đầu
    res, _ = run(o, h, l, c)
    assert "morning_star" in names(res, len(c) - 1)


def test_doji_neutral_and_direction_zero():
    o, h, l, c = base_up(); p = c[-1]
    o.append(p); c.append(p + 0.05); h.append(p + 1.5); l.append(p - 1.5)
    res, _ = run(o, h, l, c)
    d = [r for r in res if r["name"] == "doji"]
    assert d and d[0]["dir"] == 0 and d[0]["confirmed_at"] is None


@pytest.mark.parametrize("sym", ["FPT", "VCB", "XAUUSD"])
def test_detection_is_causal_on_real_data(sym):
    p = DATA / "prices" / sym / "D.json"
    if not p.exists():
        pytest.skip("chưa có dữ liệu")
    b = np.array(read_json(p)["bars"], dtype=float)[-700:]
    o, h, l, c = b[:, 1], b[:, 2], b[:, 3], b[:, 4]
    atr = ind.atr(h, l, c, 14)
    full = cp.detect(o, h, l, c, atr)
    for cut in (300, 500, 650):
        part = cp.detect(o[:cut], h[:cut], l[:cut], c[:cut], atr[:cut])
        key = lambda r: (r["index"], r["name"], r["dir"])
        assert {key(r) for r in full if r["index"] < cut} == {key(r) for r in part}, f"lệch tại cut={cut}"
    assert len(full) > 0
