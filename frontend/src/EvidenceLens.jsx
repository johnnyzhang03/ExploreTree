import React from "react";
import {
  Badge,
  Button,
  Dialog,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  DialogTrigger,
} from "@fluentui/react-components";
import {
  Dismiss20Regular,
  DocumentText20Regular,
  Globe20Regular,
  Warning20Regular,
} from "@fluentui/react-icons";
import { EvidenceSummary } from "./InsightSurface.jsx";
import { VERTICALS } from "./verticals.js";

const sourceKey = (source) =>
  (source.canonicalUrl || source.url || source.title || "").toLowerCase();

const sourceDomain = (source) => {
  if (source.domain) return source.domain.toLowerCase().replace(/^www\./, "");
  try {
    return new URL(source.url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return "";
  }
};

const formatDate = (value) => {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
};

export default function EvidenceLens({ nodes, coverage }) {
  const sources = nodes.flatMap((node) => node.sources || []);
  const uniqueSources = new Set(sources.map(sourceKey).filter(Boolean));
  const uniqueDomains = new Set(sources.map(sourceDomain).filter(Boolean));
  const verticalCounts = sources.reduce((counts, source) => {
    const vertical = VERTICALS[source.vertical] ? source.vertical : "other";
    counts[vertical] = (counts[vertical] || 0) + 1;
    return counts;
  }, {});
  const sourceMix = [
    ...Object.entries(VERTICALS)
      .map(([id, vertical]) => ({
        id,
        label: vertical.label,
        color: vertical.color,
        count: verticalCounts[id] || 0,
      }))
      .filter((item) => item.count > 0),
    ...(verticalCounts.other
      ? [
          {
            id: "other",
            label: "Other",
            color: "var(--color-text-tertiary)",
            count: verticalCounts.other,
          },
        ]
      : []),
  ];
  const mixTotal = sourceMix.reduce((total, item) => total + item.count, 0);
  const domainCounts = sources.reduce((counts, source) => {
    const domain = sourceDomain(source);
    if (domain) counts[domain] = (counts[domain] || 0) + 1;
    return counts;
  }, {});
  const topDomains = Object.entries(domainCounts)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 4);
  const datedSources = sources
    .map((source) => source.publishedAt)
    .filter((value) => value && !Number.isNaN(new Date(value).valueOf()))
    .sort((left, right) => new Date(left) - new Date(right));
  const evidenceGaps =
    coverage.evidenceGaps ??
    nodes.filter((node) => node.evidenceCoverage?.gaps?.noEvidence).length;
  const dateRange =
    datedSources.length > 0
      ? datedSources[0] === datedSources[datedSources.length - 1]
        ? formatDate(datedSources[0])
        : `${formatDate(datedSources[0])} – ${formatDate(
            datedSources[datedSources.length - 1]
          )}`
      : "No publication dates";

  return (
    <Dialog modalType="modal">
      <DialogTrigger disableButtonEnhancement>
        <Button
          appearance="transparent"
          size="small"
          className="evidence-lens-trigger"
          aria-label={`Open Evidence Lens: ${coverage.sourceCount} sources from ${coverage.domainCount} domains`}
        >
          <EvidenceSummary coverage={coverage} />
          <span className="evidence-lens-trigger-label">View evidence</span>
        </Button>
      </DialogTrigger>
      <DialogSurface className="evidence-lens">
        <DialogBody className="evidence-lens-body">
          <DialogTitle
            className="evidence-lens-head"
            action={
              <div className="evidence-lens-head-actions">
                <Badge appearance="tint" color="informative">
                  {nodes.length} visible card{nodes.length === 1 ? "" : "s"}
                </Badge>
                <DialogTrigger action="close">
                  <Button
                    appearance="subtle"
                    size="small"
                    icon={<Dismiss20Regular />}
                    className="evidence-lens-close"
                    aria-label="Close Evidence Lens"
                  >
                    Close
                  </Button>
                </DialogTrigger>
              </div>
            }
          >
            <div className="evidence-lens-title-block">
              <span className="evidence-lens-kicker">Evidence Lens</span>
              <strong>How well is this level supported?</strong>
            </div>
          </DialogTitle>

          <DialogContent className="evidence-lens-content">
            <div className="evidence-lens-totals">
              <div>
                <span>Visible card totals</span>
                <strong>
                  {coverage.sourceCount} sources · {coverage.domainCount} domains
                </strong>
              </div>
              <div>
                <span>Unique at this level</span>
                <strong>
                  {uniqueSources.size} sources · {uniqueDomains.size} domains
                </strong>
              </div>
            </div>
            <p className="evidence-lens-note">
              Card totals mirror the metrics below. Repeated evidence across cards is
              counted once in the unique view.
            </p>

            <section className="evidence-lens-section">
              <div className="evidence-lens-section-title">
                <DocumentText20Regular aria-hidden="true" />
                <strong>Source mix</strong>
              </div>
              <div className="evidence-mix">
                {sourceMix.length > 0 ? (
                  sourceMix.map((item) => (
                    <div key={item.id} className="evidence-mix-row">
                      <span>{item.label}</span>
                      <div className="evidence-mix-track" aria-hidden="true">
                        <span
                          style={{
                            width: `${(item.count / mixTotal) * 100}%`,
                            backgroundColor: item.color,
                          }}
                        />
                      </div>
                      <strong>{item.count}</strong>
                    </div>
                  ))
                ) : (
                  <p className="evidence-lens-empty">
                    No classified source evidence yet.
                  </p>
                )}
              </div>
            </section>

            <div className="evidence-lens-columns">
              <section className="evidence-lens-section">
                <div className="evidence-lens-section-title">
                  <Globe20Regular aria-hidden="true" />
                  <strong>Top domains</strong>
                </div>
                <ul className="evidence-domain-list">
                  {topDomains.length > 0 ? (
                    topDomains.map(([domain, count]) => (
                      <li key={domain}>
                        <span>{domain}</span>
                        <strong>{count}</strong>
                      </li>
                    ))
                  ) : (
                    <li className="evidence-lens-empty">
                      No source domains yet.
                    </li>
                  )}
                </ul>
              </section>

              <section className="evidence-lens-section">
                <div className="evidence-lens-section-title">
                  <Warning20Regular aria-hidden="true" />
                  <strong>Coverage checks</strong>
                </div>
                <dl className="evidence-checks">
                  <div>
                    <dt>Dated sources</dt>
                    <dd>
                      {datedSources.length}/{sources.length}
                    </dd>
                  </div>
                  <div>
                    <dt>Date range</dt>
                    <dd>{dateRange}</dd>
                  </div>
                  <div className={evidenceGaps ? "has-gap" : ""}>
                    <dt>Evidence gaps</dt>
                    <dd>{evidenceGaps}</dd>
                  </div>
                </dl>
              </section>
            </div>
          </DialogContent>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
