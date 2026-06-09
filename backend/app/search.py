import asyncio
import random
import re
from dataclasses import dataclass

import httpx

from .config import settings

# Transient HTTP statuses worth retrying (rate-limit + server-side hiccups).
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    vertical: str = "web"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "vertical": self.vertical,
        }


_TAG_RE = re.compile(r"<[^>]+>")


def _to_snippet(content: str, limit: int = 300) -> str:
    """Strip HTML tags from the result content and trim to a short snippet."""
    text = _TAG_RE.sub(" ", content or "")
    text = " ".join(text.split())
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


async def _post(endpoint: str, query: str, count: int) -> dict:
    """POST a query to a Microsoft AI search vertical and return parsed JSON.

    Retries transient failures (429 rate-limits, 5xx, connection/timeout errors)
    with short exponential backoff + jitter. The rate limit is burst-based, so a
    few short retries clear most 429s — we deliberately ignore the API's suggested
    60s retryAfter, which is too slow for live use. Non-retryable errors (other
    4xx) fail immediately.
    """
    if not settings.bing_search_key:
        raise RuntimeError("BING_SEARCH_KEY is not set — copy .env.example to .env and fill it in.")

    headers = {"x-apikey": settings.bing_search_key, "content-type": "application/json"}
    payload = {
        "query": query,
        "maxResults": count,
        "language": "en",
        "region": "US",
        "contentFormat": "html",
        "maxLength": 4000,
    }

    attempts = settings.search_max_retries + 1
    async with httpx.AsyncClient(timeout=20.0) as client:
        for attempt in range(attempts):
            try:
                resp = await client.post(endpoint, headers=headers, json=payload)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status not in _RETRYABLE_STATUS or attempt == attempts - 1:
                    raise  # non-transient, or out of attempts
            except (httpx.TransportError, httpx.TimeoutException):
                if attempt == attempts - 1:
                    raise

            # back off before the next try; jitter de-syncs parallel callers
            delay = settings.search_backoff_base * (2**attempt)
            await asyncio.sleep(delay + random.uniform(0, 0.5))

    raise RuntimeError("unreachable")  # loop either returns or raises


async def search_web(query: str, count: int = 5) -> list[SearchResult]:
    data = await _post(settings.bing_search_endpoint, query, count)
    return [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=_to_snippet(r.get("content", "")),
            vertical="web",
        )
        for r in data.get("webResults", [])
    ]


async def search_news(query: str, count: int = 5) -> list[SearchResult]:
    data = await _post(settings.bing_news_endpoint, query, count)
    return [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=_to_snippet(r.get("content", "")),
            vertical="news",
        )
        for r in data.get("newsResults", [])
    ]


def _finance_snippet(item: dict) -> str:
    """Build a compact insight from a finance result's structured stock context."""
    parts = list(item.get("snippets") or [])
    ctx = item.get("context") or {}
    inst = ctx.get("instrument") or {}
    if ctx.get("$type") == "Stock" and inst:
        sym = inst.get("symbol") or inst.get("displayName") or ""
        price = inst.get("price")
        cur = inst.get("marketCapCurrency", "")
        bits = []
        if price is not None:
            bits.append(f"price {price} {cur}".strip())
        mc = inst.get("marketCap")
        if mc:
            bits.append(f"mktcap {mc:,} {cur}".strip())
        pe = inst.get("peRatio")
        if pe:
            bits.append(f"P/E {pe:.1f}")
        dy = inst.get("dividendYieldPercent")
        if dy:
            bits.append(f"div {dy}%")
        pricing = inst.get("intradayPricing") or {}
        hi, lo = pricing.get("price52wHigh"), pricing.get("price52wLow")
        if hi and lo:
            bits.append(f"52w {lo}–{hi}")
        if bits:
            parts.append(f"{sym}: " + " · ".join(bits))
    return _to_snippet(" ".join(parts), limit=300)


async def search_finance(query: str, count: int = 5) -> list[SearchResult]:
    data = await _post(settings.bing_finance_endpoint, query, count)
    return [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=_finance_snippet(r),
            vertical="finance",
        )
        for r in data.get("financeResults", [])
    ]


def _places_snippet(item: dict) -> str:
    """Build a compact insight from a place result's structured fields."""
    bits = []
    loc = item.get("location") or {}
    if loc.get("fullAddress"):
        bits.append(loc["fullAddress"])
    cat = (item.get("category") or {}).get("primaryCategory")
    if cat:
        bits.append(cat)
    price = item.get("price") or {}
    if price.get("priceLevel"):
        sym = price.get("currencySymbol") or "$"
        bits.append(sym * int(price["priceLevel"]))
    reviews = item.get("reviews") or []
    if reviews:
        rv = reviews[0]
        score = (rv.get("rating") or {}).get("score")
        provider = (rv.get("provider") or {}).get("name")
        if score is not None and provider:
            bits.append(f"{score}★ on {provider}")
    head = " · ".join(bits)
    desc = item.get("description") or ""
    return _to_snippet(f"{head}. {desc}" if desc else head, limit=300)


async def search_places(query: str, count: int = 5) -> list[SearchResult]:
    data = await _post(settings.bing_places_endpoint, query, count)
    return [
        SearchResult(
            title=r.get("name", ""),
            url=r.get("businessUrl") or r.get("url", ""),
            snippet=_places_snippet(r),
            vertical="places",
        )
        for r in data.get("placeResults", [])
    ]


async def search_videos_text(query: str, count: int = 3) -> list[SearchResult]:
    """Video results as text sources for synthesis (AI summary, else description)."""
    data = await _post(settings.bing_videos_endpoint, query, count)
    out = []
    for r in data.get("videoResults", []):
        text = (r.get("summary") or r.get("description") or "").strip()
        if not text:
            continue
        out.append(
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url") or r.get("embeddingUrl", ""),
                snippet=_to_snippet(text),
                vertical="videos",
            )
        )
    return out


SEARCHERS = {
    "web": search_web,
    "news": search_news,
    "finance": search_finance,
    "places": search_places,
    "videos": search_videos_text,
}


async def search_images(query: str, count: int = 6) -> list[dict]:
    """Image results as media dicts: thumbnail to show, url/hostPage to open."""
    data = await _post(settings.bing_images_endpoint, query, count)
    out = []
    for r in data.get("imageResults", []):
        thumb = r.get("thumbnailUrl")
        if not thumb:
            continue
        out.append(
            {
                "title": r.get("title", ""),
                "thumbnail": thumb,
                "link": r.get("hostPageUrl") or r.get("url", ""),
                "width": r.get("width"),
                "height": r.get("height"),
            }
        )
    return out


async def search_videos(query: str, count: int = 4) -> list[dict]:
    """Video results as media dicts: thumbnail + the page/embed link to open."""
    data = await _post(settings.bing_videos_endpoint, query, count)
    out = []
    for r in data.get("videoResults", []):
        thumb = r.get("thumbnailUrl")
        if not thumb:
            continue
        out.append(
            {
                "title": r.get("title", ""),
                "thumbnail": thumb,
                "link": r.get("url") or r.get("embeddingUrl", ""),
                "publishedBy": r.get("publishedBy", ""),
                "viewCount": r.get("viewCount"),
            }
        )
    return out
