# ExploreTree — Implementation Plan

> Solo internship project · weeks-long timeline · success bar = **working demo of the core loop**
> Full vision in [proposal.md](proposal.md).

## Guiding principle

Build the **core loop vertically, end-to-end, in week 1** — one question → one decompose → one search → one live-rendered tree — then thicken it. The biggest risk is integration (WebSocket + agent + viz), not any single component. Always keep something demoable.

## MVP scope

### Keep (core loop)
- Decompose question → sub-topics (LLM-as-planner, structured output)
- Bing Web + News search (2 verticals), parallel dispatch
- LLM synthesis: one-sentence insight + source list per node
- Live-growing D3 tree over WebSocket
- Click node → drill down
- Ask follow-up on a node → new branch

### Cut / stretch (defer)
- Timeline replay
- Contradiction red-line visualization
- Confidence scoring (show source count instead)
- Pin / collapse steering
- Drag, force-directed physics polish
- Finance / Places / Images / Sonic verticals

## Architecture (MVP-trimmed)

```
React + D3 Tree Canvas
        │  WebSocket (bidirectional)
Python Agent Backend (FastAPI)
        ├─ Planner    : decompose / pick next node to expand
        ├─ Searcher   : Bing Web + News, parallel
        └─ Synthesizer: snippets → insight + sources
```

Tree state lives **server-side**; every mutation emits a `node_added` / `node_updated` event.
Frontend is a thin renderer of that state.

## Timeline (~6 weeks)

| Week | Focus | Goal by end of week |
|------|-------|---------------------|
| 1 | **Vertical slice** — Bing Web wrapper, FastAPI+WS, React canvas renders a static 3-node tree from a socket msg | Type question → hand-rolled decompose → 3 nodes appear in browser |
| 2 | **Agent loop** — LLM planner (structured), synthesizer, wire planner→searcher→synthesizer | Real question → real one-level tree, live |
| 3 | **Live growth & multi-vertical** — add News + parallel, reflection step picks next node (depth 2–3), search/grow animations | Tree autonomously grows 2–3 levels with visible status |
| 4 | **Human-in-the-loop** — click to drill, follow-up input → new branch, agent status indicator | Co-growing demo works |
| 5 | **Robustness & polish** — boundary error handling (Bing limits, LLM timeouts, bad output), D3 layout tuning, source panel | Stable; optional source-count badge |
| 6 | **Demo prep & buffer** — pick/test 2–3 reliable questions, record fallback video, slippage buffer | Demo-ready |

## Top risks
1. **LLM planner output reliability** — drifts. Strict JSON schema + retry, tested week 2.
2. **Live UX latency** — searches take seconds; tree must *show progress*, not freeze. "Searching pulse" is load-bearing, not polish.
3. **D3 readability at depth** — force-directed tangles fast. Prefer hierarchical `d3.tree()` for MVP.

## Open decisions
- [ ] `d3.tree()` hierarchical layout vs. force-directed → leaning **hierarchical** for legibility
- [ ] Drop News from week 1 (Web only), add it week 3, to keep the slice thinnest

## Future roadmap (post-MVP)

Ideas that build on the shipped foundation (autonomous multi-level tree, multi-vertical search with smart routing, side-panel detail). Ordered by how much each advances the proposal's core thesis — *the tree IS a traceable, steerable reasoning process*.

### 1. Contradiction detection ("the tree reasons, not just collects")
After a batch of nodes resolve, run a pass that compares node insights pairwise and flags conflicts (e.g. one node says "market growing 35%", another "demand declining"). Render conflicts as a **red edge** between the two nodes, with the nature of the disagreement available on hover/in the panel.
- *Why it matters:* surfaces disagreement in the evidence — something no linear search result list does. This is the proposal's signature visual and the strongest "more than pretty search" differentiator.
- *Build sketch:* new LLM pass `find_contradictions(nodes)` returning `[(idA, idB, reason)]` (structured output, like `reflect()`); emit `contradiction_added` events; draw dashed red links in `Tree.jsx` as a second link layer. Run incrementally as nodes reach `done`.

### 2. Export to cited brief ("the tree IS the report")
One-click **"Export brief"** that walks the finished tree and generates a structured, cited Markdown/PDF report — sections derived from branches, each node's insight as prose, sources as footnotes, contradictions flagged inline.
- *Why it matters:* the research artifact *is* the reasoning trace, fully traceable to sources — the killer contrast vs. black-box Deep Research that only emits a final answer. Strongest argument for *why this tool matters*.
- *Build sketch:* backend endpoint that serializes the tree (depth-first) + an LLM "report writer" prompt that turns the node graph into structured prose; render to Markdown first (cheap), PDF later. Reuse existing `node.sources` for footnotes.

### 3. Comparison mode (side-by-side trees)
Ask two questions at once ("bubble tea in Singapore *vs* Bangkok") and grow two trees with linked, comparable branches; align sibling sub-topics so differences are legible.
- *Why it matters:* makes the Finance/Places verticals concrete — compare market caps, local competition, costs across two contexts. A natural, demoable use case.
- *Build sketch:* run two `explore()` sessions, tag nodes with a `treeId`; layout two columns; optionally a "compare these nodes" action that synthesizes a delta insight. Reflection could be biased to mirror the other tree's branch structure.

### 4. Multi-modal nodes
Enrich nodes with media we can already fetch: a Places node shows its venue photo, a market node a chart/image, a topic node a relevant video thumbnail (Images/Videos verticals were probed and return `thumbnailUrl`/`embeddingUrl`).
- *Why it matters:* richer than text-only cards; some answers are inherently visual (a location, a product, a trend chart).
- *Build sketch:* extend `SEARCHERS` routing to optionally include images/videos for suitable node types; carry a `media` field on sources; render a thumbnail strip in the side panel (and optionally a small image on the card). Keep it lazy — only for nodes where the planner flags visual relevance.

### 5. Persistence + sharing
Save a finished tree, share it via URL, and let others **fork** it and keep exploring from where it left off.
- *Why it matters:* turns an ephemeral session into a durable, collaborative knowledge object — research someone else can audit, extend, or branch from.
- *Build sketch:* serialize tree state (nodes + edges + sources + insights) to storage keyed by a share id; a read-only viewer route that rehydrates the D3 tree from saved state; "fork" = clone the saved tree into a live `explore()` session that can grow further. Server-side tree state already exists ([backend/app/tree.py](backend/app/tree.py)) — needs a persistence layer + load path.

> Sequencing suggestion: **Contradiction detection** first (highest novelty, most demoable, aligns with "the tree reasons"), then **Export to brief** (closing argument for the tool's value), then the experience expanders (comparison, multi-modal, sharing) as scope allows.

