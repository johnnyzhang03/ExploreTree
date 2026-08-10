import React, { useEffect, useRef, useState } from "react";
import Tree from "./Tree.jsx";
import CardView from "./CardView.jsx";
import { useMcpBridge } from "./McpBridge.jsx";

// Same-origin in production (FastAPI serves this build); falls back to the
// dev-server origin locally, where Vite proxies /ws to the backend.
const STANDALONE_WS_URL =
  (window.location.protocol === "https:" ? "wss://" : "ws://") +
  window.location.host +
  "/ws";

const capitalize = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

// Source/media URLs come from external search results; only allow http(s) in
// href so a javascript:/data: URL can't execute when clicked.
const safeUrl = (url) => (/^https?:\/\//i.test(url || "") ? url : undefined);

function completionArtifactFor(sessionId, brief, nodes) {
  const allNodes = Object.values(nodes);
  const completedNodes = allNodes
    .filter((node) => node.parentId && node.status === "done" && node.insight)
    .sort((a, b) => a.depth - b.depth);
  const verticals = [
    ...new Set(completedNodes.flatMap((node) => node.verticals || [])),
  ];
  const sourceCount = new Set(
    completedNodes.flatMap((node) =>
      (node.sources || []).map((source) => source.url).filter(Boolean)
    )
  ).size;
  const domains = new Set(
    completedNodes.flatMap((node) =>
      (node.sources || []).map((source) => source.domain).filter(Boolean)
    )
  );
  const datedSourceCount = new Set(
    completedNodes.flatMap((node) =>
      (node.sources || []).map((source) => source.publishedAt).filter(Boolean)
    )
  ).size;
  const root = allNodes.find((node) => node.parentId === null);
  const branchCount = root
    ? allNodes.filter((node) => node.parentId === root.id).length
    : 0;
  const allEvidenceGaps = completedNodes.filter(
    (node) =>
      node.evidenceCoverage?.gaps?.noEvidence ?? !(node.sources || []).length
  );

  return {
    type: "exploretree.completion",
    sessionId,
    status: "completed",
    question: brief.question,
    coverage: {
      completedNodes: completedNodes.length,
      sources: sourceCount,
      domains: domains.size,
      datedSources: datedSourceCount,
      topLevelBranches: branchCount,
      evidenceGaps: allEvidenceGaps.length,
      maximumDepth: Math.max(0, ...completedNodes.map((node) => node.depth || 0)),
      verticals,
    },
  };
}

function modelContextFor(artifact) {
  return [
    "ExploreTree has completed, but this context intentionally contains coverage metadata only and no research findings.",
    "Do not generate an unsolicited response. Wait for the user's next message.",
    `When the user later requests insights, call get_research_results with session ID ${artifact.sessionId} before answering.`,
    JSON.stringify(artifact),
  ].join("\n");
}

function branchContextFor(sessionId, selectedId, nodes) {
  const selected = nodes[selectedId];
  const children = {};
  Object.values(nodes).forEach((node) => {
    if (!node.parentId) return;
    if (!children[node.parentId]) children[node.parentId] = [];
    children[node.parentId].push(node.id);
  });

  const path = [];
  const seen = new Set();
  let current = selected;
  while (current && !seen.has(current.id)) {
    seen.add(current.id);
    path.push({ nodeId: current.id, title: current.label });
    current = current.parentId ? nodes[current.parentId] : null;
  }

  const pending = [selectedId];
  const findings = [];
  while (pending.length && findings.length < 12) {
    const nodeId = pending.shift();
    const node = nodes[nodeId];
    if (!node) continue;
    findings.push({
      nodeId: node.id,
      parentId: node.parentId,
      title: node.label,
      status: node.status,
      insight: node.insight || "",
      evidenceCount:
        node.evidenceCoverage?.sourceCount ?? (node.sources || []).length,
      evidenceCoverage: node.evidenceCoverage,
      sources: (node.sources || [])
        .filter((source) => source.url)
        .slice(0, 2)
        .map((source) => ({
          title: source.title || source.url,
          url: source.url,
          domain: source.domain,
          publishedAt: source.publishedAt,
        })),
    });
    pending.push(...(children[nodeId] || []));
  }

  return {
    type: "exploretree.branch-context",
    sessionId,
    status: "selected",
    branches: [
      {
        nodeId: selected.id,
        title: selected.label,
        path: path.reverse(),
        findings,
        truncated: pending.length > 0,
      },
    ],
  };
}

function branchModelContextFor(context) {
  return [
    "The user explicitly selected this ExploreTree branch for discussion.",
    "Use only the compact branch context below. Do not imply that it contains the full research tree.",
    "Discuss what the branch establishes, its evidence gaps, or its relevance to the user's request. Cite supplied source URLs when relevant.",
    JSON.stringify(context),
  ].join("\n");
}

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

function FinanceCard({ data, openExternal }) {
  if (!data) return null;

  if (data.type === "link") {
    const url = safeUrl(data.url);
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="finance-link-card"
        onClick={(event) => {
          if (!url) return;
          event.preventDefault();
          openExternal(url);
        }}
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
            onClick={(event) => {
              event.preventDefault();
              openExternal(safeUrl(data.url));
            }}
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
          <span title={data.priceHistoryLabel || "Price history"}>
            <Sparkline data={data.priceHistory} width={100} height={28} color={changeColor} />
          </span>
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

function SidePanel({
  node,
  media,
  isLeaf,
  onExpand,
  onFollowup,
  onClose,
  openExternal,
  showFollowup,
  showDiscuss,
  onDiscuss,
}) {
  const [followup, setFollowup] = useState("");
  if (!node) return null;
  const allSources = node.sources || [];
  const financeData = allSources.filter((s) => s.finance).map((s) => s.finance);
  // videos render in their own thumbnail section below; finance has its own card
  const sources = allSources.filter((s) => !s.finance && s.vertical !== "videos");
  const coverage = node.evidenceCoverage;
  const canExpand = isLeaf && node.status === "done";
  const images = media?.images || [];
  const videos = media?.videos || [];
  // Media is fetched on panel-open regardless of the node's search status, so
  // it can stream in while the node/tree is still growing. `media` is the
  // payload once it arrives (null until then) — gate sections on that, not on
  // node.status, so thumbnails don't wait for the search to finish.

  const submitFollowup = () => {
    const q = followup.trim();
    if (!q) return;
    onFollowup(node.id, q);
    setFollowup("");
  };

  return (
    <aside className="panel">
      <div className="panel-head">
        <span className="panel-title">
          {node.option && node.criterion && (
            <span className="panel-option">{node.option}</span>
          )}
          {capitalize(node.label)}
        </span>
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

        {coverage && node.parentId && node.status === "done" && (
          <div
            className="panel-evidence-summary"
            title="Includes web, news, finance, places, and video evidence."
          >
            {coverage.gaps?.noEvidence && (
              <span className="coverage-gap">
                No supporting search evidence was found.
              </span>
            )}
            {!coverage.gaps?.noEvidence && (
              <span>
                {coverage.sourceCount} source
                {coverage.sourceCount === 1 ? "" : "s"} from{" "}
                {coverage.domainCount} domain
                {coverage.domainCount === 1 ? "" : "s"}
                {coverage.gaps?.singleDomain && (
                  <span className="coverage-caution"> · limited diversity</span>
                )}
              </span>
            )}
          </div>
        )}

        {showDiscuss && (
          <button className="panel-discuss" onClick={() => onDiscuss(node.id)}>
            Discuss in Copilot
          </button>
        )}

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
                <FinanceCard
                  key={fd.symbol || fd.url || i}
                  data={fd}
                  openExternal={openExternal}
                />
              ))}
            </div>
          </>
        )}

        <div className="panel-section-label">Sources</div>
        {sources.length ? (
          <ul className="panel-sources">
            {sources.map((s, i) => (
              <li key={i}>
                <span className={`src-badge src-${s.vertical || "web"}`}>
                  {s.vertical || "web"}
                </span>
                <a
                  href={safeUrl(s.url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(event) => {
                    event.preventDefault();
                    openExternal(safeUrl(s.url));
                  }}
                >
                  {s.title || s.url}
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="panel-empty">No sources yet.</p>
        )}

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
                  onClick={(event) => {
                    event.preventDefault();
                    openExternal(safeUrl(im.link));
                  }}
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

        {media && videos.length > 0 && (
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
                  onClick={(event) => {
                    event.preventDefault();
                    openExternal(safeUrl(v.link));
                  }}
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

        {showFollowup && (
          <>
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
          </>
        )}
      </div>
    </aside>
  );
}

export default function App() {
  const {
    embedded,
    toolData,
    isConnected: mcpConnected,
    isFullscreen,
    canFullscreen,
    callTool,
    openExternal,
    toggleFullscreen,
    updateModelContext,
    sendMessage,
  } = useMcpBridge();
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
  const [sessionId, setSessionId] = useState(null);
  const [streamUrl, setStreamUrl] = useState(null);
  const [researchBrief, setResearchBrief] = useState({ question });
  const [comparison, setComparison] = useState(null); // aligned compare-mode frame
  const wsRef = useRef(null);
  const nodesRef = useRef({});
  const briefRef = useRef(researchBrief);
  const sessionIdRef = useRef(sessionId);
  const completionAnnouncementsRef = useRef(new Set());
  const clientIdRef = useRef(
    globalThis.crypto?.randomUUID?.() ||
      `widget-${Date.now()}-${Math.random().toString(16).slice(2)}`
  );
  briefRef.current = researchBrief;
  sessionIdRef.current = sessionId;

  useEffect(() => {
    if (!embedded || toolData?.type !== "exploration") return;
    const incomingNodes = Object.fromEntries(
      (toolData.nodes || []).map((node) => [node.id, node])
    );
    const isNewSession = toolData.sessionId !== sessionId;
    setSessionId(toolData.sessionId);
    setStreamUrl(toolData.streamUrl);
    setQuestion(toolData.question || "");
    setResearchBrief(toolData.brief || { question: toolData.question || "" });
    setStarted(true);
    setStatus("exploring");
    if (isNewSession) {
      nodesRef.current = incomingNodes;
      setNodes(incomingNodes);
      setNodeStates({});
      setMedia({});
      setSelectedId(null);
      setPath([]);
      setComparison(toolData.comparison || null);
    } else {
      nodesRef.current = { ...nodesRef.current, ...incomingNodes };
      setNodes((previous) => ({ ...previous, ...incomingNodes }));
    }
  }, [embedded, toolData, sessionId]);

  useEffect(() => {
    const url = embedded ? streamUrl : STANDALONE_WS_URL;
    if (!url) return;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () =>
      setStatus((current) =>
        embedded && current === "exploring" ? current : "Ready"
      );
    ws.onclose = () => setStatus("disconnected");
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "node_added" || msg.type === "node_updated") {
        nodesRef.current = { ...nodesRef.current, [msg.node.id]: msg.node };
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
      } else if (msg.type === "mode") {
        setComparison(
          msg.mode === "compare"
            ? { options: msg.options || [], criteria: msg.criteria || [] }
            : null
        );
      } else if (msg.type === "media") {
        setMedia((prev) => ({
          ...prev,
          [msg.node_id]: { images: msg.images || [], videos: msg.videos || [] },
        }));
        setStatus((current) => (current === "Working…" ? "Ready" : current));
      } else if (msg.type === "done") {
        setStatus("Done");
        if (embedded) {
          const completedSessionId = sessionIdRef.current;
          if (
            !completedSessionId ||
            completionAnnouncementsRef.current.has(completedSessionId)
          ) {
            return;
          }
          completionAnnouncementsRef.current.add(completedSessionId);
          ws.send(
            JSON.stringify({
              type: "claim_completion_handoff",
              client_id: clientIdRef.current,
            })
          );
        }
      } else if (
        msg.type === "completion_handoff_claim" &&
        msg.client_id === clientIdRef.current &&
        msg.claimed
      ) {
        const completedSessionId = sessionIdRef.current;
        if (embedded && completedSessionId) {
          const artifact = completionArtifactFor(
            completedSessionId,
            briefRef.current,
            nodesRef.current
          );
          updateModelContext(modelContextFor(artifact), artifact).catch((error) => {
              completionAnnouncementsRef.current.delete(completedSessionId);
              if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "release_completion_handoff" }));
              }
              console.warn("Failed to update Copilot research context", error);
            });
        }
      } else if (msg.type === "error") {
        setStatus(msg.message || "Error");
      }
    };
    return () => ws.close();
  }, [embedded, streamUrl, updateModelContext]);

  const ask = () => {
    if (embedded) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    if (!question.trim()) return;
    setNodes({});
    nodesRef.current = {};
    setNodeStates({});
    setMedia({});
    setStarted(true);
    setSelectedId(null);
    setPath([]);
    setComparison(null);
    setStatus("exploring");
    wsRef.current.send(
      JSON.stringify({ type: "ask", question, depth, breadth })
    );
  };

  const send = async (payload) => {
    if (embedded) {
      if (!sessionId || !mcpConnected) return;
      if (payload.type !== "get_media") {
        setStatus("Working…");
      }
      try {
        if (payload.type === "expand_node") {
          await callTool("expand_node", {
            session_id: sessionId,
            node_id: payload.node_id,
          });
        } else if (payload.type === "followup") {
          await callTool("add_followup", {
            session_id: sessionId,
            parent_id: payload.parent_id,
            question: payload.query,
          });
        } else if (payload.type === "get_media") {
          await callTool("get_node_media", {
            session_id: sessionId,
            node_id: payload.node_id,
          });
        }
      } catch (error) {
        setStatus(error.message || "Tool call failed");
      }
      return;
    }
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify(payload));
  };
  const expandNode = (id) => send({ type: "expand_node", node_id: id });
  const followup = (id, query) =>
    send({ type: "followup", parent_id: id, query });
  const discussBranch = async (id) => {
    if (!embedded || !sessionId || !nodes[id]) return;
    const context = branchContextFor(sessionId, id, nodes);
    setStatus("Sharing branch…");
    try {
      await updateModelContext(branchModelContextFor(context), context);
      await sendMessage(`Discuss the "${nodes[id].label}" branch.`);
      setStatus((current) =>
        current === "Sharing branch…" ? "Ready" : current
      );
    } catch (error) {
      setStatus(error.message || "Failed to share branch");
    }
  };

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
  // Fetch media as soon as a node's panel is opened. Media is keyed off the
  // node's label (set at creation), so it does NOT need the node's search to
  // finish — fetching on selection lets thumbnails stream in while the tree
  // (and this node) are still growing.
  useEffect(() => {
    if (!selectedId) return;
    if (!nodes[selectedId]) return;
    if (media[selectedId]) return; // already fetched
    send({ type: "get_media", node_id: selectedId });
  }, [selectedId, nodes]);

  if (embedded && !started) {
    return (
      <div className="app mcp-loading">
        {mcpConnected ? "Preparing ExploreTree…" : "Connecting to Microsoft 365 Copilot…"}
      </div>
    );
  }

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
    <div className={`app ${embedded ? "mcp-app" : ""} ${isFullscreen ? "fullscreen" : ""}`}>
      <div className="topbar">
        <span className="brand-sm">
          <span className="brand-explore">Explore</span>
          <span className="brand-tree">Tree</span>
        </span>
        {!embedded && (
          <SearchBar
            question={question}
            setQuestion={setQuestion}
            ask={ask}
            disabled={status === "disconnected"}
          />
        )}
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
        {embedded && canFullscreen && (
          <button className="fullscreen-toggle" onClick={toggleFullscreen}>
            {isFullscreen ? "Exit full screen" : "Full screen"}
          </button>
        )}
        {comparison && (
          <span
            className="mode-chip"
            title={`Comparing ${comparison.options.join(", ")} against ${comparison.criteria.join(", ")}`}
          >
            Comparing {comparison.options.length} options
          </span>
        )}
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
          openExternal={openExternal}
          showFollowup={!embedded}
          showDiscuss={embedded && mcpConnected}
          onDiscuss={discussBranch}
        />
      </div>
    </div>
  );
}
