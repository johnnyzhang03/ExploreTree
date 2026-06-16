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

    async def emit(event: dict) -> None:
        await websocket.send_text(json.dumps(event))

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            kind = msg.get("type")

            if kind == "ask":
                question = (msg.get("question") or "").strip()
                if question:
                    tree = Tree()  # fresh tree per question
                    await explore(
                        question,
                        emit,
                        tree,
                        max_depth=msg.get("depth"),
                        breadth=msg.get("breadth"),
                    )
            elif kind == "expand_node" and tree is not None:
                node_id = msg.get("node_id")
                if node_id:
                    await expand_on_demand(tree, node_id, emit)
            elif kind == "followup" and tree is not None:
                parent_id = msg.get("parent_id")
                query = (msg.get("query") or "").strip()
                if parent_id and query:
                    await add_followup(tree, parent_id, query, emit)
            elif kind == "get_media" and tree is not None:
                node_id = msg.get("node_id")
                if node_id:
                    await get_media(tree, node_id, emit)
    except WebSocketDisconnect:
        return


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
