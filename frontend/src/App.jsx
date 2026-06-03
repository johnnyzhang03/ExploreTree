import React, { useEffect, useRef, useState } from "react";
import Tree from "./Tree.jsx";

const WS_URL = "ws://localhost:8000/ws";

export default function App() {
  const [question, setQuestion] = useState(
    "Is it worth opening a bubble tea shop in Singapore?"
  );
  const [nodes, setNodes] = useState({});
  const [status, setStatus] = useState("disconnected");
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
      } else if (msg.type === "done") {
        setStatus("done");
      }
    };
    return () => ws.close();
  }, []);

  const ask = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setNodes({});
    setStatus("exploring");
    wsRef.current.send(JSON.stringify({ type: "ask", question }));
  };

  return (
    <div className="app">
      <div className="topbar">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
          placeholder="Ask a complex question…"
        />
        <button onClick={ask} disabled={status === "disconnected"}>
          Explore
        </button>
        <span className="status">{status}</span>
      </div>
      <div className="canvas">
        <Tree nodes={nodes} />
      </div>
    </div>
  );
}
