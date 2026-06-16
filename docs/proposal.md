
# ExploreTree: An Agent-Driven Interactive Search Exploration Engine

## 📌 Summary

**A research agent powered by Bing Search API whose reasoning process is a visible, interactive, and user-guided knowledge tree.**

Users input a complex question; the agent autonomously decomposes it, searches across multiple Bing verticals, synthesizes insights, detects gaps and contradictions, and grows a knowledge tree in real time — while the user can observe, guide, and reshape the exploration at any moment.

---

## 🎯 Problem

When people face complex questions (business decisions, technical research, news deep-dives), existing tools fall into two extremes:

| Approach | Problem |
|----------|---------|
| **Manual search** | Open 10+ tabs, search repeatedly, organize structure manually — extremely inefficient |
| **AI Research Agents** (e.g., Deep Research) | Black-box execution — users can't see the process, can't steer direction, don't know where conclusions come from |

**Core tension: People need a big-picture view, but search engines return linear lists. People need controllability, but AI agents only deliver final reports.**

---

## 💡 Solution

ExploreTree organizes search results into a **real-time growing knowledge tree**:

- **Agent auto-explores**: Receives a question → decomposes into sub-topics → calls Bing Search across multiple verticals → synthesizes insights → detects gaps → continues growing
- **User guides in real time**: Click to drill down, ask follow-up questions, pin important nodes, collapse irrelevant branches, edit directions
- **The tree IS the reasoning process**: Every node has sources, confidence scores, and contradiction annotations; the entire tree is a traceable research report

```
Input: "Is it worth opening a bubble tea shop in Singapore?"

                    [Singapore Bubble Tea Market] 🤖
                   /            |              \\
           [Market Size]   [Competition]    [Consumer Trends]
            SGD 2.1B       Gong Cha/KOI/    Healthy low-sugar ↑35%
            📊 Finance     Tiger Sugar       📰 News
                           🌐 Web
                              |
                      [Healthy Tea Brands]  ← User follow-up
                       Heytea / Chicha San Chen
                       Priced 20-30% higher

         💡 Agent: "Information gap: missing location cost data"
                              |
                       [Rental Heatmap]
                       📍 Places + 🌐 Web
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   Frontend (React + D3.js)                    │
│                                                              │
│  Interactive Tree Canvas                                     │
│  • D3.js force-directed tree layout                         │
│  • Nodes: click / follow-up / pin / collapse / drag         │
│  • Animations: growth, searching pulse, contradiction lines │
│  • Agent status: thinking → searching → synthesizing        │
│  • Timeline replay: review how the tree grew                │
└─────────────────────────┬────────────────────────────────────┘
                          │ WebSocket (real-time bidirectional)
┌─────────────────────────▼────────────────────────────────────┐
│                   Agent Backend (Python)                      │
│                                                              │
│  ┌─────────────┐  ┌───────────────┐  ┌───────────────────┐  │
│  │   Planner    │  │  Tool Router   │  │   Synthesizer     │  │
│  │              │  │                │  │                   │  │
│  │ • Decompose  │  │ • Sub-topic →  │  │ • Snippets →     │  │
│  │   sub-topics │→│   best vertical│→│   insight +       │  │
│  │ • Plan       │  │   selection    │  │   confidence      │  │
│  │   expansion  │  │ • Parallel     │  │ • Gap detection  │  │
│  │   strategy   │  │   multi-       │  │ • Contradiction  │  │
│  │ • Stop       │  │   vertical     │  │   detection      │  │
│  │   condition  │  │   dispatch     │  │ • Source         │  │
│  │ • Respond to │  │                │  │   attribution    │  │
│  │   user input │  │                │  │                   │  │
│  └──────┬──────┘  └───────┬───────┘  └────────┬──────────┘  │
│         │                 │                    │              │
│         └────── Reflection Loop ───────────────┘              │
│              After each round:                               │
│              Enough? Contradictions? Gaps?                    │
│              → Keep growing / Flag conflicts / Conclude      │
└─────────────────────────┬────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────┐
│                  Bing Search API Layer                        │
│                                                              │
│    Web    News    Finance    Places    Images    Videos      │
│     │      │        │         │         │        │          │
│     └──────┴────────┴─────────┴─────────┴────────┘          │
│              Unified response schema + parallel calls        │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔑 Core Technical Challenges

### 1. Agent Planning: How the Tree Grows

At each step, the agent decides:

- **Which node to expand** — the one with the largest information gap? The one the user cares most about?
- **What sub-queries to generate** — not simple keyword appending, but context-aware optimal query generation
- **When to stop** — information sufficient? Budget exhausted? User satisfied?

Implementation: LLM-as-planner (GPT-4o / Claude with structured output), using the full tree state as context.

### 2. Multi-Vertical Orchestration: What to Search, Where to Search

The same sub-topic yields different dimensions of information from different verticals:

```
"Singapore bubble tea market size"
  → Bing Finance: industry reports, market data
  → Bing News: latest industry developments
  → Bing Web: background analysis, blog posts
```

A **vertical routing strategy** automatically selects the optimal vertical combination based on the node's topic type.

### 3. Synthesis & Contradiction Detection

Each node is not a pile of search snippets, but:

- **Insight**: A one-sentence takeaway distilled from multiple results
- **Confidence**: Based on source count, consistency, and recency
- **Sources**: Traceable to specific search results
- **Contradictions**: Conflicts with other nodes (visualized with red connecting lines)
- **Gaps**: What information is still missing (fed back to the Planner to trigger the next search round)

### 4. Human-Agent Collaboration: Co-Growing the Tree

| User Action | Agent Response |
|-------------|----------------|
| 🖱️ Click a node | Expand and drill deeper from this node |
| 💬 Ask follow-up on a node | Generate sub-query, grow new branches |
| 📌 Pin a node | Interpret as "important" — search for more evidence around it |
| 🚫 Collapse a branch | Interpret as "not relevant" — adjust future planning |
