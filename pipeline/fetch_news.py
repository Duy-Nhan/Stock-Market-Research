"""Thu thập tin kinh tế–tài chính từ RSS đã duyệt (config/sources.json) và gán nhãn sơ bộ theo watchlist.

  data/news/raw/YYYY-MM-DD.json   các mục mới của lần chạy (ngày chạy theo giờ VN): tiêu đề, link, thời điểm đăng, mô tả ngắn, nhãn
  data/news/index.json            {link: lần đầu thấy} để khử trùng lặp giữa các lần chạy
  data/news/cache/<sha1>.txt      văn bản bài báo đã tải (CHỈ để đọc và kiểm chứng trích dẫn; không đưa vào repo — đã .gitignore)

Chính sách: chỉ lưu tiêu đề, link, thời điểm đăng và mô tả ngắn (<= 240 ký tự) do RSS cung cấp; không sao chép nguyên văn bài báo vào dữ liệu công khai.
Dùng:  python -m pipeline.fetch_news            # thu thập RSS
       python -m pipeline.fetch_news --article URL   # tải/đọc một bài (in văn bản ra màn hình)
"""
from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

from .common import DATA, VN_TZ, FetchError, http_get, load_config, now_vn_iso, read_json, write_json_atomic

CACHE = DATA / "news" / "cache"
SNIPPET = 240


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def parse_date(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).astimezone(VN_TZ).replace(microsecond=0).isoformat()
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(s).astimezone(VN_TZ).isoformat()
        except ValueError:
            return None


def parse_rss(xml_bytes: bytes, source_id: str) -> List[Dict[str, Any]]:
    root = ET.fromstring(xml_bytes.decode("utf-8-sig", "replace").strip())
    out = []
    for it in root.iter("item"):
        link = (it.findtext("link") or "").strip()
        title = strip_html(it.findtext("title") or "")
        if not link or not title:
            continue
        out.append({"source": source_id, "title": title, "link": link, "published": parse_date(it.findtext("pubDate")),
                    "snippet": strip_html(it.findtext("description") or "")[:SNIPPET]})
    return out


def compile_terms(terms: List[str]):
    return [re.compile(r"(?<![\wÀ-ỹ])" + re.escape(t) + r"(?![\wÀ-ỹ])", re.I) for t in terms]


def tag(item: Dict[str, Any], kw: Dict[str, Any], _cache: Dict[str, Any] = {}) -> Dict[str, Any]:
    if "t" not in _cache:
        _cache["t"] = {k: compile_terms(v) for k, v in kw["tickers"].items()}
        _cache["h"] = {k: compile_terms(v) for k, v in kw["themes"].items()}
    text = item["title"] + " " + item["snippet"]
    tickers = [k for k, pats in _cache["t"].items() if any(p.search(text) for p in pats)]
    themes = [k for k, pats in _cache["h"].items() if any(p.search(text) for p in pats)]
    return {"tickers": tickers, "themes": themes}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.skip = 0
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style", "noscript", "nav", "footer", "header", "aside"):
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "nav", "footer", "header", "aside") and self.skip:
            self.skip -= 1
        if tag in ("p", "div", "li", "br", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def article_text(url: str, use_cache: bool = True) -> str:
    """Tải bài báo và trích văn bản thô (thô: gồm cả chữ ngoài thân bài). Dùng để đọc và kiểm tra trích dẫn."""
    key = hashlib.sha1(url.encode()).hexdigest()
    p = CACHE / f"{key}.txt"
    if use_cache and p.exists():
        return p.read_text(encoding="utf-8")
    raw = http_get(url, headers={"Accept-Language": "vi,en;q=0.8"}, timeout=40).decode("utf-8", "replace")
    parser = _Text()
    parser.feed(raw)
    text = html.unescape("".join(parser.parts))
    text = "\n".join(re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.splitlines())
    text = re.sub(r"\n{2,}", "\n", text).strip()
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return text


def collect() -> Dict[str, Any]:
    src = load_config("sources.json")["news_sources"]["rss"]
    kw = load_config("news_keywords.json")
    idx = read_json(DATA / "news" / "index.json", {})
    today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    path = DATA / "news" / "raw" / f"{today}.json"
    doc = read_json(path, {"date": today, "items": []})
    seen = {i["link"] for i in doc["items"]}
    stats: Dict[str, Any] = {}
    for sid, cfg in src.items():
        if cfg.get("disabled"):
            continue
        try:
            items = parse_rss(http_get(cfg["url"], timeout=30), sid)
        except (FetchError, ET.ParseError) as e:
            stats[sid] = f"LỖI: {e}"
            continue
        new = 0
        for it in items:
            if it["link"] in idx or it["link"] in seen:
                continue
            it.update(tag(it, kw)); it["first_seen"] = now_vn_iso()
            doc["items"].append(it); idx[it["link"]] = it["first_seen"]; seen.add(it["link"]); new += 1
        stats[sid] = {"fetched": len(items), "new": new}
    doc["items"].sort(key=lambda x: x.get("published") or "", reverse=True)
    write_json_atomic(path, doc, indent=1)
    write_json_atomic(DATA / "news" / "index.json", idx)
    return stats


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--article", help="tải và in văn bản một bài báo")
    a = ap.parse_args(argv)
    if a.article:
        print(article_text(a.article, use_cache=False))
        return 0
    for sid, s in collect().items():
        print(f"{sid:28s} {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
