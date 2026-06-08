import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .agent import explore

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

    async def emit(event: dict) -> None:
        await websocket.send_text(json.dumps(event))

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            if msg.get("type") == "ask":
                question = (msg.get("question") or "").strip()
                if question:
                    await explore(
                        question,
                        emit,
                        max_depth=msg.get("depth"),
                        breadth=msg.get("breadth"),
                    )
    except WebSocketDisconnect:
        return
