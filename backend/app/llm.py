"""Week-2 LLM layer: structured planner + synthesizer (Azure AI Foundry / GPT).

The planner decomposes a question into sub-topics; the synthesizer turns search
snippets into a one-sentence insight. Both use structured outputs (Pydantic via
`responses.parse`) so the model can't drift off-schema. If no API key is
configured, callers fall back to the Week-1 heuristics so the slice still runs
end-to-end.

The Foundry endpoint exposes an OpenAI-compatible /openai/v1 surface, so we point
the plain AsyncOpenAI client at it via base_url. The deployed models are served
through the Responses API; /chat/completions returns 400 for them.
"""
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from .config import settings

PLANNER_MODEL = settings.openai_planner_model
SYNTH_MODEL = settings.openai_synth_model

ALLOWED_VERTICALS = {"web", "news", "finance", "places", "videos"}
_last_error: dict[str, Any] | None = None


def record_error(operation: str, error: Exception) -> None:
    """Retain non-sensitive provider failure metadata for health diagnostics."""
    global _last_error
    causes = []
    current = error.__cause__ or error.__context__
    while current is not None and len(causes) < 4:
        causes.append(type(current).__name__)
        current = current.__cause__ or current.__context__
    _last_error = {
        "operation": operation,
        "type": type(error).__name__,
        "status": getattr(error, "status_code", None),
        "causes": causes,
    }


def provider_diagnostics() -> dict[str, Any]:
    return {
        "configured": bool(settings.openai_api_key and settings.openai_base_url),
        "lastError": _last_error,
    }

_PLANNER_SYSTEM = (
    "You are the planner for ExploreTree, a research agent that grows a knowledge "
    "tree. Given a complex question, decompose it into 3 distinct, non-overlapping "
    "sub-topics that together cover the question. Each sub-topic must be a concise, "
    "self-contained search query (not a sentence, no trailing punctuation). Avoid "
    "generic labels like 'overview' — make each one substantive and searchable.\n\n"
    "For each sub-topic, also choose which search verticals best fit it, from this "
    "set: 'web' (general background — ALWAYS include), 'news' (current events, recent "
    "developments, trends), 'finance' (company financials, stock/market data, "
    "revenue, valuation, profitability, startup costs, unit economics), 'places' "
    "(physical locations, venues, addresses, local businesses, competitors by "
    "location, rents, foot traffic), 'videos' (any topic where knowledgeable creators "
    "or experts produce substantive analysis, commentary, explainers, deep-dives, "
    "reviews, or tutorials — strong for finance/market analysis, tech and product "
    "deep-dives, science, and expert opinion, not just how-tos). Include 'finance' "
    "whenever a sub-topic touches money/market/profitability dimensions, 'places' "
    "whenever it touches physical location or local competition, and 'videos' whenever "
    "creators/experts likely cover the sub-topic with analysis or explanation (finance, "
    "tech, science, how-to, reviews, opinion). Do not add the specialized verticals to "
    "sub-topics that are purely abstract background with no expert/analytic angle."
)


class PlannedTopic(BaseModel):
    query: str
    title: str = ""
    verticals: list[str] = Field(default_factory=lambda: ["web"])


_SYNTH_SYSTEM = (
    "You are the synthesizer for ExploreTree. Given a sub-topic and a list of web "
    "search snippets, distill a single-sentence insight that answers or illuminates "
    "the sub-topic, grounded only in the provided snippets. Be specific and concrete; "
    "cite numbers or named entities when present. Do not speculate beyond the snippets."
)

_REFLECT_SYSTEM = (
    "You steer ExploreTree's exploration. Given the root question and the current "
    "frontier of leaf nodes (each with an id, label, and the insight found so far), "
    "pick the nodes whose deeper expansion would best fill the biggest remaining "
    "information gaps toward answering the root question. Return only the chosen ids, "
    "ordered by priority. Choose nodes that are substantive and under-explored; skip "
    "nodes that are already well-answered or tangential."
)


class Decomposition(BaseModel):
    subtopics: list[PlannedTopic] = Field(min_length=1, max_length=5)


