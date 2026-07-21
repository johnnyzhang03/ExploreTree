"""MCP tools and UI resource for Microsoft 365 Copilot."""

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from mcp import types
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .config import settings
from .sessions import SessionNotFoundError, sessions

WIDGET_URI = "ui://exploretree/main"


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
        "Start with explore_tree, then use expand_node or add_followup to investigate "
        "specific branches."
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
        "Research a complex question by decomposing it into a sourced knowledge tree. "
        "Depth and breadth must each be between 1 and 4."
    ),
    meta=tool_meta,
)
async def explore_tree(
    question: str,
    depth: int = 3,
    breadth: int = 2,
) -> types.CallToolResult:
    question = question.strip()
    if not question:
        return _error("Question must not be empty.")
    if not 1 <= depth <= 4 or not 1 <= breadth <= 4:
        return _error("Depth and breadth must each be between 1 and 4.")
    session = sessions.start(question, max_depth=depth, breadth=breadth)
    return _result(
        f"Started an ExploreTree research session for: {question}",
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
