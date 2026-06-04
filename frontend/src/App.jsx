import React, { useEffect, useRef, useState } from "react";
import Tree from "./Tree.jsx";

const WS_URL = "ws://localhost:8000/ws";

export default function App() {
  const [question, setQuestion] = useState(
    "Is it worth opening a bubble tea shop in Singapore?"
  );
  const [nodes, setNodes] = useState({});
  const [status, setStatus] = useState("disconnected");
  const [started, setStarted] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;
    ws.onopen = () => setStatus("ready");
    ws.onclose = () => setStatus("disconnected");
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "node_added" || msg.type === "node_updated") {
        setNodes((prev) => ({ ...prev, [msg.node.id]: msg.node }));
      } else if (msg.type === "planning") {
        setStatus("planning…");
      } else if (msg.type === "done") {
        setStatus("done");
      }
    };
    return () => ws.close();
  }, []);

  const ask = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    if (!question.trim()) return;
    setNodes({});
    setStarted(true);
    setStatus("exploring");
    wsRef.current.send(JSON.stringify({ type: "ask", question }));
  };

  const SearchBar = ({ autoFocus }) => (
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
      <button onClick={ask} disabled={status === "disconnected"}>
        Explore
      </button>
    </div>
  );

  if (!started) {
    return (
      <div className="app home">
        <div className="home-inner">
          <h1 className="brand">ExploreTree</h1>
          <SearchBar autoFocus />
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="topbar">
        <span className="brand-sm">ExploreTree</span>
        <SearchBar />
        <span className="status">{status}</span>
      </div>
      <div className="canvas">
        <Tree nodes={nodes} />
      </div>
    </div>
  );
}
