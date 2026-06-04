"""Week-3 agent: LLM planner decomposes, multi-vertical searcher fetches, LLM
synthesizer distills, and an LLM reflection step grows the tree level by level.

Each round: expand the new frontier in parallel (web + news search → synthesize),
then ask the reflector which leaves to expand next. Bounded by settings.max_depth.
All LLM steps fall back to Week-1 heuristics when no key is configured, so the
vertical slice always runs end-to-end.
"""
import asyncio
from typing import Awaitable, Callable

from . import llm
from .config import settings
from .search import search_news, search_web
from .tree import Node, Tree

Emit = Callable[[dict], Awaitable[None]]


def _fallback_decompose(question: str) -> list[str]:
    """Week-1 stand-in used when the LLM planner is unavailable."""
    q = question.strip().rstrip("?")
    return [
        f"{q} — overview",
        f"{q} — key factors",
        f"{q} — risks and challenges",
    ]


async def decompose(question: str) -> list[str]:
    """Plan sub-topics via the LLM, falling back to the template on empty/no-key."""
    try:
        subtopics = await llm.plan(question)
    except Exception:  # boundary: LLM API — never let planning kill the run
        subtopics = []
    return subtopics or _fallback_decompose(question)


async def _expand_node(tree: Tree, node_id: str, emit: Emit) -> None:
    node = tree.nodes[node_id]
    node.status = "searching"
    await emit({"type": "node_updated", "node": node.to_dict()})

    web, news = await asyncio.gather(
        search_web(node.label, count=4),
        search_news(node.label, count=3),
        return_exceptions=True,
    )
    results = []
    for group in (web, news):
        if isinstance(group, BaseException):
            continue
        results.extend(group)

    if not results:
        node.status = "done"
        exc = next((g for g in (web, news) if isinstance(g, BaseException)), None)
        node.insight = f"(search failed: {exc})" if exc else "(no results)"
        await emit({"type": "node_updated", "node": node.to_dict()})
        return

    node.sources = [r.to_dict() for r in results]

    snippets = [r.snippet for r in results if r.snippet]
    insight = ""
    try:
        insight = await llm.synthesize(node.label, snippets)
    except Exception:  # boundary: LLM API
        insight = ""
    node.insight = insight or (results[0].snippet if results else "(no results)")

    node.status = "done"
    await emit({"type": "node_updated", "node": node.to_dict()})


async def _grow_children(tree: Tree, parent: Node, emit: Emit) -> list[Node]:
    """Decompose a parent into children, emit them, and expand all in parallel."""
    children = [
        tree.add(label=sub, parent_id=parent.id, depth=parent.depth + 1)
        for sub in await decompose(parent.label)
    ]
    for child in children:
        await emit({"type": "node_added", "node": child.to_dict()})

    await asyncio.gather(*(_expand_node(tree, c.id, emit) for c in children))
    return children


async def _pick_next(question: str, frontier: list[Node]) -> list[Node]:
    """Reflection: pick which frontier leaves to expand next (LLM, with fallback)."""
    by_id = {n.id: n for n in frontier}
    try:
        ids = await llm.reflect(
            question,
            [{"id": n.id, "label": n.label, "insight": n.insight} for n in frontier],
            settings.expand_per_level,
        )
    except Exception:  # boundary: LLM API
        ids = []
    picked = [by_id[i] for i in ids if i in by_id]
    return picked or frontier[: settings.expand_per_level]


async def explore(question: str, emit: Emit) -> None:
    """Grow the tree: root → decompose → search/synthesize → reflect → repeat."""
    tree = Tree()

    root = tree.add(label=question, parent_id=None, status="done", depth=0)
    await emit({"type": "node_added", "node": root.to_dict()})

    await emit({"type": "planning"})
    frontier = await _grow_children(tree, root, emit)

    while frontier and frontier[0].depth < settings.max_depth:
        await emit({"type": "planning"})
        picks = await _pick_next(question, frontier)
        if not picks:
            break

        grown = await asyncio.gather(*(_grow_children(tree, p, emit) for p in picks))
        frontier = [child for children in grown for child in children]

    await emit({"type": "done"})
