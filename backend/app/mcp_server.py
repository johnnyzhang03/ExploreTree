"""MCP tools and UI resource for Microsoft 365 Copilot."""

from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit, urlunsplit

from mcp import types
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field

from .config import settings
from .research_brief import ResearchBrief
from .sessions import SessionNotFoundError, sessions

WIDGET_URI = "ui://exploretree/main-v2"
BriefItems = Annotated[list[str], Field(max_length=8)]
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
            "ExploreTree is still researching this question. Wait for the widget "
            "to finish before requesting conclusions."
        )
    if artifact["status"] == "failed":
        return "ExploreTree research failed before a complete artifact was produced."
    lines = [
        "ExploreTree research is complete. Use these sourced findings:",
    ]
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
        "Use ExploreTree to research complex questions as a visible knowledge tree. "
        "Start with explore_tree. Use get_tree_outline and get_branch_context to "
        "understand existing branches, then expand_node or add_followup to investigate "
        "them further."
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
        "Build a sourced, interactive evidence map for a complex question, decision, "
        "or investigation. Include the objective, audience, scope, constraints, "
        "freshness, and desired output when known. Depth and breadth must each be "
        "between 1 and 4."
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
) -> types.CallToolResult:
    if len(scope or []) > 8 or len(constraints or []) > 8:
        return _error("Scope and constraints can each contain at most 8 items.")
    brief = ResearchBrief.create(
        question,
        objective=objective,
        audience=audience,
        scope=scope,
        constraints=constraints,
        freshness=freshness,
        desired_output=desired_output,
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
            f"ExploreTree is researching this question in the interactive widget: "
            f"{brief.question}. Findings are still streaming, so do not answer from general "
            "knowledge or claim that research is complete. End this tool sequence now; "
            "do not call get_research_results in the same conversation turn."
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
        "ExploreTree session. Use this to resolve a branch mentioned by the user "
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
        "Use this compact tree outline to resolve branch names to node IDs.",
        outline,
    )


@mcp.tool(
    name="get_branch_context",
    description=(
        "Retrieve compact sourced context for one or two branches in an existing "
        "ExploreTree session. Use two node IDs when the user asks to compare branches."
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
        "Use this branch context to discuss or compare the selected branches.",
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
