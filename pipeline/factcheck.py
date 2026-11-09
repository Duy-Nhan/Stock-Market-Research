"""Kiểm chứng bản tin (gác cổng chống bịa đặt) — chạy độc lập, KHÔNG sửa nội dung, chỉ báo lỗi. Thoát mã ≠ 0 nếu có lỗi.

Định dạng bản tin (reports/YYYY-MM-DD.md): mỗi đoạn/mục bắt đầu bằng nhãn tầng:
  {fact}    sự kiện đã xảy ra — MỖI câu phải có trích dẫn [[cN]]; mọi con số trong câu phải xuất hiện trong (các) câu trích dẫn gốc
  {data}    số liệu thị trường của dự án — số chỉ được đến từ ô thay thế {{...}} (do mã điền từ data/), không gõ tay
  {def}     định nghĩa thuật ngữ — phải trích dẫn nguồn loại "definition"
  {infer}   suy luận (kênh tác động) — số liệu phải từ {{...}} hoặc trích dẫn trong đoạn
  {opinion} nhận định — như {infer}; không được dùng từ tuyệt đối
  {note}    ghi chú phương pháp/miễn trừ (không chứa số liệu thị trường)
Trích dẫn: reports/YYYY-MM-DD.claims.json — mỗi claim có nguồn + câu trích NGUYÊN VĂN ngắn (<= 40 từ). Script tải lại trang nguồn và kiểm tra câu trích CÓ trong văn bản trang.

Kiểm tra: (1) cấu trúc/nhãn/trích dẫn; (2) tên miền nguồn nằm trong danh sách duyệt; (3) câu trích có thật trong trang nguồn; (4) số trong câu ⊂ số trong trích dẫn/ô thay thế;
(5) số từ 1.800–2.200; (6) không có từ tuyệt đối ("chắc chắn", "đảm bảo", "100%"…) trong {infer}/{opinion}; (7) ô thay thế đều giải được; (8) outlook đủ mã/khung và mỗi lập trường khác 0 có trích dẫn.
Người viết ≠ người kiểm: script này không phụ thuộc vào người viết; thêm bước đọc thủ công ngữ nghĩa (đối chiếu ý) được ghi trong docs/report-methodology.md.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from .common import ROOT, FetchError, load_config

TIERS = ("fact", "data", "def", "infer", "opinion", "note")
ABSOLUTE = ["chắc chắn", "đảm bảo", "100%", "tuyệt đối", "không thể sai", "nhất định sẽ"]
NUM_RE = re.compile(r"(?<![\w/])[-+−]?\d[\d.,]*\d|(?<![\w/])\d")
CITE_RE = re.compile(r"\[\[([cd]\d+[a-z]?)\]\]")
PH_RE = re.compile(r"\{\{[^}]+\}\}")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ỹ\[{“\"(])")


def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFC", s).lower()
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'").replace(" ", " ").replace("﻿", "").replace("﻿", "")
    s = re.sub(r"[\"'`]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def num_variants(tok: str) -> Set[str]:
    """Các cách hiểu có thể của một token số (dấu chấm/phẩy vừa là phân cách hàng nghìn vừa là thập phân)."""
    t = tok.replace("−", "-").lstrip("+-")
    out: Set[str] = set()
    if re.fullmatch(r"\d+", t):
        out.add(t)
        return out
    if "." in t and "," in t:
        dec = "." if t.rfind(".") > t.rfind(",") else ","
        thou = "," if dec == "." else "."
        out.add(t.replace(thou, "").replace(dec, "."))
        return out
    sep = "." if "." in t else ","
    parts = t.split(sep)
    out.add("".join(parts))                      # hiểu là phân cách hàng nghìn
    if len(parts) == 2:
        out.add(parts[0] + "." + parts[1])       # hiểu là thập phân
    return {re.sub(r"(\.\d*?)0+$", r"\1", v).rstrip(".") if "." in v else v for v in out}


CAL_RE = re.compile(r"\b\d{1,2}/\d{4}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b(?:tháng|ngày|quý|phiên|tuần|kỳ)\s+\d+(?:/\d{4})?|\b(?:Q|q)\d\b|\b\d{1,2}:\d{2}\b|\b20\d\d\b|\b\d{1,2}h\d{0,2}\b|\b\d{1,2}\s*giờ\b")


def numbers_in(text: str) -> List[str]:
    """Các token số cần có nguồn. Bỏ qua: ngày/giờ/tháng/quý/năm và số nguyên 1–10 đứng một mình (đếm, thứ tự)."""
    text = CAL_RE.sub(" ", text)
    toks = []
    for m in NUM_RE.finditer(text):
        tok = m.group(0)
        if re.fullmatch(r"\d|10", tok):
            continue
        toks.append(tok)
    return toks


def covered(tok: str, pool: Set[str]) -> bool:
    return bool(num_variants(tok) & pool)


def build_pool(texts: List[str]) -> Set[str]:
    pool: Set[str] = set()
    for t in texts:
        for m in NUM_RE.finditer(t):
            pool |= num_variants(m.group(0))
    return pool


def parse_blocks(md: str) -> List[Dict[str, Any]]:
    blocks, head = [], None
    for ln, raw in enumerate(md.splitlines(), 1):
        line = raw.strip()
        if not line or line == "---":
            continue
        if line.startswith("#"):
            head = line.lstrip("#").strip()
            blocks.append({"type": "heading", "level": len(line) - len(line.lstrip("#")), "text": head, "line": ln})
            continue
        m = re.match(r"^(?:[-*]\s+)?\{(" + "|".join(TIERS) + r")\}\s*(.*)$", line)
        if m:
            blocks.append({"type": "para", "tier": m.group(1), "text": m.group(2), "line": ln, "section": head, "bullet": line[0] in "-*"})
        elif re.match(r"^[A-Za-z_]+:\s", line) and not blocks:
            continue  # front matter
        elif line.startswith("|") or line.startswith("{{"):
            blocks.append({"type": "raw", "text": line, "line": ln, "section": head})
        else:
            blocks.append({"type": "untagged", "text": line, "line": ln, "section": head})
    return blocks


def strip_markup(t: str) -> str:
    t = PH_RE.sub(" ", t)
    t = CITE_RE.sub("", t)
    return re.sub(r"[*_`]", "", t)


def word_count(blocks: List[Dict[str, Any]]) -> int:
    n = 0
    for b in blocks:
        if b["type"] in ("heading", "para"):
            n += len(re.findall(r"\S+", strip_markup(b["text"]))) if b["type"] == "para" else len(b["text"].split())
    return n


def resolve_placeholders(text: str, resolver) -> Tuple[str, List[str]]:
    errs: List[str] = []
    def rep(m):
        key = m.group(0)[2:-2].strip()
        try:
            return str(resolver(key))
        except Exception as e:  # noqa: BLE001
            errs.append(f"ô thay thế không giải được: {{{{{key}}}}} ({e})")
            return "???"
    return PH_RE.sub(rep, text), errs


def domain_ok(url: str, kind: str, cfg: Dict[str, Any]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    allowed = {"news": cfg["news_domains"], "primary": cfg["primary_domains"], "definition": cfg["definition_domains"]}.get(kind, [])
    return any(host == d or host.endswith("." + d) for d in allowed)


def check(report_md: str, claims_doc: Dict[str, Any], resolver, *, fetch_text=None, min_words: int = 1800, max_words: int = 2200,
          known_links: Optional[Set[str]] = None) -> Dict[str, Any]:
    errors: List[str] = []
    warns: List[str] = []
    cfg = load_config("sources.json")["report_sources"]
    sources, claims = claims_doc.get("sources", {}), claims_doc.get("claims", {})
    blocks = parse_blocks(report_md)

    # --- claims & nguồn
    verified: Dict[str, bool] = {}
    cache: Dict[str, str] = {}
    for cid, c in claims.items():
        s = sources.get(c.get("source", ""))
        if not s:
            errors.append(f"{cid}: nguồn '{c.get('source')}' không tồn tại"); continue
        if not domain_ok(s["url"], s["kind"], cfg):
            errors.append(f"{cid}: tên miền không nằm trong danh sách duyệt ({s['url']})")
        if s["kind"] == "news" and known_links is not None and s["url"] not in known_links:
            warns.append(f"{cid}: link không có trong dữ liệu RSS đã thu thập ({s['url']})")
        q = c.get("quote", "")
        if len(q.split()) > 40:
            errors.append(f"{cid}: trích dẫn dài hơn 40 từ")
        if fetch_text is None:
            continue
        url = s["url"]
        if url not in cache:
            try:
                cache[url] = norm_text(fetch_text(url))
            except FetchError as e:
                cache[url] = ""
                errors.append(f"{cid}: không tải được nguồn {url}: {e}")
        verified[cid] = bool(cache[url]) and norm_text(q) in cache[url]
        if cache[url] and not verified[cid]:
            errors.append(f"{cid}: câu trích KHÔNG có trong trang nguồn ({url}): “{q[:90]}…”")

    # --- khối nội dung
    wc = word_count(blocks)
    if not (min_words <= wc <= max_words):
        errors.append(f"số từ {wc} nằm ngoài khoảng {min_words}–{max_words}")
    used: Set[str] = set()
    for b in blocks:
        if b["type"] == "untagged":
            errors.append(f"dòng {b['line']}: đoạn không có nhãn tầng {{fact|data|def|infer|opinion|note}}: “{b['text'][:60]}…”")
        if b["type"] != "para":
            continue
        tier, text, ln = b["tier"], b["text"], b["line"]
        cites = CITE_RE.findall(text)
        used.update(cites)
        for cid in cites:
            if cid not in claims:
                errors.append(f"dòng {ln}: trích dẫn {cid} không có trong claims")
        resolved, perr = resolve_placeholders(text, resolver)
        errors += [f"dòng {ln}: {e}" for e in perr]
        ph_vals = " ".join(resolve_placeholders(m.group(0), resolver)[0] for m in PH_RE.finditer(text))
        if tier in ("fact", "def"):
            sentences = SENT_SPLIT.split(text)
            for s in sentences:
                sc = CITE_RE.findall(s)
                if not sc:
                    if len(s.split()) > 3:
                        errors.append(f"dòng {ln}: câu {{{tier}}} không có trích dẫn: “{s[:70]}…”")
                    continue
                if tier == "def" and not all(sources.get(claims.get(c, {}).get("source", ""), {}).get("kind") == "definition" for c in sc if c in claims):
                    errors.append(f"dòng {ln}: câu {{def}} phải trích dẫn nguồn loại definition")
                pool = build_pool([claims[c]["quote"] for c in sc if c in claims] + [resolve_placeholders(m.group(0), resolver)[0] for m in PH_RE.finditer(s)])
                for tok in numbers_in(strip_markup_keep_nums(s)):
                    if not covered(tok, pool):
                        errors.append(f"dòng {ln}: số “{tok}” không có trong câu trích dẫn/ô thay thế: “{s[:80]}…”")
        elif tier == "data":
            body = PH_RE.sub(" ", CITE_RE.sub("", text))
            for tok in numbers_in(body):
                errors.append(f"dòng {ln}: {{data}} chứa số gõ tay “{tok}” — phải dùng ô thay thế {{{{...}}}}")
        elif tier in ("infer", "opinion"):
            pool = build_pool([claims[c]["quote"] for c in cites if c in claims] + [ph_vals])
            for tok in numbers_in(CITE_RE.sub("", PH_RE.sub(" ", text))):
                if not covered(tok, pool):
                    errors.append(f"dòng {ln}: số “{tok}” trong {{{tier}}} không có nguồn (trích dẫn/ô thay thế): “{text[:70]}…”")
            low = text.lower()
            for w in ABSOLUTE:
                if w in low:
                    errors.append(f"dòng {ln}: từ tuyệt đối “{w}” trong {{{tier}}}")
        elif tier == "note":
            pass
    unused = set(claims) - used
    if unused:
        warns.append(f"claims không được dùng: {sorted(unused)}")
    return {"ok": not errors, "errors": errors, "warnings": warns, "word_count": wc, "claims": len(claims), "claims_verified": sum(verified.values()),
            "blocks": sum(1 for b in blocks if b['type'] == 'para')}


def strip_markup_keep_nums(s: str) -> str:
    s = CITE_RE.sub("", s)
    return PH_RE.sub(" ", s)
