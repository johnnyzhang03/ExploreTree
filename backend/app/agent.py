"""Week-2 agent: LLM planner decomposes, searcher fetches, LLM synthesizer distills.

The planner (llm.plan) replaces the Week-1 template decompose, and the synthesizer
(llm.synthesize) replaces the naive "top snippet is the insight". Both gracefully
fall back to the Week-1 heuristics when no Anthropic key is configured, so the
vertical slice always runs end-to-end.
"""
import asyncio
from typing import Awaitable, Callable

from . import llm
from .search import search_web
from .tree import Tree

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

    try:
        results = await search_web(node.label, count=5)
    except Exception as exc:  # boundary: external API
        node.status = "done"
        node.insight = f"(search failed: {exc})"
        await emit({"type": "node_updated", "node": node.to_dict()})
        return

    node.sources = [r.to_dict() for r in results]

    # Synthesize an insight from the snippets; fall back to the top snippet.
    snippets = [r.snippet for r in results if r.snippet]
    insight = ""
    try:
        insight = await llm.synthesize(node.label, snippets)
    except Exception:  # boundary: LLM API
        insight = ""
    node.insight = insight or (results[0].snippet if results else "(no results)")

    node.status = "done"
    await emit({"type": "node_updated", "node": node.to_dict()})


async def explore(question: str, emit: Emit) -> None:
    """Run the core loop: root → LLM decompose → search + synthesize each child."""
    tree = Tree()

    root = tree.add(label=question, parent_id=None, status="done")
    await emit({"type": "node_added", "node": root.to_dict()})

    children = [tree.add(label=sub, parent_id=root.id) for sub in await decompose(question)]
    for child in children:
        await emit({"type": "node_added", "node": child.to_dict()})

    await asyncio.gather(*(_expand_node(tree, c.id, emit) for c in children))

    await emit({"type": "done"})
