# ExploreTree — Product Roadmap

> Full product vision in [proposal.md](proposal.md).

## Product direction

ExploreTree is Microsoft 365 Copilot's visual, inspectable research workspace.
Copilot frames the user's intent and applies the findings; ExploreTree executes,
visualizes, and exposes the evidence structure.

## Current foundation

- Microsoft 365 declarative agent with an MCP App widget.
- Structured research briefs passed from Copilot to ExploreTree.
- Autonomous decomposition, multi-vertical search, synthesis, and reflection.
- Live tree updates over a session-scoped WebSocket.
- Interactive branch expansion, follow-ups, sources, images, and videos.
- Completed research artifacts available to Copilot for later synthesis.

## Product priorities

### 1. Clear completion experience

Make the asynchronous workflow obvious and trustworthy.

- Show distinct running, completed, partially completed, and failed states.
- Keep the widget focused on live exploration, with only a compact status.
- When research completes, publish the artifact and start a new Copilot chat
  turn.
- Have Copilot acknowledge completion, summarize coverage, and suggest useful
  follow-up questions without automatically repeating the findings.
- Prevent Copilot from retrieving or summarizing results before completion.

### 2. Copilot-to-tree branch interaction

Allow natural-language conversation to control and discuss the visual tree.

- Give branches stable identifiers and concise semantic metadata. **Implemented.**
- Support requests such as:
  - "Compare these two branches."
  - "Expand the regulatory risk."
  - "Investigate this evidence gap."
  - "Which branch matters most to the decision?"
- Return compact branch context to Copilot without duplicating the full tree.
  **Implemented for one or two branches.**
- Keep widget interactions and conversational actions synchronized. **Implemented
  for expansion, follow-ups, and explicit "Discuss in Copilot" selection.**

Branch ranking and decision relevance remain dependent on priorities 3 and 4.
Compare mode (priority 4) now supplies aligned option and criterion coordinates
for branch comparison.

### 3. Research quality signals

Show why a finding should be trusted instead of using an opaque confidence score.

- Evidence count per node. **Implemented as unique source coverage.**
- Source diversity across domains and verticals. **Implemented.**
- Source freshness and date coverage. **Publication-date coverage and range
  implemented where source metadata is available; freshness judgments remain
  dependent on the research mode and brief.**
- Unsupported or weakly supported claims.
- Conflicting evidence and contradictions.
- Unexplored questions and information gaps. **Nodes with no evidence and
  single-domain coverage are surfaced; semantic gap detection remains deferred.**
- Include the same quality signals in artifacts returned to Copilot.
  **Implemented for evidence coverage.**

The current MVP deliberately reports descriptive evidence coverage rather than
a quality or confidence score. Claim-level support and contradiction detection
require claim-to-source attribution and should not be inferred from aggregate
source counts.

### 4. Decision-oriented research modes

Adapt the research process to what the user intends to accomplish. Two modes
ship: **Explore** and **Compare**. A mode must change how research is *run*, not
just how it is worded.

#### Explore

Build a broad map of a topic, its major dimensions, and open questions.
Gap-driven growth: reflection expands whichever leaves leave the biggest
information gaps. **Implemented** — this is the default mode.

#### Compare

Use aligned branches and consistent criteria to compare options, markets, or
strategies. **Implemented.**

- Level 1 is the options; every level below applies the same criteria to every
  option, in the same order, so the branches stay aligned.
- Reflection selects *criteria*, not individual nodes — deepening a single node
  would destroy the alignment. A chosen criterion is refined into sub-criteria
  once and applied across all options.
- Copilot infers the mode and passes the options; the user can override it.
- The artifact carries an option-by-criterion matrix and names the cells that
  were never filled, so an incomplete comparison reads as incomplete.
- If no two distinct options can be resolved, the run degrades to Explore rather
  than presenting a comparison that isn't one.
- Automatic growth stays symmetric; an explicit user expansion or follow-up is
  allowed to break symmetry.

#### Recommend — deferred, gated on priority 3

Decision-ready output separated into findings, tradeoffs, assumptions, risks,
evidence gaps, and a final qualified recommendation.

This is **not** implemented, and deliberately so. Tradeoffs, assumptions, and
risk sections require claim-to-source attribution, which priority 3 explicitly
defers. Built on today's aggregate evidence coverage, those sections would be
LLM-asserted while presenting as decision-grade — a worse failure than not
shipping them.

A thin Recommend mode was also rejected: it would have changed only artifact
wording, making it an output preference wearing a mode's clothes, while a third
enum value would degrade Copilot's mode inference. Recommendation *intent*
already reaches the planner through the existing `objective` and
`desired_output` brief fields, so nothing is lost by waiting.

Recommend earns a mode once claim-level attribution exists, because it will then
genuinely change stopping criteria — stop when the decision is supported, rather
than when the map is covered — and artifact structure.

## Suggested sequence

1. Clear completion experience.
2. Copilot-to-tree branch interaction.
3. Research quality signals.
4. Explore and Compare modes. **Implemented.** Recommend follows priority 3.
