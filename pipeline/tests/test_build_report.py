from pipeline import build_report as br


def test_combine_agree_caps_confidence_at_medium():
    r = br.combine(-1, "high", -1)
    assert r["direction"] == -1 and r["confidence"] == "medium" and r["relation"] == "agree"
    assert br.combine(1, "low", 1)["confidence"] == "low"


def test_combine_conflict_is_neutral_and_flagged():
    r = br.combine(1, "high", -1)
    assert r["direction"] == 0 and r["confidence"] == "low" and r["relation"] == "conflict"


def test_combine_one_sided_is_low_confidence():
    assert br.combine(0, "low", 1) == {"direction": 1, "confidence": "low", "relation": "news_only", "relation_vi": "chỉ tin tức nghiêng, kỹ thuật trung lập"}
    r = br.combine(-1, "high", 0)
    assert r["direction"] == -1 and r["confidence"] == "low" and r["relation"] == "tech_only"
    assert br.combine(0, "low", 0)["relation"] == "both_neutral"
