"""Kiểm tra mô hình giá bằng chuỗi dựng tay (chỉ kiểm tra logic) + tính nhân quả trên dữ liệu thật."""
import numpy as np
import pytest

from pipeline import chart_patterns as cpt
from pipeline import indicators as ind
from pipeline import structure as st
from pipeline.common import DATA, read_json


def series(points, n):
    """Nội suy tuyến tính giữa các điểm (chỉ số, giá) -> giá đóng cửa; h=c+0.3, l=c-0.3."""
    xs, ys = zip(*points)
    c = np.interp(np.arange(n), xs, ys)
    return c + 0.3, c - 0.3, c


def sw(index, typ, price, k=5):
    return {"index": index, "type": typ, "price": price, "confirmed_at": index + k}


def test_double_top_lifecycle_and_measured_move():
    n = 120
    h, l, c = series([(0, 100), (30, 120), (45, 112), (60, 120), (95, 102), (119, 98)], n)
    h[30], h[60] = 120.5, 120.2
    atr = np.full(n, 1.0)
    pats = cpt.detect(h, l, c, atr, None, [sw(30, "high", 120.5), sw(60, "high", 120.2)])
    p = [x for x in pats if x["type"] == "double_top"]
    assert len(p) == 1
    p = p[0]
    neck = float(l[31:60].min())
    exp_break = next(j for j in range(61, n) if c[j] < neck - 0.25)
    assert p["formed_at"] == 65 and p["confirmed_at"] == max(65, exp_break)
    height = (120.5 + 120.2) / 2 - neck
    assert p["target"] == pytest.approx(neck - height)
    assert cpt.status_at(p, 64) is None and cpt.status_at(p, 65) == "forming" and cpt.status_at(p, p["confirmed_at"]) == "confirmed"
    exp_hit = next((j for j in range(p["confirmed_at"] + 1, n) if l[j] <= p["target"]), None)
    assert p["target_hit_at"] == exp_hit


def test_double_top_invalidated_if_price_breaks_above():
    n = 100
    h, l, c = series([(0, 100), (30, 120), (45, 112), (60, 120), (75, 123), (99, 130)], n)
    h[30], h[60] = 120.5, 120.2
    pats = cpt.detect(h, l, c, np.full(n, 1.0), None, [sw(30, "high", 120.5), sw(60, "high", 120.2)])
    p = [x for x in pats if x["type"] == "double_top"][0]
    assert p["confirmed_at"] is None and p["invalidated_at"] is not None
    assert cpt.status_at(p, 99) == "invalidated"


def test_double_top_rejected_when_tops_differ_by_more_than_one_atr():
    n = 100
    h, l, c = series([(0, 100), (30, 120), (45, 112), (60, 117), (99, 100)], n)
    h[30], h[60] = 120.5, 117.2
    pats = cpt.detect(h, l, c, np.full(n, 1.0), None, [sw(30, "high", 120.5), sw(60, "high", 117.2)])
    assert not [x for x in pats if x["type"] == "double_top"]


def test_double_bottom_mirror():
    n = 120
    h, l, c = series([(0, 140), (30, 120), (45, 128), (60, 120), (95, 138), (119, 142)], n)
    l[30], l[60] = 119.5, 119.8
    pats = cpt.detect(h, l, c, np.full(n, 1.0), None, [sw(30, "low", 119.5), sw(60, "low", 119.8)])
    p = [x for x in pats if x["type"] == "double_bottom"]
    assert len(p) == 1 and p[0]["bias"] == 1 and p[0]["confirmed_at"] is not None and p[0]["target"] > p[0]["neckline"]["p1"]


def test_head_and_shoulders_breakdown():
    n = 160
    pts = [(0, 100), (20, 118), (30, 110), (50, 126), (70, 110), (90, 118), (125, 100), (159, 92)]
    h, l, c = series(pts, n)
    h[20], h[50], h[90] = 118.4, 126.4, 118.2
    swings = [sw(20, "high", 118.4), sw(50, "high", 126.4), sw(90, "high", 118.2)]
    pats = cpt.detect(h, l, c, np.full(n, 1.0), None, swings)
    p = [x for x in pats if x["type"] == "head_shoulders"]
    assert len(p) == 1
    p = p[0]
    assert p["formed_at"] == 95 and p["confirmed_at"] is not None and p["target"] < p["neckline"]["p1"]
    assert p["bias"] == -1 and len(p["points"]) == 5


