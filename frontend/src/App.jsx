import React, { useEffect, useRef, useState } from "react";
import Tree from "./Tree.jsx";

const WS_URL = "ws://localhost:8000/ws";

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

function SidePanel({ node, onClose }) {
  if (!node) return null;
  const sources = node.sources || [];
  return (
    <aside className="panel">
      <div className="panel-head">
        <span className="panel-title">{node.label}</span>
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
      </div>
    </aside>
  );
}

export default function App() {
  const [question, setQuestion] = useState(
    "Is it worth opening a bubble tea shop in Singapore?"
  );
  const [nodes, setNodes] = useState({});
  const [status, setStatus] = useState("disconnected");
  const [started, setStarted] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
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
    setStarted(true);
    setSelectedId(null);
    setStatus("exploring");
    wsRef.current.send(JSON.stringify({ type: "ask", question }));
  };

  if (!started) {
    return (
      <div className="app home">
        <div className="home-inner">
          <h1 className="brand">ExploreTree</h1>
          <SearchBar
            autoFocus
            question={question}
            setQuestion={setQuestion}
            ask={ask}
            disabled={status === "disconnected"}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="topbar">
        <span className="brand-sm">ExploreTree</span>
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
          onSelectNode={setSelectedId}
          selectedId={selectedId}
        />
        <SidePanel
          node={selectedId ? nodes[selectedId] : null}
          onClose={() => setSelectedId(null)}
        />
      </div>
    </div>
  );
}

