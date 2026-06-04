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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "parentId": self.parent_id,
            "status": self.status,
            "insight": self.insight,
            "sources": self.sources,
            "depth": self.depth,
        }


class Tree:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}

    def add(self, label: str, parent_id: str | None, status: str = "pending", depth: int = 0) -> Node:
        node = Node(id=next_id(), label=label, parent_id=parent_id, status=status, depth=depth)
        self.nodes[node.id] = node
        return node