def test_head_and_shoulders_needs_head_higher_than_shoulders():
    n = 160
    pts = [(0, 100), (20, 118), (30, 110), (50, 118.6), (70, 110), (90, 118), (125, 100), (159, 92)]
    h, l, c = series(pts, n)
    h[20], h[50], h[90] = 118.4, 119.0, 118.2
    swings = [sw(20, "high", 118.4), sw(50, "high", 119.0), sw(90, "high", 118.2)]
    assert not [x for x in cpt.detect(h, l, c, np.full(n, 1.0), None, swings) if x["type"] == "head_shoulders"]


def test_ascending_triangle_breakout_with_volume():
    n = 100
    h, l, c = series([(0, 100), (20, 109.7), (30, 100.3), (45, 109.7), (55, 104.3), (60, 107), (75, 116), (99, 120)], n)
    h[20], h[45] = 110.0, 110.0
    l[30], l[55] = 100.0, 104.0
    swings = [sw(20, "high", 110.0), sw(45, "high", 110.0), sw(30, "low", 100.0), sw(55, "low", 104.0)]
    vr = np.full(n, 1.6)
    pats = cpt.detect(h, l, c, np.full(n, 1.0), vr, swings)
    t = [x for x in pats if x["type"] == "ascending_triangle"]
    assert t, "phải nhận diện tam giác tăng"
    t = t[0]
    assert t["formed_at"] == 60 and t["confirmed_at"] is not None and t["breakout_dir"] == 1
    assert t["volume_confirmed"] is True and t["target"] > 110.0


def test_status_is_causal_confirmation_not_visible_early():
    n = 120
    h, l, c = series([(0, 100), (30, 120), (45, 112), (60, 120), (95, 102), (119, 98)], n)
    h[30], h[60] = 120.5, 120.2
    p = [x for x in cpt.detect(h, l, c, np.full(n, 1.0), None, [sw(30, "high", 120.5), sw(60, "high", 120.2)]) if x["type"] == "double_top"][0]
    for i in range(65, p["confirmed_at"]):
        assert cpt.status_at(p, i) == "forming"


@pytest.mark.parametrize("sym,res", [("FPT", "D"), ("VCB", "D"), ("XAUUSD", "D"), ("GAS", "D")])
def test_chart_patterns_causal_on_real_data(sym, res):
    p = DATA / "prices" / sym / f"{res}.json"
    if not p.exists():
        pytest.skip("chưa có dữ liệu")
    b = np.array(read_json(p)["bars"], dtype=float)[-900:]
    h, l, c, v = b[:, 2], b[:, 3], b[:, 4], b[:, 5]
    atr = ind.atr(h, l, c, 14)
    vr = v / ind.sma(v, 20) if v.sum() > 0 else None
    sws = st.find_swings(h, l, 5)
    full = cpt.detect(h, l, c, atr, vr, sws)
    ev = ["confirmed_at", "invalidated_at", "expired_at", "failed_at", "target_hit_at", "superseded_at"]
    for cut in (400, 600, 800):
        part = cpt.detect(h[:cut], l[:cut], c[:cut], atr[:cut], None if vr is None else vr[:cut], [s for s in sws if s["confirmed_at"] < cut])
        pk = {(x["type"], x["formed_at"]): x for x in part}
        for x in full:
            if x["formed_at"] >= cut:
                continue
            y = pk.get((x["type"], x["formed_at"]))
            assert y is not None, f"thiếu mô hình {x['type']}@{x['formed_at']} khi cắt ở {cut}"
            for e in ev:
                exp = x.get(e) if (x.get(e) is not None and x.get(e) < cut) else None
                assert y.get(e) == exp, f"{x['type']}@{x['formed_at']} {e}: {y[e]} != {exp} (cut={cut})"
        assert len(part) == len([x for x in full if x["formed_at"] < cut])
