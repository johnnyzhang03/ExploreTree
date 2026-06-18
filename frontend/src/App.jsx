import React, { useEffect, useRef, useState } from "react";
import Tree from "./Tree.jsx";
import CardView from "./CardView.jsx";

// Same-origin in production (FastAPI serves this build); falls back to the
// dev-server origin locally, where Vite proxies /ws to the backend.
const WS_URL =
  (window.location.protocol === "https:" ? "wss://" : "ws://") +
  window.location.host +
  "/ws";

const capitalize = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

// Source/media URLs come from external search results; only allow http(s) in
// href so a javascript:/data: URL can't execute when clicked.
const safeUrl = (url) => (/^https?:\/\//i.test(url || "") ? url : undefined);

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

function formatNumber(n) {
  if (n >= 1e12) return (n / 1e12).toFixed(2) + "T";
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
  return n.toFixed(2);
}

function Sparkline({ data, width = 80, height = 24, color = "#188038" }) {
  if (!data || data.length < 2) return null;
  const values = data.filter((v) => v != null);
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 2) - 1;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg className="sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={points} />
    </svg>
  );
}

function FinanceCard({ data, safeUrl }) {
  if (!data) return null;

  if (data.type === "link") {
    return (
      <a
        href={safeUrl(data.url)}
        target="_blank"
        rel="noopener noreferrer"
        className="finance-link-card"
      >
        <span className="src-badge src-finance">Finance</span>
        <span className="finance-link-title">{data.title || data.url}</span>
      </a>
    );
  }

  if (!data.symbol && data.price === undefined) return null;

  const changeColor = (data.change ?? 0) >= 0 ? "#188038" : "#d93025";
  const changeSign = (data.change ?? 0) >= 0 ? "+" : "";
  const hasHistory = data.priceHistory && data.priceHistory.length >= 2;
  const isEtf = data.type === "etf";
  const isIndex = data.type === "index";

  return (
    <div className="finance-card">
      <div className="finance-header">
        {data.symbol && <span className="finance-symbol">{data.symbol}</span>}
        {data.name && data.name !== data.symbol && (
          <span className="finance-name">{data.name}</span>
        )}
        {data.url && (
          <a
            href={safeUrl(data.url)}
            target="_blank"
            rel="noopener noreferrer"
            className="finance-link"
            title="View details"
          >
            ↗
          </a>
        )}
      </div>
      <div className="finance-price-chart">
        {data.price !== undefined && (
          <div className="finance-price-row">
            <span className="finance-price">
              {data.currency === "USD" ? "$" : data.currency + " "}
              {data.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            {data.change !== undefined && (
              <span className="finance-change" style={{ color: changeColor }}>
                {changeSign}{data.change.toFixed(2)}
                {data.changePercent !== undefined && ` (${changeSign}${data.changePercent.toFixed(2)}%)`}
              </span>
            )}
          </div>
        )}
        {hasHistory && (
          <Sparkline data={data.priceHistory} width={100} height={28} color={changeColor} />
        )}
      </div>
      <div className="finance-metrics">
        {data.marketCap && (
          <div className="finance-metric">
            <span className="metric-label">Mkt Cap</span>
            <span className="metric-value">{formatNumber(data.marketCap)}</span>
          </div>
        )}
        {data.netAssets && (
          <div className="finance-metric">
            <span className="metric-label">Net Assets</span>
            <span className="metric-value">{formatNumber(data.netAssets)}</span>
          </div>
        )}
        {data.peRatio && (
          <div className="finance-metric">
            <span className="metric-label">P/E</span>
            <span className="metric-value">{data.peRatio.toFixed(2)}</span>
          </div>
        )}
        {data.expenseRatio && (
          <div className="finance-metric">
            <span className="metric-label">Expense</span>
            <span className="metric-value">{data.expenseRatio}%</span>
          </div>
        )}
        {data.dividendYield && (
          <div className="finance-metric">
            <span className="metric-label">{data.type === "etf" ? "Yield" : "Div Yield"}</span>
            <span className="metric-value">{Number(data.dividendYield).toFixed(2)}%</span>
          </div>
        )}
        {data.low52w && data.high52w && (
          <div className="finance-metric">
            <span className="metric-label">52W Range</span>
            <span className="metric-value">{data.low52w} – {data.high52w}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function SidePanel({ node, media, isLeaf, onExpand, onFollowup, onClose }) {
  const [followup, setFollowup] = useState("");
  if (!node) return null;
  const allSources = node.sources || [];
  const financeData = allSources.filter((s) => s.finance).map((s) => s.finance);
  // videos render in their own thumbnail section below; finance has its own card
  const sources = allSources.filter((s) => !s.finance && s.vertical !== "videos");
  const canExpand = isLeaf && node.status === "done";
  const images = media?.images || [];
  const videos = media?.videos || [];
  const showMedia = node.status === "done";

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

        {financeData.length > 0 && (
          <>
            <div className="panel-section-label">Finance</div>
            <div className="finance-cards">
              {financeData.map((fd, i) => (
                <FinanceCard key={fd.symbol || fd.url || i} data={fd} safeUrl={safeUrl} />
              ))}
            </div>
          </>
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
                <a href={safeUrl(s.url)} target="_blank" rel="noopener noreferrer">
                  {s.title || s.url}
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="panel-empty">No sources yet.</p>
        )}

        {showMedia && (images.length > 0 || !media) && (
          <>
            <div className="panel-section-label">Images</div>
            {media ? (
              images.length ? (
                <div className="media-grid">
                  {images.slice(0, 6).map((im, i) => (
                    <a
                      key={i}
                      href={safeUrl(im.link)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="media-thumb"
                      title={im.title}
                    >
                      <img src={im.thumbnail} alt={im.title} loading="lazy" />
                    </a>
                  ))}
                </div>
              ) : (
                <p className="panel-empty">No images found.</p>
              )
            ) : (
              <p className="panel-empty">Loading…</p>
            )}
          </>
        )}

        {showMedia && media && videos.length > 0 && (
          <>
            <div className="panel-section-label">Videos</div>
            <div className="media-videos">
              {videos.slice(0, 4).map((v, i) => (
                <a
                  key={i}
                  href={safeUrl(v.link)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="video-card"
                >
                  <img src={v.thumbnail} alt={v.title} loading="lazy" />
                  <div className="video-meta">
                    <span className="video-title">{v.title}</span>
                    <span className="video-by">{v.publishedBy}</span>
                  </div>
                </a>
              ))}
            </div>
          </>
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
  const [media, setMedia] = useState({}); // id -> { images, videos }
  const [status, setStatus] = useState("disconnected");
  const [started, setStarted] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [depth, setDepth] = useState(3);
  const [breadth, setBreadth] = useState(2);
  const [view, setView] = useState("cards"); // "cards" | "map"
  const [path, setPath] = useState([]); // node-id trail for the card view
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
      } else if (msg.type === "media") {
        setMedia((prev) => ({
          ...prev,
          [msg.node_id]: { images: msg.images || [], videos: msg.videos || [] },
        }));
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
    setMedia({});
    setStarted(true);
    setSelectedId(null);
    setPath([]);
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

  // seed the card-view path at the root question once it arrives
  const rootNode = Object.values(nodes).find((n) => n.parentId === null);
  useEffect(() => {
    if (rootNode && path.length === 0) setPath([rootNode.id]);
  }, [rootNode, path.length]);

  // card-view navigation
  const drillInto = (node) => {
    if (isLeaf(node.id)) expandNode(node.id); // grow children, then show its page
    setPath((prev) => [...prev, node.id]);
  };
  const goToCrumb = (i) => setPath((prev) => prev.slice(0, i + 1));

  // the current card page is "loading" if global exploration is running, or the
  // page's own node is mid-expand (e.g. after clicking Expand on a deep leaf)
  const pageNodeId = path[path.length - 1];
  const pageLoading =
    status === "exploring" ||
    status === "Planning…" ||
    nodeStates[pageNodeId] === "expanding" ||
    nodeStates[pageNodeId] === "considering";

  // lazily fetch media the first time a node's panel is opened
  useEffect(() => {
    if (!selectedId) return;
    const node = nodes[selectedId];
    if (!node || node.status !== "done") return;
    if (media[selectedId]) return; // already fetched
    send({ type: "get_media", node_id: selectedId });
  }, [selectedId, nodes]);

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
        <div className="view-toggle">
          <button
            className={view === "cards" ? "active" : ""}
            onClick={() => setView("cards")}
          >
            Cards
          </button>
          <button
            className={view === "map" ? "active" : ""}
            onClick={() => setView("map")}
          >
            Map
          </button>
        </div>
        <span className="status">{status}</span>
      </div>
      <div className="canvas">
        {view === "map" ? (
          <Tree
            nodes={nodes}
            nodeStates={nodeStates}
            onSelectNode={setSelectedId}
            selectedId={selectedId}
          />
        ) : (
          <CardView
            nodes={nodes}
            nodeStates={nodeStates}
            path={path}
            loading={pageLoading}
            onCrumb={goToCrumb}
            onOpen={setSelectedId}
            onDrill={drillInto}
          />
        )}
        <SidePanel
          node={selectedId ? nodes[selectedId] : null}
          media={selectedId ? media[selectedId] : null}
          isLeaf={selectedId ? isLeaf(selectedId) : false}
          onExpand={expandNode}
          onFollowup={followup}
          onClose={() => setSelectedId(null)}
        />
      </div>
    </div>
  );
}

