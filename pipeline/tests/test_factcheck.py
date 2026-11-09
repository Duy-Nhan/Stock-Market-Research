"""Test gác cổng chống bịa đặt: phải BẮT được số bịa, câu thiếu trích dẫn, trích dẫn không có thật, v.v."""
import pytest

from pipeline import factcheck as fc

SRC = {"s1": {"url": "https://vnexpress.net/a.html", "kind": "news", "title": "t", "outlet": "VnExpress"},
       "d1": {"url": "https://en.wikipedia.org/wiki/X", "kind": "definition", "title": "d", "outlet": "Wikipedia"}}
PAGES = {"https://vnexpress.net/a.html": "Giá USD ngân hàng giảm thêm 50 đồng, về 25.730 đồng. Xuất khẩu tăng 51,43% so với cùng kỳ.",
         "https://en.wikipedia.org/wiki/X": "Net interest margin (NIM) is a measure of the difference between interest income and interest paid."}
CL = {"sources": SRC, "claims": {"c1": {"source": "s1", "quote": "Giá USD ngân hàng giảm thêm 50 đồng, về 25.730 đồng"},
                                 "c2": {"source": "s1", "quote": "Xuất khẩu tăng 51,43% so với cùng kỳ"},
                                 "c3": {"source": "d1", "quote": "Net interest margin (NIM) is a measure of the difference"}}}


def run(md, claims=CL, **kw):
    return fc.check(md, claims, lambda k: {"px:VCB": "53.600"}[k], fetch_text=lambda u: PAGES[u], min_words=0, max_words=10**6, **kw)


def test_good_report_passes():
    md = "## A\n{fact} Giá USD ngân hàng giảm 50 đồng, về 25.730 đồng [[c1]]. Xuất khẩu tăng 51,43% [[c2]].\n{data} VCB đóng cửa {{px:VCB}} đồng.\n{def} NIM đo chênh lệch thu nhập lãi và chi phí lãi [[c3]]."
    r = run(md)
    assert r["ok"], r["errors"]


def test_fabricated_number_in_fact_is_caught():
    r = run("{fact} Xuất khẩu tăng 61,43% [[c2]].")
    assert not r["ok"] and any("61,43" in e for e in r["errors"])


def test_sentence_without_citation_is_caught():
    r = run("{fact} Giá USD giảm [[c1]]. Thị trường rất sôi động và nhiều người mua vào.")
    assert not r["ok"] and any("không có trích dẫn" in e for e in r["errors"])


def test_quote_not_in_source_is_caught():
    bad = {"sources": SRC, "claims": {"c1": {"source": "s1", "quote": "Giá USD tăng mạnh 200 đồng"}}}
    r = run("{fact} Giá USD tăng 200 đồng [[c1]].", claims=bad)
    assert not r["ok"] and any("KHÔNG có trong trang nguồn" in e for e in r["errors"])


def test_handtyped_number_in_data_tier_is_caught():
    r = run("{data} VCB đóng cửa 53.600 đồng.")
    assert not r["ok"] and any("gõ tay" in e for e in r["errors"])


def test_unresolvable_placeholder_is_caught():
    r = run("{data} VCB {{px:XXX}} đồng.")
    assert not r["ok"] and any("không giải được" in e for e in r["errors"])


def test_untagged_paragraph_and_absolute_words_are_caught():
    r = run("Một đoạn không nhãn.\n{opinion} Giá chắc chắn sẽ tăng.")
    assert not r["ok"]
    assert any("không có nhãn" in e for e in r["errors"]) and any("chắc chắn" in e for e in r["errors"])


def test_definition_must_cite_definition_source():
    r = run("{def} NIM là chênh lệch lãi [[c1]].")
    assert not r["ok"] and any("definition" in e for e in r["errors"])


def test_domain_not_approved_is_caught():
    bad = {"sources": {"s1": {"url": "https://blog.example.com/a", "kind": "news", "title": "", "outlet": ""}}, "claims": {"c1": {"source": "s1", "quote": "x"}}}
    r = fc.check("{fact} A [[c1]].", bad, lambda k: "", fetch_text=lambda u: "x", min_words=0, max_words=99999)
    assert not r["ok"] and any("tên miền" in e for e in r["errors"])


def test_number_variants_handle_vi_and_en_formats():
    assert fc.covered("1.714,32", fc.build_pool(["đóng cửa 1,714.32 điểm"]))
    assert fc.covered("0,64", fc.build_pool(["giảm 0.64%"]))
    assert fc.covered("25.730", fc.build_pool(["25.730 đồng"]))
    assert not fc.covered("25.370", fc.build_pool(["25.730 đồng"]))


def test_dates_and_small_integers_are_not_flagged():
    r = run("{fact} Ngày 9/11, giá USD giảm 50 đồng, về 25.730 đồng trong tháng 11 năm 2026 [[c1]].")
    assert r["ok"], r["errors"]


def test_word_count_bounds():
    r = fc.check("{note} Ngắn.", {"sources": {}, "claims": {}}, lambda k: "", fetch_text=lambda u: "", min_words=1800, max_words=2200)
    assert not r["ok"] and any("số từ" in e for e in r["errors"])
