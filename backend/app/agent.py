"""Week-1 slice agent: hand-rolled decompose, real Bing search, naive synthesis.

The LLM planner/synthesizer arrives in Week 2 — for now decompose is template-based
and the "insight" is the top result's snippet, so the full vertical slice runs end-to-end.
"""
import asyncio
from typing import Awaitable, Callable

from .search import search_web
from .tree import Tree

Emit = Callable[[dict], Awaitable[None]]


def decompose(question: str) -> list[str]:
    """Stand-in for the LLM planner: split a question into 3 sub-topics."""
    q = question.strip().rstrip("?")
    return [
        f"{q} — overview",
        f"{q} — key factors",
        f"{q} — risks and challenges",
    ]


async def _expand_node(tree: Tree, node_id: str, emit: Emit) -> None:
    node = tree.nodes[node_id]
    node.status = "searching"
    await emit({"type": "node_updated", "node": node.to_dict()})

    try:
        results = await search_web(node.label, count=5)
    except Exception as exc:  # boundary: external API
        node.status = "done"
        node.insight = f"(search failed: {exc})"
        await emit({"type": "node_updated", "node": node.to_dict()})
        return

    node.sources = [r.to_dict() for r in results]
    node.insight = results[0].snippet if results else "(no results)"
    node.status = "done"
    await emit({"type": "node_updated", "node": node.to_dict()})


async def explore(question: str, emit: Emit) -> None:
    """Run the core loop: root → decompose → search each child in parallel."""
    tree = Tree()

    root = tree.add(label=question, parent_id=None, status="done")
    await emit({"type": "node_added", "node": root.to_dict()})

    children = [tree.add(label=sub, parent_id=root.id) for sub in decompose(question)]
    for child in children:
        await emit({"type": "node_added", "node": child.to_dict()})

    await asyncio.gather(*(_expand_node(tree, c.id, emit) for c in children))

    await emit({"type": "done"})
