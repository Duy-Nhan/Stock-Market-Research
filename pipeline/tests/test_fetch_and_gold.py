"""Test logic chuẩn hóa/hợp nhất/kiểm tra dữ liệu và quy đổi vàng. Không gọi mạng."""
import pytest

from pipeline import fetch_prices as fp
from pipeline import gold


def test_normalize_dchart_multiplier_and_rounding():
    payload = {"s": "ok", "t": [1, 2], "o": [17.55, 1.0], "h": [17.6, 1.1], "l": [17.5, 0.9], "c": [17.55, 1.0], "v": [10, 20]}
    bars = fp.normalize_dchart(payload, 1000.0)
    assert bars[0][1:5] == [17550.0, 17600.0, 17500.0, 17550.0]  # không dính lỗi dấu phẩy động 17550.000000000002


def test_normalize_dchart_no_data_and_bad_status():
    assert fp.normalize_dchart({"s": "no_data"}, 1.0) == []
    with pytest.raises(fp.FetchError):
        fp.normalize_dchart({"s": "error"}, 1.0)
    with pytest.raises(fp.FetchError):
        fp.normalize_dchart({"s": "ok", "t": [1, 2], "o": [1], "h": [1, 1], "l": [1, 1], "c": [1, 1], "v": [1, 1]}, 1.0)


def test_merge_new_bar_overrides_partial_old():
    old = [[1, 1, 1, 1, 1, 5], [2, 2, 2, 2, 2, 5]]
    new = [[2, 2, 3, 2, 3, 9], [3, 3, 3, 3, 3, 1]]
    m = fp.merge_bars(old, new)
    assert [b[0] for b in m] == [1, 2, 3] and m[1][5] == 9


def test_validate_counts_anomalies_without_modifying():
    bars = [[1, 10, 12, 9, 11, 5], [1, 10, 8, 9, 11, 0], [0, 10, 12, 9, 11, -1]]
    snapshot = [b[:] for b in bars]
    r = fp.validate_bars(bars)["counts"]
    assert r["duplicate_time"] == 1 and r["non_monotonic_time"] == 1 and r["high_below_low"] == 1
    assert r["negative_volume"] == 1 and r["zero_volume_bars"] == 1
    assert bars == snapshot


def test_plan_window_incremental_has_overlap():
    now = 10_000_000
    existing = {"bars": [[now - 1000, 1, 1, 1, 1, 1]]}
    assert fp.plan_window(existing, "1", now, full=False) == now - 1000 - 86400
    assert fp.plan_window(existing, "1", now, full=True) == now - fp.RETENTION_DAYS["1"] * 86400
    assert fp.plan_window(None, "D", now, full=False) == now - fp.RETENTION_DAYS["D"] * 86400


def test_gold_conversion_constants_and_premium_identity():
    # 1 oz = 31,1034768 g; 1 lượng = 37,5 g -> 1 lượng = 1,2056 oz
    assert gold.LUONG_G / gold.TROY_OUNCE_G == pytest.approx(1.20565, rel=1e-4)
    w = gold.world_price_vnd_per_luong(4000.0, 25000.0)
    assert w == pytest.approx(4000 * 25000 * 37.5 / 31.1034768)
    assert gold.premium(w, 4000.0, 25000.0) == pytest.approx(0.0, abs=1e-12)
    assert gold.premium(w * 1.1, 4000.0, 25000.0) == pytest.approx(0.1)


# ---------------------------------------------------------------- phát hiện điều chỉnh giá hồi tố
def _payload(ts, close):
    return {"s": "ok", "t": ts, "o": close, "h": close, "l": close, "c": close, "v": [1] * len(ts)}


def test_fetch_refetches_full_history_when_prices_are_retroactively_adjusted(tmp_path, monkeypatch):
    import time
    now = int(time.time())
    day = 86400
    ts = [now - (10 - i) * day for i in range(10)]  # 10 nến ngày
    calls = []

    def fake_get_json(url, **kw):
        calls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(fp, "DATA", tmp_path)
    monkeypatch.setattr(fp, "get_json", fake_get_json)

    # lần 1: lấy lịch sử ban đầu, giá = 100
    responses = [_payload(ts, [100.0] * 10)]
    fp.fetch_dchart_symbol("AAA", 1.0, "D", full=False)

    # lần 2: nguồn đã điều chỉnh hồi tố (giá cũ x0,9). Cửa sổ chồng lấn lệch -> phải gọi lần nữa lấy toàn bộ
    responses = [_payload(ts[-6:], [90.0] * 6), _payload(ts, [90.0] * 10)]
    meta = fp.fetch_dchart_symbol("AAA", 1.0, "D", full=False)
    saved = fp.read_json(tmp_path / "prices" / "AAA" / "D.json")
    assert meta["refetch_reason"] and "điều chỉnh" in meta["refetch_reason"]
    assert all(b[4] == 90.0 for b in saved["bars"]), "chuỗi bị trộn giữa giá cũ và giá đã điều chỉnh"
    assert len(saved["bars"]) == 10

    # lần 3: không có điều chỉnh mới -> không lấy lại toàn bộ
    responses = [_payload(ts[-6:], [90.0] * 6)]
    calls.clear()
    meta = fp.fetch_dchart_symbol("AAA", 1.0, "D", full=False)
    assert meta["refetch_reason"] is None and len(calls) == 1


def test_yahoo_synthetic_quote_bar_is_dropped():
    payload = {"chart": {"result": [{"timestamp": [1700000040, 1700000100, 1700000112],
                                     "indicators": {"quote": [{"open": [1, 2, 3], "high": [1, 2, 3], "low": [1, 2, 3],
                                                               "close": [1, 2, 3], "volume": [5, 6, 0]}]},
                                     "meta": {"symbol": "GC=F"}}], "error": None}}
    bars, extra = fp.normalize_yahoo(payload)
    assert [b[0] for b in bars] == [1700000040, 1700000100]  # 1700000112 có giây lẻ -> nến giả
    assert extra["synthetic_quote_bars_dropped"] == 1
