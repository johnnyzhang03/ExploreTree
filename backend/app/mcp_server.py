"""MCP tools and UI resource for Microsoft 365 Copilot."""

from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit, urlunsplit

from mcp import types
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field

from .config import settings
from .research_brief import ResearchBrief, normalize_mode
from .sessions import SessionNotFoundError, sessions

WIDGET_URI = "ui://exploretree/main-v2"
BriefItems = Annotated[list[str], Field(max_length=8)]
CompareOptions = Annotated[list[str], Field(max_length=4)]
BranchIds = Annotated[list[str], Field(min_length=1, max_length=2)]


def _public_origin() -> str:
    return settings.public_base_url.rstrip("/")


def _stream_url(session_id: str) -> str:
    base = urlsplit(_public_origin())
    scheme = "wss" if base.scheme == "https" else "ws"
    return urlunsplit(
        (scheme, base.netloc, f"/ws/sessions/{session_id}", "", "")
    )


def _stream_origin() -> str:
    base = urlsplit(_public_origin())
    scheme = "wss" if base.scheme == "https" else "ws"
    return urlunsplit((scheme, base.netloc, "", "", ""))


def _widget_html() -> str:
    here = Path(__file__).resolve()
    for candidate in (
        here.parent.parent.parent / "frontend" / "dist" / "index.html",
        here.parent.parent / "frontend" / "dist" / "index.html",
    ):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return """<!doctype html>
<html><body><p>ExploreTree widget is not built. Run npm run build in frontend.</p></body></html>"""


def _result(text: str, data: dict) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        structuredContent=data,
    )


def _error(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)],
        isError=True,
    )


def _session_data(session) -> dict:
    return {
        "type": "exploration",
        **session.snapshot(),
        "streamUrl": _stream_url(session.id),
    }


def _artifact_text(artifact: dict) -> str:
    if artifact["status"] == "running":
        return (
            "ExploreTree is still researching this question. Status: running. "
            "No findings are available yet."
        )
    if artifact["status"] == "failed":
        return "ExploreTree research failed before a complete artifact was produced."
    lines = [
        "ExploreTree research is complete. Sourced findings:",
    ]
    comparison = artifact.get("comparison")
    if comparison:
        lines.append(
            "This is an aligned comparison of "
            f"{', '.join(comparison['options'])} against the same criteria: "
            f"{', '.join(comparison['criteria'])}."
        )
        for cell in comparison["cells"]:
            coverage = cell["evidenceCoverage"]
            lines.append(
                f"- [{cell['nodeId']}] {cell['option']} — {cell['criterion']}: "
                f"{cell['insight']} Evidence coverage: {coverage['sourceCount']} "
                f"unique sources across {coverage['domainCount']} domains."
            )
        if comparison["unfilledCells"]:
            unfilled = "; ".join(
                f"{cell['option']} — {cell['criterion']}"
                for cell in comparison["unfilledCells"]
            )
            lines.append(
                "These comparison cells have no findings, so the comparison is "
                f"incomplete on those points: {unfilled}."
            )
        return "\n".join(lines)
    for finding in artifact["keyFindings"]:
        source = finding["sources"][0]["url"] if finding["sources"] else ""
        suffix = f" Source: {source}" if source else ""
        coverage = finding["evidenceCoverage"]
        evidence = (
            f" Evidence coverage: {coverage['sourceCount']} unique sources "
            f"across {coverage['domainCount']} domains."
        )
        lines.append(
            f"- [{finding['nodeId']}] {finding['title']}: "
            f"{finding['insight']}{evidence}{suffix}"
        )
    return "\n".join(lines)


widget_meta = {
    "ui": {
        "csp": {
            "connectDomains": [
                _public_origin(),
                _stream_origin(),
            ],
            "resourceDomains": [
                "https://*.bing.com",
                "https://*.mm.bing.net",
            ],
        }
    }
}
tool_meta = {"ui": {"resourceUri": WIDGET_URI}}

mcp = FastMCP(
    "ExploreTree",
    instructions=(
        "For every request to research, explore, investigate, assess, compare, or "
        "recommend about a substantive topic, call explore_tree instead of answering "
        "from general knowledge. explore_tree starts asynchronous work and returns "
        "before findings exist. "
        "After calling it, end the tool sequence and report only that research is "
        "continuing in the widget. Never call another tool or answer the research "
        "question in that same conversation turn. Use branch-reading and mutation "
        "tools only in response to a later user message."
    ),
    host="0.0.0.0",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    ),
)


@mcp.resource(
    WIDGET_URI,
    name="ExploreTree interactive research widget",
    mime_type="text/html;profile=mcp-app",
    meta=widget_meta,
)
async def exploretree_widget() -> str:
    return _widget_html()


