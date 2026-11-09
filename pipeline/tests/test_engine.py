import numpy as np
import pandas as pd
import pytest

from pipeline import engine as eg
from pipeline import indicators as ind
from pipeline.common import DATA, read_json


def V(group, vote, na=False):
    return {"group": group, "group_vi": group, "vote": vote, "reading": "", "text": "", "evidence": [], "na": na}


def test_decide_high_needs_three_groups_and_no_opposition():
    r = eg.Engine.decide([V("trend", 1), V("momentum", 1), V("volume", 1), V("structure", 0)])
    assert r["direction"] == 1 and r["confidence"] == "high"
    r = eg.Engine.decide([V("trend", 1), V("momentum", 1), V("volume", 1), V("structure", -1)])
    assert r["direction"] == 1 and r["confidence"] == "medium"  # có 1 nhóm ngược chiều -> không "high"


def test_decide_conflict_and_single_group_are_sideways_low():
    r = eg.Engine.decide([V("trend", 1), V("momentum", 1), V("volume", -1), V("structure", -1)])
    assert r["direction"] == 0 and r["confidence"] == "low" and "mâu thuẫn" in r["confluence_note"]
    r = eg.Engine.decide([V("trend", 1), V("momentum", 0), V("volume", 0), V("structure", 0)])
    assert r["direction"] == 0 and r["confidence"] == "low"


def test_decide_ignores_not_applicable_groups():
    r = eg.Engine.decide([V("trend", -1), V("momentum", -1), V("volume", 0, na=True), V("structure", 0)])
    assert r["direction"] == -1 and r["confidence"] == "medium"


def real_engine(sym="FPT", last=700):
    p = DATA / "prices" / sym / "D.json"
    if not p.exists():
        pytest.skip("chưa có dữ liệu")
    b = np.array(read_json(p)["bars"], dtype=float)
    df = pd.DataFrame(b, columns=["t", "o", "h", "l", "c", "v"])
    return df


@pytest.mark.parametrize("sym", ["FPT", "XAUUSD"])
@pytest.mark.parametrize("horizon", eg.HORIZONS)
def test_signals_are_causal(sym, horizon):
    df = real_engine(sym)
    full_ind = ind.compute_all(df, with_volume=bool(df["v"].sum() > 0))
    full = eg.Engine(df, full_ind)
    d_full, c_full = full.signal_arrays(horizon, start=df.shape[0] - 400)
    for cut in (len(df) - 250, len(df) - 120, len(df) - 30):
        part = eg.Engine(df.iloc[:cut], full_ind.iloc[:cut])
        d_p, c_p = part.signal_arrays(horizon, start=len(df) - 400)
        np.testing.assert_array_equal(np.nan_to_num(d_full[:cut], nan=9), np.nan_to_num(d_p, nan=9), err_msg=f"hướng lệch {sym} {horizon} cut={cut}")
        np.testing.assert_array_equal(np.nan_to_num(c_full[:cut], nan=9), np.nan_to_num(c_p, nan=9))


def test_explain_has_evidence_and_consistent_direction():
    df = real_engine("VCB")
    e = eg.Engine(df, ind.compute_all(df))
    for h in eg.HORIZONS:
        x = e.explain(len(df) - 1, h)
        assert x["direction"] in (-1, 0, 1) and x["confidence"] in ("low", "medium", "high")
        assert len(x["groups"]) == 4 and all(g["text"] for g in x["groups"])
        assert x["scenario_main"] and x["scenario_alt"]
        if x["direction"] != 0:
            assert x["invalidation"] is not None
        # hướng trong explain phải trùng với signal_arrays tại cùng nến
        d, _ = e.signal_arrays(h, start=len(df) - 3)
        assert d[-1] == x["direction"]


def test_vn_number_format():
    assert eg.vn(51000, 0) == "51.000" and eg.vn(1234.5, 2) == "1.234,50" and eg.vn(None) == "—"
