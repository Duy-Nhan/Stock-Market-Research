"""Test sổ nhật ký trên thư mục dữ liệu tạm với chuỗi giá dựng tay (chỉ để kiểm tra logic)."""
import json
import math
import time
from datetime import datetime

import numpy as np
import pytest

from pipeline import journal as jr
from pipeline.common import VN_TZ, write_json_atomic


def make_data(tmp_path, n=420, drift=0.002, seed=3, adjust_last=None):
    """n nến ngày (loại cuối tuần giả: mỗi nến cách 1 ngày), kết thúc tại 'hôm qua' lúc 07:00 VN (như dchart)."""
    rng = np.random.default_rng(seed)
    end = datetime.now(VN_TZ).replace(hour=7, minute=0, second=0, microsecond=0)
    ts = [int(end.timestamp()) - (n - 1 - i) * 86400 for i in range(n)]
    c = 100 * np.exp(np.cumsum(drift + rng.normal(0, 0.01, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * 1.004; l = np.minimum(o, c) * 0.996
    v = rng.integers(1_000_000, 2_000_000, n).astype(float)
    bars = [[ts[i], float(o[i]), float(h[i]), float(l[i]), float(c[i]), float(v[i])] for i in range(n)]
    write_json_atomic(tmp_path / "prices" / "AAA" / "D.json", {"meta": {"fetched_at": "x"}, "bars": bars})
    return ts, bars


INS = [{"symbol": "AAA", "kind": "vn", "type": "stock", "name": "Test"}]


def at(ts_last, hour):
    d = datetime.fromtimestamp(ts_last, VN_TZ).replace(hour=hour, minute=0, second=0, microsecond=0)
    return d.timestamp()


def test_issue_is_idempotent_and_immutable(tmp_path):
    ts, _ = make_data(tmp_path)
    now = at(ts[-1], 16)  # sau 15:00 cùng ngày của nến cuối -> nến hoàn tất
    r1 = jr.issue(now, tmp_path, INS)
    assert len(r1["created"]) == 2, r1
    path = jr.day_file(tmp_path, jr.vn_date(ts[-1]))
    before = path.read_text()
    r2 = jr.issue(now + 600, tmp_path, INS)
    assert r2["created"] == [] and path.read_text() == before  # không ghi đè, không đổi byte nào


def test_no_issue_when_newer_bar_started_or_stale(tmp_path):
    ts, _ = make_data(tmp_path)
    r = jr.issue(at(ts[-1], 10), tmp_path, INS)  # 10:00 ngày của nến cuối: nến chưa hoàn tất -> dùng nến trước -> đã có nến mới hơn
    assert r["created"] == []
    r = jr.issue(at(ts[-1], 16) + 5 * 86400, tmp_path, INS)  # quá 66 giờ
    assert r["created"] == [] and any("giờ" in why for _, why in r["skipped"])


def test_score_uses_stored_tau_and_flags_adjustment(tmp_path):
    ts, bars = make_data(tmp_path)
    now = at(ts[-1], 16)
    jr.issue(now, tmp_path, INS)
    # bổ sung 10 nến tương lai: tăng mạnh 3%/nến, để nhận định 'tăng' (nếu có) đúng và ngược lại
    last = bars[-1]
    for k in range(1, 11):
        p = last[4] * (1.03 ** k)
        bars.append([ts[-1] + k * 86400, p, p * 1.004, p * 0.996, p, 1_500_000.0])
    write_json_atomic(tmp_path / "prices" / "AAA" / "D.json", {"meta": {"fetched_at": "x"}, "bars": bars})
    s = jr.score(at(bars[-1][0], 16) + 3600, tmp_path, INS)
    assert s["newly_scored_evaluations"] == 3  # next_session@1, 1_2_weeks@5, @10
    doc = json.load(open(jr.day_file(tmp_path, jr.vn_date(ts[-1]))))
    for p in doc["predictions"]:
        for e in p["evaluations"]:
            assert e["outcome"] == 1  # tăng 3%/nến vượt xa τ
            assert e["correct"] == (p["direction"] == 1)
            assert e["adjustment_event"] is False
            assert e["tau"] == p["tau"][str(e["h"])]
    # chấm lần 2 không tạo thêm
    assert jr.score(at(bars[-1][0], 16) + 7200, tmp_path, INS)["newly_scored_evaluations"] == 0
    # mô phỏng điều chỉnh giá hồi tố ×0,9 cho toàn bộ lịch sử -> cờ adjustment_event, kết quả vẫn dùng cùng một cơ sở
    for p in doc["predictions"]:
        p["evaluations"] = []
    write_json_atomic(jr.day_file(tmp_path, jr.vn_date(ts[-1])), doc)
    adj = [[b[0]] + [x * 0.9 for x in b[1:5]] + [b[5]] for b in bars]
    write_json_atomic(tmp_path / "prices" / "AAA" / "D.json", {"meta": {}, "bars": adj})
    jr.score(at(bars[-1][0], 16) + 3600, tmp_path, INS)
    doc = json.load(open(jr.day_file(tmp_path, jr.vn_date(ts[-1]))))
    assert all(e["adjustment_event"] and e["outcome"] == 1 for p in doc["predictions"] for e in p["evaluations"])


def test_score_waits_for_complete_future_bar(tmp_path):
    ts, bars = make_data(tmp_path)
    jr.issue(at(ts[-1], 16), tmp_path, INS)
    p = bars[-1][4]
    bars.append([ts[-1] + 86400, p, p, p, p, 1.0])
    write_json_atomic(tmp_path / "prices" / "AAA" / "D.json", {"meta": {}, "bars": bars})
    assert jr.score(at(ts[-1] + 86400, 10), tmp_path, INS)["newly_scored_evaluations"] == 0  # 10:00: nến mới chưa hoàn tất
    assert jr.score(at(ts[-1] + 86400, 16), tmp_path, INS)["newly_scored_evaluations"] == 1


def test_stats_small_sample_flag(tmp_path):
    ts, bars = make_data(tmp_path)
    jr.issue(at(ts[-1], 16), tmp_path, INS)
    p = bars[-1][4]
    bars.append([ts[-1] + 86400, p, p, p, p, 1.0])
    write_json_atomic(tmp_path / "prices" / "AAA" / "D.json", {"meta": {}, "bars": bars})
    jr.score(at(ts[-1] + 86400, 16), tmp_path, INS)
    s = jr.stats(tmp_path)
    assert s["predictions_issued"] == 2 and s["evaluations_scored"] == 1 and s["overall"]["enough_sample"] is False


def test_issue_combined_overrides_direction_and_keeps_engine_record(tmp_path):
    ts, _ = make_data(tmp_path)
    now = at(ts[-1], 16)
    asof = jr.vn_date(ts[-1])
    jr.issue(now, tmp_path, INS)
    rows = []
    for hz in ("next_session", "1_2_weeks"):
        rows.append({"symbol": "AAA", "horizon": hz, "engine_asof": asof, "engine_direction": 0, "engine_confidence": "low",
                     "news_stance": -1, "news_channel": "kênh thử", "news_claims": ["c1"], "combined_direction": -1,
                     "combined_confidence": "low", "relation": "news_only", "relation_vi": "chỉ tin tức nghiêng"})
    op = tmp_path / "outlook.json"
    write_json_atomic(op, {"date": "2026-01-01", "rows": rows})
    r = jr.issue_combined("2026-01-01", now + 60, tmp_path, INS, outlook_path=op)
    assert len(r["created"]) == 2 and all(c.endswith("_news") for c in r["created"]), r
    doc = json.load(open(jr.day_file(tmp_path, asof)))
    news = [p for p in doc["predictions"] if p["id"].endswith("_news")]
    eng = [p for p in doc["predictions"] if not p["id"].endswith("_news")]
    assert len(eng) == 2 and len(news) == 2
    assert all(p["basis"] == "engine+news" and p["direction"] == -1 and p["news"]["stance"] == -1 for p in news)
    assert all(p["basis"] == "engine" for p in eng)
    before = jr.day_file(tmp_path, asof).read_text()
    assert jr.issue_combined("2026-01-01", now + 120, tmp_path, INS, outlook_path=op)["created"] == []
    assert jr.day_file(tmp_path, asof).read_text() == before
