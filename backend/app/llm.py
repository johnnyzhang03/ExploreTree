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

_PLANNER_SYSTEM = (
    "You are the planner for ExploreTree, a research agent that grows a knowledge "
    "tree. Given a complex question, decompose it into 3 distinct, non-overlapping "
    "sub-topics that together cover the question. Each sub-topic must be a concise, "
    "self-contained search query (not a sentence, no trailing punctuation). Avoid "
    "generic labels like 'overview' — make each one substantive and searchable."
)

_SYNTH_SYSTEM = (
    "You are the synthesizer for ExploreTree. Given a sub-topic and a list of web "
    "search snippets, distill a single-sentence insight that answers or illuminates "
    "the sub-topic, grounded only in the provided snippets. Be specific and concrete; "
    "cite numbers or named entities when present. Do not speculate beyond the snippets."
)


class Decomposition(BaseModel):
    subtopics: list[str] = Field(min_length=1, max_length=5)


class Insight(BaseModel):
    insight: str


def _client() -> AsyncOpenAI | None:
    if not (settings.openai_api_key and settings.openai_base_url):
        return None
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


async def plan(question: str) -> list[str]:
    """Decompose a question into sub-topics. Returns [] if no LLM is configured."""
    client = _client()
    if client is None:
        return []

    response = await client.responses.parse(
        model=PLANNER_MODEL,
        instructions=_PLANNER_SYSTEM,
        input=f"Question: {question}",
        text_format=Decomposition,
    )
    parsed = response.output_parsed
    return list(parsed.subtopics) if parsed else []


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
