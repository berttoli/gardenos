"use client";

import { useState } from "react";

import type { MetricItem } from "../shared";
import type { GardenServiceContext } from "../services/context";
import { getMapModel } from "../services/map-service";
import type { PageWorkspaceView } from "./registry";
import { ActionNoticeCard, Icon, useTimedNotice } from "../shared";
import {
  InspectorMetricCard,
  InspectorScoreCard,
  InspectorTab,
  MapControls,
  PriorityTaskRow,
  SegmentTab,
  PageCommandStrip,
} from "../shared";

function MapIllustration({ backgroundSrc }: { backgroundSrc: string }) {
  const zones = [
    { label: "North Field", status: "Good", dot: "#a9d37f", x: 190, y: 160 },
    { label: "Shade House", status: "Good", dot: "#a9d37f", x: 580, y: 132 },
    { label: "Display Garden", status: "Good", dot: "#a9d37f", x: 760, y: 262 },
    { label: "Propagation", status: "Fair", dot: "#f0bf47", x: 178, y: 320 },
    { label: "Container Yard", status: "Needs Attention", dot: "#ee8f35", x: 405, y: 380, selected: true },
    { label: "South Field", status: "Critical", dot: "#e06b39", x: 170, y: 535 },
    { label: "Native Area", status: "Good", dot: "#a9d37f", x: 610, y: 520 },
    { label: "Compost Area", status: "Good", dot: "#a9d37f", x: 885, y: 528 },
  ] as const;

  return (
    <svg
      aria-label="Property map with zone overlays"
      className="map-svg"
      role="img"
      viewBox="0 0 1160 680"
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        <radialGradient id="glow" cx="50%" cy="50%" r="60%">
          <stop offset="0%" stopColor="#fff4df" stopOpacity=".85" />
          <stop offset="100%" stopColor="#fff4df" stopOpacity="0" />
        </radialGradient>
        <filter id="lift" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="10" stdDeviation="10" floodColor="#9b8c73" floodOpacity=".14" />
        </filter>
      </defs>
      <image href={backgroundSrc} x="0" y="0" width="1160" height="680" preserveAspectRatio="xMidYMid slice" />
      <rect width="1160" height="680" rx="34" fill="#eadfcf" opacity=".16" />

      <path
        d="M88 125C148 86 244 83 319 135C389 182 388 269 324 314C254 363 152 352 101 295C56 247 50 167 88 125Z"
        fill="#d8e3cd"
        fillOpacity=".24"
        stroke="#abc5a0"
        strokeOpacity=".42"
        strokeWidth="5"
        strokeLinejoin="round"
        filter="url(#lift)"
      />
      <path
        d="M323 88C408 45 527 53 592 128C649 195 640 296 562 347C479 402 356 377 308 297C267 230 283 127 323 88Z"
        fill="#cdddc0"
        fillOpacity=".22"
        stroke="#8fb08a"
        strokeOpacity=".42"
        strokeWidth="5"
        strokeLinejoin="round"
        filter="url(#lift)"
      />
      <path
        d="M587 86C672 49 792 53 857 126C913 188 902 292 825 344C744 398 629 376 580 301C541 241 549 132 587 86Z"
        fill="#bed2ad"
        fillOpacity=".22"
        stroke="#8ea586"
        strokeOpacity=".42"
        strokeWidth="5"
        strokeLinejoin="round"
        filter="url(#lift)"
      />
      <path
        d="M828 90C911 53 1038 65 1089 142C1134 209 1118 306 1041 354C960 404 852 381 808 307C770 244 779 127 828 90Z"
        fill="#d6e4d4"
        fillOpacity=".22"
        stroke="#a8c1ac"
        strokeOpacity=".4"
        strokeWidth="5"
        strokeLinejoin="round"
        filter="url(#lift)"
      />

      <path
        d="M128 374C196 323 297 314 362 366C424 415 420 502 364 551C300 606 201 600 143 545C88 494 70 419 128 374Z"
        fill="#d8b56d"
        fillOpacity=".24"
        stroke="#d79a4c"
        strokeOpacity=".76"
        strokeWidth="6"
        strokeLinejoin="round"
        filter="url(#lift)"
      />
      <path
        d="M369 342C456 300 572 308 639 377C698 440 693 533 614 578C527 626 414 602 359 531C309 468 319 384 369 342Z"
        fill="#cfe0c3"
        fillOpacity=".22"
        stroke="#8cb18c"
        strokeOpacity=".44"
        strokeWidth="5"
        strokeLinejoin="round"
        filter="url(#lift)"
      />
      <path
        d="M648 343C725 309 834 313 895 381C950 441 944 537 867 580C786 622 679 604 629 531C586 470 594 383 648 343Z"
        fill="#e5c49a"
        fillOpacity=".24"
        stroke="#d99a60"
        strokeOpacity=".44"
        strokeWidth="5"
        strokeLinejoin="round"
        filter="url(#lift)"
      />
      <path
        d="M909 344C981 305 1087 320 1124 394C1155 457 1125 536 1042 578C950 624 844 596 799 529C761 472 779 389 909 344Z"
        fill="#cee0cf"
        fillOpacity=".22"
        stroke="#99ba99"
        strokeOpacity=".42"
        strokeWidth="5"
        strokeLinejoin="round"
        filter="url(#lift)"
      />

      <g opacity=".92">
        <circle cx="446" cy="334" r="56" fill="url(#glow)" />
        <path
          d="M446 297c13.2 0 24 10.7 24 23.8 0 20.2-24 43.8-24 43.8s-24-23.6-24-43.8c0-13.1 10.8-23.8 24-23.8Z"
          fill="#f7f5ef"
          stroke="#ee8f35"
          strokeWidth="2.2"
        />
        <circle cx="446" cy="323" r="8.5" fill="#6e8c72" />
        <path d="M441 321.5c1.8-1.8 4.8-3.5 8.7-4.2-1.1 4.5-3.4 7.7-7.1 9.4" stroke="#fff" strokeWidth="1.5" />
      </g>

      {zones.map((zone) => (
        <g key={zone.label} transform={`translate(${zone.x} ${zone.y})`}>
          <text
            x="0"
            y="0"
            fill="rgba(255, 251, 245, 0.98)"
            fontSize="18"
            fontWeight="700"
            letterSpacing="0.04em"
            stroke="rgba(26, 34, 28, 0.34)"
            strokeWidth="1.2"
            paintOrder="stroke"
            textAnchor="start"
          >
            {zone.label.toUpperCase()}
          </text>
          <circle cx="7" cy="18" r="4" fill={zone.dot} />
          <text
            x="19"
            y="22"
            fill="rgba(255, 251, 245, 0.88)"
            fontSize="12"
            fontWeight="600"
            letterSpacing="0.02em"
            stroke="rgba(26, 34, 28, 0.24)"
            strokeWidth="0.8"
            paintOrder="stroke"
            textAnchor="start"
          >
            {zone.status}
          </text>
          {"selected" in zone && zone.selected ? (
            <rect
              x="-18"
              y="-18"
              width="180"
              height="48"
              rx="18"
              fill="transparent"
              stroke="rgba(255, 181, 86, 0.9)"
              strokeWidth="2"
            />
          ) : null}
        </g>
      ))}
    </svg>
  );
}

