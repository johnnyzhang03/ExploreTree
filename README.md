# ExploreTree

Agent-driven interactive search exploration engine. See [docs/proposal.md](docs/proposal.md) and [docs/plan.md](docs/plan.md).

This is the **Week 1 vertical slice**: type a question → hand-rolled decompose into 3 sub-topics → parallel Bing Web search → live-growing D3 tree over WebSocket.

## Run

### Backend (FastAPI, port 8000)

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt # macOS/Linux

cp .env.example .env        # then fill in BING_SEARCH_KEY
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 --reload
```

### Frontend (Vite + React + D3, port 5173)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, type a question, hit **Explore**.

## What's a stub for now (per plan.md, Weeks 2–3)

- **Decompose** is template-based, not the LLM planner ([backend/app/agent.py](backend/app/agent.py) `decompose`).
- **Insight** is the top result's snippet, not LLM synthesis.
- **News + other verticals**, reflection loop, click-to-drill, follow-ups — deferred.
