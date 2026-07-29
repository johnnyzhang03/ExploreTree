"""Week-3 agent: LLM planner decomposes + routes verticals, multi-vertical searcher
fetches, LLM synthesizer distills, and an LLM reflection step grows the tree level
by level.

Each round: expand the new frontier in parallel (the planner-chosen verticals per
node → synthesize), then ask the reflector which leaves to expand next. Bounded by
settings.max_depth. All LLM steps fall back to Week-1 heuristics when no key is
configured, so the vertical slice always runs end-to-end.

Compare mode grows a different shape: level 1 is the options, and every level
below applies the *same* criteria to *every* option, so the branches stay aligned.
Its reflection step therefore picks criteria rather than individual nodes —
deepening one node alone would destroy the alignment that makes the comparison
readable.
"""
import asyncio
import re
from typing import Awaitable, Callable

from . import llm
from .config import settings
from .llm import ComparisonCriterion, ComparisonOption, ComparisonPlan, PlannedTopic
from .research_brief import ResearchBrief
from .search import SEARCHERS, deduplicate_results, search_images, search_videos
from .tree import Node, Tree

Emit = Callable[[dict], Awaitable[None]]

# How many results to pull per vertical (kept small to bound latency/cost).
_VERTICAL_COUNTS = {"web": 4, "news": 3, "finance": 2, "places": 3, "videos": 3}

# Compare mode fans out options x criteria per level, so both are capped tightly.
_MAX_CRITERIA = 3
_MAX_SUB_CRITERIA = 2


def _fallback_decompose(
    question: str, parent_label: str = ""
) -> list[PlannedTopic]:
    """Week-1 stand-in used when the LLM planner is unavailable."""
    q = question.strip().rstrip("?")
    prefix = (
        f"{parent_label}: "
        if parent_label and parent_label.casefold() != question.casefold()
        else ""
    )
    return [
        PlannedTopic(
            title=f"{prefix}Current landscape",
            query=f"{q} current landscape and recent developments",
            verticals=["web", "news"],
        ),
        PlannedTopic(
            title=f"{prefix}Key drivers and evidence",
            query=f"{q} key drivers evidence and data",
            verticals=["web", "news"],
        ),
        PlannedTopic(
            title=f"{prefix}Risks and outlook",
            query=f"{q} risks constraints and future outlook",
            verticals=["web", "news"],
        ),
    ]


async def decompose(
    question: str,
    parent_label: str = "",
    research_brief: ResearchBrief | None = None,
) -> list[PlannedTopic]:
    """Plan sub-topics (with routed verticals) via the LLM, falling back to template."""
    try:
        planner_input = (
            research_brief.planning_prompt(question)
            if research_brief
            else question
        )
        subtopics = await llm.plan(planner_input)
    except Exception as error:  # boundary: LLM API — keep the run usable
        llm.record_error("plan", error)
        subtopics = []
    return subtopics or _fallback_decompose(question, parent_label)


_OPTION_SPLIT = re.compile(r"\s+(?:vs\.?|versus|or)\s+", re.IGNORECASE)
_COMPARE_LEAD = re.compile(
    r"^(?:please\s+)?(?:compare|comparing|contrast|evaluate|choose\s+between|"
    r"decide\s+between|pick\s+between)\s+",
    re.IGNORECASE,
)


def _infer_options(question: str) -> list[str]:
    """Best-effort option extraction for the no-LLM fallback tier.

    Only used when no API key is configured; the LLM planner and the explicit
    brief options are the real paths.
    """
    text = _COMPARE_LEAD.sub("", question.strip().rstrip("?")).strip()
    parts = [part.strip(" ,.") for part in _OPTION_SPLIT.split(text)]
    parts = [part for part in parts if part and len(part.split()) <= 6]
    if len(parts) < 2:
        return []
    return list(dict.fromkeys(parts))[:4]


def _fallback_criteria() -> list[ComparisonCriterion]:
    """Generic but genuinely comparable criteria, used when the LLM is unavailable."""
    return [
        ComparisonCriterion(
            name="Capabilities and strengths",
            query_template="{option} capabilities strengths and differentiators",
            verticals=["web", "news"],
        ),
        ComparisonCriterion(
            name="Cost and economics",
            query_template="{option} pricing cost and total cost of ownership",
            verticals=["web", "finance"],
        ),
        ComparisonCriterion(
            name="Risks and limitations",
            query_template="{option} risks limitations and known drawbacks",
            verticals=["web", "news"],
        ),
    ]


