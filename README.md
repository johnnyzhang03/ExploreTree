# ExploreTree

**An agent-driven research engine whose reasoning is a visible, interactive, user-steerable knowledge tree.**

**[▶ Live demo](https://exploretree-demo-a2hze7c2dbabg2bp.eastus2-01.azurewebsites.net)** — ask a question and watch a knowledge tree grow, as browsable cards or a live map.

Ask a question in the standalone web app or Microsoft 365 Copilot. ExploreTree
turns it into a structured research brief, decomposes it, searches across
multiple Bing verticals, synthesizes sourced insights, and grows a knowledge
tree in real time — while you watch it work and steer where it goes next.

Unlike black-box research agents that only hand you a final report, **the tree *is* the reasoning process**: every node shows its insight, its sources, and how it was reached.

> Full vision in [docs/proposal.md](docs/proposal.md); roadmap and weekly plan in [docs/plan.md](docs/plan.md).

<p align="center"><em>Live tree growth from a question</em></p>

![ExploreTree growing a tree](docs/media/demo1.gif)

<p align="center"><em>Inspecting a node — insight, sources, and media</em></p>

![Exploring a node in ExploreTree](docs/media/demo2.gif)

---

## Features

- **LLM planner** decomposes a question into distinct, searchable sub-topics ([structured output](backend/app/llm.py), graceful fallback to heuristics if no key).
- **Multi-vertical search with smart routing** — the planner tags each sub-topic with the verticals that fit it, so the agent queries only what's relevant per node:
  - **Web** & **News** (general background + current events)
  - **Finance** (structured stock/market data — market cap, P/E, dividend yield)
  - **Places** (local businesses — address, category, ratings, price)
  - **Videos** (expert/creator analysis, explainers, reviews, how-tos — routed for finance, tech, science, and more; the AI summary/description feeds synthesis)
- **Autonomous multi-level growth** — an LLM **reflection** step picks the most promising leaves to expand, growing the tree level by level up to a chosen depth.
- **Two ways to explore the same knowledge tree:**
  - **Cards** (default) — a familiar, Pinterest-style drill-down: each topic is an image-forward card; a breadcrumb tracks your path; click to read detail, drill into sub-topics, or expand a leaf.
  - **Map** — the live D3 tree canvas, for an at-a-glance view of the whole structure as it grows.
- **Multi-modal detail** — open a node to see its full insight, linked sources, plus a lazily-loaded **image grid and video cards** relevant to that node.
- **Live, animated visualization** — nodes appear and fill in over a WebSocket; D3 enter/update/exit transitions, pan/zoom with auto-fit, and on-canvas cues showing the agent *evaluating* and *expanding* nodes.
- **User-controlled scope** — depth & breadth sliders on the home screen with a live Quick / Balanced / Deep "vibe" indicator.
- **Human-in-the-loop steering** — click any node for a detail panel with its full insight and linked sources; **expand** a leaf on demand, or ask a **follow-up** question to grow a custom branch.
- **Aligned comparison mode** — named alternatives are researched against the
  same criteria, with uncovered option/criterion cells reported as evidence
  gaps instead of being filled from model knowledge.
- **Native Microsoft 365 Copilot integration** — a declarative agent calls the
  remote MCP server, renders the same interactive tree as an MCP App, and can
  use compact sourced artifacts on later conversation turns.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Standalone browser        Microsoft 365 Copilot              │
│ React + D3 UI             Declarative agent + MCP App host    │
└───────────────┬──────────────────────────┬───────────────────┘
                │ WebSocket                │ Streamable HTTP MCP
┌───────────────▼──────────────────────────▼───────────────────┐
│                  FastAPI application                         │
│  Web UI · /mcp tools/resources · session WebSockets          │
│                                                              │
│  Planner → vertical search → synthesis → reflection loop     │
│                    server-side tree/session state             │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Microsoft AI Search · Azure AI Foundry                       │
│ web · news · finance · places · images · videos · LLM        │
└──────────────────────────────────────────────────────────────┘
```

Tree state lives **server-side** and persists for the session, so the agent can act on existing nodes (expand / follow-up). Every mutation emits a `node_added` / `node_updated` / `node_state` event; the frontend is a thin renderer of that stream.

### Project layout

```
backend/app/
  main.py        FastAPI app, WebSockets, MCP route, and static frontend
  mcp_server.py  MCP tools + self-contained MCP App resource
  agent.py       orchestration: explore(), reflection loop, expand/follow-up
  llm.py         planner · synthesizer · reflection (Azure AI Foundry)
  search.py      vertical adapters and result shaping
  sessions.py    asynchronous research sessions and artifacts
  tree.py        server-side Tree / Node state
frontend/src/
  App.jsx       state, WebSocket wiring, search bar, scope sliders, view toggle
  McpBridge.jsx MCP Apps host bridge (tool results/calls, theme, fullscreen)
  CardView.jsx  Pinterest-style card drill-down + breadcrumb navigation
  Tree.jsx      D3 tree "map" rendering, animations, pan/zoom, click handling
  verticals.js  shared per-vertical labels/colors (used by cards + tree)
  styles.css    styling
docs/         proposal.md · plan.md · DEPLOY.md
m365-agent/
  appPackage/      Teams manifest, declarative agent, plugin, instructions
  build-package.ps1 development sideload-package builder
```

### Microsoft 365 Copilot MCP App

ExploreTree exposes a remote Streamable HTTP MCP server at `/mcp`. Its
declarative agent treats each valid new information request as an ExploreTree
request rather than answering from model knowledge. The first turn calls
`explore_tree` exactly once and returns immediately with an empty running
session; findings stream into the `ui://exploretree/main-v2` MCP App over a
session-scoped WebSocket.

| MCP tool | Purpose |
|---|---|
| `explore_tree` | Start an `explore` or aligned `compare` research session |
| `get_research_results` | Return compact sourced findings on a later turn |
| `get_tree_outline` | Resolve stable node IDs without copying the full tree |
| `get_branch_context` | Return sourced context for one or two branches |
| `expand_node` | Research an existing leaf more deeply |
| `add_followup` | Add a focused question beneath an existing node |
| `get_node_media` | Load node media for the MCP App UI |

The MCP contract separates responsibilities between the host and ExploreTree.
Microsoft 365 Copilot turns the conversation into a research brief containing
the objective, audience, scope, constraints, freshness, desired output, and
optional comparison choices. When research completes, the widget updates model
context without forcing an unsolicited Copilot reply. On a later user turn,
Copilot retrieves the compact artifact, cites the supplied evidence, and labels
missing or conflicting evidence instead of filling gaps from prior knowledge.

The production frontend build is a self-contained HTML document so the MCP
server can return it as the `ui://exploretree/main-v2` resource with MIME type
`text/html;profile=mcp-app`. The standalone web application remains available
at `/`.

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

Open **http://localhost:5173**, set depth/breadth, type a question, hit **Explore**. Browse the results as **Cards** or switch to the **Map** view; click any card/node to inspect it, drill in, expand it, or ask a follow-up.

To exercise the MCP App resource locally, build the frontend first and restart
the backend:

```bash
cd frontend
npm run build
cd ../backend
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

The MCP endpoint is then `http://localhost:8000/mcp`. Microsoft 365 Copilot
requires a publicly reachable HTTPS deployment; localhost is suitable only for
the standalone app and local MCP clients.

---

## Configuration

Settings are read from `backend/.env` (gitignored; see [backend/.env.example](backend/.env.example)).

| Variable | Purpose |
|---|---|
| `BING_SEARCH_KEY` | Microsoft AI Search API key (used by all verticals) |
| `BING_SEARCH_ENDPOINT` | Web search endpoint |
| `BING_NEWS_ENDPOINT` / `BING_FINANCE_ENDPOINT` / `BING_PLACES_ENDPOINT` / `BING_IMAGES_ENDPOINT` / `BING_VIDEOS_ENDPOINT` | Vertical endpoints |
| `OPENAI_API_KEY` | Azure AI Foundry key |
| `OPENAI_BASE_URL` | Foundry `/openai/v1` base URL |
| `OPENAI_PLANNER_MODEL` / `OPENAI_SYNTH_MODEL` | Foundry deployment names for planning vs. synthesis |
| `PUBLIC_BASE_URL` | Public HTTPS origin used in MCP widget WebSocket URLs |
| `MCP_WIDGET_ORIGIN` | Hashed Microsoft widget origin allowed by CORS/WebSocket validation |

Tuning knobs (in [backend/app/config.py](backend/app/config.py)): `max_depth`, `expand_per_level` (defaults; overridable per-request via the UI sliders), `openai_timeout`, `openai_planner_effort`.

> **Note on the LLM layer:** the deployed Foundry models are served via the OpenAI **Responses API** (`client.responses.parse`), not chat-completions. See [backend/app/llm.py](backend/app/llm.py).

---

## Deploy

The app runs as a **single service** — FastAPI serves the built frontend and the WebSocket from one origin. See **[docs/DEPLOY.md](docs/DEPLOY.md)** for a step-by-step Azure App Service guide (build the frontend, set secrets as app settings, enable WebSockets, deploy).

### Add to Microsoft 365 Copilot

Use a Microsoft 365 account that has access to Copilot and belongs to a tenant
where custom app upload is enabled. ExploreTree must already be deployed at a
public HTTPS origin; Copilot cannot call a server running on `localhost`.

#### 1. Build the agent package

From the repository root, run:

```powershell
$TeamsAppId = [guid]::NewGuid().ToString()

.\m365-agent\build-package.ps1 `
  -McpServerUrl "https://<your-app>.azurewebsites.net" `
  -TeamsAppId $TeamsAppId `
  -PublisherEmail "publisher@example.com"
```

This creates `m365-agent\build\ExploreTree.dev.zip`. The script injects the MCP
origin, Teams app ID, ` dev` name suffix, and publisher email. Record
`$TeamsAppId` with the handoff notes because future package updates must reuse
it.

#### 2. Upload it for personal testing

1. Sign in to the Microsoft Teams desktop or web client with the same account
   used for Microsoft 365 Copilot.
2. Go to **Apps** > **Manage your apps** > **Upload an app** >
   **Upload a custom app**.
3. Select `m365-agent\build\ExploreTree.dev.zip`, then select **Add**.
4. Open [Microsoft 365 Copilot](https://m365.cloud.microsoft/chat). Next to
   **New Chat**, open the conversation drawer and select **ExploreTree dev**.
5. Try a conversation starter or ask a research question. A successful test
   calls `explore_tree` and displays the interactive tree while research
   results arrive.

If **Upload a custom app** is unavailable, a Teams administrator must enable
**Teams apps** > **Setup policies** > **Global (Org-wide default)** >
**Upload custom apps** in the
[Teams admin center](https://admin.teams.microsoft.com/). For a controlled
multi-user test, an administrator can instead use
[Microsoft 365 admin center](https://admin.microsoft.com/) >
**Copilot Control System** > **Agents** > **Upload custom agent**, upload the
same ZIP, and assign it to **Just me** or a test group.

#### 3. Update an existing test installation

Changes under `m365-agent\appPackage` require rebuilding and uploading a new
ZIP. Increment `version` in `m365-agent\appPackage\manifest.json` and pass the
same app ID used for the previous package:

```powershell
.\m365-agent\build-package.ps1 `
  -McpServerUrl "https://<your-app>.azurewebsites.net" `
  -TeamsAppId "<existing-teams-app-id>" `
  -PublisherEmail "publisher@example.com"
```

Using a new app ID creates a second agent instead of updating the installed
one. Backend-only or frontend-only deployments do not require another package
upload unless the public MCP origin changes.

The development package uses anonymous MCP authentication. Before production
distribution, add Entra SSO or OAuth 2.1 and bind research sessions to
authenticated users. See Microsoft's guidance for
[sideloading agents](https://learn.microsoft.com/en-us/microsoft-365/copilot/agent-essentials/agent-policies/agent-sideload)
and
[uploading custom agents](https://learn.microsoft.com/en-us/microsoft-365/copilot/agent-essentials/agent-lifecycle/agent-upload-agents).

### Tests

```powershell
cd backend
.venv\Scripts\python.exe -m unittest discover -s tests
cd ..\frontend
npm run build
```
