import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .agent import add_followup, expand_on_demand, explore, get_media
from .tree import Tree

app = FastAPI(title="ExploreTree")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    tree: Tree | None = None  # persists across messages so we can act on nodes later
    tasks: set[asyncio.Task] = set()
    grow_task: asyncio.Task | None = None  # in-flight ask/expand/followup, if any
    # The receive loop must never block on a long operation, or messages sent
    # during it (e.g. get_media on panel-open while the tree is still growing)
    # sit unread in the socket buffer until it finishes. So every handler runs as
    # a tracked task and the loop returns immediately to receive_text(). Concurrent
    # send_text on one socket would interleave frames, so serialize emits via lock.
    send_lock = asyncio.Lock()

    async def emit(event: dict) -> None:
        async with send_lock:
            await websocket.send_text(json.dumps(event))

    def spawn(coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return task

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            kind = msg.get("type")

            if kind == "ask":
                question = (msg.get("question") or "").strip()
                if question:
                    if grow_task is not None:
                        grow_task.cancel()  # abandon a still-growing previous tree
                    tree = Tree()  # fresh tree per question
                    grow_task = spawn(
                        explore(
                            question,
                            emit,
                            tree,
                            max_depth=msg.get("depth"),
                            breadth=msg.get("breadth"),
                        )
                    )
            elif kind == "expand_node" and tree is not None:
                node_id = msg.get("node_id")
                if node_id:
                    grow_task = spawn(expand_on_demand(tree, node_id, emit))
            elif kind == "followup" and tree is not None:
                parent_id = msg.get("parent_id")
                query = (msg.get("query") or "").strip()
                if parent_id and query:
                    grow_task = spawn(add_followup(tree, parent_id, query, emit))
            elif kind == "get_media" and tree is not None:
                node_id = msg.get("node_id")
                if node_id:
                    spawn(get_media(tree, node_id, emit))
    except WebSocketDisconnect:
        return
    finally:
        for task in tasks:
            task.cancel()


# Serve the built frontend (single-service deploy). Mounted last so the /health
# and /ws routes above take precedence; html=True gives SPA fallback to index.html.
# Tries both layouts: local (backend/app/ -> ../../frontend/dist) and the deployed
# wwwroot-root layout (app/ -> ../frontend/dist).
_here = Path(__file__).resolve()
for _candidate in (
    _here.parent.parent.parent / "frontend" / "dist",  # local: backend/app/..
    _here.parent.parent / "frontend" / "dist",          # deployed: app/ at root
):
    if _candidate.is_dir():
        app.mount("/", StaticFiles(directory=_candidate, html=True), name="static")
        break