async def plan_comparison(
    research_brief: ResearchBrief | None, question: str
) -> ComparisonPlan | None:
    """Resolve the options and shared criteria for a comparison.

    Returns None when no credible set of options can be determined, which tells
    the caller to degrade to ordinary exploration rather than fake a comparison.
    """
    options_hint = list(research_brief.options) if research_brief else []
    prompt = research_brief.planning_prompt() if research_brief else question
    try:
        plan = await llm.plan_comparison(prompt, options_hint)
    except Exception as error:  # boundary: LLM API — degrade, don't fail the run
        llm.record_error("plan_comparison", error)
        plan = None
    if plan is not None:
        if not plan.criteria:
            plan.criteria = _fallback_criteria()
        return plan

    names = options_hint or _infer_options(question)
    if len(names) < 2:
        return None
    return ComparisonPlan(
        options=[
            # Without the LLM there is no reliable way to weave the question's
            # context into an option query, so keep it self-contained.
            ComparisonOption(
                name=name, query=f"{name} overview capabilities and positioning"
            )
            for name in names[:4]
        ],
        criteria=_fallback_criteria(),
    )


async def _sub_criteria(
    research_brief: ResearchBrief | None,
    question: str,
    criterion: str,
) -> list[ComparisonCriterion]:
    """Refine one criterion into aligned sub-criteria applied to every option."""
    prompt = research_brief.planning_prompt() if research_brief else question
    try:
        criteria = await llm.plan_criteria(prompt, criterion, _MAX_SUB_CRITERIA)
    except Exception as error:  # boundary: LLM API
        llm.record_error("plan_criteria", error)
        criteria = []
    if criteria:
        return criteria[:_MAX_SUB_CRITERIA]
    return [
        ComparisonCriterion(
            name=f"{criterion}: evidence and data",
            query_template=f"{{option}} {criterion} evidence data and benchmarks",
            verticals=["web", "news"],
        ),
        ComparisonCriterion(
            name=f"{criterion}: tradeoffs",
            query_template=f"{{option}} {criterion} tradeoffs and criticism",
            verticals=["web", "news"],
        ),
    ][:_MAX_SUB_CRITERIA]


def _apply_option(template: str, option: str) -> str:
    """Substitute an option into a criterion query template."""
    template = (template or "").strip()
    if "{option}" in template:
        return template.replace("{option}", option).strip()
    return f"{option} {template}".strip()


async def _grow_criteria(
    tree: Tree,
    parents: list[Node],
    criteria: list[ComparisonCriterion],
    emit: Emit,
) -> dict[str, list[Node]]:
    """Apply the same criteria, in the same order, under every parent.

    Identical ordering is what makes the comparison read as aligned rows in the
    tree layout. Returns the new nodes grouped by criterion (the "slots" the
    next reflection round chooses between).
    """
    slots: dict[str, list[Node]] = {}
    created = []
    for parent in parents:
        option = parent.option or parent.label
        for criterion in criteria:
            child = tree.add(
                label=criterion.name,
                parent_id=parent.id,
                depth=parent.depth + 1,
                verticals=list(criterion.verticals),
                query=_apply_option(criterion.query_template, option),
                option=option,
                criterion=criterion.name,
            )
            slots.setdefault(criterion.name, []).append(child)
            created.append(child)

    for child in created:
        await emit({"type": "node_added", "node": child.to_dict()})
    await asyncio.gather(*(_expand_node(tree, c.id, emit) for c in created))
    return slots


async def _pick_criteria(
    research_brief: ResearchBrief | None,
    question: str,
    slots: dict[str, list[Node]],
    limit: int,
) -> list[str]:
    """Reflection for compare mode: choose criterion slots, never single nodes."""
    listing = [
        {
            "name": name,
            "findings": [
                {"option": node.option, "insight": node.insight} for node in nodes
            ],
        }
        for name, nodes in slots.items()
    ]
    prompt = research_brief.planning_prompt() if research_brief else question
    try:
        picked = await llm.reflect_criteria(prompt, listing, limit)
    except Exception as error:  # boundary: LLM API
        llm.record_error("reflect_criteria", error)
        picked = []
    return picked or list(slots)[:limit]


