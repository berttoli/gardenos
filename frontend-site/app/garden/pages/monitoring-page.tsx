"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { GardenServiceContext } from "../services/context";
import { fetchGardenApiJson, type GardenApiPath } from "../services/api-client";
import type {
  GardenPlatformAlert,
  GardenPlatformTelemetryEvent,
} from "../services/bootstrap-service";
import type { GardenPlatformEvent } from "../services/platform-events-service";
import {
  buildMonitoringStreamEntries,
  buildMonitoringStreamSummary,
  getMonitoringConsoleModel,
  type MonitoringConsoleModel,
  type MonitoringStreamStatus,
} from "../services/monitoring-service";
import type { PageWorkspaceView } from "./registry";
import { ActionButton, ActionNoticeCard, Chip, Icon, InspectorMetricCard, useTimedNotice, type ShellTone } from "../shared";
import {
  loadGardenPlatformEvents,
  subscribeGardenPlatformEvents,
} from "../services/platform-events-service";

type MonitoringLogEntry = MonitoringConsoleModel["loggingPanel"]["entries"][number];
type MonitoringTelemetryEntry = MonitoringConsoleModel["telemetryPanel"]["signals"][number];
type MonitoringServiceEntry = MonitoringConsoleModel["systemServicesPanel"]["services"][number];
type MonitoringIncidentEntry = MonitoringConsoleModel["monitoringPanel"]["incidents"][number];
type MonitoringAlertEntry = MonitoringConsoleModel["alertingPanel"]["alerts"][number];
type MonitoringPolicyEntry = MonitoringConsoleModel["alertingPanel"]["policies"][number];
type MonitoringChannelEntry = MonitoringConsoleModel["alertingPanel"]["channels"][number];
type MonitoringTimelinePoint = MonitoringConsoleModel["loggingPanel"]["timeline"][number];
type MonitoringModeSummary = MonitoringConsoleModel["modeSummaries"][number];

type MonitoringConsoleFocus =
  | { mode: "logging"; id: string }
  | { mode: "telemetry"; id: string }
  | { mode: "monitoring"; kind: "service" | "incident"; id: string }
  | { mode: "alerting"; kind: "alert" | "policy" | "channel" | "incident"; id: string };

type MonitoringCollections = {
  loggingEntries: MonitoringLogEntry[];
  telemetryEntries: MonitoringTelemetryEntry[];
  monitoringServices: MonitoringServiceEntry[];
  monitoringIncidents: MonitoringIncidentEntry[];
  alertEntries: MonitoringAlertEntry[];
  policyEntries: MonitoringPolicyEntry[];
  channelEntries: MonitoringChannelEntry[];
  alertIncidents: MonitoringIncidentEntry[];
};

