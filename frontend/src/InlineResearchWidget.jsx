import React from "react";

const capitalize = (value) =>
  value ? value.charAt(0).toUpperCase() + value.slice(1) : value;

function summarizeState(status, completed, total) {
  const normalized = String(status || "").toLowerCase();
  if (normalized.includes("connecting")) {
    return {
      label: "Connecting to Copilot",
      detail: "Preparing the interactive research widget",
      tone: "progress",
    };
  }
  if (normalized === "disconnected") {
    return {
      label: "Connection interrupted",
      detail: "The research session may still be running.",
      tone: "error",
    };
  }
  if (normalized.includes("error") || normalized.includes("fail")) {
    return {
      label: "Research needs attention",
      detail: status,
      tone: "error",
    };
  }
  if (status === "Done") {
    return {
      label: "Research complete",
      detail: `${completed} topic${completed === 1 ? "" : "s"} ready to review`,
      tone: "success",
    };
  }
  if (!total || status === "Planning…") {
    return {
      label: "Planning the research",
      detail: "Identifying the most useful lines of inquiry",
      tone: "progress",
    };
  }
  return {
    label: "Researching",
    detail: `${completed} of ${total} topic${total === 1 ? "" : "s"} complete`,
    tone: "progress",
  };
}

export default function InlineResearchWidget({
  question,
  nodes,
  status,
  comparison,
  canExpand,
  onExpand,
}) {
  const allNodes = Object.values(nodes);
  const root = allNodes.find((node) => node.parentId === null);
  const researchNodes = allNodes.filter((node) => node.parentId !== null);
  const completedNodes = researchNodes.filter(
    (node) => node.status === "done"
  );
  const topLevelBranches = root
    ? allNodes.filter((node) => node.parentId === root.id)
    : [];
  const visibleBranches = topLevelBranches.slice(0, 3);
  const sourceCount = new Set(
    completedNodes.flatMap((node) =>
      (node.sources || []).map((source) => source.url).filter(Boolean)
    )
  ).size;
  const evidenceGaps = completedNodes.filter(
    (node) =>
      node.evidenceCoverage?.gaps?.noEvidence ?? !(node.sources || []).length
  ).length;
  const state = summarizeState(
    status,
    completedNodes.length,
    researchNodes.length
  );
  const progress =
    researchNodes.length > 0
      ? Math.round((completedNodes.length / researchNodes.length) * 100)
      : 0;

  return (
    <section className="mcp-inline-card" aria-labelledby="inline-research-title">
      <header className="mcp-inline-header">
        <span className="mcp-inline-logo" aria-hidden="true">
          ET
        </span>
        <div>
          <div className="mcp-inline-agent">ExploreTree</div>
          <div className="mcp-inline-kicker">Interactive research</div>
        </div>
        {comparison && (
          <span
            className="mcp-inline-mode"
            title={`Comparing ${comparison.options.join(", ")}`}
          >
            Comparison
          </span>
        )}
      </header>

      <h2 id="inline-research-title" className="mcp-inline-question">
        {question || "Preparing your research workspace…"}
      </h2>

      <div
        className={`mcp-inline-state mcp-inline-state--${state.tone}`}
        role="status"
        aria-live="polite"
      >
        <span className="mcp-inline-state-dot" aria-hidden="true" />
        <span>
          <strong>{state.label}</strong>
          <span>{state.detail}</span>
        </span>
      </div>

      <div
        className={`mcp-inline-progress ${
          researchNodes.length ? "" : "is-indeterminate"
        }`}
        role="progressbar"
        aria-label="Research progress"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={researchNodes.length ? progress : undefined}
      >
        <span style={{ width: `${progress}%` }} />
      </div>

      {visibleBranches.length > 0 && (
        <div className="mcp-inline-branches">
          <div className="mcp-inline-section-label">Research branches</div>
          <ul>
            {visibleBranches.map((branch) => (
              <li key={branch.id}>
                <span
                  className={`mcp-inline-branch-dot is-${branch.status}`}
                  aria-hidden="true"
                />
                <span className="mcp-inline-branch-copy">
                  <strong>{capitalize(branch.label)}</strong>
                  <span>
                    {branch.status === "done"
                      ? branch.insight || "Ready to review"
                      : branch.status === "searching"
                      ? "Searching sources…"
                      : "Queued"}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          {topLevelBranches.length > visibleBranches.length && (
            <div className="mcp-inline-more">
              +{topLevelBranches.length - visibleBranches.length} more in the
              workspace
            </div>
          )}
        </div>
      )}

      {completedNodes.length > 0 && (
        <div className="mcp-inline-metrics" aria-label="Research coverage">
          <span>
            <strong>{completedNodes.length}</strong> topics
          </span>
          <span>
            <strong>{sourceCount}</strong> sources
          </span>
          <span className={evidenceGaps ? "has-gap" : ""}>
            <strong>{evidenceGaps}</strong> evidence gaps
          </span>
        </div>
      )}

      {canExpand && (
        <footer className="mcp-inline-actions">
          <button type="button" onClick={onExpand}>
            Open workspace
          </button>
        </footer>
      )}
    </section>
  );
}
