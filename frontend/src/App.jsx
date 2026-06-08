import React, { useEffect, useRef, useState } from "react";
import Tree from "./Tree.jsx";

const WS_URL = "ws://localhost:8000/ws";

const capitalize = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

// Map (depth, breadth) to a human "vibe" label shown next to the sliders.
function vibeOf(depth, breadth) {
  const score = depth + breadth;
  if (score <= 4) return "Quick";
  if (score <= 6) return "Balanced";
  return "Deep";
}

function ScopeControls({ depth, breadth, setDepth, setBreadth }) {
  const vibe = vibeOf(depth, breadth);
  return (
    <div className="scope">
      <div className="scope-row">
        <label>Depth</label>
        <input
          type="range"
          min="1"
          max="4"
          value={depth}
          onChange={(e) => setDepth(Number(e.target.value))}
        />
        <span className="scope-val">{depth}</span>
      </div>
      <div className="scope-row">
        <label>Breadth</label>
        <input
          type="range"
          min="1"
          max="4"
          value={breadth}
          onChange={(e) => setBreadth(Number(e.target.value))}
        />
        <span className="scope-val">{breadth}</span>
      </div>
      <div className={`scope-vibe vibe-${vibe.toLowerCase()}`}>{vibe}</div>
    </div>
  );
}

function SearchBar({ autoFocus, question, setQuestion, ask, disabled }) {
  return (
    <div className="search">
      <svg className="search-icon" viewBox="0 0 24 24" width="20" height="20">
        <path
          fill="currentColor"
          d="M15.5 14h-.79l-.28-.27a6.5 6.5 0 1 0-.7.7l.27.28v.79l5 4.99L20.49 19l-4.99-5Zm-6 0A4.5 4.5 0 1 1 14 9.5 4.49 4.49 0 0 1 9.5 14Z"
        />
      </svg>
      <input
        autoFocus={autoFocus}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && ask()}
        placeholder="Ask a complex question…"
      />
      <button onClick={ask} disabled={disabled}>
        Explore
      </button>
    </div>
  );
}

function SidePanel({ node, isLeaf, onExpand, onFollowup, onClose }) {
  const [followup, setFollowup] = useState("");
  if (!node) return null;
  const sources = node.sources || [];
  const canExpand = isLeaf && node.status === "done";

  const submitFollowup = () => {
    const q = followup.trim();
    if (!q) return;
    onFollowup(node.id, q);
    setFollowup("");
  };

  return (
    <aside className="panel">
      <div className="panel-head">
        <span className="panel-title">{capitalize(node.label)}</span>
        <button className="panel-close" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>
      <div className="panel-body">
        <div className="panel-section-label">Insight</div>
        <p className="panel-insight">
          {node.status === "done"
            ? node.insight || "No insight generated."
            : node.status === "searching"
            ? "searching…"
            : "pending…"}
        </p>

        {canExpand && (
          <button className="panel-expand" onClick={() => onExpand(node.id)}>
            Expand this branch
          </button>
        )}

        <div className="panel-section-label">
          Sources {sources.length ? `(${sources.length})` : ""}
        </div>
        {sources.length ? (
          <ul className="panel-sources">
            {sources.map((s, i) => (
              <li key={i}>
                <span className={`src-badge src-${s.vertical || "web"}`}>
                  {s.vertical || "web"}
                </span>
                <a href={s.url} target="_blank" rel="noopener noreferrer">
                  {s.title || s.url}
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="panel-empty">No sources yet.</p>
        )}

        <div className="panel-section-label">Ask a follow-up</div>
        <div className="panel-followup">
          <input
            value={followup}
            onChange={(e) => setFollowup(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitFollowup()}
            placeholder="Ask something about this node…"
          />
          <button onClick={submitFollowup} disabled={!followup.trim()}>
            Ask
          </button>
        </div>
      </div>
    </aside>
  );
}

export default function App() {
  const [question, setQuestion] = useState(
    "What's driving the recent surge in AI chip demand?"
  );
  const [nodes, setNodes] = useState({});
  const [nodeStates, setNodeStates] = useState({}); // id -> transient cue
  const [status, setStatus] = useState("disconnected");
  const [started, setStarted] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [depth, setDepth] = useState(3);
  const [breadth, setBreadth] = useState(2);
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;
    ws.onopen = () => setStatus("Ready");
    ws.onclose = () => setStatus("disconnected");
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "node_added" || msg.type === "node_updated") {
        setNodes((prev) => ({ ...prev, [msg.node.id]: msg.node }));
      } else if (msg.type === "node_state") {
        setNodeStates((prev) => {
          const next = { ...prev };
          for (const id of msg.ids) {
            if (msg.state) next[id] = msg.state;
            else delete next[id];
          }
          return next;
        });
      } else if (msg.type === "planning") {
        setStatus("Planning…");
      } else if (msg.type === "done") {
        setStatus("Done");
      }
    };
    return () => ws.close();
  }, []);

  const ask = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    if (!question.trim()) return;
    setNodes({});
    setNodeStates({});
    setStarted(true);
    setSelectedId(null);
    setStatus("exploring");
    wsRef.current.send(
      JSON.stringify({ type: "ask", question, depth, breadth })
    );
  };

  const send = (payload) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify(payload));
  };
  const expandNode = (id) => send({ type: "expand_node", node_id: id });
  const followup = (id, query) =>
    send({ type: "followup", parent_id: id, query });

  // a node is an unexpanded leaf if nothing else points to it as parent
  const parentIds = new Set(
    Object.values(nodes)
      .map((n) => n.parentId)
      .filter(Boolean)
  );
  const isLeaf = (id) => !parentIds.has(id);

  if (!started) {
    return (
      <div className="app home">
        <div className="home-inner">
          <h1 className="brand">
            <span className="brand-explore">Explore</span>
            <span className="brand-tree">Tree</span>
          </h1>
          <SearchBar
            autoFocus
            question={question}
            setQuestion={setQuestion}
            ask={ask}
            disabled={status === "disconnected"}
          />
          <ScopeControls
            depth={depth}
            breadth={breadth}
            setDepth={setDepth}
            setBreadth={setBreadth}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="topbar">
        <span className="brand-sm">
          <span className="brand-explore">Explore</span>
          <span className="brand-tree">Tree</span>
        </span>
        <SearchBar
          question={question}
          setQuestion={setQuestion}
          ask={ask}
          disabled={status === "disconnected"}
        />
        <span className="status">{status}</span>
      </div>
      <div className="canvas">
        <Tree
          nodes={nodes}
          nodeStates={nodeStates}
          onSelectNode={setSelectedId}
          selectedId={selectedId}
        />
        <SidePanel
          node={selectedId ? nodes[selectedId] : null}
          isLeaf={selectedId ? isLeaf(selectedId) : false}
          onExpand={expandNode}
          onFollowup={followup}
          onClose={() => setSelectedId(null)}
        />
      </div>
    </div>
  );
}

