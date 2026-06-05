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
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from .config import settings

PLANNER_MODEL = settings.openai_planner_model
SYNTH_MODEL = settings.openai_synth_model

ALLOWED_VERTICALS = {"web", "news", "finance", "places"}

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
    "location, rents, foot traffic). Include 'finance' whenever a sub-topic touches "
    "money/market/profitability dimensions, and 'places' whenever it touches physical "
    "location or local competition — but do not add them to sub-topics that are purely "
    "about general concepts, consumer sentiment, or background."
)


class PlannedTopic(BaseModel):
    query: str
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
        verts = [v for v in dict.fromkeys(t.verticals) if v in ALLOWED_VERTICALS]
        if "web" not in verts:
            verts.insert(0, "web")
        topics.append(PlannedTopic(query=t.query, verticals=verts))
    return topics


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
