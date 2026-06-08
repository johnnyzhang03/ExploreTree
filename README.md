# ExploreTree

**An agent-driven research engine whose reasoning is a visible, interactive, user-steerable knowledge tree.**

You ask a complex question; an LLM agent decomposes it, searches across multiple Bing verticals, synthesizes insights, and grows a knowledge tree in real time — while you watch it think and steer where it goes next.

Unlike black-box research agents that only hand you a final report, **the tree *is* the reasoning process**: every node shows its insight, its sources, and how it was reached.

> Full vision in [docs/proposal.md](docs/proposal.md); roadmap and weekly plan in [docs/plan.md](docs/plan.md).

---

## Features

- **LLM planner** decomposes a question into distinct, searchable sub-topics ([structured output](backend/app/llm.py), graceful fallback to heuristics if no key).
- **Multi-vertical search with smart routing** — the planner tags each sub-topic with the verticals that fit it, so the agent queries only what's relevant per node:
  - **Web** & **News** (general background + current events)
  - **Finance** (structured stock/market data — market cap, P/E, dividend yield)
  - **Places** (local businesses — address, category, ratings, price)
- **Autonomous multi-level growth** — an LLM **reflection** step picks the most promising leaves to expand, growing the tree level by level up to a chosen depth.
- **Live, animated visualization** — nodes appear and fill in over a WebSocket; D3 enter/update/exit transitions, pan/zoom with auto-fit, and on-canvas cues showing the agent *evaluating* and *expanding* nodes.
- **User-controlled scope** — depth & breadth sliders on the home screen with a live Quick / Balanced / Deep "vibe" indicator.
- **Human-in-the-loop steering** — click any node for a detail panel with its full insight and linked sources; **expand** a leaf on demand, or ask a **follow-up** question to grow a custom branch.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│            Frontend — React + D3  (Vite)              │
│  Interactive tree canvas · side panel · scope sliders │
└───────────────────────────┬──────────────────────────┘
                            │  WebSocket  (live, bidirectional)
┌───────────────────────────▼──────────────────────────┐
│              Backend — FastAPI  (Python)              │
│                                                       │
│   Planner ─→ Tool router ─→ Searcher ─→ Synthesizer   │
│      │  (decompose)  (per-node verticals)   │         │
│      └──────────── Reflection loop ─────────┘         │
│            (pick next nodes · grow deeper)            │
└───────────────────────────┬──────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────┐
│   Microsoft AI Search   ·   Azure AI Foundry (LLM)    │
│   web · news · finance · places       GPT (Responses) │
└──────────────────────────────────────────────────────┘
```

Tree state lives **server-side** and persists for the session, so the agent can act on existing nodes (expand / follow-up). Every mutation emits a `node_added` / `node_updated` / `node_state` event; the frontend is a thin renderer of that stream.

### Project layout

```
backend/app/
  main.py     FastAPI app + WebSocket handler (owns the per-session tree)
  agent.py    orchestration: explore(), reflection loop, expand/follow-up
  llm.py      planner · synthesizer · reflection (Azure AI Foundry, Responses API)
  search.py   per-vertical adapters (web/news/finance/places) + result shaping
  tree.py     server-side Tree / Node state
  config.py   settings (pydantic-settings, reads backend/.env)
frontend/src/
  App.jsx     state, WebSocket wiring, search bar, scope sliders, side panel
  Tree.jsx    D3 tree rendering, animations, pan/zoom, click handling
  styles.css  styling
docs/         proposal.md · plan.md
```

---

## Setup & run

### Prerequisites
- Python 3.12+ and Node 18+
- A Microsoft AI Search API key, and an Azure AI Foundry endpoint + deployed model (for the LLM layer). Without the LLM key the app still runs end-to-end via heuristic fallbacks.

### Backend (FastAPI, port 8000)

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt    # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux

cp .env.example .env        # then fill in your keys (see below)
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

### Frontend (Vite + React + D3, port 5173)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**, set depth/breadth, type a question, hit **Explore**. Click a node to inspect it, expand it, or ask a follow-up.

---

## Configuration

Settings are read from `backend/.env` (gitignored; see [backend/.env.example](backend/.env.example)).

| Variable | Purpose |
|---|---|
| `BING_SEARCH_KEY` | Microsoft AI Search API key (used by all verticals) |
| `BING_SEARCH_ENDPOINT` | Web search endpoint |
| `BING_NEWS_ENDPOINT` / `BING_FINANCE_ENDPOINT` / `BING_PLACES_ENDPOINT` | Vertical endpoints |
| `OPENAI_API_KEY` | Azure AI Foundry key |
| `OPENAI_BASE_URL` | Foundry `/openai/v1` base URL |
| `OPENAI_PLANNER_MODEL` / `OPENAI_SYNTH_MODEL` | Foundry deployment names for planning vs. synthesis |

Tuning knobs (in [backend/app/config.py](backend/app/config.py)): `max_depth`, `expand_per_level` (defaults; overridable per-request via the UI sliders), `openai_timeout`, `openai_planner_effort`.

> **Note on the LLM layer:** the deployed Foundry models are served via the OpenAI **Responses API** (`client.responses.parse`), not chat-completions. See [backend/app/llm.py](backend/app/llm.py).

---

## Status

Weeks 1–4 of the [plan](docs/plan.md) are complete: vertical slice → LLM agent loop → multi-level growth & multi-vertical → human-in-the-loop. Post-MVP ideas (contradiction detection, export-to-brief, comparison mode, multi-modal nodes, sharing) are sketched in [docs/plan.md](docs/plan.md).