function titleCaseWords(value: string): string {
  return value
    .trim()
    .replace(/[_-]+/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatElapsed(timestamp: string): string {
  const then = new Date(timestamp).getTime();
  const now = Date.now();
  const deltaSeconds = Math.max(0, Math.round((now - then) / 1000));

  if (deltaSeconds < 60) {
    return `${deltaSeconds}s ago`;
  }

  const deltaMinutes = Math.round(deltaSeconds / 60);
  if (deltaMinutes < 60) {
    return `${deltaMinutes}m ago`;
  }

  const deltaHours = Math.round(deltaMinutes / 60);
  return `${deltaHours}h ago`;
}

function normalizeQuery(value: string): string {
  return value.trim().toLowerCase();
}

function includesQuery(values: Array<string | null | undefined>, query: string): boolean {
  if (!query) {
    return true;
  }

  return values.some((value) => value?.toLowerCase().includes(query));
}

function monitoringSourceLabel(context: GardenServiceContext | null): string {
  return context?.source === "backend" ? "Backend bootstrap" : "Fallback shell";
}

function alertToneForStatus(status: string, severity: string): ShellTone {
  if (status === "resolved") {
    return "forest";
  }

  if (status === "acknowledged") {
    return "sky";
  }

  if (status === "muted") {
    return "sage";
  }

  if (severity === "critical" || severity === "high") {
    return "amber";
  }

  if (severity === "warning") {
    return "amber";
  }

  return "sage";
}

function buildModeTabs(model: MonitoringConsoleModel): MonitoringModeSummary[] {
  return model.modeSummaries;
}

function getDefaultFocus(mode: MonitoringConsoleFocus["mode"], collections: MonitoringCollections): MonitoringConsoleFocus | null {
  if (mode === "logging") {
    return collections.loggingEntries[0] ? { mode: "logging", id: collections.loggingEntries[0].id } : null;
  }

  if (mode === "telemetry") {
    return collections.telemetryEntries[0] ? { mode: "telemetry", id: collections.telemetryEntries[0].id } : null;
  }

  if (mode === "monitoring") {
    if (collections.monitoringServices[0]) {
      return { mode: "monitoring", kind: "service", id: collections.monitoringServices[0].key };
    }

    if (collections.monitoringIncidents[0]) {
      return { mode: "monitoring", kind: "incident", id: collections.monitoringIncidents[0].id };
    }

    return null;
  }

  if (collections.alertEntries[0]) {
    return { mode: "alerting", kind: "alert", id: collections.alertEntries[0].id };
  }

  if (collections.policyEntries[0]) {
    return { mode: "alerting", kind: "policy", id: collections.policyEntries[0].id };
  }

  if (collections.channelEntries[0]) {
    return { mode: "alerting", kind: "channel", id: collections.channelEntries[0].id };
  }

  if (collections.alertIncidents[0]) {
    return { mode: "alerting", kind: "incident", id: collections.alertIncidents[0].id };
  }

  return null;
}

function resolveFocus(
  mode: MonitoringConsoleFocus["mode"],
  focus: MonitoringConsoleFocus | null,
  collections: MonitoringCollections,
): MonitoringConsoleFocus | null {
  if (!focus || focus.mode !== mode) {
    return getDefaultFocus(mode, collections);
  }

  switch (focus.mode) {
    case "logging":
      return collections.loggingEntries.some((entry) => entry.id === focus.id) ? focus : getDefaultFocus(mode, collections);
    case "telemetry":
      return collections.telemetryEntries.some((entry) => entry.id === focus.id) ? focus : getDefaultFocus(mode, collections);
    case "monitoring":
      if (focus.kind === "service") {
        return collections.monitoringServices.some((entry) => entry.key === focus.id) ? focus : getDefaultFocus(mode, collections);
      }
      return collections.monitoringIncidents.some((entry) => entry.id === focus.id) ? focus : getDefaultFocus(mode, collections);
    case "alerting":
      if (focus.kind === "alert") {
        return collections.alertEntries.some((entry) => entry.id === focus.id) ? focus : getDefaultFocus(mode, collections);
      }
      if (focus.kind === "policy") {
        return collections.policyEntries.some((entry) => entry.id === focus.id) ? focus : getDefaultFocus(mode, collections);
      }
      if (focus.kind === "channel") {
        return collections.channelEntries.some((entry) => entry.id === focus.id) ? focus : getDefaultFocus(mode, collections);
      }
      return collections.alertIncidents.some((entry) => entry.id === focus.id) ? focus : getDefaultFocus(mode, collections);
  }
}

function buildAlertSearchText(entry: MonitoringAlertEntry): string {
  return [
    entry.title,
    entry.detail,
    entry.meta,
    entry.source,
    entry.severity,
    entry.eventType,
    entry.payloadSummary,
    entry.status,
    entry.policyLabel,
    entry.scopeLabel,
  ]
    .filter(Boolean)
    .join(" ");
}

function buildPolicySearchText(entry: MonitoringPolicyEntry): string {
  return [entry.title, entry.detail, entry.meta, entry.status, entry.rule, entry.severity, entry.source].filter(Boolean).join(" ");
}

function buildChannelSearchText(entry: MonitoringChannelEntry): string {
  return [entry.title, entry.detail, entry.meta, entry.status, entry.source, entry.connectorKind].filter(Boolean).join(" ");
}

function buildIncidentSearchText(entry: MonitoringIncidentEntry): string {
  return [entry.title, entry.detail, entry.meta, entry.status, entry.policyLabel, entry.scopeLabel, entry.severity].filter(Boolean).join(" ");
}

function MonitoringModeCard({
  summary,
  active,
  onSelect,
}: {
  summary: MonitoringModeSummary;
  active?: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      className="target-monitoring-mode-card"
      data-active={active ? "true" : "false"}
      data-tone={summary.tone}
      type="button"
      aria-pressed={active ? "true" : "false"}
      onClick={onSelect}
    >
      <div className="target-monitoring-mode-card-head">
        <span className="target-monitoring-mode-card-icon" data-tone={summary.tone}>
          <Icon name={summary.icon} />
        </span>
        <Chip icon={summary.icon} tone={summary.tone} ariaLabel={`${summary.label} count`} title={summary.title}>
          {summary.count}
        </Chip>
      </div>

      <div className="target-monitoring-mode-card-copy">
        <strong>{summary.label}</strong>
        <span>{summary.title}</span>
        <small>{summary.detail}</small>
      </div>

      <div className="target-monitoring-mode-card-status">{summary.status}</div>
    </button>
  );
}

function MonitoringRow({
  icon,
  tone,
  title,
  detail,
  meta,
  status,
  active,
  onSelect,
}: {
  icon: Parameters<typeof Icon>[0]["name"];
  tone: ShellTone;
  title: string;
  detail: string;
  meta: string;
  status?: string;
  active?: boolean;
  onSelect?: () => void;
}) {
  const content = (
    <>
      <span className="target-monitoring-row-icon" data-tone={tone}>
        <Icon name={icon} />
      </span>

      <span className="target-monitoring-row-copy">
        <strong>{title}</strong>
        <span>{detail}</span>
      </span>

      {status ? (
        <span className="target-monitoring-row-status">
          <Chip tone={tone} title={status} ariaLabel={status}>
            {status}
          </Chip>
        </span>
      ) : null}

      <span className="target-monitoring-row-meta">{meta}</span>

      <Icon name="chevron" className="target-monitoring-row-chevron" />
    </>
  );

  if (onSelect) {
    return (
      <button
        className="target-monitoring-row"
        data-tone={tone}
        data-selected={active ? "true" : "false"}
        type="button"
        aria-pressed={active ? "true" : "false"}
        onClick={onSelect}
      >
        {content}
      </button>
    );
  }

  return (
    <article className="target-monitoring-row" data-tone={tone} data-selected={active ? "true" : "false"}>
      {content}
    </article>
  );
}

function MonitoringTimeline({ points }: { points: MonitoringTimelinePoint[] }) {
  const maxValue = Math.max(...points.map((point) => point.value), 1);

  return (
    <div className="target-monitoring-timeline" aria-label="Timeline">
      {points.map((point) => {
        const barHeight = Math.max(12, Math.round((point.value / maxValue) * 100));

        return (
          <div key={point.label} className="target-monitoring-timeline-point" data-tone={point.tone}>
            <span className="target-monitoring-timeline-label">{point.label}</span>
            <div className="target-monitoring-timeline-track" aria-hidden="true">
              <span style={{ height: `${barHeight}%` }} />
            </div>
            <strong>{point.detail}</strong>
            <span>{point.meta}</span>
          </div>
        );
      })}
    </div>
  );
}

function MonitoringDetailCard({
  label,
  title,
  detail,
  icon,
  tone,
  status,
  meta,
  lines,
  children,
}: {
  label: string;
  title: string;
  detail: string;
  icon: Parameters<typeof Icon>[0]["name"];
  tone: ShellTone;
  status?: string;
  meta?: string;
  lines: Array<{ label: string; value: string }>;
  children?: ReactNode;
}) {
  return (
    <article className="target-monitoring-detail-card" data-tone={tone}>
      <span className="target-note-label">{label}</span>

      <div className="target-monitoring-detail-head">
        <span className="target-monitoring-detail-icon" data-tone={tone}>
          <Icon name={icon} />
        </span>

        <div className="target-monitoring-detail-copy">
          <strong>{title}</strong>
          <span>{detail}</span>
        </div>

        {status ? (
          <Chip tone={tone} title={status} ariaLabel={status}>
            {status}
          </Chip>
        ) : null}
      </div>

      <div className="target-monitoring-detail-lines">
        {lines.map((line) => (
          <div key={line.label} className="target-monitoring-detail-line">
            <span>{line.label}</span>
            <strong>{line.value}</strong>
          </div>
        ))}
      </div>

      {children ? <div className="target-monitoring-detail-body">{children}</div> : null}
      {meta ? <div className="target-monitoring-detail-meta">{meta}</div> : null}
    </article>
  );
}

function getAlertId(entryId: string): string {
  return entryId.replace(/^alert:/, "");
}

function getTelemetryId(entryId: string): string {
  return entryId.replace(/^telemetry:/, "");
}

function getAlertShowPath(alertId: string): GardenApiPath {
  return `/platform/alerts/${encodeURIComponent(alertId)}` as GardenApiPath;
}

function getAlertActionPath(alertId: string, action: "acknowledge" | "resolve" | "mute" | "unmute"): GardenApiPath {
  return `/platform/alerts/${encodeURIComponent(alertId)}/${action}` as GardenApiPath;
}

function getTelemetryShowPath(telemetryEventId: string): GardenApiPath {
  return `/platform/telemetry/${encodeURIComponent(telemetryEventId)}` as GardenApiPath;
}

function payloadString(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];

  if (typeof value !== "string") {
    return null;
  }

  const text = value.trim();
  return text ? text : null;
}

function payloadSummary(payload: Record<string, unknown>): string | null {
  return (
    payloadString(payload, "summary")
    ?? payloadString(payload, "title")
    ?? payloadString(payload, "message")
    ?? payloadString(payload, "detail")
    ?? payloadString(payload, "reason")
  );
}

export function MonitoringPage(context: GardenServiceContext | null = null): PageWorkspaceView {
  const model = useMemo(() => getMonitoringConsoleModel(context), [context]);
  const [activeMode, setActiveMode] = useState<MonitoringModeSummary["id"]>("monitoring");
  const [query, setQuery] = useState("");
  const [focus, setFocus] = useState<MonitoringConsoleFocus | null>(null);
  const [notice, setNotice] = useTimedNotice();
  const [liveEvents, setLiveEvents] = useState<GardenPlatformEvent[]>([]);
  const [streamStatus, setStreamStatus] = useState<MonitoringStreamStatus>(context?.source === "backend" ? "connecting" : "offline");
  const [selectedTelemetryDetail, setSelectedTelemetryDetail] = useState<GardenPlatformTelemetryEvent | null>(null);
  const [selectedAlertDetail, setSelectedAlertDetail] = useState<GardenPlatformAlert | null>(null);
  const [alertSnapshots, setAlertSnapshots] = useState<Record<string, GardenPlatformAlert>>({});

  useEffect(() => {
    let cancelled = false;

    if (context?.source !== "backend") {
      setLiveEvents([]);
      setStreamStatus("offline");
      return () => {
        cancelled = true;
      };
    }

    setStreamStatus("connecting");

    void loadGardenPlatformEvents({ limit: 12 })
      .then((events) => {
        if (cancelled) {
          return;
        }

        setLiveEvents(events);
        setStreamStatus("live");
      })
      .catch(() => {
        if (cancelled) {
          return;
        }

        setLiveEvents([]);
        setStreamStatus("degraded");
      });

    const source = subscribeGardenPlatformEvents(
      (event) => {
        setLiveEvents((current) => [event, ...current.filter((item) => item.id !== event.id)].slice(0, 12));
        setStreamStatus("live");
      },
      () => {
        if (!cancelled) {
          setStreamStatus("degraded");
        }
      },
      { limit: 12 },
    );

    return () => {
      cancelled = true;
      source?.close();
    };
  }, [context?.source]);

  const normalizedQuery = normalizeQuery(query);
  const sourceLabel = monitoringSourceLabel(context);
  const streamSummary = useMemo(() => buildMonitoringStreamSummary(streamStatus, liveEvents), [streamStatus, liveEvents]);
  const liveFeedEntries = useMemo(() => buildMonitoringStreamEntries(liveEvents, 4), [liveEvents]);
  const modeSummaries = buildModeTabs(model);
  const activePanel =
    activeMode === "logging"
      ? model.loggingPanel
      : activeMode === "telemetry"
        ? model.telemetryPanel
        : activeMode === "monitoring"
          ? model.monitoringPanel
          : model.alertingPanel;

  const loggingEntries = useMemo(
    () =>
      model.loggingPanel.entries.filter((entry) =>
        includesQuery([entry.title, entry.detail, entry.meta, entry.source, entry.severity, entry.eventType, entry.payloadSummary, entry.status], normalizedQuery),
      ),
    [model.loggingPanel.entries, normalizedQuery],
  );

  const telemetryEntries = useMemo(
    () =>
      model.telemetryPanel.signals.filter((entry) =>
        includesQuery([entry.title, entry.detail, entry.meta, entry.source, entry.severity, entry.eventType, entry.payloadSummary, entry.traceId, entry.correlationId], normalizedQuery),
      ),
    [model.telemetryPanel.signals, normalizedQuery],
  );

  const monitoringServices = useMemo(
    () => model.systemServicesPanel.services.filter((entry) => includesQuery([entry.label, entry.detail, entry.status, entry.statusLabel, entry.endpoint, entry.lastChecked], normalizedQuery)),
    [model.systemServicesPanel.services, normalizedQuery],
  );

  const monitoringIncidents = useMemo(
    () => model.monitoringPanel.incidents.filter((entry) => buildAlertSearchText(entry) && includesQuery([buildAlertSearchText(entry)], normalizedQuery)),
    [model.monitoringPanel.incidents, normalizedQuery],
  );

  const alertEntries = useMemo(
    () =>
      model.alertingPanel.alerts
        .map((entry) => {
          const snapshot = alertSnapshots[getAlertId(entry.id)] ?? null;
          if (!snapshot) {
            return entry;
          }

          const statusLabel = titleCaseWords(snapshot.status);
          return {
            ...entry,
            tone: alertToneForStatus(snapshot.status, entry.severity),
            status: snapshot.status,
            meta: entry.meta.replace(/(Open|Acknowledged|Resolved|Muted)$/i, statusLabel),
            detail: entry.detail.replace(/(Open|Acknowledged|Resolved|Muted)$/i, statusLabel),
            openedAt: snapshot.opened_at,
            acknowledgedAt: snapshot.acknowledged_at,
            resolvedAt: snapshot.resolved_at,
          };
        })
        .filter((entry) => includesQuery([buildAlertSearchText(entry)], normalizedQuery)),
    [alertSnapshots, model.alertingPanel.alerts, normalizedQuery],
  );

  const policyEntries = useMemo(
    () => model.alertingPanel.policies.filter((entry) => includesQuery([buildPolicySearchText(entry)], normalizedQuery)),
    [model.alertingPanel.policies, normalizedQuery],
  );

  const channelEntries = useMemo(
    () => model.alertingPanel.channels.filter((entry) => includesQuery([buildChannelSearchText(entry)], normalizedQuery)),
    [model.alertingPanel.channels, normalizedQuery],
  );

  const alertIncidents = useMemo(
    () => model.alertingPanel.incidents.filter((entry) => includesQuery([buildIncidentSearchText(entry)], normalizedQuery)),
    [model.alertingPanel.incidents, normalizedQuery],
  );

  const collections: MonitoringCollections = {
    loggingEntries,
    telemetryEntries,
    monitoringServices,
    monitoringIncidents,
    alertEntries,
    policyEntries,
    channelEntries,
    alertIncidents,
  };

  const selectedFocus = resolveFocus(activeMode, focus, collections);
  const activeSummary = modeSummaries.find((summary) => summary.id === activeMode) ?? modeSummaries[0];
  const selectedLoggingEntry = selectedFocus?.mode === "logging" ? loggingEntries.find((entry) => entry.id === selectedFocus.id) ?? null : null;
  const selectedTelemetryEntry =
    selectedFocus?.mode === "telemetry" ? telemetryEntries.find((entry) => entry.id === selectedFocus.id) ?? null : null;
  const selectedMonitoringService =
    selectedFocus?.mode === "monitoring" && selectedFocus.kind === "service"
      ? monitoringServices.find((entry) => entry.key === selectedFocus.id) ?? null
      : null;
  const selectedMonitoringIncident =
    selectedFocus?.mode === "monitoring" && selectedFocus.kind === "incident"
      ? monitoringIncidents.find((entry) => entry.id === selectedFocus.id) ?? null
      : null;
  const selectedAlertEntry =
    selectedFocus?.mode === "alerting" && selectedFocus.kind === "alert" ? alertEntries.find((entry) => entry.id === selectedFocus.id) ?? null : null;
  const selectedPolicyEntry =
    selectedFocus?.mode === "alerting" && selectedFocus.kind === "policy" ? policyEntries.find((entry) => entry.id === selectedFocus.id) ?? null : null;
  const selectedChannelEntry =
    selectedFocus?.mode === "alerting" && selectedFocus.kind === "channel" ? channelEntries.find((entry) => entry.id === selectedFocus.id) ?? null : null;
  const selectedAlertIncident =
    selectedFocus?.mode === "alerting" && selectedFocus.kind === "incident"
      ? alertIncidents.find((entry) => entry.id === selectedFocus.id) ?? null
      : null;
  const selectedTelemetryId = selectedTelemetryEntry ? getTelemetryId(selectedTelemetryEntry.id) : null;
  const selectedAlertId = selectedAlertEntry ? getAlertId(selectedAlertEntry.id) : null;
  const selectedTelemetryPayload = selectedTelemetryDetail?.payload ?? null;
  const selectedTelemetryPayloadSummary = selectedTelemetryPayload ? payloadSummary(selectedTelemetryPayload) : null;
  const selectedTelemetryPayloadMessage = selectedTelemetryPayload ? payloadString(selectedTelemetryPayload, "message") : null;
  const selectedTelemetryTraceId = selectedTelemetryPayload
    ? payloadString(selectedTelemetryPayload, "trace_id") ?? payloadString(selectedTelemetryPayload, "traceId")
    : null;
  const selectedTelemetryCorrelationId = selectedTelemetryPayload
    ? payloadString(selectedTelemetryPayload, "correlation_id") ?? payloadString(selectedTelemetryPayload, "correlationId")
    : null;

  useEffect(() => {
    let cancelled = false;

    if (context?.source !== "backend" || !selectedTelemetryId) {
      setSelectedTelemetryDetail(null);
      return () => {
        cancelled = true;
      };
    }

    void fetchGardenApiJson<GardenPlatformTelemetryEvent>(getTelemetryShowPath(selectedTelemetryId))
      .then((record) => {
        if (!cancelled) {
          setSelectedTelemetryDetail(record);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSelectedTelemetryDetail(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [context?.source, selectedTelemetryId]);

  useEffect(() => {
    let cancelled = false;

    if (context?.source !== "backend" || !selectedAlertId) {
      setSelectedAlertDetail(null);
      return () => {
        cancelled = true;
      };
    }

    void fetchGardenApiJson<GardenPlatformAlert>(getAlertShowPath(selectedAlertId))
      .then((record) => {
        if (cancelled) {
          return;
        }

        setSelectedAlertDetail(record);
        setAlertSnapshots((current) => ({ ...current, [record.id]: record }));
      })
      .catch(() => {
        if (!cancelled) {
          setSelectedAlertDetail(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [context?.source, selectedAlertId]);

  const handleModeChange = (mode: MonitoringConsoleFocus["mode"]) => {
    setActiveMode(mode);
    const summary = modeSummaries.find((item) => item.id === mode);
    if (summary) {
      setNotice(`Focused ${summary.label}.`);
    }
  };

  const handleAlertMutation = async (action: "acknowledge" | "resolve" | "mute" | "unmute") => {
    if (!selectedAlertEntry) {
      setNotice("Select an alert first.");
      return;
    }

    if (context?.source !== "backend") {
      setNotice("Alert actions need a live backend connection.");
      return;
    }

    try {
      const response = await fetchGardenApiJson<{ alert: GardenPlatformAlert }>(getAlertActionPath(selectedAlertId ?? getAlertId(selectedAlertEntry.id), action), {
        method: "POST",
      });
      setAlertSnapshots((current) => ({ ...current, [response.alert.id]: response.alert }));
      setSelectedAlertDetail(response.alert);
      setNotice(`Alert ${titleCaseWords(action)}d.`);
    } catch {
      setNotice(`Unable to ${action} the selected alert.`);
    }
  };

  const showActionNotice = (message: string) => {
    setNotice(message);
  };

  const main = (
    <section className="target-center-stack target-monitoring-console" aria-label="Monitoring workspace">
      <article className="panel target-monitoring-shell">
        <div className="target-monitoring-head">
          <div className="target-monitoring-head-copy">
            <span className="section-label">Observability</span>
            <h2>Monitoring console</h2>
            <p>{activePanel.detail}</p>
          </div>

          <div className="target-monitoring-head-meta">
            <Chip icon={streamSummary.icon} tone={streamSummary.tone} title={streamSummary.title} ariaLabel={streamSummary.title}>
              {streamSummary.label}
            </Chip>
            <Chip
              icon={context?.source === "backend" ? "people" : "offline"}
              tone={context?.source === "backend" ? "forest" : "amber"}
              title={sourceLabel}
              ariaLabel={sourceLabel}
            >
              {sourceLabel}
            </Chip>
            <Chip icon="health" tone="forest" title={model.systemServicesPanel.status} ariaLabel={model.systemServicesPanel.status}>
              {model.systemServicesPanel.status}
            </Chip>
          </div>
        </div>

        <div className="target-monitoring-toolbar">
          <label className="target-monitoring-search" aria-label="Search monitoring surfaces">
            <Icon name="search" className="target-monitoring-search-icon" />
            <input
              value={query}
              placeholder={
                activeMode === "logging"
                  ? "Search logs, traces, event types, and sources"
                  : activeMode === "telemetry"
                    ? "Search signals, traces, and metrics"
                    : activeMode === "monitoring"
                      ? "Search services, incidents, and diagnostics"
                      : "Search alerts, policies, channels, and incidents"
              }
              type="search"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>

          <div className="target-monitoring-toolbar-chips">
            <Chip icon="queue" tone="sage" title={`${liveEvents.length} live events`}>
              {liveEvents.length} live
            </Chip>
            <Chip icon="layers" tone="forest" title={`${model.modeSummaries.length} console modes`}>
              {model.modeSummaries.length} modes
            </Chip>
          </div>
        </div>

        <ActionNoticeCard label="Console update" title="Selection changed" notice={notice} />

        <div className="target-monitoring-layout">
          <aside className="target-monitoring-rail" aria-label="Monitoring navigation">
            <section className="target-monitoring-rail-card">
              <span className="section-label">Primary sections</span>
              <div className="target-monitoring-mode-list">
                {modeSummaries.map((summary) => (
                  <MonitoringModeCard
                    key={summary.id}
                    summary={summary}
                    active={summary.id === activeMode}
                    onSelect={() => handleModeChange(summary.id)}
                  />
                ))}
              </div>
            </section>

            <section className="target-monitoring-rail-card">
              <span className="section-label">Active summary</span>
              <div className="target-monitoring-rail-metrics">
                {activePanel.metrics.map((metric) => (
                  <InspectorMetricCard key={metric.label} {...metric} />
                ))}
              </div>
            </section>

            <section className="target-monitoring-rail-card">
              <span className="section-label">Live relay</span>
              <article className="target-monitoring-stream-card" data-tone={streamSummary.tone}>
                <div className="target-monitoring-stream-head">
                  <span className="target-monitoring-stream-icon">
                    <Icon name={streamSummary.icon} />
                  </span>
                  <div className="target-monitoring-stream-copy">
                    <strong>{streamSummary.title}</strong>
                    <span>{streamSummary.detail}</span>
                  </div>
                  <Chip tone={streamSummary.tone} title={streamSummary.label} ariaLabel={streamSummary.label}>
                    {streamSummary.label}
                  </Chip>
                </div>
                <div className="target-monitoring-stream-meta">{streamSummary.meta}</div>
              </article>

              <div className="target-monitoring-live-feed">
                {liveFeedEntries.map((entry, index) => (
                  <MonitoringRow
                    key={`${entry.title}-${index}`}
                    icon={entry.icon}
                    tone={entry.tone}
                    title={entry.title}
                    detail={entry.detail}
                    meta={entry.meta}
                  />
                ))}
              </div>
            </section>
          </aside>

          <div className="target-monitoring-workspace">
            {activeMode === "logging" ? (
              <article className="target-monitoring-panel">
                <div className="target-monitoring-panel-head">
                  <div className="target-monitoring-panel-copy">
                    <span className="section-label">{model.loggingPanel.tabLabel}</span>
                    <h3>{model.loggingPanel.title}</h3>
                    <p>{model.loggingPanel.detail}</p>
                  </div>

                  <div className="target-monitoring-action-row">
                    {model.loggingPanel.actions.map((action) => (
                      <ActionButton
                        key={action.label}
                        icon={action.icon ?? "spark"}
                        label={action.label}
                        primary={action.primary}
                        onClick={() => showActionNotice(`${action.label} queued.`)}
                      />
                    ))}
                  </div>
                </div>

                <article className="target-monitoring-callout target-note-card">
                  <span className="target-note-label">{model.loggingPanel.calloutLabel}</span>
                  <div className="target-note-body">
                    <strong>{model.loggingPanel.calloutTitle}</strong>
                    <span>{model.loggingPanel.calloutBody}</span>
                  </div>
                  <div className="target-note-meta">{model.loggingPanel.calloutMeta}</div>
                </article>

                <div className="target-monitoring-logging-grid">
                  <section className="target-monitoring-pane target-monitoring-query-pane">
                    <div className="target-monitoring-pane-head">
                      <div>
                        <span className="section-label">{model.loggingPanel.queryLabel}</span>
                        <h4>Query pane</h4>
                        <p>{model.loggingPanel.queryPlaceholder}</p>
                      </div>
                    </div>

                    <div className="target-monitoring-saved-query-list" aria-label="Saved queries">
                      {model.loggingPanel.savedQueries.map((savedQuery) => (
                        <article key={savedQuery.id} className="target-monitoring-saved-query" data-tone={savedQuery.tone}>
                          <span className="target-monitoring-saved-query-icon">
                            <Icon name={savedQuery.icon} />
                          </span>
                          <div className="target-monitoring-saved-query-copy">
                            <strong>{savedQuery.label}</strong>
                            <span>{savedQuery.query || "All rows"}</span>
                            <small>{savedQuery.detail}</small>
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>

                  <section className="target-monitoring-pane target-monitoring-fields-pane">
                    <div className="target-monitoring-pane-head">
                      <div>
                        <span className="section-label">Fields</span>
                        <h4>Metadata filter</h4>
                        <p>Focus the stream by source, severity, and trace context.</p>
                      </div>
                    </div>

                    <div className="target-monitoring-fields-list">
                      {model.loggingPanel.fields.map((field) => (
                        <article key={field.id} className="target-monitoring-field-card" data-tone={field.tone}>
                          <span className="target-monitoring-field-icon">
                            <Icon name={field.icon} />
                          </span>
                          <div className="target-monitoring-field-copy">
                            <strong>{field.label}</strong>
                            <span>{field.value}</span>
                            <small>{field.detail}</small>
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>

                  <section className="target-monitoring-pane target-monitoring-results-pane">
                    <div className="target-monitoring-pane-head">
                      <div>
                        <span className="section-label">Timeline</span>
                        <h4>Query results</h4>
                        <p>{loggingEntries.length} matching rows in the active view.</p>
                      </div>
                    </div>

                    <MonitoringTimeline points={model.loggingPanel.timeline} />

                    <div className="target-monitoring-results-list" aria-label="Logging results">
                      {loggingEntries.map((entry) => (
                        <MonitoringRow
                          key={entry.id}
                          icon={entry.icon}
                          tone={entry.tone}
                          title={entry.title}
                          detail={entry.detail}
                          meta={entry.meta}
                          status={entry.status}
                          active={selectedLoggingEntry?.id === entry.id}
                          onSelect={() => setFocus({ mode: "logging", id: entry.id })}
                        />
                      ))}
                    </div>
                  </section>
                </div>
              </article>
            ) : null}

            {activeMode === "telemetry" ? (
              <article className="target-monitoring-panel">
                <div className="target-monitoring-panel-head">
                  <div className="target-monitoring-panel-copy">
                    <span className="section-label">{model.telemetryPanel.tabLabel}</span>
                    <h3>{model.telemetryPanel.title}</h3>
                    <p>{model.telemetryPanel.detail}</p>
                  </div>

                  <div className="target-monitoring-action-row">
                    {model.telemetryPanel.actions.map((action) => (
                      <ActionButton
                        key={action.label}
                        icon={action.icon ?? "spark"}
                        label={action.label}
                        primary={action.primary}
                        onClick={() => showActionNotice(`${action.label} queued.`)}
                      />
                    ))}
                  </div>
                </div>

                <article className="target-monitoring-callout target-note-card">
                  <span className="target-note-label">{model.telemetryPanel.calloutLabel}</span>
                  <div className="target-note-body">
                    <strong>{model.telemetryPanel.calloutTitle}</strong>
                    <span>{model.telemetryPanel.calloutBody}</span>
                  </div>
                  <div className="target-note-meta">{model.telemetryPanel.calloutMeta}</div>
                </article>

                <div className="target-monitoring-metric-grid">
                  {model.telemetryPanel.metrics.map((metric) => (
                    <InspectorMetricCard key={metric.label} {...metric} />
                  ))}
                </div>

                <div className="target-monitoring-telemetry-grid">
                  <section className="target-monitoring-pane target-monitoring-chart-pane">
                    <div className="target-monitoring-pane-head">
                      <div>
                        <span className="section-label">Metrics Explorer</span>
                        <h4>Telemetry timeline</h4>
                        <p>Chart-like summaries and signal drift across the current platform state.</p>
                      </div>
                    </div>

                    <MonitoringTimeline points={model.telemetryPanel.timeline} />

                    <div className="target-monitoring-correlation-card">
                      <span className="section-label">Correlation</span>
                      <div className="target-monitoring-correlation-copy">
                        <strong>{selectedTelemetryDetail?.source_kind ?? selectedTelemetryEntry?.source ?? "Telemetry signals"}</strong>
                        <span>
                          {selectedTelemetryDetail
                            ? `${selectedTelemetryDetail.event_kind} · ${selectedTelemetryDetail.severity} · ${selectedTelemetryTraceId ? "trace linked" : "no trace"}`
                            : "Select a signal to inspect the current payload and trace context."}
                        </span>
                      </div>
                    </div>
                  </section>

                  <section className="target-monitoring-pane target-monitoring-signals-pane">
                    <div className="target-monitoring-pane-head">
                      <div>
                        <span className="section-label">Signals</span>
                        <h4>Trace explorer</h4>
                        <p>{telemetryEntries.length} signals in the active selection.</p>
                      </div>
                    </div>

                    <div className="target-monitoring-results-list" aria-label="Telemetry signals">
                      {telemetryEntries.map((entry) => (
                        <MonitoringRow
                          key={entry.id}
                          icon={entry.icon}
                          tone={entry.tone}
                          title={entry.title}
                          detail={entry.detail}
                          meta={entry.meta}
                          status={entry.severity}
                          active={selectedTelemetryEntry?.id === entry.id}
                          onSelect={() => setFocus({ mode: "telemetry", id: entry.id })}
                        />
                      ))}
                    </div>
                  </section>
                </div>
              </article>
            ) : null}

            {activeMode === "monitoring" ? (
              <article className="target-monitoring-panel">
                <div className="target-monitoring-panel-head">
                  <div className="target-monitoring-panel-copy">
                    <span className="section-label">{model.monitoringPanel.tabLabel}</span>
                    <h3>{model.monitoringPanel.title}</h3>
                    <p>{model.monitoringPanel.detail}</p>
                  </div>

                  <div className="target-monitoring-action-row">
                    {model.monitoringPanel.actions.map((action) => (
                      <ActionButton
                        key={action.label}
                        icon={action.icon ?? "spark"}
                        label={action.label}
                        primary={action.primary}
                        onClick={() => showActionNotice(`${action.label} queued.`)}
                      />
                    ))}
                  </div>
                </div>

                <article className="target-monitoring-callout target-note-card">
                  <span className="target-note-label">{model.monitoringPanel.calloutLabel}</span>
                  <div className="target-note-body">
                    <strong>{model.monitoringPanel.calloutTitle}</strong>
                    <span>{model.monitoringPanel.calloutBody}</span>
                  </div>
                  <div className="target-note-meta">{model.monitoringPanel.calloutMeta}</div>
                </article>

                <div className="target-monitoring-metric-grid">
                  {model.monitoringPanel.metrics.map((metric) => (
                    <InspectorMetricCard key={metric.label} {...metric} />
                  ))}
                </div>

                <div className="target-monitoring-monitoring-grid">
                  <section className="target-monitoring-pane target-monitoring-diagnostics-pane">
                    <div className="target-monitoring-pane-head">
                      <div>
                        <span className="section-label">System services</span>
                        <h4>Shared diagnostics</h4>
                        <p>Postgres, API, platform catalog, telemetry, and event stream stay visible here as secondary diagnostics.</p>
                      </div>
                    </div>

                    <div className="target-monitoring-service-grid">
                      {monitoringServices.map((service) => (
                        <MonitoringRow
                          key={service.key}
                          icon={service.icon}
                          tone={service.tone}
                          title={service.label}
                          detail={service.detail}
                          meta={service.endpoint ?? service.lastChecked}
                          status={service.statusLabel}
                          active={selectedMonitoringService?.key === service.key}
                          onSelect={() => setFocus({ mode: "monitoring", kind: "service", id: service.key })}
                        />
                      ))}
                    </div>
                  </section>

                  <section className="target-monitoring-pane target-monitoring-incidents-pane">
                    <div className="target-monitoring-pane-head">
                      <div>
                        <span className="section-label">Incidents</span>
                        <h4>Monitoring alerts</h4>
                        <p>{monitoringIncidents.length} incident rows are visible in the active scope.</p>
                      </div>
                    </div>

                    <div className="target-monitoring-results-list" aria-label="Monitoring incidents">
                      {monitoringIncidents.map((entry) => (
                        <MonitoringRow
                          key={entry.id}
                          icon={entry.icon}
                          tone={entry.tone}
                          title={entry.title}
                          detail={entry.detail}
                          meta={entry.meta}
                          status={entry.status}
                          active={selectedMonitoringIncident?.id === entry.id}
                          onSelect={() => setFocus({ mode: "monitoring", kind: "incident", id: entry.id })}
                        />
                      ))}
                    </div>
                  </section>
                </div>
              </article>
            ) : null}

            {activeMode === "alerting" ? (
              <article className="target-monitoring-panel">
                <div className="target-monitoring-panel-head">
                  <div className="target-monitoring-panel-copy">
                    <span className="section-label">{model.alertingPanel.tabLabel}</span>
                    <h3>{model.alertingPanel.title}</h3>
                    <p>{model.alertingPanel.detail}</p>
                  </div>

                  <div className="target-monitoring-action-row">
                    {model.alertingPanel.actions.map((action) => (
                      <ActionButton
                        key={action.label}
                        icon={action.icon ?? "spark"}
                        label={action.label}
                        primary={action.primary}
                        onClick={() => showActionNotice(`${action.label} queued.`)}
                      />
                    ))}
                  </div>
                </div>

                <article className="target-monitoring-callout target-note-card">
                  <span className="target-note-label">{model.alertingPanel.calloutLabel}</span>
                  <div className="target-note-body">
                    <strong>{model.alertingPanel.calloutTitle}</strong>
                    <span>{model.alertingPanel.calloutBody}</span>
                  </div>
                  <div className="target-note-meta">{model.alertingPanel.calloutMeta}</div>
                </article>

                <div className="target-monitoring-metric-grid">
                  {model.alertingPanel.metrics.map((metric) => (
                    <InspectorMetricCard key={metric.label} {...metric} />
                  ))}
                </div>

                <div className="target-monitoring-alerting-grid">
                  <section className="target-monitoring-pane target-monitoring-alerts-pane">
                    <div className="target-monitoring-pane-head">
                      <div>
                        <span className="section-label">Alerts</span>
                        <h4>Active alerts</h4>
                        <p>{alertEntries.length} alerts remain in the current selection.</p>
                      </div>
                    </div>

                    <div className="target-monitoring-results-list" aria-label="Alerts">
                      {alertEntries.map((entry) => (
                        <MonitoringRow
                          key={entry.id}
                          icon={entry.icon}
                          tone={entry.tone}
                          title={entry.title}
                          detail={entry.detail}
                          meta={entry.meta}
                          status={entry.status}
                          active={selectedAlertEntry?.id === entry.id}
                          onSelect={() => setFocus({ mode: "alerting", kind: "alert", id: entry.id })}
                        />
                      ))}
                    </div>
                  </section>

                  <section className="target-monitoring-pane target-monitoring-policy-pane">
                    <div className="target-monitoring-pane-head">
                      <div>
                        <span className="section-label">Policies</span>
                        <h4>Policy summaries</h4>
                        <p>{policyEntries.length} alert policies are currently surfaced.</p>
                      </div>
                    </div>

                    <div className="target-monitoring-policy-grid" aria-label="Alert policies">
                      {policyEntries.map((entry) => (
                        <MonitoringRow
                          key={entry.id}
                          icon={entry.icon}
                          tone={entry.tone}
                          title={entry.title}
                          detail={entry.detail}
                          meta={entry.meta}
                          status={entry.status}
                          active={selectedPolicyEntry?.id === entry.id}
                          onSelect={() => setFocus({ mode: "alerting", kind: "policy", id: entry.id })}
                        />
                      ))}
                    </div>
                  </section>

                  <section className="target-monitoring-pane target-monitoring-channel-pane">
                    <div className="target-monitoring-pane-head">
                      <div>
                        <span className="section-label">Channels</span>
                        <h4>Notification routes</h4>
                        <p>{channelEntries.length} notification and email channels are tracked.</p>
                      </div>
                    </div>

                    <div className="target-monitoring-channel-grid" aria-label="Notification channels">
                      {channelEntries.map((entry) => (
                        <MonitoringRow
                          key={entry.id}
                          icon={entry.icon}
                          tone={entry.tone}
                          title={entry.title}
                          detail={entry.detail}
                          meta={entry.meta}
                          status={entry.status}
                          active={selectedChannelEntry?.id === entry.id}
                          onSelect={() => setFocus({ mode: "alerting", kind: "channel", id: entry.id })}
                        />
                      ))}
                    </div>
                  </section>

                  <section className="target-monitoring-pane target-monitoring-incident-pane">
                    <div className="target-monitoring-pane-head">
                      <div>
                        <span className="section-label">Incidents</span>
                        <h4>Recent incident history</h4>
                        <p>{alertIncidents.length} incident rows remain in the alerting backlog.</p>
                      </div>
                    </div>

                    <div className="target-monitoring-results-list" aria-label="Incident history">
                      {alertIncidents.map((entry) => (
                        <MonitoringRow
                          key={entry.id}
                          icon={entry.icon}
                          tone={entry.tone}
                          title={entry.title}
                          detail={entry.detail}
                          meta={entry.meta}
                          status={entry.status}
                          active={selectedAlertIncident?.id === entry.id}
                          onSelect={() => setFocus({ mode: "alerting", kind: "incident", id: entry.id })}
                        />
                      ))}
                    </div>
                  </section>
                </div>
              </article>
            ) : null}
          </div>
        </div>
      </article>
    </section>
  );

  const controlPanelContent = (() => {
    if (selectedFocus?.mode === "logging" && selectedLoggingEntry) {
      return (
        <section className="target-monitoring-control">
          <MonitoringDetailCard
            label="Selected log"
            title={selectedLoggingEntry.title}
            detail={selectedLoggingEntry.detail}
            icon={selectedLoggingEntry.icon}
            tone={selectedLoggingEntry.tone}
            status={selectedLoggingEntry.status}
            meta={selectedLoggingEntry.meta}
            lines={[
              { label: "Source", value: selectedLoggingEntry.source },
              { label: "Event type", value: selectedLoggingEntry.eventType },
              { label: "Severity", value: selectedLoggingEntry.severity },
              { label: "Trace", value: selectedLoggingEntry.traceId ?? "None" },
            ]}
          />

          <article className="target-note-card target-monitoring-control-note">
            <span className="target-note-label">Query</span>
            <div className="target-note-body">
              <strong>{model.loggingPanel.queryValue || "All rows"}</strong>
              <span>{selectedLoggingEntry.payloadSummary}</span>
            </div>
            <div className="target-note-meta">{model.loggingPanel.calloutMeta}</div>
          </article>
        </section>
      );
    }

    if (selectedFocus?.mode === "telemetry") {
      const selectedSignal = selectedTelemetryEntry;
      const telemetryDetail = selectedTelemetryDetail ?? null;

      if (!selectedSignal) {
        return null;
      }

      return (
        <section className="target-monitoring-control">
          <MonitoringDetailCard
            label="Selected signal"
            title={telemetryDetail?.source_kind ? `${titleCaseWords(telemetryDetail.source_kind)} · ${titleCaseWords(telemetryDetail.event_kind)}` : selectedSignal.title}
            detail={selectedTelemetryPayloadSummary ?? selectedSignal.detail}
            icon={selectedSignal.icon}
            tone={selectedSignal.tone}
            status={telemetryDetail?.severity ?? selectedSignal.severity}
            meta={telemetryDetail ? `${formatElapsed(telemetryDetail.occurred_at)} · ${telemetryDetail.source_id ?? telemetryDetail.source_kind}` : selectedSignal.meta}
            lines={[
              { label: "Source", value: telemetryDetail?.source_kind ?? selectedSignal.source },
              { label: "Event", value: telemetryDetail?.event_kind ?? selectedSignal.eventType },
              { label: "Trace", value: selectedTelemetryTraceId ?? selectedSignal.traceId ?? "None" },
              { label: "Correlation", value: selectedTelemetryCorrelationId ?? selectedSignal.correlationId ?? "None" },
            ]}
          />

          <article className="target-note-card target-monitoring-control-note">
            <span className="target-note-label">Correlation</span>
            <div className="target-note-body">
              <strong>{selectedTelemetryPayloadSummary ?? "Trace explorer"}</strong>
              <span>{selectedTelemetryPayloadMessage ?? "Select a signal to inspect payload details."}</span>
            </div>
            <div className="target-note-meta">{model.telemetryPanel.calloutMeta}</div>
          </article>
        </section>
      );
    }

    if (selectedFocus?.mode === "monitoring") {
      if (selectedFocus.kind === "service" && selectedMonitoringService) {
        return (
          <section className="target-monitoring-control">
            <MonitoringDetailCard
              label="System service"
              title={selectedMonitoringService.label}
              detail={selectedMonitoringService.detail}
              icon={selectedMonitoringService.icon}
              tone={selectedMonitoringService.tone}
              status={selectedMonitoringService.statusLabel}
              meta={selectedMonitoringService.endpoint ?? selectedMonitoringService.lastChecked}
              lines={[
                { label: "Status", value: selectedMonitoringService.status },
                { label: "Endpoint", value: selectedMonitoringService.endpoint ?? "Not configured" },
                { label: "Last checked", value: selectedMonitoringService.lastChecked },
              ]}
            />

            <article className="target-note-card target-monitoring-control-note">
              <span className="target-note-label">Shared payload</span>
              <div className="target-note-body">
                <strong>System services stay secondary</strong>
                <span>The monitoring page keeps the shared service health payload visible without turning it back into a top-level mode.</span>
              </div>
              <div className="target-note-meta">{model.systemServicesPanel.calloutMeta}</div>
            </article>
          </section>
        );
      }

      if (selectedFocus.kind === "incident" && selectedMonitoringIncident) {
        return (
          <section className="target-monitoring-control">
            <MonitoringDetailCard
              label="Incident"
              title={selectedMonitoringIncident.title}
              detail={selectedMonitoringIncident.detail}
              icon={selectedMonitoringIncident.icon}
              tone={selectedMonitoringIncident.tone}
              status={selectedMonitoringIncident.status}
              meta={selectedMonitoringIncident.meta}
              lines={[
                { label: "Policy", value: selectedMonitoringIncident.policyLabel ?? "None" },
                { label: "Scope", value: selectedMonitoringIncident.scopeLabel ?? "Workspace" },
                { label: "Opened", value: selectedMonitoringIncident.openedAt ?? selectedMonitoringIncident.timestamp },
              ]}
            />
          </section>
        );
      }
    }

    if (selectedFocus?.mode === "alerting") {
      if (selectedFocus.kind === "alert" && selectedAlertEntry) {
        const alertDetail = selectedAlertDetail ?? null;

        return (
          <section className="target-monitoring-control">
            <MonitoringDetailCard
              label="Selected alert"
              title={alertDetail?.summary ?? selectedAlertEntry.title}
              detail={selectedAlertEntry.detail}
              icon={selectedAlertEntry.icon}
              tone={selectedAlertEntry.tone}
              status={alertDetail?.status ?? selectedAlertEntry.status}
              meta={alertDetail ? `${formatElapsed(alertDetail.opened_at)} · ${alertDetail.scope_node_id}` : selectedAlertEntry.meta}
              lines={[
                { label: "Policy", value: selectedAlertEntry.policyLabel ?? "None" },
                { label: "Scope", value: selectedAlertEntry.scopeLabel ?? "Workspace" },
                { label: "Opened", value: alertDetail?.opened_at ?? selectedAlertEntry.openedAt ?? selectedAlertEntry.timestamp },
                { label: "Acknowledged", value: alertDetail?.acknowledged_at ?? selectedAlertEntry.acknowledgedAt ?? "None" },
                { label: "Resolved", value: alertDetail?.resolved_at ?? selectedAlertEntry.resolvedAt ?? "None" },
              ]}
            >
              <div className="target-monitoring-control-actions">
                {context?.source === "backend" ? (
                  <>
                    <ActionButton
                      icon="bellOutline"
                      label="Acknowledge"
                      onClick={() => void handleAlertMutation("acknowledge")}
                    />
                    <ActionButton
                      icon="health"
                      label="Resolve"
                      onClick={() => void handleAlertMutation("resolve")}
                    />
                    <ActionButton icon="clock" label="Mute" onClick={() => void handleAlertMutation("mute")} />
                    <ActionButton icon="queue" label="Unmute" onClick={() => void handleAlertMutation("unmute")} />
                  </>
                ) : (
                  <article className="target-note-card target-monitoring-control-note">
                    <span className="target-note-label">Alert actions</span>
                    <div className="target-note-body">
                      <strong>Backend connection required</strong>
                      <span>Alert mutations are available when the GardenOS backend is connected.</span>
                    </div>
                  </article>
                )}
              </div>
            </MonitoringDetailCard>
          </section>
        );
      }

      if (selectedFocus.kind === "policy" && selectedPolicyEntry) {
        return (
          <section className="target-monitoring-control">
            <MonitoringDetailCard
              label="Policy"
              title={selectedPolicyEntry.title}
              detail={selectedPolicyEntry.detail}
              icon={selectedPolicyEntry.icon}
              tone={selectedPolicyEntry.tone}
              status={selectedPolicyEntry.status}
              meta={selectedPolicyEntry.meta}
              lines={[
                { label: "Rule", value: selectedPolicyEntry.rule ?? "None" },
                { label: "Severity", value: selectedPolicyEntry.severity },
                { label: "Connector kind", value: selectedPolicyEntry.connectorKind ?? "None" },
              ]}
            />
          </section>
        );
      }

      if (selectedFocus.kind === "channel" && selectedChannelEntry) {
        return (
          <section className="target-monitoring-control">
            <MonitoringDetailCard
              label="Channel"
              title={selectedChannelEntry.title}
              detail={selectedChannelEntry.detail}
              icon={selectedChannelEntry.icon}
              tone={selectedChannelEntry.tone}
              status={selectedChannelEntry.status}
              meta={selectedChannelEntry.meta}
              lines={[
                { label: "Connector kind", value: selectedChannelEntry.connectorKind ?? "None" },
                { label: "Source", value: selectedChannelEntry.source },
                { label: "Payload", value: selectedChannelEntry.payloadSummary },
              ]}
            />
          </section>
        );
      }

      if (selectedFocus.kind === "incident" && selectedAlertIncident) {
        return (
          <section className="target-monitoring-control">
            <MonitoringDetailCard
              label="Incident"
              title={selectedAlertIncident.title}
              detail={selectedAlertIncident.detail}
              icon={selectedAlertIncident.icon}
              tone={selectedAlertIncident.tone}
              status={selectedAlertIncident.status}
              meta={selectedAlertIncident.meta}
              lines={[
                { label: "Policy", value: selectedAlertIncident.policyLabel ?? "None" },
                { label: "Scope", value: selectedAlertIncident.scopeLabel ?? "Workspace" },
                { label: "Opened", value: selectedAlertIncident.openedAt ?? selectedAlertIncident.timestamp },
              ]}
            />
          </section>
        );
      }
    }

    return (
      <section className="target-monitoring-control">
        <MonitoringDetailCard
          label={activePanel.tabLabel}
          title={activePanel.title}
          detail={activePanel.detail}
          icon={activeSummary?.icon ?? "queue"}
          tone={activeSummary?.tone ?? "sage"}
          status={activePanel.status}
          meta={activePanel.calloutMeta}
          lines={activePanel.metrics.map((metric) => ({
            label: metric.label,
            value: metric.value,
          }))}
        />
      </section>
    );
  })();

  return {
    main,
    controlPanel: {
      eyebrow: activePanel.tabLabel,
      title: activePanel.title,
      headerAccessory: (
        <Chip icon={streamSummary.icon} tone={streamSummary.tone} title={streamSummary.title} ariaLabel={streamSummary.title}>
          {streamSummary.label}
        </Chip>
      ),
      content: controlPanelContent,
    },
  };
}
