import React from "react";
import {
  Body1,
  Caption1,
  Caption1Strong,
} from "@fluentui/react-components";
import {
  DocumentText20Regular,
  Globe20Regular,
  Lightbulb20Regular,
  Warning20Regular,
} from "@fluentui/react-icons";

export function EvidenceSummary({ coverage, compact = false, className = "" }) {
  if (!coverage) return null;

  const sourceCount = coverage.sourceCount ?? 0;
  const domainCount = coverage.domainCount ?? 0;
  const evidenceGaps =
    coverage.evidenceGaps ?? (coverage.gaps?.noEvidence ? 1 : 0);
  const limitedDiversity = coverage.gaps?.singleDomain && !evidenceGaps;
  const onlyEvidenceGap = evidenceGaps && !sourceCount && !domainCount;

  if (onlyEvidenceGap) {
    return (
      <div
        className={`evidence-summary evidence-summary--warning ${
          compact ? "evidence-summary--compact" : ""
        } ${className}`}
      >
        <Warning20Regular aria-hidden="true" />
        <Caption1>
          {evidenceGaps} evidence gap{evidenceGaps === 1 ? "" : "s"}
        </Caption1>
      </div>
    );
  }

  return (
    <div
      className={`evidence-summary ${
        compact ? "evidence-summary--compact" : ""
      } ${className}`}
      aria-label={`${sourceCount} sources from ${domainCount} domains`}
    >
      <span>
        <DocumentText20Regular aria-hidden="true" />
        <Caption1>
          {sourceCount} source{sourceCount === 1 ? "" : "s"}
        </Caption1>
      </span>
      <span>
        <Globe20Regular aria-hidden="true" />
        <Caption1>
          {domainCount} domain{domainCount === 1 ? "" : "s"}
        </Caption1>
      </span>
      {!!evidenceGaps && (
        <span className="evidence-summary__warning">
          <Warning20Regular aria-hidden="true" />
          <Caption1>
            {evidenceGaps} gap{evidenceGaps === 1 ? "" : "s"}
          </Caption1>
        </span>
      )}
      {limitedDiversity && (
        <span className="evidence-summary__warning">
          <Warning20Regular aria-hidden="true" />
          <Caption1>Limited diversity</Caption1>
        </span>
      )}
    </div>
  );
}

export function InsightSurface({
  label = "Key insight",
  accent = "#0f6cbd",
  compact = false,
  className = "",
  children,
  footer,
}) {
  return (
    <section
      className={`insight-surface ${
        compact ? "insight-surface--compact" : ""
      } ${className}`}
      style={{ "--insight-accent": accent }}
    >
      <div className="insight-surface__icon" aria-hidden="true">
        <Lightbulb20Regular />
      </div>
      <div className="insight-surface__content">
        <div className="insight-surface__label">
          <Caption1Strong>{label}</Caption1Strong>
        </div>
        <div className="insight-surface__body">
          <Body1>{children}</Body1>
        </div>
        {footer && <div className="insight-surface__footer">{footer}</div>}
      </div>
    </section>
  );
}
