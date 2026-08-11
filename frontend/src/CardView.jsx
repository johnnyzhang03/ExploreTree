import React from "react";
import {
  Badge,
  Button,
  Card as FluentCard,
  CardPreview,
  Spinner,
} from "@fluentui/react-components";
import { VERTICALS, nodeVerticals } from "./verticals.js";
import { EvidenceSummary, InsightSurface } from "./InsightSurface.jsx";

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
              <Button
                type="button"
                appearance="transparent"
                size="small"
                className="crumb"
                onClick={() => onCrumb(i)}
              >
                {capitalize(node.label)}
              </Button>
            )}
            {!last && <span className="crumb-sep">›</span>}
          </span>
        );
      })}
    </nav>
  );
}

function BranchCard({ node, childCount, childrenGrowing, onOpen, onDrill }) {
  // node.cardImage ships with the node: null/undefined = still loading (shimmer);
  // {} = searched, no image (colored placeholder); {thumbnail} = the cover image.
  const ci = node.cardImage;
  const imgLoading = ci === undefined || ci === null;
  const img = ci && ci.thumbnail ? ci.thumbnail : null;
  const verticals = nodeVerticals(node);
  const accent = VERTICALS[verticals[0]]?.color || "#0f6cbd";
  const isLeaf = childCount === 0;
  const drillLabel = isLeaf ? "Expand" : `Open ${childCount} sub-topic${childCount > 1 ? "s" : ""}`;
  // can't drill while a leaf is still searching, or while its children are growing
  const drillable = (isLeaf ? node.status === "done" : true) && !childrenGrowing;

  return (
    <FluentCard
      appearance="outline"
      className={`card ${node.status}`}
      onClick={() => onOpen(node.id)}
    >
      <CardPreview>
        {imgLoading ? (
          <div className="card-image sk-shimmer" />
        ) : img ? (
          <div className="card-image">
            <img src={img} alt="" loading="lazy" />
          </div>
        ) : (
          <div
            className="card-image card-image--placeholder"
            style={{ background: accent }}
          >
            <span className="card-image-initial">
              {capitalize(node.label).charAt(0)}
            </span>
          </div>
        )}
      </CardPreview>
      <div className="card-body">
        <div
          className={`card-option ${
            node.option && node.criterion ? "" : "card-option--empty"
          }`}
        >
          {node.option || "\u00a0"}
        </div>
        <div className="card-title">{capitalize(node.label)}</div>
        <p className="card-insight">
          {node.status === "done"
            ? node.insight || "No insight yet."
            : node.status === "searching"
            ? "searching…"
            : "pending…"}
        </p>
        <div className="card-coverage-slot">
          {node.status === "done" && (
            <EvidenceSummary compact coverage={node.evidenceCoverage} />
          )}
        </div>
        <div className="card-badges">
          {verticals.map((v) => (
            <Badge
              key={v}
              size="medium"
              appearance="filled"
              className={`src-badge src-${v}`}
              style={{
                backgroundColor: VERTICALS[v].color,
                color: "#fff",
              }}
            >
              {VERTICALS[v].label}
            </Badge>
          ))}
        </div>
        {childrenGrowing ? (
          <div className="card-growing">
            <Spinner size="tiny" />
            Growing sub-topics…
          </div>
        ) : (
          <Button
            type="button"
            appearance="secondary"
            size="medium"
            className="card-drill"
            disabled={!drillable}
            onClick={(e) => {
              e.stopPropagation();
              onDrill(node);
            }}
          >
            {drillLabel}
          </Button>
        )}
      </div>
    </FluentCard>
  );
}

function SkeletonCard({ i }) {
  // staggered shimmer so the cards feel alive, not a static block
  return (
    <FluentCard
      appearance="outline"
      className="card card-skeleton"
      style={{ animationDelay: `${i * 0.12}s` }}
    >
      <div className="card-image sk-shimmer" />
      <div className="card-body">
        <div className="sk-line sk-shimmer" style={{ width: "85%" }} />
        <div className="sk-line sk-shimmer" style={{ width: "70%" }} />
        <div className="sk-line sk-line--sm sk-shimmer" style={{ width: "40%" }} />
      </div>
    </FluentCard>
  );
}

function GrowingLoader() {
  return (
    <div className="grow-loader">
      <Spinner size="tiny" />
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
  const completedChildren = children.filter((node) => node.status === "done");
  const summarySourceCount = completedChildren.reduce(
    (total, node) => total + (node.evidenceCoverage?.sourceCount ?? 0),
    0
  );
  const summaryDomainCount = completedChildren.reduce(
    (total, node) => total + (node.evidenceCoverage?.domainCount ?? 0),
    0
  );
  const summaryCoverage = {
    sourceCount: summarySourceCount,
    domainCount: summaryDomainCount,
    evidenceGaps: completedChildren.filter(
      (node) =>
        node.evidenceCoverage?.gaps?.noEvidence ??
        !(node.sources || []).length
    ).length,
    gaps: {
      singleDomain: summarySourceCount > 0 && summaryDomainCount === 1,
    },
  };
  const currentVerticals = nodeVerticals(current);
  const summaryAccent =
    VERTICALS[currentVerticals[0]]?.color ||
    VERTICALS[nodeVerticals(children[0] || {})[0]]?.color ||
    "#0f6cbd";
  const summaryText =
    current.insight && current.status === "done"
      ? current.insight
      : loading
      ? "ExploreTree is organizing the research branches and gathering evidence."
      : "Explore the branches below to review the findings and supporting evidence.";

  return (
    <div className="cardview">
      <div className="cardview-inner">
        <Breadcrumb trail={trail} onCrumb={onCrumb} />
        <div className="cardview-title">
          <h2>{capitalize(current.label)}</h2>
          <InsightSurface
            label="Research summary"
            accent={summaryAccent}
            className="cardview-context"
            footer={
              completedChildren.length > 0 ? (
                <EvidenceSummary coverage={summaryCoverage} />
              ) : null
            }
          >
            {summaryText}
          </InsightSurface>
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
                <BranchCard
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