async def _explore_comparison(
    question: str,
    emit: Emit,
    tree: Tree,
    root: Node,
    max_depth: int,
    breadth: int,
    research_brief: ResearchBrief | None,
) -> bool:
    """Grow an aligned options x criteria comparison. False if no comparison is possible."""
    await emit({"type": "planning"})
    plan = await plan_comparison(research_brief, question)
    if plan is None:
        return False

    criteria = plan.criteria[:_MAX_CRITERIA]
    tree.mode = "compare"
    tree.comparison = {
        "options": [option.name for option in plan.options],
        "criteria": [criterion.name for criterion in criteria],
    }
    await emit({"type": "mode", "mode": "compare", **tree.comparison})

    option_nodes = [
        tree.add(
            label=option.name,
            parent_id=root.id,
            depth=1,
            verticals=["web", "news"],
            query=option.query or option.name,
            option=option.name,
        )
        for option in plan.options
    ]
    for node in option_nodes:
        await emit({"type": "node_added", "node": node.to_dict()})
    await asyncio.gather(*(_expand_node(tree, n.id, emit) for n in option_nodes))

    if max_depth < 2:
        await emit({"type": "done"})
        return True

    slots = await _grow_criteria(tree, option_nodes, criteria, emit)

    depth = 2
    while slots and depth < max_depth:
        await emit({"type": "planning"})
        frontier_ids = [node.id for nodes in slots.values() for node in nodes]
        await emit({"type": "node_state", "ids": frontier_ids, "state": "considering"})

        picks = await _pick_criteria(research_brief, question, slots, breadth)

        await emit({"type": "node_state", "ids": frontier_ids, "state": None})
        if not picks:
            break

        picked_ids = [node.id for name in picks for node in slots.get(name, [])]
        await emit({"type": "node_state", "ids": picked_ids, "state": "expanding"})

        next_slots: dict[str, list[Node]] = {}
        for name in picks:
            parents = slots.get(name, [])
            if not parents:
                continue
            grown = await _grow_criteria(
                tree,
                parents,
                await _sub_criteria(research_brief, question, name),
                emit,
            )
            for criterion_name, nodes in grown.items():
                next_slots.setdefault(criterion_name, []).extend(nodes)

        await emit({"type": "node_state", "ids": picked_ids, "state": None})
        slots = next_slots
        depth += 1

    await emit({"type": "done"})
    return True


async def _expand_node(tree: Tree, node_id: str, emit: Emit) -> None:
    node = tree.nodes[node_id]
    node.status = "searching"
    await emit({"type": "node_updated", "node": node.to_dict()})

    verticals = node.verticals or ["web", "news"]
    searches = [
        SEARCHERS[v](node.query, count=_VERTICAL_COUNTS.get(v, 3))
        for v in verticals
        if v in SEARCHERS
    ]
    # Fetch the card cover image in the same parallel batch as the verticals,
    # so the thumbnail ships with the node (no separate round-trip per card).
    img_task = asyncio.create_task(search_images(node.query, count=4))
    groups = await asyncio.gather(*searches, return_exceptions=True)

    try:
        imgs = await img_task
        node.card_image = await tree.claim_card_image(imgs)
    except Exception:  # boundary: image search — never block the node on it
        node.card_image = {}

    results = []
    for group in groups:
        if isinstance(group, BaseException):
            continue
        results.extend(group)
    results = deduplicate_results(results)

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
        insight = await llm.synthesize(node.query, snippets)
    except Exception as error:  # boundary: LLM API
        llm.record_error("synthesize", error)
        insight = ""
    node.insight = insight or (results[0].snippet if results else "(no results)")

    node.status = "done"
    await emit({"type": "node_updated", "node": node.to_dict()})


async def _grow_children(
    tree: Tree,
    parent: Node,
    emit: Emit,
    research_brief: ResearchBrief | None = None,
) -> list[Node]:
    """Decompose a parent into children, emit them, and expand all in parallel."""
    children = [
        tree.add(
            label=topic.title or topic.query,
            parent_id=parent.id,
            depth=parent.depth + 1,
            verticals=topic.verticals,
            query=topic.query,
            option=parent.option,
        )
        for topic in await decompose(
            parent.query,
            parent.label,
            research_brief=research_brief,
        )
    ]
    for child in children:
        await emit({"type": "node_added", "node": child.to_dict()})

    await asyncio.gather(*(_expand_node(tree, c.id, emit) for c in children))
    return children


