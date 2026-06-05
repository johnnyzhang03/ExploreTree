"""Server-side tree state. Frontend is a thin renderer of these events."""
from dataclasses import dataclass, field
from itertools import count


_ids = count(1)


def next_id() -> str:
    return f"n{next(_ids)}"


@dataclass
class Node:
    id: str
    label: str
    parent_id: str | None
    status: str = "pending"  # pending | searching | done
    insight: str = ""
    sources: list[dict] = field(default_factory=list)
    depth: int = 0
    verticals: list[str] = field(default_factory=lambda: ["web", "news"])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "parentId": self.parent_id,
            "status": self.status,
            "insight": self.insight,
            "sources": self.sources,
            "depth": self.depth,
            "verticals": self.verticals,
        }


class Tree:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}

    def add(
        self,
        label: str,
        parent_id: str | None,
        status: str = "pending",
        depth: int = 0,
        verticals: list[str] | None = None,
    ) -> Node:
        node = Node(
            id=next_id(),
            label=label,
            parent_id=parent_id,
            status=status,
            depth=depth,
            verticals=verticals if verticals is not None else ["web", "news"],
        )
        self.nodes[node.id] = node
        return node
