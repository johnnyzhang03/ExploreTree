import re
from dataclasses import dataclass

import httpx

from .config import settings


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

    def to_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}


_TAG_RE = re.compile(r"<[^>]+>")


def _to_snippet(content: str, limit: int = 300) -> str:
    """Strip HTML tags from the result content and trim to a short snippet."""
    text = _TAG_RE.sub(" ", content or "")
    text = " ".join(text.split())
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


async def search_web(query: str, count: int = 5) -> list[SearchResult]:
    """Query the Microsoft AI web search endpoint. Returns top results."""
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

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(settings.bing_search_endpoint, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("webResults", [])
    return [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=_to_snippet(r.get("content", "")),
        )
        for r in results
    ]
