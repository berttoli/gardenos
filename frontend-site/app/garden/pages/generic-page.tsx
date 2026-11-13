"use client";

import type { AppPageKey } from "../shared";
import { getPageConfig } from "../services/page-service";
import type { GardenServiceContext } from "../services/context";
import type { PageWorkspaceView } from "./registry";
import { ActionNoticeCard, InspectorMetricCard, useTimedNotice } from "../shared";

export function GenericPage({
  pageKey,
}: {
  pageKey: Exclude<AppPageKey, "map" | "plants">;
}, _context?: GardenServiceContext | null): PageWorkspaceView {
  const page = getPageConfig(pageKey);
  const [notice] = useTimedNotice();
  void _context;

  return {
    main: (
      <section className="target-center-stack">
        <article className="panel target-generic-panel">
          <div className="target-generic-copy">
            <span className="section-label">{page.eyebrow}</span>
            <h2>{page.title}</h2>
            <p>{page.description}</p>
          </div>

          <div className="target-generic-metrics">
            {page.metrics.map((metric) => (
              <InspectorMetricCard key={metric.label} {...metric} />
            ))}
          </div>

          <ActionNoticeCard label={page.eyebrow} title={page.title} notice={notice} />
        </article>
      </section>
    ),
    controlPanel: {
      eyebrow: page.focusLabel,
      title: page.focusTitle,
      content: (
        <article className="panel target-inspector">
          <div className="target-inspector-status">
            <span className="target-status-dot" />
            <span>{page.focusStatus}</span>
          </div>

          <div className="target-inspector-acres">{page.focusDetail}</div>

          <article className="target-note-card">
            <span className="target-note-label">{page.noteLabel}</span>
            <div className="target-note-body">{page.noteBody}</div>
            <div className="target-note-meta">{page.noteMeta}</div>
          </article>

        </article>
      ),
    },
  };
}