_COMPARISON_SYSTEM = (
    "You are the comparison planner for ExploreTree. The user wants options "
    "evaluated side by side, not a broad topic map. Identify the distinct options "
    "being compared, and a set of shared evaluation criteria that will be applied "
    "identically to EVERY option so the comparison stays aligned.\n\n"
    "FIRST decide poses_a_choice: does the question actually ask the reader to "
    "choose or decide between distinct, mutually exclusive alternatives? Set it "
    "true only if a decision between named or clearly implied alternatives is at "
    "stake, or the user supplied explicit options. Set it FALSE for open-ended "
    "questions that ask what is happening, why something is happening, how "
    "something works, or what the outlook is — those are explanations, not "
    "choices, even when several entities appear in the answer. For example, "
    "'What's driving the surge in AI chip demand?' is FALSE: the vendors involved "
    "are participants in the explanation, not alternatives the reader is picking "
    "between. When poses_a_choice is false, return empty options and criteria; "
    "inventing alternatives for such a question produces a misleading comparison.\n\n"
    "Options: use exactly the options the user named if they named any; otherwise "
    "infer the 2-4 genuine alternatives implied by the question. Each option name "
    "must be short and concrete (a product, company, market, strategy, or approach) "
    "— never a criterion or a question.\n\n"
    "For each option also write a query: a self-contained search query that "
    "characterizes that option in the context of THIS question, so the option's "
    "overview is grounded in the user's situation rather than being a bare name "
    "lookup.\n\n"
    "Criteria: choose 3 dimensions that actually discriminate between the options "
    "and that evidence exists for. Each criterion needs a short name and a "
    "query_template — a concise search query containing the literal placeholder "
    "{option}, which will be substituted with each option name in turn. Criteria "
    "must be comparable across all options; never make a criterion that only "
    "applies to one option.\n\n"
    "For each criterion also choose search verticals from: 'web' (ALWAYS include), "
    "'news' (current events, recent developments), 'finance' (financials, pricing, "
    "market data, unit economics), 'places' (physical locations, local competition), "
    "'videos' (expert analysis, reviews, deep-dives). The same verticals are used "
    "for that criterion across every option, so choose what fits the criterion "
    "rather than any single option."
)


class ComparisonOption(BaseModel):
    name: str
    query: str = ""


class ComparisonCriterion(BaseModel):
    name: str
    query_template: str = ""
    verticals: list[str] = Field(default_factory=lambda: ["web"])


class ComparisonPlan(BaseModel):
    # Gate first: an open-ended question is an explanation, not a choice, and
    # must degrade to ordinary exploration rather than invent alternatives.
    poses_a_choice: bool = True
    options: list[ComparisonOption] = Field(default_factory=list, max_length=4)
    criteria: list[ComparisonCriterion] = Field(default_factory=list, max_length=4)


_CRITERIA_SYSTEM = (
    "You refine one criterion of an ExploreTree side-by-side comparison into "
    "sub-criteria. Given the comparison question and the parent criterion, produce "
    "2-3 sharper sub-criteria that will each be applied identically to EVERY option, "
    "so the comparison stays aligned. Each needs a short name and a query_template "
    "containing the literal placeholder {option}, which is substituted with each "
    "option name. Never produce a sub-criterion that applies to only one option. "
    "Also route search verticals from: 'web' (ALWAYS include), 'news', 'finance', "
    "'places', 'videos'."
)


class CriteriaSet(BaseModel):
    criteria: list[ComparisonCriterion] = Field(min_length=1, max_length=3)


_CRITERIA_REFLECT_SYSTEM = (
    "You steer the depth of an ExploreTree side-by-side comparison. You are given "
    "the comparison question and the current evaluation criteria, each with the "
    "insights found so far across all options. Pick the criteria whose deeper "
    "investigation would most improve the user's ability to choose between the "
    "options. Prefer criteria that are decision-relevant but still thin or "
    "ambiguous; skip criteria that are already well-evidenced across the options or "
    "that fail to discriminate between them. Return only the chosen criterion names, "
    "exactly as given, ordered by priority."
)


class CriteriaSelection(BaseModel):
    criteria: list[str] = Field(default_factory=list)


class Insight(BaseModel):
    insight: str


class Expansion(BaseModel):
    node_ids: list[str] = Field(default_factory=list)


def _client() -> AsyncOpenAI | None:
    if not (settings.openai_api_key and settings.openai_base_url):
        return None
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=settings.openai_timeout,
        max_retries=0,
    )


def _normalize_verticals(verticals: list[str]) -> list[str]:
    """Keep only known verticals, drop duplicates, and always ground in 'web'."""
    verts = [v for v in dict.fromkeys(verticals) if v in ALLOWED_VERTICALS]
    if "web" not in verts:
        verts.insert(0, "web")
    return verts


async def plan(question: str) -> list[PlannedTopic]:
    """Decompose a question into sub-topics with routed verticals. [] if no LLM."""
    client = _client()
    if client is None:
        return []

    response = await client.responses.parse(
        model=PLANNER_MODEL,
        instructions=_PLANNER_SYSTEM,
        input=f"Question: {question}",
        text_format=Decomposition,
        reasoning={"effort": settings.openai_planner_effort},
    )
    parsed = response.output_parsed
    if not parsed:
        return []

    topics = []
    for t in parsed.subtopics:
        verts = _normalize_verticals(t.verticals)
        topics.append(
            PlannedTopic(query=t.query, title=t.title or t.query, verticals=verts)
        )
    return topics


async def plan_comparison(
    question: str, options_hint: list[str] | None = None
) -> ComparisonPlan | None:
    """Plan a side-by-side comparison: the options and the shared criteria.

    Returns None when no LLM is configured, so the caller can fall back to a
    deterministic comparison plan.
    """
    client = _client()
    if client is None:
        return None

    prompt = question
    if options_hint:
        prompt = (
            f"{question}\n\nThe user explicitly named these options; use exactly "
            f"these: {'; '.join(options_hint)}"
        )
    response = await client.responses.parse(
        model=PLANNER_MODEL,
        instructions=_COMPARISON_SYSTEM,
        input=prompt,
        text_format=ComparisonPlan,
        reasoning={"effort": settings.openai_planner_effort},
    )
    parsed = response.output_parsed
    if not parsed or not parsed.poses_a_choice:
        return None
    return _clean_comparison(parsed.options, parsed.criteria)


