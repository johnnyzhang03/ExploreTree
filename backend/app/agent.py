"""Week-3 agent: LLM planner decomposes + routes verticals, multi-vertical searcher
fetches, LLM synthesizer distills, and an LLM reflection step grows the tree level
by level.

Each round: expand the new frontier in parallel (the planner-chosen verticals per
node → synthesize), then ask the reflector which leaves to expand next. Bounded by
settings.max_depth. All LLM steps fall back to Week-1 heuristics when no key is
configured, so the vertical slice always runs end-to-end.
"""
import asyncio
from typing import Awaitable, Callable

from . import llm
from .config import settings
from .llm import PlannedTopic
from .search import SEARCHERS, search_images, search_videos
from .tree import Node, Tree

Emit = Callable[[dict], Awaitable[None]]

# How many results to pull per vertical (kept small to bound latency/cost).
_VERTICAL_COUNTS = {"web": 4, "news": 3, "finance": 2, "places": 3, "videos": 3}


def _fallback_decompose(question: str) -> list[PlannedTopic]:
    """Week-1 stand-in used when the LLM planner is unavailable."""
    q = question.strip().rstrip("?")
    return [
        PlannedTopic(query=f"{q} — overview", verticals=["web", "news"]),
        PlannedTopic(query=f"{q} — key factors", verticals=["web", "news"]),
        PlannedTopic(query=f"{q} — risks and challenges", verticals=["web", "news"]),
    ]


async def decompose(question: str) -> list[PlannedTopic]:
    """Plan sub-topics (with routed verticals) via the LLM, falling back to template."""
    try:
        subtopics = await llm.plan(question)
    except Exception:  # boundary: LLM API — never let planning kill the run
        subtopics = []
    return subtopics or _fallback_decompose(question)


async def _expand_node(tree: Tree, node_id: str, emit: Emit) -> None:
    node = tree.nodes[node_id]
    node.status = "searching"
    await emit({"type": "node_updated", "node": node.to_dict()})

    verticals = node.verticals or ["web", "news"]
    searches = [
        SEARCHERS[v](node.label, count=_VERTICAL_COUNTS.get(v, 3))
        for v in verticals
        if v in SEARCHERS
    ]
    # Fetch the card cover image in the same parallel batch as the verticals,
    # so the thumbnail ships with the node (no separate round-trip per card).
    img_task = asyncio.create_task(search_images(node.label, count=1))
    groups = await asyncio.gather(*searches, return_exceptions=True)

    try:
        imgs = await img_task
        node.card_image = imgs[0] if imgs else {}
    except Exception:  # boundary: image search — never block the node on it
        node.card_image = {}

    results = []
    for group in groups:
        if isinstance(group, BaseException):
            continue
        results.extend(group)

    if not results:
        node.status = "done"
        exc = next((g for g in groups if isinstance(g, BaseException)), None)
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
        tree.add(
            label=topic.query,
            parent_id=parent.id,
            depth=parent.depth + 1,
            verticals=topic.verticals,
        )
        for topic in await decompose(parent.label)
    ]
    for child in children:
        await emit({"type": "node_added", "node": child.to_dict()})

    await asyncio.gather(*(_expand_node(tree, c.id, emit) for c in children))
    return children


async def _pick_next(question: str, frontier: list[Node], breadth: int) -> list[Node]:
    """Reflection: pick which frontier leaves to expand next (LLM, with fallback)."""
    by_id = {n.id: n for n in frontier}
    try:
        ids = await llm.reflect(
            question,
            [{"id": n.id, "label": n.label, "insight": n.insight} for n in frontier],
            breadth,
        )
    except Exception:  # boundary: LLM API
        ids = []
    picked = [by_id[i] for i in ids if i in by_id]
    return picked or frontier[:breadth]


async def explore(
    question: str,
    emit: Emit,
    tree: Tree,
    max_depth: int | None = None,
    breadth: int | None = None,
) -> None:
    """Grow the tree: root → decompose → search/synthesize → reflect → repeat.

    The caller owns the tree (so it can be acted on later via expand_on_demand /
    add_followup). max_depth / breadth override the server defaults when provided
    (per-request, clamped so a user request can't trigger a runaway tree).
    """
    max_depth = settings.max_depth if max_depth is None else max(1, min(max_depth, 4))
    breadth = settings.expand_per_level if breadth is None else max(1, min(breadth, 4))

    root = tree.add(label=question, parent_id=None, status="done", depth=0)
    await emit({"type": "node_added", "node": root.to_dict()})

    await emit({"type": "planning"})
    frontier = await _grow_children(tree, root, emit)

    while frontier and frontier[0].depth < max_depth:
        await emit({"type": "planning"})
        # #1: show the agent is evaluating the current frontier (on-canvas cue)
        frontier_ids = [n.id for n in frontier]
        await emit({"type": "node_state", "ids": frontier_ids, "state": "considering"})

        picks = await _pick_next(question, frontier, breadth)

        # clear the "considering" cue from everyone, then...
        await emit({"type": "node_state", "ids": frontier_ids, "state": None})
        if not picks:
            break
        # #2: highlight the chosen parents before their children are generated
        await emit(
            {"type": "node_state", "ids": [p.id for p in picks], "state": "expanding"}
        )

        grown = await asyncio.gather(*(_grow_children(tree, p, emit) for p in picks))
        # the chosen parents are done expanding once their children exist
        await emit(
            {"type": "node_state", "ids": [p.id for p in picks], "state": None}
        )
        frontier = [child for children in grown for child in children]

    await emit({"type": "done"})


async def expand_on_demand(tree: Tree, node_id: str, emit: Emit) -> None:
    """User-driven: decompose a specific existing node into children and search them."""
    node = tree.nodes.get(node_id)
    if node is None:
        await emit({"type": "done"})
        return
    await emit({"type": "node_state", "ids": [node_id], "state": "expanding"})
    await _grow_children(tree, node, emit)
    await emit({"type": "node_state", "ids": [node_id], "state": None})
    await emit({"type": "done"})


async def add_followup(tree: Tree, parent_id: str, query: str, emit: Emit) -> None:
    """User-driven: add one custom-query child under a node and search/synthesize it."""
    parent = tree.nodes.get(parent_id)
    if parent is None or not query.strip():
        await emit({"type": "done"})
        return
    child = tree.add(
        label=query.strip(),
        parent_id=parent_id,
        depth=parent.depth + 1,
        verticals=["web", "news"],
    )
    await emit({"type": "node_added", "node": child.to_dict()})
    await _expand_node(tree, child.id, emit)
    await emit({"type": "done"})


async def get_media(tree: Tree, node_id: str, emit: Emit) -> None:
    """Lazily fetch images + videos for a node (on panel-open) and emit them."""
    node = tree.nodes.get(node_id)
    if node is None:
        return
    images, videos = await asyncio.gather(
        search_images(node.label, count=6),
        search_videos(node.label, count=4),
        return_exceptions=True,
    )
    await emit(
        {
            "type": "media",
            "node_id": node_id,
            "images": images if not isinstance(images, BaseException) else [],
            "videos": videos if not isinstance(videos, BaseException) else [],
        }
    )

