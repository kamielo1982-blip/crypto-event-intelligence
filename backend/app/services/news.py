from __future__ import annotations

import re
from hashlib import sha256
from urllib.parse import urlsplit, urlunsplit


_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s가-힣]")


def canonical_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def canonical_title(title: str) -> str:
    normalized = _PUNCT_RE.sub(" ", title.lower())
    return _SPACE_RE.sub(" ", normalized).strip()


def duplicate_key(title: str, url: str) -> str:
    source = canonical_url(url) or canonical_title(title)
    return sha256(source.encode("utf-8")).hexdigest()[:32]


def infer_related_symbols(title: str, summary: str | None, known_symbols: list[str]) -> list[str]:
    body = f"{title} {summary or ''}".upper()
    matches = [symbol for symbol in known_symbols if re.search(rf"\b{re.escape(symbol)}\b", body)]
    return sorted(set(matches))


def dedupe_news_items(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        key = item.get("duplicate_key") or duplicate_key(item.get("title", ""), item.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append({**item, "duplicate_key": key})
    return unique
