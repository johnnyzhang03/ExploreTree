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
