import asyncio
import json
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .mcp_server import mcp, mcp_http_app
from .sessions import SessionNotFoundError, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="ExploreTree", lifespan=lifespan)


def _origin(value: str) -> str:
    parsed = urlsplit(value)
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""


allowed_origins = {
    "http://localhost:5173",
    _origin(settings.public_base_url),
    _origin(settings.mcp_widget_origin),
}
allowed_origins.discard("")

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allowed_origins),
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "mcp-session-id"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def _websocket_origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin", "")
    return origin in allowed_origins


async def _forward_session(websocket: WebSocket, session_id: str) -> None:
    session = sessions.get(session_id)
    backlog, queue = await session.subscribe()
    try:
        for event in backlog:
            await websocket.send_text(json.dumps(event))
        while True:
            await websocket.send_text(json.dumps(await queue.get()))
    finally:
        await session.unsubscribe(queue)


@app.websocket("/ws/sessions/{session_id}")
async def session_ws(websocket: WebSocket, session_id: str) -> None:
    if not _websocket_origin_allowed(websocket):
        await websocket.close(code=4403)
        return
    try:
        sessions.get(session_id)
    except SessionNotFoundError:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    try:
        await _forward_session(websocket, session_id)
    except (WebSocketDisconnect, SessionNotFoundError, RuntimeError):
        return


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    if not _websocket_origin_allowed(websocket):
        await websocket.close(code=4403)
        return
    await websocket.accept()
    active_session_id: str | None = None
    forward_task: asyncio.Task | None = None

    async def switch_forwarding(session_id: str) -> None:
        nonlocal forward_task
        if forward_task is not None:
            forward_task.cancel()
            with suppress(asyncio.CancelledError):
                await forward_task
        forward_task = asyncio.create_task(
            _forward_session(websocket, session_id)
        )

    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            kind = msg.get("type")

            if kind == "ask":
                question = (msg.get("question") or "").strip()
                if question:
                    session = sessions.start(
                        question,
                        max_depth=msg.get("depth"),
                        breadth=msg.get("breadth"),
                    )
                    active_session_id = session.id
                    await switch_forwarding(session.id)
            elif kind == "expand_node" and active_session_id:
                node_id = msg.get("node_id")
                if node_id:
                    try:
                        sessions.expand(active_session_id, node_id)
                    except (SessionNotFoundError, ValueError) as exc:
                        await websocket.send_text(
                            json.dumps({"type": "error", "message": str(exc)})
                        )
            elif kind == "followup" and active_session_id:
                parent_id = msg.get("parent_id")
                query = (msg.get("query") or "").strip()
                if parent_id and query:
                    try:
                        sessions.follow_up(active_session_id, parent_id, query)
                    except (SessionNotFoundError, ValueError) as exc:
                        await websocket.send_text(
                            json.dumps({"type": "error", "message": str(exc)})
                        )
            elif kind == "get_media" and active_session_id:
                node_id = msg.get("node_id")
                if node_id:
                    try:
                        sessions.fetch_media(active_session_id, node_id)
                    except (SessionNotFoundError, ValueError) as exc:
                        await websocket.send_text(
                            json.dumps({"type": "error", "message": str(exc)})
                        )
    except WebSocketDisconnect:
        return
    finally:
        if forward_task is not None:
            forward_task.cancel()


# FastMCP's Streamable HTTP route is added directly so its public endpoint is
# exactly /mcp while FastAPI remains responsible for the shared application.
app.router.routes.extend(mcp_http_app.routes)


# Serve the built frontend last so API, MCP, and WebSocket routes take precedence.
_here = Path(__file__).resolve()
for _candidate in (
    _here.parent.parent.parent / "frontend" / "dist",
    _here.parent.parent / "frontend" / "dist",
):
    if _candidate.is_dir():
        app.mount("/", StaticFiles(directory=_candidate, html=True), name="static")
        break