@mcp.tool(
    name="explore_tree",
    description=(
        "Use this tool whenever the user asks to research, explore, investigate, "
        "assess, compare, or recommend about a substantive topic. Start an interactive, "
        "sourced knowledge-tree investigation instead of answering from general "
        "knowledge. This returns before any findings are available. After calling "
        "it, do not answer the research question and do not call any other tool in the "
        "same conversation turn. Include the objective, audience, scope, constraints, "
        "freshness, and desired output when known. Set mode to 'compare' when the "
        "user is weighing specific alternatives against each other, and pass those "
        "alternatives in options; otherwise use 'explore'. A request for a "
        "recommendation between named alternatives is a comparison: use mode "
        "'compare' and put the decision in objective. Depth and breadth must "
        "each be between 1 and 4."
    ),
    meta=tool_meta,
)
async def explore_tree(
    question: str,
    depth: int = 3,
    breadth: int = 2,
    objective: str = "",
    audience: str = "",
    scope: BriefItems | None = None,
    constraints: BriefItems | None = None,
    freshness: str = "",
    desired_output: str = "",
    mode: str = "explore",
    options: CompareOptions | None = None,
) -> types.CallToolResult:
    if len(scope or []) > 8 or len(constraints or []) > 8:
        return _error("Scope and constraints can each contain at most 8 items.")
    if mode and normalize_mode(mode) != mode.strip().casefold():
        return _error("Mode must be either 'explore' or 'compare'.")
    brief = ResearchBrief.create(
        question,
        objective=objective,
        audience=audience,
        scope=scope,
        constraints=constraints,
        freshness=freshness,
        desired_output=desired_output,
        mode=mode,
        options=options,
    )
    if not brief.question:
        return _error("Question must not be empty.")
    if not 1 <= depth <= 4 or not 1 <= breadth <= 4:
        return _error("Depth and breadth must each be between 1 and 4.")
    session = sessions.start(
        brief.question,
        brief=brief,
        max_depth=depth,
        breadth=breadth,
    )
    return _result(
        (
            "ExploreTree research has started in the interactive widget. "
            "Status: running. No findings are available in this result yet; "
            "they will appear in the widget as the exploration progresses."
        ),
        _session_data(session),
    )


@mcp.tool(
    name="expand_node",
    description="Expand a leaf node in an existing ExploreTree research session.",
    meta=tool_meta,
)
async def expand_node(session_id: str, node_id: str) -> types.CallToolResult:
    try:
        session = sessions.expand(session_id, node_id)
    except SessionNotFoundError:
        return _error("The exploration session was not found or has expired.")
    except ValueError as exc:
        return _error(str(exc))
    return _result(f"Expanding node {node_id}.", _session_data(session))


@mcp.tool(
    name="add_followup",
    description=(
        "Add a focused follow-up question below a node in an existing ExploreTree "
        "research session."
    ),
    meta=tool_meta,
)
async def add_followup(
    session_id: str,
    parent_id: str,
    question: str,
) -> types.CallToolResult:
    question = question.strip()
    if not question:
        return _error("Follow-up question must not be empty.")
    try:
        session = sessions.follow_up(session_id, parent_id, question)
    except SessionNotFoundError:
        return _error("The exploration session was not found or has expired.")
    except ValueError as exc:
        return _error(str(exc))
    return _result("Added the follow-up branch.", _session_data(session))


@mcp.tool(
    name="get_research_results",
    description=(
        "Retrieve the current status and compact sourced findings for an existing "
        "ExploreTree session. Call only after the user sends a later message asking "
        "about a previously started exploration. Never call in the same conversation "
        "turn as explore_tree."
    ),
)
async def get_research_results(session_id: str) -> types.CallToolResult:
    try:
        session = sessions.get(session_id)
    except SessionNotFoundError:
        return _error("The exploration session was not found or has expired.")
    artifact = session.artifact()
    return _result(_artifact_text(artifact), artifact)


@mcp.tool(
    name="get_tree_outline",
    description=(
        "Retrieve compact semantic metadata and stable node IDs for an existing "
        "ExploreTree session on a later user turn. Never call in the same conversation "
        "turn as explore_tree. Use this to resolve a branch mentioned by the user "
        "before expanding it, adding a follow-up, or requesting branch context."
    ),
)
async def get_tree_outline(session_id: str) -> types.CallToolResult:
    try:
        session = sessions.get(session_id)
    except SessionNotFoundError:
        return _error("The exploration session was not found or has expired.")
    outline = session.tree_outline()
    return _result(
        "Compact tree outline with stable node IDs for this session.",
        outline,
    )


@mcp.tool(
    name="get_branch_context",
    description=(
        "Retrieve compact sourced context for one or two branches in an existing "
        "ExploreTree session on a later user turn. Never call in the same conversation "
        "turn as explore_tree. Use two node IDs when the user asks to compare branches."
    ),
)
async def get_branch_context(
    session_id: str,
    node_ids: BranchIds,
) -> types.CallToolResult:
    if not 1 <= len(node_ids) <= 2:
        return _error("Provide one or two node IDs.")
    try:
        session = sessions.get(session_id)
        context = session.branch_context(node_ids)
    except SessionNotFoundError:
        return _error("The exploration session was not found or has expired.")
    except ValueError as exc:
        return _error(str(exc))
    return _result(
        "Sourced context for the selected branches.",
        context,
    )


@mcp.tool(
    name="get_node_media",
    description="Load image and video references for an ExploreTree node.",
    meta={"ui": {"resourceUri": WIDGET_URI, "visibility": ["app"]}},
)
async def get_node_media(session_id: str, node_id: str) -> types.CallToolResult:
    try:
        session = sessions.fetch_media(session_id, node_id)
    except SessionNotFoundError:
        return _error("The exploration session was not found or has expired.")
    except ValueError as exc:
        return _error(str(exc))
    return _result(f"Loading media for node {node_id}.", _session_data(session))


mcp_http_app = mcp.streamable_http_app()