function InspectorPreview() {
  return (
    <article className="target-inspector-preview">
      <div className="target-inspector-preview-photo" role="img" aria-label="Container Yard aerial preview">
        <div className="target-inspector-preview-badge">Live capture</div>
        <div className="target-inspector-preview-copy">
          <span className="section-label">Container Yard</span>
          <strong>Zone overview</strong>
          <span>2.3 acres, ready for assignment</span>
        </div>
      </div>
    </article>
  );
}

export function MapPage(context: GardenServiceContext | null = null): PageWorkspaceView {
  const { tabs, inspectorTabs, backgroundSrc, priorityTasks, inspectorMetrics, quickActions } = getMapModel(context);
  const [activeMapTabIndex, setActiveMapTabIndex] = useState(0);
  const [activeInspectorTabIndex, setActiveInspectorTabIndex] = useState(0);
  const [notice, setNotice] = useTimedNotice();
  const commandActions = quickActions.map((action) => ({
    ...action,
    onClick: () => {
      setNotice(`${action.label} opened for the selected zone.`);
    },
  }));

  return {
    main: (
      <section className="target-center-stack">
        <article className="panel target-map-panel">
          <div className="target-map-stage">
            <div className="target-map-tabs" aria-label="Map mode">
              {tabs.map((tab, index) => (
                <SegmentTab
                  key={tab}
                  label={tab}
                  active={index === activeMapTabIndex}
                  onClick={() => {
                    setActiveMapTabIndex(index);
                    setNotice(`${tab} map mode selected.`);
                  }}
                />
              ))}
            </div>

            <MapIllustration backgroundSrc={backgroundSrc} />
            <MapControls />
          </div>
        </article>

        <section className="panel target-tasks-panel">
          <div className="target-section-head">
            <div>
              <span className="section-label">Priority Tasks</span>
              <h3>
                Priority Tasks <span className="target-section-count">8</span>
              </h3>
            </div>

            <button
              className="target-view-all"
              type="button"
              onClick={() => {
                setNotice("Opened the full priority task list.");
              }}
            >
              <span>View all</span>
              <Icon name="chevron" />
            </button>
          </div>

          <div className="target-task-list">
            {priorityTasks.map((task) => (
              <PriorityTaskRow key={task.title} task={task} />
            ))}
          </div>

          <ActionNoticeCard label="Map update" title="Task list" notice={notice} />
        </section>
      </section>
    ),
    controlPanel: {
      eyebrow: "Map overview",
      title: "Container Yard",
      content: (
        <article className="panel target-inspector">
          <div className="target-inspector-status">
            <span className="target-status-dot" />
            <span>Needs Attention</span>
          </div>

          <div className="target-inspector-acres">2.3 acres</div>

          <div className="target-inspector-tabs" aria-label="Inspector sections">
            {inspectorTabs.map((tab, index) => (
              <InspectorTab
                key={tab}
                label={tab}
                active={index === activeInspectorTabIndex}
                onClick={() => {
                  setActiveInspectorTabIndex(index);
                  setNotice(`${tab} inspector section selected.`);
                }}
              />
            ))}
          </div>

          <div className="target-inspector-stack">
            <InspectorPreview />
            <InspectorScoreCard />

            <div className="target-inspector-metrics">
              {inspectorMetrics
                .filter((metric): metric is Extract<MetricItem, { kind: "metric" }> => metric.kind === "metric")
                .map((metric) => (
                  <InspectorMetricCard key={metric.label} {...metric} />
                ))}
            </div>

            <article className="target-inspector-callout">
              <div className="target-inspector-callout-head">
                <strong>Best irrigation window</strong>
                <span className="target-inspector-callout-badge">Good</span>
              </div>
              <span>Today 6:00 - 10:00 AM</span>
              <p>Low wind, moderate temps.</p>
            </article>

            <article className="target-note-card">
              <span className="target-note-label">Recent Notes</span>
              <div className="target-note-body">
                Hot spell increasing stress.
                <br />
                Watch new maples.
              </div>
              <div className="target-note-meta">- 2h ago by Jordan</div>
            </article>

            <PageCommandStrip
              actions={commandActions}
              align="left"
              eyebrow="Map overview"
              side="top"
              title="Zone actions"
              triggerIcon="map"
              triggerLabel="Actions"
            />
          </div>
        </article>
      ),
    },
  };
}
