import React from "react";
import { VERTICALS, nodeVerticals } from "./verticals.js";

const capitalize = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

function Breadcrumb({ trail, onCrumb }) {
  return (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      {trail.map((node, i) => {
        const last = i === trail.length - 1;
        return (
          <span key={node.id} className="crumb-wrap">
            {last ? (
              <span className="crumb crumb-current">{capitalize(node.label)}</span>
            ) : (
              <button className="crumb" onClick={() => onCrumb(i)}>
                {capitalize(node.label)}
              </button>
            )}
            {!last && <span className="crumb-sep">›</span>}
          </span>
        );
      })}
    </nav>
  );
}

function Card({ node, childCount, childrenGrowing, onOpen, onDrill }) {
  // node.cardImage ships with the node: null/undefined = still loading (shimmer);
  // {} = searched, no image (colored placeholder); {thumbnail} = the cover image.
  const ci = node.cardImage;
  const imgLoading = ci === undefined || ci === null;
  const img = ci && ci.thumbnail ? ci.thumbnail : null;
  const verticals = nodeVerticals(node);
  const accent = VERTICALS[verticals[0]]?.color || "#1a73e8";
  const isLeaf = childCount === 0;
  const drillLabel = isLeaf ? "Expand" : `Open ${childCount} sub-topic${childCount > 1 ? "s" : ""}`;
  // can't drill while a leaf is still searching, or while its children are growing
  const drillable = (isLeaf ? node.status === "done" : true) && !childrenGrowing;

  return (
    <div className={`card ${node.status}`} onClick={() => onOpen(node.id)}>
      {imgLoading ? (
        <div className="card-image sk-shimmer" />
      ) : img ? (
        <div className="card-image">
          <img src={img} alt="" loading="lazy" />
        </div>
      ) : (
        <div className="card-image card-image--placeholder" style={{ background: accent }}>
          <span className="card-image-initial">{capitalize(node.label).charAt(0)}</span>
        </div>
      )}
      <div className="card-body">
        <div className="card-title">{capitalize(node.label)}</div>
        <p className="card-insight">
          {node.status === "done"
            ? node.insight || "No insight yet."
            : node.status === "searching"
            ? "searching…"
            : "pending…"}
        </p>
        <div className="card-badges">
          {verticals.map((v) => (
            <span key={v} className={`src-badge src-${v}`}>
              {VERTICALS[v].label}
            </span>
          ))}
        </div>
        {childrenGrowing ? (
          <div className="card-growing">
            <span className="card-growing-dots">
              <span />
              <span />
              <span />
            </span>
            Growing sub-topics…
          </div>
        ) : (
          <button
            className="card-drill"
            disabled={!drillable}
            onClick={(e) => {
              e.stopPropagation();
              onDrill(node);
            }}
          >
            {drillLabel}
          </button>
        )}
      </div>
    </div>
  );
}

function SkeletonCard({ i }) {
  // staggered shimmer so the cards feel alive, not a static block
  return (
    <div className="card card-skeleton" style={{ animationDelay: `${i * 0.12}s` }}>
      <div className="card-image sk-shimmer" />
      <div className="card-body">
        <div className="sk-line sk-shimmer" style={{ width: "85%" }} />
        <div className="sk-line sk-shimmer" style={{ width: "70%" }} />
        <div className="sk-line sk-line--sm sk-shimmer" style={{ width: "40%" }} />
      </div>
    </div>
  );
}

function GrowingLoader() {
  return (
    <div className="grow-loader">
      <div className="grow-dots">
        <span />
        <span />
        <span />
      </div>
      <span className="grow-text">Growing your knowledge tree…</span>
    </div>
  );
}

export default function CardView({
  nodes,
  nodeStates = {},
  path,
  loading = false,
  onCrumb,
  onOpen,
  onDrill,
}) {
  const trail = path.map((id) => nodes[id]).filter(Boolean);
  const current = trail[trail.length - 1];
  if (!current) return <div className="cardview cardview-empty">Planning…</div>;

  const children = Object.values(nodes).filter((n) => n.parentId === current.id);

  return (
    <div className="cardview">
      <div className="cardview-inner">
        <Breadcrumb trail={trail} onCrumb={onCrumb} />
        <div className="cardview-title">
          <h2>{capitalize(current.label)}</h2>
          {current.insight && current.status === "done" && (
            <p className="cardview-context">{current.insight}</p>
          )}
        </div>

        {children.length ? (
          <div className="card-grid">
            {children.map((child) => {
              const kids = Object.values(nodes).filter(
                (n) => n.parentId === child.id
              );
              // growing if the agent flagged it for expansion (before children
              // exist) OR its children exist but aren't all done yet
              const growing =
                nodeStates[child.id] === "expanding" ||
                (kids.length > 0 && kids.some((k) => k.status !== "done"));
              return (
                <Card
                  key={child.id}
                  node={child}
                  childCount={kids.length}
                  childrenGrowing={growing}
                  onOpen={onOpen}
                  onDrill={onDrill}
                />
              );
            })}
          </div>
        ) : loading ? (
          <>
            <GrowingLoader />
            <div className="card-grid">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonCard key={i} i={i} />
              ))}
            </div>
          </>
        ) : (
          <div className="cardview-leaf">
            No sub-topics yet — open this card's detail to expand or ask a follow-up.
          </div>
        )}
      </div>
    </div>
  );
}
