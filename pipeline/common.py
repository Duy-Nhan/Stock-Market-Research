"""Tiện ích dùng chung cho pipeline: đường dẫn, cấu hình, HTTP có retry, ghi file nguyên tử."""
from __future__ import annotations

import gzip
import json
import os
import zlib
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG = ROOT / "config"
VN_TZ = timezone(timedelta(hours=7))
USER_AGENT = "StockMarketResearch/0.1 (personal research project; non-commercial)"


def load_config(name: str) -> Dict[str, Any]:
    with open(CONFIG / name, encoding="utf-8") as f:
        return json.load(f)


def now_vn_iso() -> str:
    return datetime.now(VN_TZ).replace(microsecond=0).isoformat()


def ts_to_vn_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, VN_TZ).replace(microsecond=0).isoformat()


class FetchError(RuntimeError):
    pass


def http_get(url: str, *, headers: Optional[Dict[str, str]] = None, timeout: int = 30,
             retries: int = 3, backoff: float = 2.0) -> bytes:
    """GET có retry/backoff. Ném FetchError (không nuốt lỗi) nếu hết lượt thử."""
    hdrs = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    hdrs.update(headers or {})
    last: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower()
            if enc == "gzip" or data[:2] == b"\x1f\x8b":  # một số máy chủ nén gzip dù không được yêu cầu
                data = gzip.decompress(data)
            elif enc == "deflate":
                data = zlib.decompress(data)
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404, 422):  # lỗi do yêu cầu, thử lại vô ích
                break
        except Exception as e:  # mạng, timeout...
            last = e
        time.sleep(backoff ** attempt)
    raise FetchError(f"GET thất bại sau {retries} lần: {url} -> {last!r}")


def get_json(url: str, **kw: Any) -> Any:
    raw = http_get(url, **kw)
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise FetchError(f"Phản hồi không phải JSON: {url} -> {raw[:120]!r}") from e


def write_json_atomic(path: Path, obj: Any, *, indent: Optional[int] = None) -> None:
    """Ghi qua file tạm rồi đổi tên: không để lại file hỏng nếu bị ngắt giữa chừng."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=indent, separators=(",", ":") if indent is None else None)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)