def _clean_comparison(
    options: list[ComparisonOption], criteria: list[ComparisonCriterion]
) -> ComparisonPlan | None:
    """None when there is no real choice to make; the caller then degrades to explore.

    Missing criteria are not fatal — the caller substitutes defaults — but fewer
    than two distinct options means the question is not a comparison at all.
    """
    clean_options = _clean_options(options)
    if len(clean_options) < 2:
        return None
    return ComparisonPlan(options=clean_options, criteria=_clean_criteria(criteria))


def _clean_options(options: list[ComparisonOption]) -> list[ComparisonOption]:
    seen: set[str] = set()
    cleaned = []
    for option in options:
        name = option.name.strip()
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        cleaned.append(
            ComparisonOption(name=name, query=(option.query or name).strip())
        )
    return cleaned[:4]


def _clean_criteria(
    criteria: list[ComparisonCriterion],
) -> list[ComparisonCriterion]:
    seen: set[str] = set()
    cleaned = []
    for criterion in criteria:
        name = criterion.name.strip()
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        cleaned.append(
            ComparisonCriterion(
                name=name,
                query_template=(criterion.query_template or name).strip(),
                verticals=_normalize_verticals(criterion.verticals),
            )
        )
    return cleaned[:4]


async def plan_criteria(
    question: str, parent_criterion: str, limit: int = 3
) -> list[ComparisonCriterion]:
    """Refine one criterion into aligned sub-criteria. [] if no LLM configured."""
    client = _client()
    if client is None:
        return []

    response = await client.responses.parse(
        model=PLANNER_MODEL,
        instructions=f"{_CRITERIA_SYSTEM} Produce at most {limit} sub-criteria.",
        input=f"{question}\n\nParent criterion to refine: {parent_criterion}",
        text_format=CriteriaSet,
        reasoning={"effort": settings.openai_planner_effort},
    )
    parsed = response.output_parsed
    if not parsed:
        return []
    return _clean_criteria(parsed.criteria)[:limit]


async def reflect_criteria(
    question: str, criteria: list[dict], limit: int
) -> list[str]:
    """Pick up to `limit` criterion names to deepen across all options.

    Compare mode reflects over criteria rather than individual nodes: expanding a
    single node would break the alignment that makes the comparison readable.
    """
    client = _client()
    if client is None or not criteria:
        return []

    listing = "\n".join(
        f"- {item['name']}\n"
        + "\n".join(
            f"    - {finding['option']}: {finding.get('insight') or '(none)'}"
            for finding in item.get("findings", [])
        )
        for item in criteria
    )
    response = await client.responses.parse(
        model=PLANNER_MODEL,
        instructions=f"{_CRITERIA_REFLECT_SYSTEM} Pick at most {limit} criteria.",
        input=f"Comparison question: {question}\n\nCurrent criteria:\n{listing}",
        text_format=CriteriaSelection,
        reasoning={"effort": settings.openai_planner_effort},
    )
    parsed = response.output_parsed
    by_name = {item["name"].casefold(): item["name"] for item in criteria}
    picked = []
    for name in parsed.criteria if parsed else []:
        resolved = by_name.get(name.strip().casefold())
        if resolved and resolved not in picked:
            picked.append(resolved)
    return picked[:limit]


async def synthesize(subtopic: str, snippets: list[str]) -> str:
    """Distill snippets into a one-sentence insight. Returns '' if no LLM configured."""
    client = _client()
    if client is None or not snippets:
        return ""

    joined = "\n".join(f"- {s}" for s in snippets)
    response = await client.responses.parse(
        model=SYNTH_MODEL,
        instructions=_SYNTH_SYSTEM,
        input=f"Sub-topic: {subtopic}\n\nSnippets:\n{joined}",
        text_format=Insight,
    )
    parsed = response.output_parsed
    return parsed.insight if parsed else ""


async def reflect(question: str, frontier: list[dict], limit: int) -> list[str]:
    """Pick up to `limit` frontier node ids to expand next. Returns [] if no LLM."""
    client = _client()
    if client is None or not frontier:
        return []

    listing = "\n".join(
        f"- id={n['id']} | {n['label']} | insight: {n.get('insight') or '(none)'}"
        for n in frontier
    )
    response = await client.responses.parse(
        model=PLANNER_MODEL,
        instructions=f"{_REFLECT_SYSTEM} Pick at most {limit} ids.",
        input=f"Root question: {question}\n\nFrontier nodes:\n{listing}",
        text_format=Expansion,
        reasoning={"effort": settings.openai_planner_effort},
    )
    parsed = response.output_parsed
    valid = {n["id"] for n in frontier}
    ids = [i for i in (parsed.node_ids if parsed else []) if i in valid]
    return ids[:limit]
