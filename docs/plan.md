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

Adapt the research process to what the user intends to accomplish.

#### Explore

Build a broad map of a topic, its major dimensions, and open questions.

#### Compare

Use aligned branches and consistent criteria to compare options, markets, or
strategies.

#### Recommend

Produce decision-ready evidence separated into:

- Findings
- Tradeoffs
- Assumptions
- Risks and uncertainties
- Evidence gaps
- Final qualified recommendation

Copilot should infer the mode from the conversation while allowing the user to
override it. The selected mode should influence planning, tree structure,
reflection priorities, stopping criteria, and the final research artifact.

## Suggested sequence

1. Clear completion experience.
2. Copilot-to-tree branch interaction.
3. Research quality signals.
4. Explore, Compare, and Recommend modes.