async def _pick_next(
    question: str,
    frontier: list[Node],
    breadth: int,
    research_brief: ResearchBrief | None = None,
) -> list[Node]:
    """Reflection: pick which frontier leaves to expand next (LLM, with fallback)."""
    by_id = {n.id: n for n in frontier}
    try:
        ids = await llm.reflect(
            research_brief.planning_prompt() if research_brief else question,
            [{"id": n.id, "label": n.label, "insight": n.insight} for n in frontier],
            breadth,
        )
    except Exception as error:  # boundary: LLM API
        llm.record_error("reflect", error)
        ids = []
    picked = [by_id[i] for i in ids if i in by_id]
    return picked or frontier[:breadth]


async def explore(
    question: str,
    emit: Emit,
    tree: Tree,
    max_depth: int | None = None,
    breadth: int | None = None,
    research_brief: ResearchBrief | None = None,
) -> None:
    """Grow the tree: root → decompose → search/synthesize → reflect → repeat.

    The caller owns the tree (so it can be acted on later via expand_on_demand /
    add_followup). max_depth / breadth override the server defaults when provided
    (per-request, clamped so a user request can't trigger a runaway tree).

    A comparison brief grows an aligned options x criteria tree instead; if no
    credible set of options can be resolved, it degrades to ordinary exploration
    rather than presenting a comparison that isn't one.
    """
    max_depth = settings.max_depth if max_depth is None else max(1, min(max_depth, 4))
    breadth = settings.expand_per_level if breadth is None else max(1, min(breadth, 4))

    root = tree.add(label=question, parent_id=None, status="done", depth=0)
    await emit({"type": "node_added", "node": root.to_dict()})

    if research_brief is not None and research_brief.is_comparison:
        if await _explore_comparison(
            question, emit, tree, root, max_depth, breadth, research_brief
        ):
            return
        await emit(
            {
                "type": "mode",
                "mode": "explore",
                "requestedMode": "compare",
                "reason": "No distinct options to compare could be identified.",
            }
        )

    await emit({"type": "planning"})
    frontier = await _grow_children(
        tree,
        root,
        emit,
        research_brief=research_brief,
    )

    while frontier and frontier[0].depth < max_depth:
        await emit({"type": "planning"})
        # #1: show the agent is evaluating the current frontier (on-canvas cue)
        frontier_ids = [n.id for n in frontier]
        await emit({"type": "node_state", "ids": frontier_ids, "state": "considering"})

        picks = await _pick_next(
            question,
            frontier,
            breadth,
            research_brief=research_brief,
        )

        # clear the "considering" cue from everyone, then...
        await emit({"type": "node_state", "ids": frontier_ids, "state": None})
        if not picks:
            break
        # #2: highlight the chosen parents before their children are generated
        await emit(
            {"type": "node_state", "ids": [p.id for p in picks], "state": "expanding"}
        )

        grown = await asyncio.gather(
            *(
                _grow_children(
                    tree,
                    p,
                    emit,
                    research_brief=research_brief,
                )
                for p in picks
            )
        )
        # the chosen parents are done expanding once their children exist
        await emit(
            {"type": "node_state", "ids": [p.id for p in picks], "state": None}
        )
        frontier = [child for children in grown for child in children]

    await emit({"type": "done"})


async def expand_on_demand(
    tree: Tree,
    node_id: str,
    emit: Emit,
    research_brief: ResearchBrief | None = None,
) -> None:
    """User-driven: decompose a specific existing node into children and search them."""
    node = tree.nodes.get(node_id)
    if node is None:
        await emit({"type": "done"})
        return
    await emit({"type": "node_state", "ids": [node_id], "state": "expanding"})
    await _grow_children(
        tree,
        node,
        emit,
        research_brief=research_brief,
    )
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
        option=parent.option,
    )
    await emit({"type": "node_added", "node": child.to_dict()})
    await _expand_node(tree, child.id, emit)
    await emit({"type": "done"})


async def get_media(tree: Tree, node_id: str, emit: Emit) -> None:
    """Lazily fetch images + videos for a node (on panel-open) and emit them.

    Videos are only fetched for nodes the planner routed to the videos vertical,
    so the bottom Videos section stays consistent with the node's source badges
    (and we skip the extra search call for non-video nodes).
    """
    node = tree.nodes.get(node_id)
    if node is None:
        return
    wants_videos = "videos" in (node.verticals or [])
    images, videos = await asyncio.gather(
        search_images(node.query, count=6),
        search_videos(node.query, count=4) if wants_videos else _no_media(),
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


async def _no_media() -> list[dict]:
    return []
