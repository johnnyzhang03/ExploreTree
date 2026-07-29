"""Server-side tree state. Frontend is a thin renderer of these events."""
import asyncio
from dataclasses import dataclass, field
from itertools import count
from urllib.parse import urlsplit


_ids = count(1)


def next_id() -> str:
    return f"n{next(_ids)}"


def evidence_coverage(sources: list[dict]) -> dict:
    source_keys = set()
    dated_source_keys = set()
    domains = set()
    verticals = set()
    published_dates = set()

    for source in sources:
        url = (source.get("url") or "").strip()
        title = (source.get("title") or "").strip()
        key = (source.get("canonicalUrl") or url).casefold() or title.casefold()
        if key:
            source_keys.add(key)

        domain = (source.get("domain") or urlsplit(url).hostname or "").casefold()
        if domain.startswith("www."):
            domain = domain[4:]
        if domain:
            domains.add(domain)

        vertical = (source.get("vertical") or "").strip()
        if vertical:
            verticals.add(vertical)

        published_at = (source.get("publishedAt") or "").strip()
        if published_at:
            if key:
                dated_source_keys.add(key)
            published_dates.add(published_at)

    source_count = len(source_keys)
    domain_count = len(domains)
    dated_source_count = len(dated_source_keys)
    return {
        "sourceCount": source_count,
        "domainCount": domain_count,
        "verticalCount": len(verticals),
        "datedSourceCount": dated_source_count,
        "dateRange": (
            {
                "oldest": min(published_dates),
                "newest": max(published_dates),
            }
            if published_dates
            else None
        ),
        "gaps": {
            "noEvidence": source_count == 0,
            "singleSource": source_count == 1,
            "singleDomain": source_count > 0 and domain_count == 1,
            "noDateMetadata": source_count > 0 and dated_source_count == 0,
        },
    }


@dataclass
class Node:
    id: str
    label: str
    parent_id: str | None
    query: str = ""
    status: str = "pending"  # pending | searching | done
    insight: str = ""
    sources: list[dict] = field(default_factory=list)
    depth: int = 0
    verticals: list[str] = field(default_factory=lambda: ["web", "news"])
    card_image: dict | None = None  # one thumbnail for the card cover

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "parentId": self.parent_id,
            "status": self.status,
            "insight": self.insight,
            "sources": self.sources,
            "evidenceCoverage": evidence_coverage(self.sources),
            "depth": self.depth,
            "verticals": self.verticals,
            "cardImage": self.card_image,
        }


class Tree:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self._card_image_urls: set[str] = set()
        self._card_image_lock = asyncio.Lock()

    def add(
        self,
        label: str,
        parent_id: str | None,
        status: str = "pending",
        depth: int = 0,
        verticals: list[str] | None = None,
        query: str | None = None,
    ) -> Node:
        node = Node(
            id=next_id(),
            label=label,
            parent_id=parent_id,
            query=query or label,
            status=status,
            depth=depth,
            verticals=verticals if verticals is not None else ["web", "news"],
        )
        self.nodes[node.id] = node
        return node

    async def claim_card_image(self, images: list[dict]) -> dict:
        async with self._card_image_lock:
            for image in images:
                url = image.get("thumbnail") or image.get("link")
                if url and url not in self._card_image_urls:
                    self._card_image_urls.add(url)
                    return image
        return {}
