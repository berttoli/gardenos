import type { IconName, PageCommandAction, PageMetric, ShellTone } from "../shared";
import type { GardenServiceContext } from "./context";
import type {
  GardenPlatformAlert,
  GardenPlatformAlertPolicy,
  GardenPlatformAutomationRun,
  GardenPlatformBootstrap,
  GardenPlatformChangeSet,
  GardenPlatformConnectorDefinition,
  GardenPlatformScopeNode,
  GardenPlatformTelemetryEvent,
  GardenSystemServiceRecord,
  GardenSystemServices,
} from "./bootstrap-service";
import type { GardenPlatformEvent } from "./platform-events-service";

export type MonitoringPanelModel = {
  tabLabel: string;
  title: string;
  status: string;
  detail: string;
  metrics: PageMetric[];
  calloutLabel: string;
  calloutTitle: string;
  calloutBody: string;
  calloutMeta: string;
  actions: ReadonlyArray<PageCommandAction>;
};

export type MonitoringLogEntry = {
  icon: IconName;
  tone: ShellTone;
  title: string;
  detail: string;
  meta: string;
};

export type MonitoringStreamStatus = "connecting" | "live" | "degraded" | "offline";

export type MonitoringStreamSummary = {
  status: MonitoringStreamStatus;
  label: string;
  icon: IconName;
  tone: ShellTone;
  title: string;
  detail: string;
  meta: string;
};

export type LoggingPanelModel = {
  tabLabel: string;
  title: string;
  status: string;
  detail: string;
  metrics: PageMetric[];
  entries: MonitoringLogEntry[];
  calloutLabel: string;
  calloutTitle: string;
  calloutBody: string;
  calloutMeta: string;
  actions: ReadonlyArray<PageCommandAction>;
};

export type SystemServiceKey = keyof GardenSystemServices;

export type SystemServiceEntry = {
  key: SystemServiceKey;
  label: string;
  icon: IconName;
  tone: ShellTone;
  status: string;
  statusLabel: string;
  detail: string;
  endpoint: string | null;
  lastChecked: string;
};

export type SystemServicesPanelModel = {
  tabLabel: string;
  title: string;
  status: string;
  detail: string;
  metrics: PageMetric[];
  services: SystemServiceEntry[];
  calloutLabel: string;
  calloutTitle: string;
  calloutBody: string;
  calloutMeta: string;
  actions: ReadonlyArray<PageCommandAction>;
};

export type AssistantPanelModel = {
  tabLabel: string;
  title: string;
  status: string;
  detail: string;
  promptLabel: string;
  promptPlaceholder: string;
  suggestedPrompts: string[];
  calloutLabel: string;
  calloutTitle: string;
  calloutBody: string;
  calloutMeta: string;
  actions: ReadonlyArray<PageCommandAction>;
};

export type MonitoringWorkspaceModel = {
  monitoringPanel: MonitoringPanelModel;
  loggingPanel: LoggingPanelModel;
  systemServicesPanel: SystemServicesPanelModel;
  assistantPanel: AssistantPanelModel;
};

function collectScopes(nodes: GardenPlatformScopeNode[]): GardenPlatformScopeNode[] {
  return nodes.flatMap((node) => [node, ...collectScopes(node.children)]);
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

function titleCase(value: string): string {
  return value
    .trim()
    .replace(/\s+/g, " ")
    .split(" ")
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(" ");
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

function humanizeEventType(eventType: string): string {
  return titleCase(
    eventType
      .split(".")
      .map((part) => part.replace(/[-_]+/g, " "))
      .join(" "),
  );
}

function streamToneFromEvent(event: GardenPlatformEvent): ShellTone {
  if (event.event_type.includes("alert")) {
    return "amber";
  }

  if (event.event_type.includes("telemetry")) {
    return "sky";
  }

  if (event.event_type.includes("changeset")) {
    return "forest";
  }

  if (event.event_type.includes("task")) {
    return "sage";
  }

  return "moss";
}

function streamIconFromEvent(event: GardenPlatformEvent): IconName {
  if (event.event_type.includes("alert")) {
    return "alert";
  }

  if (event.event_type.includes("telemetry")) {
    if (Object.hasOwn(event.payload, "moisture")) {
      return "droplet";
    }

    return "health";
  }

  if (event.event_type.includes("changeset")) {
    return "notebook";
  }

  if (event.event_type.includes("scheduler")) {
    return "calendar";
  }

  if (event.event_type.includes("task")) {
    return "tasks";
  }

  if (event.event_type.includes("automation")) {
    return "spark";
  }

  return "queue";
}

function streamTitleFromEvent(event: GardenPlatformEvent): string {
  const explicitTitles: Record<string, string> = {
    "scheduler.schedule_rule.created": "Schedule rule created",
    "automation.run.created": "Automation run created",
    "automation.run.event.recorded": "Automation run event recorded",
    "telemetry.recorded": "Telemetry recorded",
    "alert.opened": "Alert opened",
    "changeset.created": "Change set created",
    "changeset.updated": "Change set updated",
    "changeset.entry.added": "Change set entry added",
    "task.occurrence.scheduled": "Task scheduled",
    "task.occurrence.completed": "Task completed",
  };

  return explicitTitles[event.event_type] ?? humanizeEventType(event.event_type);
}

function streamDetailFromEvent(event: GardenPlatformEvent): string {
  const payload = event.payload;
  const summary = payloadSummary(payload);

  if (event.event_type === "telemetry.recorded") {
    const sourceId = payloadString(payload, "source_id") ?? event.source_id;
    const eventKind = payloadString(payload, "event_kind") ?? humanizeEventType(event.event_type);

    if (sourceId) {
      return `${sourceId} reported ${eventKind}.`;
    }

    return `${event.source_kind} reported ${eventKind}.`;
  }

  if (event.event_type === "alert.opened") {
    const policyId = payloadString(payload, "alert_policy_id");
    if (policyId) {
      return `Alert policy ${policyId} opened a new alert.`;
    }
  }

  if (event.event_type.startsWith("changeset")) {
    const changeSetKey = payloadString(payload, "key");
    const status = payloadString(payload, "status");
    if (changeSetKey && status) {
      return `Change set ${changeSetKey} is now ${status}.`;
    }
  }

  if (event.event_type.startsWith("task.")) {
    const taskDefinitionId = payloadString(payload, "task_definition_id");
    if (taskDefinitionId) {
      return `Task definition ${taskDefinitionId} updated its queue entry.`;
    }
  }

  if (summary) {
    return summary.endsWith(".") ? summary : `${summary}.`;
  }

  const sourceId = event.source_id ? `Source ${event.source_id}` : null;

  return [humanizeEventType(event.event_type), sourceId].filter(Boolean).join(" · ");
}

export function buildMonitoringStreamEntry(event: GardenPlatformEvent): MonitoringLogEntry {
  return {
    icon: streamIconFromEvent(event),
    tone: streamToneFromEvent(event),
    title: streamTitleFromEvent(event),
    detail: streamDetailFromEvent(event),
    meta: `${formatElapsed(event.occurred_at)} · ${event.source_kind}`,
  };
}

export function buildMonitoringStreamEntries(
  events: GardenPlatformEvent[],
  limit = 6,
): MonitoringLogEntry[] {
  return [...events]
    .sort((left, right) => new Date(right.occurred_at).getTime() - new Date(left.occurred_at).getTime())
    .slice(0, limit)
    .map((event) => buildMonitoringStreamEntry(event));
}

export function buildMonitoringStreamSummary(
  status: MonitoringStreamStatus,
  events: GardenPlatformEvent[],
): MonitoringStreamSummary {
  const latestEvent = buildMonitoringStreamEntries(events, 1)[0] ?? null;

  if (status === "offline") {
    return {
      status,
      label: "Offline",
      icon: "queue",
      tone: "moss",
      title: "Realtime feed offline",
      detail: "The monitoring shell is running without a backend stream.",
      meta: "Fallback bootstrap",
    };
  }

  if (status === "degraded") {
    return {
      status,
      label: "Reconnecting",
      icon: "alert",
      tone: "amber",
      title: latestEvent ? `Retrying after ${latestEvent.title.toLowerCase()}` : "Event relay degraded",
      detail: "The browser is retrying the monitoring feed.",
      meta: latestEvent ? latestEvent.meta : "Waiting for a stable connection",
    };
  }

  if (status === "connecting") {
    return {
      status,
      label: "Connecting",
      icon: "clock",
      tone: "sky",
      title: "Connecting to the event relay",
      detail: "Loading the most recent platform events.",
      meta: latestEvent ? latestEvent.meta : "Awaiting the first frame",
    };
  }

  return {
    status,
    label: "Live",
    icon: latestEvent?.icon ?? "queue",
    tone: latestEvent?.tone ?? "forest",
    title: latestEvent ? latestEvent.title : "Live event relay",
    detail: latestEvent
      ? latestEvent.detail
      : "The monitoring feed is connected and waiting for activity.",
    meta: latestEvent ? `Latest update ${latestEvent.meta}` : "No events captured yet",
  };
}

function severityTone(severity: string): ShellTone {
  if (severity === "critical" || severity === "high") {
    return "amber";
  }

  if (severity === "warning") {
    return "moss";
  }

  return "sage";
}

function entryIconFromTelemetry(event: GardenPlatformTelemetryEvent): IconName {
  if (event.event_kind.includes("moisture")) {
    return "droplet";
  }

  if (event.event_kind.includes("alert")) {
    return "alert";
  }

  if (event.source_kind.includes("sensor")) {
    return "health";
  }

  return "notebook";
}

function entryToneFromTelemetry(event: GardenPlatformTelemetryEvent): ShellTone {
  if (event.severity === "critical") {
    return "amber";
  }

  if (event.severity === "warning") {
    return "forest";
  }

  return "sky";
}

const systemServiceMeta: Record<
  SystemServiceKey,
  {
    label: string;
    icon: IconName;
    tone: ShellTone;
    detail: string;
  }
> = {
  postgres: {
    label: "Postgres",
    icon: "health",
    tone: "forest",
    detail: "Database layer for persistent records and bootstrap data.",
  },
  api: {
    label: "API",
    icon: "spark",
    tone: "sage",
    detail: "Request layer exposed through the shared system_services payload.",
  },
  platform_catalog: {
    label: "Platform catalog",
    icon: "layers",
    tone: "forest",
    detail: "Catalog source for scopes, skills, connectors, and automations.",
  },
  telemetry: {
    label: "Telemetry",
    icon: "chart",
    tone: "sky",
    detail: "Event and sensor feed that powers monitoring surfaces.",
  },
  event_stream: {
    label: "Event stream",
    icon: "queue",
    tone: "amber",
    detail: "Realtime relay used by the monitoring stream.",
  },
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

function serviceStatusTone(status: string): ShellTone {
  const normalized = status.trim().toLowerCase();

  if (normalized.includes("healthy") || normalized.includes("ok") || normalized.includes("online") || normalized.includes("ready") || normalized.includes("live") || normalized.includes("connected")) {
    return "forest";
  }

  if (normalized.includes("warning") || normalized.includes("degrad") || normalized.includes("reconnect") || normalized.includes("partial")) {
    return "amber";
  }

  if (normalized.includes("offline") || normalized.includes("down") || normalized.includes("fail") || normalized.includes("error")) {
    return "amber";
  }

  return "sage";
}

function serviceStatusLabel(status: string): string {
  const normalized = status.trim();
  if (!normalized) {
    return "Unknown";
  }

  return titleCaseWords(normalized);
}

function serviceDetail(record: GardenSystemServiceRecord, fallback: string): string {
  return record.detail?.trim() || record.details?.trim() || record.summary?.trim() || fallback;
}

function serviceEndpoint(record: GardenSystemServiceRecord): string | null {
  const value = record.endpoint?.trim();
  return value ? value : null;
}

function serviceLastChecked(record: GardenSystemServiceRecord, latestActivity: string): string {
  if (record.last_checked_at) {
    return formatElapsed(record.last_checked_at);
  }

  return latestActivity;
}

function buildSystemServiceEntry(
  key: SystemServiceKey,
  record: GardenSystemServiceRecord,
  latestActivity: string,
): SystemServiceEntry {
  const meta = systemServiceMeta[key];

  return {
    key,
    label: meta.label,
    icon: meta.icon,
    tone: serviceStatusTone(record.status),
    status: record.status,
    statusLabel: serviceStatusLabel(record.status),
    detail: serviceDetail(record, meta.detail),
    endpoint: serviceEndpoint(record),
    lastChecked: serviceLastChecked(record, latestActivity),
  };
}

function buildSystemServicesPanel(
  systemServices: GardenSystemServices | null,
  latestActivity: string,
): SystemServicesPanelModel {
  if (!systemServices) {
    return systemServicesPanel;
  }

  const services = (Object.entries(systemServices) as Array<[SystemServiceKey, GardenSystemServiceRecord]>)
    .map(([key, record]) => buildSystemServiceEntry(key, record, latestActivity));
  const healthyCount = services.filter((service) => service.tone === "forest").length;
  const attentionCount = services.length - healthyCount;
  const latestChecked = services
    .map((service) => service.lastChecked)
    .find((value) => value !== latestActivity)
    ?? latestActivity;

  return {
    tabLabel: "System services",
    title: "Shared service health",
    status: attentionCount === 0 ? "Healthy" : "Watch",
    detail: "Postgres, API, catalog, telemetry, and event-stream now read from the shared bootstrap payload.",
    metrics: [
      {
        kind: "metric",
        label: "Services healthy",
        value: `${healthyCount}/${services.length}`,
        status: attentionCount === 0 ? "Healthy" : "Watch",
        detail: "Derived from the shared system_services payload",
        icon: "health",
        tone: attentionCount === 0 ? "forest" : "amber",
        progress: services.length > 0 ? Math.round((healthyCount / services.length) * 100) : 0,
      },
      {
        kind: "metric",
        label: "Attention needed",
        value: String(attentionCount),
        status: attentionCount === 0 ? "Stable" : "Watch",
        detail: "Non-green service states are surfaced here",
        icon: "alert",
        tone: attentionCount === 0 ? "sage" : "amber",
        progress: services.length > 0 ? Math.round((attentionCount / services.length) * 100) : 0,
      },
      {
        kind: "metric",
        label: "Last checked",
        value: latestChecked,
        status: "Live",
        detail: "Latest available service timestamp",
        icon: "clock",
        tone: "sky",
        progress: 100,
      },
    ],
    services,
    calloutLabel: "Shared contract",
    calloutTitle: "One payload, two bootstrap sources",
    calloutBody:
      "The monitoring UI reads the same system_services shape from workspace bootstrap or platform catalog so the contract stays aligned with v1 docs.",
    calloutMeta: `Updated ${latestActivity}`,
    actions: [
      { label: "Refresh services", primary: true, icon: "health" },
      { label: "Inspect telemetry", icon: "chart" },
      { label: "Inspect event stream", icon: "queue" },
    ],
  };
}

const systemServicesPanel: SystemServicesPanelModel = {
  tabLabel: "System services",
  title: "Shared service health",
  status: "Stable",
  detail: "Postgres, API, catalog, telemetry, and event-stream stay visible in one shared payload.",
  metrics: [
    {
      kind: "metric",
      label: "Services healthy",
      value: "5/5",
      status: "Healthy",
      detail: "Shared bootstrap payload",
      icon: "health",
      tone: "forest",
      progress: 100,
    },
    {
      kind: "metric",
      label: "Attention needed",
      value: "0",
      status: "Stable",
      detail: "No degraded services reported",
      icon: "alert",
      tone: "sage",
      progress: 0,
    },
    {
      kind: "metric",
      label: "Last checked",
      value: "just now",
      status: "Live",
      detail: "Fallback shell snapshot",
      icon: "clock",
      tone: "sky",
      progress: 100,
    },
  ],
  services: [
    {
      key: "postgres",
      label: "Postgres",
      icon: "health",
      tone: "forest",
      status: "healthy",
      statusLabel: "Healthy",
      detail: "Database layer for persistent records and bootstrap data.",
      endpoint: "/api/v1/workspace",
      lastChecked: "just now",
    },
    {
      key: "api",
      label: "API",
      icon: "spark",
      tone: "sage",
      status: "healthy",
      statusLabel: "Healthy",
      detail: "Request layer exposed through the shared system_services payload.",
      endpoint: "/api/v1/platform/system-services",
      lastChecked: "just now",
    },
    {
      key: "platform_catalog",
      label: "Platform catalog",
      icon: "layers",
      tone: "forest",
      status: "healthy",
      statusLabel: "Healthy",
      detail: "Catalog source for scopes, skills, connectors, and automations.",
      endpoint: "/api/v1/platform/catalog",
      lastChecked: "just now",
    },
    {
      key: "telemetry",
      label: "Telemetry",
      icon: "chart",
      tone: "sky",
      status: "healthy",
      statusLabel: "Healthy",
      detail: "Event and sensor feed that powers monitoring surfaces.",
      endpoint: "/api/v1/platform/telemetry",
      lastChecked: "just now",
    },
    {
      key: "event_stream",
      label: "Event stream",
      icon: "queue",
      tone: "forest",
      status: "healthy",
      statusLabel: "Healthy",
      detail: "Realtime relay used by the monitoring stream.",
      endpoint: "/api/v1/platform/events/stream",
      lastChecked: "just now",
    },
  ],
  calloutLabel: "Shared contract",
  calloutTitle: "One payload, two bootstrap sources",
  calloutBody:
    "The monitoring UI reads the same system_services shape from workspace bootstrap or platform catalog so the contract stays aligned with v1 docs.",
  calloutMeta: "Fallback shell snapshot",
  actions: [
    { label: "Refresh services", primary: true, icon: "health" },
    { label: "Inspect telemetry", icon: "chart" },
    { label: "Inspect event stream", icon: "queue" },
  ],
};

function buildLiveMonitoringModel(
  platform: GardenPlatformBootstrap,
  systemServices: GardenSystemServices | null,
): MonitoringWorkspaceModel {
  const scopes = collectScopes(platform.catalog.scopes);
  const zones = scopes.filter((scope) => scope.scope_type === "zone");
  const openAlerts = platform.alerts.filter((alert) => alert.status === "open");
  const telemetryMoisture = platform.telemetry.filter(
    (event) => event.event_kind.includes("moisture") || Object.hasOwn(event.payload, "moisture"),
  );
  const offlineConnectors = platform.catalog.connectors.filter((connector) => connector.supports_offline);
  const sensorHealth = platform.catalog.connectors.length > 0
    ? Math.round((offlineConnectors.length / platform.catalog.connectors.length) * 100)
    : 0;
  const stableZones = Math.max(zones.length - new Set(openAlerts.map((alert) => alert.scope_node_id)).size, 0);
  const latestTelemetry = platform.telemetry[0]?.occurred_at ?? platform.alerts[0]?.opened_at ?? null;
  const latestActivity = latestTelemetry ? formatElapsed(latestTelemetry) : "just now";
  const systemServicesPanelModel = buildSystemServicesPanel(systemServices, latestActivity);

  const mergedEntries = [
    ...platform.telemetry.slice(0, 3).map((event) => ({
      sortAt: event.occurred_at,
      entry: {
        icon: entryIconFromTelemetry(event),
        tone: entryToneFromTelemetry(event),
        title: `${event.source_kind} ${event.event_kind}`.replace(/\b\w/g, (char) => char.toUpperCase()),
        detail: event.source_id
          ? `Source ${event.source_id} reported ${event.event_kind}.`
          : `${event.event_kind} reported from ${event.source_kind}.`,
        meta: `${formatElapsed(event.occurred_at)} · ${event.source_kind}`,
      } satisfies MonitoringLogEntry,
    })),
    ...platform.alerts.slice(0, 2).map((alert) => ({
      sortAt: alert.opened_at,
      entry: {
        icon: "alert",
        tone: severityTone(alert.status === "open" ? "critical" : alert.status),
        title: alert.summary ?? "Alert opened",
        detail: `Alert policy ${alert.alert_policy_id} is ${alert.status}.`,
        meta: `${formatElapsed(alert.opened_at)} · ${alert.status}`,
      } satisfies MonitoringLogEntry,
    })),
    ...platform.changeSets.slice(0, 2).map((changeSet) => ({
      sortAt: changeSet.created_at,
      entry: {
        icon: "notebook",
        tone: changeSet.status === "rolled_back" ? "amber" : "forest",
        title: `Change set ${changeSet.key}`,
        detail: changeSet.summary,
        meta: `${formatElapsed(changeSet.created_at)} · ${changeSet.status}`,
      } satisfies MonitoringLogEntry,
    })),
    ...platform.automationRuns.slice(0, 2).map((run) => ({
      sortAt: run.created_at,
      entry: {
        icon: "spark",
        tone: run.status === "failed" ? "amber" : "sage",
        title: `Automation run ${run.triggered_by}`,
        detail: run.reason ?? `Run ${run.status} for version ${run.automation_version_id}.`,
        meta: `${formatElapsed(run.created_at)} · ${run.status}`,
      } satisfies MonitoringLogEntry,
    })),
  ]
    .sort((left, right) => new Date(right.sortAt).getTime() - new Date(left.sortAt).getTime())
    .slice(0, 4)
    .map((item) => item.entry);

  const loggingMetrics: PageMetric[] = [
    {
      kind: "metric",
      label: "Events captured",
      value: String(platform.telemetry.length + platform.alerts.length + platform.changeSets.length),
      status: "Live",
      detail: "Across telemetry, alerts, and change sets",
      icon: "queue",
      tone: "sage",
      progress: Math.min(100, platform.telemetry.length + platform.alerts.length + platform.changeSets.length),
    },
    {
      kind: "metric",
      label: "Warnings",
      value: String(openAlerts.length),
      status: openAlerts.length > 0 ? "Watch" : "Healthy",
      detail: "Open platform alerts",
      icon: "alert",
      tone: "amber",
      progress: Math.min(100, openAlerts.length * 20),
    },
    {
      kind: "metric",
      label: "Sync delay",
      value: latestActivity,
      status: "Healthy",
      detail: "Latest signal age",
      icon: "clock",
      tone: "forest",
      progress: 90,
    },
  ];

  return {
    monitoringPanel: {
      tabLabel: "Monitoring",
      title: "Sensor watch",
      status: "Live",
      detail: `Sensors are holding steady while ${openAlerts.length} alerts remain open.`,
      metrics: [
        {
          kind: "metric",
          label: "Sensors online",
          value: `${sensorHealth}%`,
          status: sensorHealth >= 90 ? "Stable" : "Watch",
          detail: `${offlineConnectors.length} of ${platform.catalog.connectors.length} connectors support offline workflows`,
          icon: "health",
          tone: "sage",
          progress: sensorHealth,
        },
        {
          kind: "metric",
          label: "Moisture drift",
          value: String(telemetryMoisture.length),
          status: telemetryMoisture.length > 0 ? "Watch" : "Good",
          detail: `${platform.telemetry.length} telemetry events in the live stream`,
          icon: "droplet",
          tone: "amber",
          progress: Math.min(100, telemetryMoisture.length * 25),
        },
        {
          kind: "metric",
          label: "Zones stable",
          value: String(stableZones),
          status: stableZones === zones.length ? "Good" : "Watch",
          detail: `${zones.length} zones tracked in the catalog`,
          icon: "chart",
          tone: "forest",
          progress: zones.length > 0 ? Math.round((stableZones / zones.length) * 100) : 0,
        },
      ],
      calloutLabel: "Field note",
      calloutTitle: "Live platform watch",
      calloutBody: `Monitoring is fed by ${platform.catalog.summary.connector_count} connectors, ${platform.alerts.length} alerts, and ${platform.catalog.summary.automation_definition_count} automation definitions.`,
      calloutMeta: `Updated ${latestActivity}`,
      actions: [
        { label: "Review alerts", primary: true, icon: "alert" },
        { label: "Calibrate sensor", icon: "health" },
        { label: "Acknowledge", icon: "bellOutline" },
      ],
    },
    loggingPanel: {
      tabLabel: "Logging",
      title: "Event stream",
      status: "Live",
      detail: `${platform.telemetry.length + platform.alerts.length + platform.changeSets.length} events captured in the live stream.`,
      metrics: loggingMetrics,
      entries: mergedEntries,
      calloutLabel: "Stream note",
      calloutTitle: "Logging cadence",
      calloutBody:
        "Keep automatic writes, telemetry, and approvals in the same stream so the field trail stays readable after reconnects.",
      calloutMeta: `Updated ${latestActivity}`,
      actions: [
        { label: "Open log stream", primary: true, icon: "queue" },
        { label: "Filter events", icon: "spark" },
        { label: "Export CSV", icon: "reports" },
      ],
    },
    systemServicesPanel: systemServicesPanelModel,
    assistantPanel: {
      tabLabel: "Assistant",
      title: "Local assistant",
      status: "Connected",
      detail: "The local assistant container can inspect the same v1 platform state as the monitoring UI.",
      promptLabel: "Ask GardenOS",
      promptPlaceholder: "Ask for tasks, services, logs, or the current nursery state.",
      suggestedPrompts: [
        "Summarize the current monitoring state",
        "What services are active in this nursery?",
        "Show me overdue tasks and alerts",
      ],
      calloutLabel: "Assistant note",
      calloutTitle: "Container-backed chat",
      calloutBody:
        "This surface is wired to the local assistant service so the UI can speak to a real container instead of a mock.",
      calloutMeta: `Updated ${latestActivity}`,
      actions: [
        { label: "Open assistant", primary: true, icon: "spark" },
        { label: "Copy prompt", icon: "notebook" },
      ],
    },
  };
}

const monitoringPanel: MonitoringPanelModel = {
  tabLabel: "Monitoring",
  title: "Sensor watch",
  status: "Stable",
  detail: "Sensors are holding steady while 3 zones drift slightly.",
  metrics: [
    {
      kind: "metric",
      label: "Sensors online",
      value: "96%",
      status: "Stable",
      detail: "4 devices need attention",
      icon: "health",
      tone: "sage",
      progress: 96,
    },
    {
      kind: "metric",
      label: "Moisture drift",
      value: "4",
      status: "Watch",
      detail: "2 zones trending upward",
      icon: "droplet",
      tone: "amber",
      progress: 54,
    },
    {
      kind: "metric",
      label: "Zones stable",
      value: "12",
      status: "Good",
      detail: "No manual action needed",
      icon: "chart",
      tone: "forest",
      progress: 78,
    },
  ],
  calloutLabel: "Field note",
  calloutTitle: "Best inspection window",
  calloutBody:
    "Walk the sensor route before the afternoon heat rises so moisture corrections land before the next irrigation cycle.",
  calloutMeta: "Updated 13:11 by ops",
  actions: [
    { label: "Review alerts", primary: true, icon: "alert" },
    { label: "Calibrate sensor", icon: "health" },
    { label: "Acknowledge", icon: "bellOutline" },
  ],
};

const loggingPanel: LoggingPanelModel = {
  tabLabel: "Logging",
  title: "Event stream",
  status: "Live",
  detail: "18 events captured in the last 15 minutes.",
  metrics: [
    {
      kind: "metric",
      label: "Events captured",
      value: "128",
      status: "Live",
      detail: "Last 15 minutes",
      icon: "queue",
      tone: "sage",
      progress: 82,
    },
    {
      kind: "metric",
      label: "Warnings",
      value: "6",
      status: "Watch",
      detail: "3 repeated by zone",
      icon: "alert",
      tone: "amber",
      progress: 42,
    },
    {
      kind: "metric",
      label: "Sync delay",
      value: "12s",
      status: "Healthy",
      detail: "Within threshold",
      icon: "clock",
      tone: "forest",
      progress: 90,
    },
  ],
  entries: [
    {
      icon: "droplet",
      tone: "sky",
      title: "Greenhouse 3 moisture update",
      detail: "Value stabilized at 61% after irrigation.",
      meta: "2 min ago · sensor 14",
    },
    {
      icon: "alert",
      tone: "amber",
      title: "Zone 2 spike detected",
      detail: "Short humidity jump resolved automatically.",
      meta: "11 min ago · auto rule",
    },
    {
      icon: "notebook",
      tone: "forest",
      title: "Manual note synced",
      detail: "Crew inspection note attached to Container Yard.",
      meta: "23 min ago · Jordan",
    },
    {
      icon: "bellOutline",
      tone: "sage",
      title: "Calibration reminder queued",
      detail: "Reminder will surface with the next morning route.",
      meta: "35 min ago · system",
    },
  ],
  calloutLabel: "Stream note",
  calloutTitle: "Logging cadence",
  calloutBody:
    "Keep automatic writes and manual notes in the same stream so the field trail stays readable after reconnects.",
  calloutMeta: "Updated 13:11 by logging service",
  actions: [
    { label: "Open log stream", primary: true, icon: "queue" },
    { label: "Filter events", icon: "spark" },
    { label: "Export CSV", icon: "reports" },
  ],
};

export function getMonitoringModel(
  context: GardenServiceContext | null = null,
): MonitoringWorkspaceModel {
  const platform = context?.platform ?? null;
  const systemServices = context?.workspace?.system_services ?? context?.platform?.catalog.system_services ?? null;

  if (platform) {
    return buildLiveMonitoringModel(platform, systemServices);
  }

  return {
    monitoringPanel,
    loggingPanel,
    systemServicesPanel,
    assistantPanel: {
      tabLabel: "Assistant",
      title: "Local assistant",
      status: "Connected",
      detail: "The local assistant container can inspect the same v1 platform state as the monitoring UI.",
      promptLabel: "Ask GardenOS",
      promptPlaceholder: "Ask for tasks, services, logs, or the current nursery state.",
      suggestedPrompts: [
        "Summarize the current monitoring state",
        "What services are active in this nursery?",
        "Show me overdue tasks and alerts",
      ],
      calloutLabel: "Assistant note",
      calloutTitle: "Container-backed chat",
      calloutBody:
        "This surface is wired to the local assistant service so the UI can speak to a real container instead of a mock.",
      calloutMeta: "Updated 13:11 by assistant service",
      actions: [
        { label: "Open assistant", primary: true, icon: "spark" },
        { label: "Copy prompt", icon: "notebook" },
      ],
    },
  };
}

export type MonitoringConsoleModeId = "logging" | "telemetry" | "monitoring" | "alerting";

export type MonitoringConsoleModeSummary = {
  id: MonitoringConsoleModeId;
  label: string;
  title: string;
  detail: string;
  icon: IconName;
  tone: ShellTone;
  count: string;
  status: string;
};

export type MonitoringConsoleEventEntry = {
  id: string;
  kind: "log" | "telemetry" | "alert" | "change-set" | "automation" | "policy" | "channel";
  icon: IconName;
  tone: ShellTone;
  title: string;
  detail: string;
  meta: string;
  source: string;
  severity: string;
  eventType: string;
  timestamp: string;
  traceId: string | null;
  correlationId: string | null;
  payloadSummary: string;
  status?: string;
  policyId?: string;
  policyLabel?: string;
  scopeLabel?: string;
  openedAt?: string;
  acknowledgedAt?: string | null;
  resolvedAt?: string | null;
  rule?: string;
  connectorKind?: string;
};

export type MonitoringConsoleSavedQuery = {
  id: string;
  label: string;
  query: string;
  detail: string;
  icon: IconName;
  tone: ShellTone;
};

export type MonitoringConsoleField = {
  id: string;
  label: string;
  value: string;
  detail: string;
  icon: IconName;
  tone: ShellTone;
};

export type MonitoringConsoleTimelinePoint = {
  label: string;
  value: number;
  detail: string;
  meta: string;
  tone: ShellTone;
};

export type MonitoringConsoleLoggingPanel = {
  tabLabel: string;
  title: string;
  status: string;
  detail: string;
  queryLabel: string;
  queryPlaceholder: string;
  queryValue: string;
  savedQueries: MonitoringConsoleSavedQuery[];
  fields: MonitoringConsoleField[];
  timeline: MonitoringConsoleTimelinePoint[];
  entries: MonitoringConsoleEventEntry[];
  metrics: PageMetric[];
  actions: ReadonlyArray<PageCommandAction>;
  calloutLabel: string;
  calloutTitle: string;
  calloutBody: string;
  calloutMeta: string;
};

export type MonitoringConsoleTelemetryPanel = {
  tabLabel: string;
  title: string;
  status: string;
  detail: string;
  metrics: PageMetric[];
  timeline: MonitoringConsoleTimelinePoint[];
  signals: MonitoringConsoleEventEntry[];
  actions: ReadonlyArray<PageCommandAction>;
  calloutLabel: string;
  calloutTitle: string;
  calloutBody: string;
  calloutMeta: string;
};

export type MonitoringConsoleMonitoringPanel = {
  tabLabel: string;
  title: string;
  status: string;
  detail: string;
  metrics: PageMetric[];
  dashboards: PageMetric[];
  incidents: MonitoringConsoleEventEntry[];
  services: SystemServiceEntry[];
  actions: ReadonlyArray<PageCommandAction>;
  calloutLabel: string;
  calloutTitle: string;
  calloutBody: string;
  calloutMeta: string;
};

export type MonitoringConsolePolicyEntry = MonitoringConsoleEventEntry;
export type MonitoringConsoleChannelEntry = MonitoringConsoleEventEntry;

export type MonitoringConsoleAlertingPanel = {
  tabLabel: string;
  title: string;
  status: string;
  detail: string;
  metrics: PageMetric[];
  alerts: MonitoringConsoleEventEntry[];
  policies: MonitoringConsolePolicyEntry[];
  channels: MonitoringConsoleChannelEntry[];
  incidents: MonitoringConsoleEventEntry[];
  actions: ReadonlyArray<PageCommandAction>;
  calloutLabel: string;
  calloutTitle: string;
  calloutBody: string;
  calloutMeta: string;
};

export type MonitoringConsoleModel = {
  modeSummaries: MonitoringConsoleModeSummary[];
  loggingPanel: MonitoringConsoleLoggingPanel;
  telemetryPanel: MonitoringConsoleTelemetryPanel;
  monitoringPanel: MonitoringConsoleMonitoringPanel;
  alertingPanel: MonitoringConsoleAlertingPanel;
  systemServicesPanel: SystemServicesPanelModel;
};

function buildConsoleEntryMeta(
  timestamp: string,
  source: string,
  traceId: string | null,
  extra?: string,
): string {
  const segments = [formatElapsed(timestamp), source];

  if (traceId) {
    segments.push(`trace ${traceId.slice(0, 8)}`);
  }

  if (extra) {
    segments.push(extra);
  }

  return segments.join(" · ");
}

function buildConsoleTimeline(timestamps: string[], tone: ShellTone): MonitoringConsoleTimelinePoint[] {
  const bucketCount = 6;
  const validTimes = timestamps
    .map((value) => new Date(value).getTime())
    .filter((value) => Number.isFinite(value))
    .sort((left, right) => left - right);

  if (validTimes.length === 0) {
    return [
      { label: "Now", value: 0, detail: "No activity", meta: "Fallback shell", tone },
      { label: "5m", value: 0, detail: "No activity", meta: "Fallback shell", tone },
      { label: "10m", value: 0, detail: "No activity", meta: "Fallback shell", tone },
      { label: "15m", value: 0, detail: "No activity", meta: "Fallback shell", tone },
      { label: "30m", value: 0, detail: "No activity", meta: "Fallback shell", tone },
      { label: "Now", value: 0, detail: "No activity", meta: "Fallback shell", tone },
    ];
  }

  const minTime = validTimes[0];
  const maxTime = validTimes[validTimes.length - 1];
  const span = Math.max(maxTime - minTime, 1);
  const counts = Array.from({ length: bucketCount }, () => 0);

  for (const time of validTimes) {
    const normalized = Math.min(bucketCount - 1, Math.floor(((time - minTime) / span) * bucketCount));
    counts[normalized] += 1;
  }

  const maxCount = Math.max(...counts, 1);

  return counts.map((value, index) => {
    const remaining = bucketCount - index - 1;
    const minutes = remaining === 0 ? 0 : Math.max(5, remaining * 5);

    return {
      label: remaining === 0 ? "Now" : `${minutes}m`,
      value,
      detail: `${value} event${value === 1 ? "" : "s"}`,
      meta: value > 0 ? `${Math.round((value / maxCount) * 100)}% of peak` : "Quiet bucket",
      tone: value > 0 ? tone : "sage",
    };
  });
}

function buildConsoleTelemetryEntry(
  event: GardenPlatformTelemetryEvent,
  relatedTraceId: string | null = null,
): MonitoringConsoleEventEntry {
  const traceId = payloadString(event.payload, "trace_id") ?? relatedTraceId;
  const correlationId = payloadString(event.payload, "correlation_id");

  return {
    id: `telemetry:${event.id}`,
    kind: "telemetry",
    icon: entryIconFromTelemetry(event),
    tone: entryToneFromTelemetry(event),
    title: `${titleCaseWords(event.source_kind)} · ${titleCaseWords(event.event_kind)}`,
    detail:
      payloadSummary(event.payload)
      ?? `${event.source_id ?? event.source_kind} reported ${event.event_kind}.`,
    meta: buildConsoleEntryMeta(event.occurred_at, event.source_kind, traceId, event.severity),
    source: event.source_id ?? event.source_kind,
    severity: event.severity,
    eventType: event.event_kind,
    timestamp: event.occurred_at,
    traceId,
    correlationId,
    payloadSummary: payloadSummary(event.payload) ?? event.event_kind,
  };
}

function buildConsoleAlertEntry(
  alert: GardenPlatformAlert,
  policyById: Map<string, GardenPlatformAlertPolicy>,
): MonitoringConsoleEventEntry {
  const policy = policyById.get(alert.alert_policy_id) ?? null;
  const severity = policy?.severity ?? (alert.status === "resolved" ? "low" : "warning");
  const statusLabel = titleCaseWords(alert.status);

  return {
    id: `alert:${alert.id}`,
    kind: "alert",
    icon: "alert",
    tone: severityTone(severity),
    title: alert.summary ?? policy?.name ?? "Alert opened",
    detail: policy ? `${policy.rule} · ${statusLabel}` : statusLabel,
    meta: buildConsoleEntryMeta(alert.opened_at, alert.scope_node_id, null, statusLabel),
    source: alert.scope_node_id,
    severity,
    eventType: "alert.opened",
    timestamp: alert.opened_at,
    traceId: null,
    correlationId: null,
    payloadSummary: alert.summary ?? policy?.rule ?? alert.alert_policy_id,
    status: alert.status,
    policyId: alert.alert_policy_id,
    policyLabel: policy?.name ?? alert.alert_policy_id,
    scopeLabel: alert.scope_node_id,
    openedAt: alert.opened_at,
    acknowledgedAt: alert.acknowledged_at,
    resolvedAt: alert.resolved_at,
  };
}

function buildConsoleChangeSetEntry(changeSet: GardenPlatformChangeSet): MonitoringConsoleEventEntry {
  const status = titleCaseWords(changeSet.status);
  const severity = changeSet.status === "rolled_back" ? "warning" : "info";

  return {
    id: `changeset:${changeSet.id}`,
    kind: "change-set",
    icon: "notebook",
    tone: changeSet.status === "rolled_back" ? "amber" : "forest",
    title: `Change set ${changeSet.key}`,
    detail: `${changeSet.summary} · ${status}`,
    meta: buildConsoleEntryMeta(changeSet.created_at, changeSet.scope_node_id ?? "workspace", null, status),
    source: changeSet.scope_node_id ?? "workspace",
    severity,
    eventType: "changeset.updated",
    timestamp: changeSet.created_at,
    traceId: null,
    correlationId: null,
    payloadSummary: changeSet.reason ?? changeSet.summary,
  };
}

function buildConsoleAutomationRunEntry(run: GardenPlatformAutomationRun): MonitoringConsoleEventEntry {
  const status = titleCaseWords(run.status);
  const severity = run.status === "failed" ? "warning" : "info";
  const timestamp = run.started_at ?? run.ended_at ?? new Date().toISOString();

  return {
    id: `automation:${run.id}`,
    kind: "automation",
    icon: "spark",
    tone: run.status === "failed" ? "amber" : "sage",
    title: `Automation run ${run.triggered_by}`,
    detail: run.reason ?? `Run ${run.status} for version ${run.automation_version_id}.`,
    meta: buildConsoleEntryMeta(timestamp, run.scope_node_id ?? "workspace", null, status),
    source: run.scope_node_id ?? "workspace",
    severity,
    eventType: "automation.run",
    timestamp,
    traceId: null,
    correlationId: null,
    payloadSummary: run.reason ?? run.automation_version_id,
  };
}

function buildConsolePolicyEntry(policy: GardenPlatformAlertPolicy): MonitoringConsolePolicyEntry {
  const status = policy.is_active ? "Active" : "Paused";

  return {
    id: `policy:${policy.id}`,
    kind: "policy",
    icon: "bellOutline",
    tone: severityTone(policy.severity),
    title: policy.name,
    detail: policy.rule,
    meta: buildConsoleEntryMeta(policy.updated_at, policy.source_kind, null, status),
    source: policy.scope_node_id,
    severity: policy.severity,
    eventType: "alert.policy",
    timestamp: policy.updated_at,
    traceId: null,
    correlationId: null,
    payloadSummary: policy.rule,
    status,
    policyId: policy.id,
    policyLabel: policy.name,
    rule: policy.rule,
    connectorKind: policy.source_kind,
  };
}

function buildConsoleChannelEntry(
  connector: GardenPlatformConnectorDefinition,
  latestActivity: string,
): MonitoringConsoleChannelEntry {
  const status = connector.supports_offline ? "Ready" : "Live";
  const detail =
    connector.description?.trim()
    ?? (connector.connector_kind === "notification"
      ? "Push notification delivery for app surfaces."
      : "Outbound email delivery for alerts and approvals.");

  return {
    id: `channel:${connector.id}`,
    kind: "channel",
    icon: connector.connector_kind === "email" ? "bellOutline" : "bell",
    tone: connector.connector_kind === "email" ? "amber" : "forest",
    title: connector.name,
    detail,
    meta: `${connector.connector_kind} · ${connector.auth_kind} · ${connector.supports_offline ? "offline ready" : "online only"} · ${latestActivity}`,
    source: connector.scope_node_id,
    severity: "info",
    eventType: "connector",
    timestamp: new Date().toISOString(),
    traceId: null,
    correlationId: null,
    payloadSummary: connector.description ?? connector.name,
    status,
    connectorKind: connector.connector_kind,
  };
}

function buildConsoleFieldSummaries(entries: MonitoringConsoleEventEntry[]): MonitoringConsoleField[] {
  const sources = new Set(entries.map((entry) => entry.source));
  const eventTypes = new Set(entries.map((entry) => entry.eventType));
  const traceCount = entries.filter((entry) => entry.traceId || entry.correlationId).length;
  const payloadCount = entries.filter((entry) => entry.payloadSummary.trim().length > 0).length;

  return [
    {
      id: "sources",
      label: "Source kinds",
      value: String(sources.size),
      detail: [...sources].slice(0, 3).join(", "),
      icon: "network",
      tone: "forest",
    },
    {
      id: "event-types",
      label: "Event types",
      value: String(eventTypes.size),
      detail: [...eventTypes].slice(0, 3).join(", "),
      icon: "queue",
      tone: "sage",
    },
    {
      id: "trace-links",
      label: "Trace links",
      value: String(traceCount),
      detail: `${traceCount} rows expose trace or correlation IDs`,
      icon: "spark",
      tone: "sky",
    },
    {
      id: "payloads",
      label: "Payloads",
      value: String(payloadCount),
      detail: `${payloadCount} rows include payload summaries`,
      icon: "layers",
      tone: "amber",
    },
  ];
}

function buildConsoleSavedQueries(
  loggingEntries: MonitoringConsoleEventEntry[],
  telemetryEntries: MonitoringConsoleEventEntry[],
  alertEntries: MonitoringConsoleEventEntry[],
  changeSetEntries: MonitoringConsoleEventEntry[],
  automationEntries: MonitoringConsoleEventEntry[],
): MonitoringConsoleSavedQuery[] {
  return [
    {
      id: "alerts",
      label: "Open alerts",
      query: "kind:alert status:open",
      detail: `${alertEntries.filter((entry) => entry.status === "open").length} open alerts`,
      icon: "alert",
      tone: "amber",
    },
    {
      id: "telemetry",
      label: "Telemetry",
      query: "kind:telemetry",
      detail: `${telemetryEntries.length} telemetry signals`,
      icon: "chart",
      tone: "sky",
    },
    {
      id: "changes",
      label: "Change sets",
      query: "kind:change-set",
      detail: `${changeSetEntries.length} change-set events`,
      icon: "notebook",
      tone: "forest",
    },
    {
      id: "automation",
      label: "Automation runs",
      query: "kind:automation",
      detail: `${automationEntries.length} automation events`,
      icon: "spark",
      tone: "sage",
    },
    {
      id: "logs",
      label: "All logs",
      query: "",
      detail: `${loggingEntries.length} rows in the combined stream`,
      icon: "queue",
      tone: "forest",
    },
  ];
}

function buildPlatformConsoleEntries(
  platform: GardenPlatformBootstrap,
  policyById: Map<string, GardenPlatformAlertPolicy>,
): MonitoringConsoleEventEntry[] {
  const telemetryEntries = platform.telemetry.map((event) => buildConsoleTelemetryEntry(event));
  const alertEntries = platform.alerts.map((alert) => buildConsoleAlertEntry(alert, policyById));
  const changeSetEntries = platform.changeSets.map((changeSet) => buildConsoleChangeSetEntry(changeSet));
  const automationEntries = platform.automationRuns.map((run) => buildConsoleAutomationRunEntry(run));

  return [
    ...telemetryEntries,
    ...alertEntries,
    ...changeSetEntries,
    ...automationEntries,
  ]
    .sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime())
    .slice(0, 16);
}

function buildLoggingPanelModel(
  platform: GardenPlatformBootstrap,
  loggingEntries: MonitoringConsoleEventEntry[],
  alertEntries: MonitoringConsoleEventEntry[],
  telemetryEntries: MonitoringConsoleEventEntry[],
  changeSetEntries: MonitoringConsoleEventEntry[],
  automationEntries: MonitoringConsoleEventEntry[],
  latestActivity: string,
): MonitoringConsoleLoggingPanel {
  const traceCoverage = loggingEntries.filter((entry) => entry.traceId || entry.correlationId).length;
  const openAlerts = alertEntries.filter((entry) => entry.status === "open").length;

  return {
    tabLabel: "Logging",
    title: "Logs Explorer",
    status: "Live",
    detail: "Query, filter, and review the live event stream without leaving the console.",
    queryLabel: "Query",
    queryPlaceholder: "Search logs, traces, event types, and sources",
    queryValue: "kind:telemetry OR kind:alert",
    savedQueries: buildConsoleSavedQueries(loggingEntries, telemetryEntries, alertEntries, changeSetEntries, automationEntries),
    fields: buildConsoleFieldSummaries(loggingEntries),
    timeline: buildConsoleTimeline(loggingEntries.map((entry) => entry.timestamp), "forest"),
    entries: loggingEntries,
    metrics: [
      {
        kind: "metric",
        label: "Rows",
        value: String(loggingEntries.length),
        status: "Live",
        detail: "Combined telemetry, alerts, change sets, and automation events",
        icon: "queue",
        tone: "sage",
        progress: Math.min(100, loggingEntries.length * 8),
      },
      {
        kind: "metric",
        label: "Trace links",
        value: String(traceCoverage),
        status: traceCoverage > 0 ? "Connected" : "Sparse",
        detail: "Rows carrying trace or correlation IDs",
        icon: "spark",
        tone: "sky",
        progress: Math.min(100, traceCoverage * 12),
      },
      {
        kind: "metric",
        label: "Open alerts",
        value: String(openAlerts),
        status: openAlerts > 0 ? "Watch" : "Healthy",
        detail: "Alerts surfaced in the log stream",
        icon: "alert",
        tone: "amber",
        progress: Math.min(100, openAlerts * 25),
      },
    ],
    actions: [
      { label: "Share query", primary: true, icon: "network" },
      { label: "Save view", icon: "notebook" },
      { label: "Preferences", icon: "settings" },
    ],
    calloutLabel: "Logs Explorer",
    calloutTitle: "Primary query surface",
    calloutBody:
      "Use the query bar and saved searches to focus on a narrow set of logs while keeping fields and timelines visible.",
    calloutMeta: `Updated ${latestActivity}`,
  };
}

function buildTelemetryPanelModel(
  telemetryEntries: MonitoringConsoleEventEntry[],
  loggingEntries: MonitoringConsoleEventEntry[],
  latestActivity: string,
): MonitoringConsoleTelemetryPanel {
  const tracedSignals = telemetryEntries.filter((entry) => entry.traceId || entry.correlationId).length;
  const warningSignals = telemetryEntries.filter((entry) => entry.severity === "warning" || entry.severity === "critical").length;

  return {
    tabLabel: "Telemetry",
    title: "Metrics Explorer",
    status: telemetryEntries.length > 0 ? "Live" : "Idle",
    detail: "Chart-like summaries and trace-style signal rows pulled from the current platform state.",
    metrics: [
      {
        kind: "metric",
        label: "Signals",
        value: String(telemetryEntries.length),
        status: telemetryEntries.length > 0 ? "Live" : "Idle",
        detail: "Telemetry points in the current view",
        icon: "chart",
        tone: "sky",
        progress: Math.min(100, telemetryEntries.length * 12),
      },
      {
        kind: "metric",
        label: "Trace links",
        value: String(tracedSignals),
        status: tracedSignals > 0 ? "Connected" : "Sparse",
        detail: "Signals carrying trace or correlation references",
        icon: "spark",
        tone: "forest",
        progress: Math.min(100, tracedSignals * 14),
      },
      {
        kind: "metric",
        label: "Warnings",
        value: String(warningSignals),
        status: warningSignals > 0 ? "Watch" : "Healthy",
        detail: "Signals needing operator attention",
        icon: "alert",
        tone: "amber",
        progress: Math.min(100, warningSignals * 20),
      },
    ],
    timeline: buildConsoleTimeline(telemetryEntries.map((entry) => entry.timestamp), "sky"),
    signals: telemetryEntries,
    actions: [
      { label: "Open traces", primary: true, icon: "spark" },
      { label: "Correlate logs", icon: "queue" },
      { label: "Export sample", icon: "reports" },
    ],
    calloutLabel: "Trace Explorer",
    calloutTitle: "Split attention across charts and rows",
    calloutBody:
      "Keep the most recent telemetry buckets on screen while the inspector follows one selected signal or trace path.",
    calloutMeta: `Related log rows: ${loggingEntries.length} available · Updated ${latestActivity}`,
  };
}

function buildMonitoringPanelModel(
  platform: GardenPlatformBootstrap,
  systemServicesPanelModel: SystemServicesPanelModel,
  alertEntries: MonitoringConsoleEventEntry[],
  latestActivity: string,
): MonitoringConsoleMonitoringPanel {
  const healthyServices = systemServicesPanelModel.services.filter((service) => service.tone === "forest").length;
  const dashboardCards: PageMetric[] = [
    {
      kind: "metric",
      label: "Catalog coverage",
      value: `${platform.catalog.summary.scope_count} scopes`,
      status: "Tracked",
      detail: `${platform.catalog.summary.connector_count} connectors and ${platform.catalog.summary.skill_count} skills`,
      icon: "layers",
      tone: "forest",
      progress: Math.min(100, platform.catalog.summary.scope_count * 8),
    },
    {
      kind: "metric",
      label: "Telemetry volume",
      value: `${platform.telemetry.length}`,
      status: platform.telemetry.length > 0 ? "Live" : "Idle",
      detail: "Signals feeding the monitoring console",
      icon: "chart",
      tone: "sky",
      progress: Math.min(100, platform.telemetry.length * 12),
    },
    {
      kind: "metric",
      label: "Automation coverage",
      value: `${platform.catalog.summary.automation_definition_count}`,
      status: "Tracked",
      detail: `${platform.catalog.summary.service_action_count} service actions available`,
      icon: "spark",
      tone: "sage",
      progress: Math.min(100, platform.catalog.summary.automation_definition_count * 14),
    },
    {
      kind: "metric",
      label: "Alert rules",
      value: `${platform.alertPolicies.length}`,
      status: platform.alertPolicies.length > 0 ? "Configured" : "Idle",
      detail: "Policies backing the alerting surface",
      icon: "alert",
      tone: "amber",
      progress: Math.min(100, platform.alertPolicies.length * 20),
    },
  ];

  return {
    tabLabel: "Monitoring",
    title: "Cloud-style monitoring",
    status: "Healthy",
    detail: "Cloud Monitoring-inspired health cards, incidents, and a secondary system-services diagnostics card.",
    metrics: [
      {
        kind: "metric",
        label: "Services healthy",
        value: `${healthyServices}/${systemServicesPanelModel.services.length}`,
        status: healthyServices === systemServicesPanelModel.services.length ? "Healthy" : "Watch",
        detail: "Shared system_services payload from bootstrap or catalog",
        icon: "health",
        tone: healthyServices === systemServicesPanelModel.services.length ? "forest" : "amber",
        progress: systemServicesPanelModel.services.length > 0 ? Math.round((healthyServices / systemServicesPanelModel.services.length) * 100) : 0,
      },
      {
        kind: "metric",
        label: "Incidents",
        value: String(alertEntries.filter((entry) => entry.status === "open").length),
        status: alertEntries.some((entry) => entry.status === "open") ? "Watch" : "Stable",
        detail: "Open alerts surfaced as incidents in monitoring",
        icon: "alert",
        tone: "amber",
        progress: Math.min(100, alertEntries.filter((entry) => entry.status === "open").length * 25),
      },
      {
        kind: "metric",
        label: "Latest activity",
        value: latestActivity,
        status: "Live",
        detail: "Most recent platform update across monitoring surfaces",
        icon: "clock",
        tone: "sky",
        progress: 92,
      },
    ],
    dashboards: dashboardCards,
    incidents: alertEntries.slice(0, 4),
    services: systemServicesPanelModel.services,
    actions: [
      { label: "Review incidents", primary: true, icon: "alert" },
      { label: "Refresh diagnostics", icon: "health" },
      { label: "Open system services", icon: "network" },
    ],
    calloutLabel: "Monitoring",
    calloutTitle: "System services remain secondary diagnostics",
    calloutBody:
      "The Postgres, API, platform catalog, telemetry, and event-stream status cards stay available here without taking over the page mode.",
    calloutMeta: `Updated ${latestActivity}`,
  };
}

function buildAlertingPanelModel(
  platform: GardenPlatformBootstrap,
  alertEntries: MonitoringConsoleEventEntry[],
  policyEntries: MonitoringConsolePolicyEntry[],
  channelEntries: MonitoringConsoleChannelEntry[],
  latestActivity: string,
): MonitoringConsoleAlertingPanel {
  const activeAlerts = alertEntries.filter((entry) => entry.status === "open" || entry.status === "acknowledged");
  const activePolicies = policyEntries.filter((policy) => policy.status === "Active");

  return {
    tabLabel: "Alerting",
    title: "Alerting center",
    status: activeAlerts.length > 0 ? "Watch" : "Healthy",
    detail: "Active alerts, policy summaries, notification channels, and recent incident history.",
    metrics: [
      {
        kind: "metric",
        label: "Active alerts",
        value: String(activeAlerts.length),
        status: activeAlerts.length > 0 ? "Watch" : "Healthy",
        detail: "Alerts needing an operator decision",
        icon: "alert",
        tone: "amber",
        progress: Math.min(100, activeAlerts.length * 25),
      },
      {
        kind: "metric",
        label: "Policies",
        value: String(activePolicies.length),
        status: activePolicies.length > 0 ? "Configured" : "Idle",
        detail: "Alert policies driving the current rules",
        icon: "bellOutline",
        tone: "forest",
        progress: Math.min(100, activePolicies.length * 20),
      },
      {
        kind: "metric",
        label: "Channels",
        value: String(channelEntries.length),
        status: channelEntries.length > 0 ? "Ready" : "Idle",
        detail: "Notification and email connectors",
        icon: "network",
        tone: "sky",
        progress: Math.min(100, channelEntries.length * 20),
      },
    ],
    alerts: alertEntries,
    policies: policyEntries,
    channels: channelEntries,
    incidents: alertEntries.slice(0, 4),
    actions: [
      { label: "Create policy", primary: true, icon: "add" },
      { label: "Review channels", icon: "network" },
      { label: "Acknowledge", icon: "bellOutline" },
    ],
    calloutLabel: "Alerting",
    calloutTitle: "Routes to notification and email connectors",
    calloutBody:
      "Alert policies are visible here alongside the connectors that can deliver them, so the UI owns the full alerting loop.",
    calloutMeta: `Updated ${latestActivity} · ${platform.alerts.length} alerts visible`,
  };
}

function buildConsoleModeSummaries(model: MonitoringConsoleModel): MonitoringConsoleModeSummary[] {
  return [
    {
      id: "logging",
      label: model.loggingPanel.tabLabel,
      title: model.loggingPanel.title,
      detail: model.loggingPanel.detail,
      icon: "queue",
      tone: "sage",
      count: String(model.loggingPanel.entries.length),
      status: model.loggingPanel.status,
    },
    {
      id: "telemetry",
      label: model.telemetryPanel.tabLabel,
      title: model.telemetryPanel.title,
      detail: model.telemetryPanel.detail,
      icon: "chart",
      tone: "sky",
      count: String(model.telemetryPanel.signals.length),
      status: model.telemetryPanel.status,
    },
    {
      id: "monitoring",
      label: model.monitoringPanel.tabLabel,
      title: model.monitoringPanel.title,
      detail: model.monitoringPanel.detail,
      icon: "health",
      tone: "forest",
      count: String(model.monitoringPanel.incidents.length + model.monitoringPanel.services.length),
      status: model.monitoringPanel.status,
    },
    {
      id: "alerting",
      label: model.alertingPanel.tabLabel,
      title: model.alertingPanel.title,
      detail: model.alertingPanel.detail,
      icon: "alert",
      tone: "amber",
      count: String(model.alertingPanel.alerts.length),
      status: model.alertingPanel.status,
    },
  ];
}

function buildConsoleAlertPolicyMap(platform: GardenPlatformBootstrap): Map<string, GardenPlatformAlertPolicy> {
  return new Map(platform.alertPolicies.map((policy) => [policy.id, policy] as const));
}

function buildConsoleMonitoringModel(
  platform: GardenPlatformBootstrap,
  systemServices: GardenSystemServices | null,
): MonitoringConsoleModel {
  const policyById = buildConsoleAlertPolicyMap(platform);
  const allEntries = buildPlatformConsoleEntries(platform, policyById);
  const telemetryEntries = allEntries.filter((entry) => entry.kind === "telemetry");
  const alertEntries = allEntries.filter((entry) => entry.kind === "alert");
  const changeSetEntries = allEntries.filter((entry) => entry.kind === "change-set");
  const automationEntries = allEntries.filter((entry) => entry.kind === "automation");
  const latestStamp =
    allEntries[0]?.timestamp
    ?? platform.telemetry[0]?.occurred_at
    ?? platform.alerts[0]?.opened_at
    ?? platform.changeSets[0]?.created_at
    ?? platform.automationRuns[0]?.created_at
    ?? null;
  const latestActivity = latestStamp ? formatElapsed(latestStamp) : "just now";
  const systemServicesPanelModel = buildSystemServicesPanel(systemServices, latestActivity);
  const loggingPanel = buildLoggingPanelModel(
    platform,
    allEntries,
    alertEntries,
    telemetryEntries,
    changeSetEntries,
    automationEntries,
    latestActivity,
  );
  const telemetryPanel = buildTelemetryPanelModel(telemetryEntries, loggingPanel.entries, latestActivity);
  const monitoringPanel = buildMonitoringPanelModel(platform, systemServicesPanelModel, alertEntries, latestActivity);
  const alertingPanel = buildAlertingPanelModel(
    platform,
    alertEntries,
    platform.alertPolicies.map((policy) => buildConsolePolicyEntry(policy)),
    platform.catalog.connectors
      .filter((connector) => connector.connector_kind === "notification" || connector.connector_kind === "email")
      .map((connector) => buildConsoleChannelEntry(connector, latestActivity)),
    latestActivity,
  );
  const model: MonitoringConsoleModel = {
    modeSummaries: [],
    loggingPanel,
    telemetryPanel,
    monitoringPanel,
    alertingPanel,
    systemServicesPanel: systemServicesPanelModel,
  };

  model.modeSummaries = buildConsoleModeSummaries(model);
  return model;
}

function createFallbackMonitoringConsoleModel(systemServices: GardenSystemServices | null): MonitoringConsoleModel {
  const now = Date.now();
  const sampleLogEntries: MonitoringConsoleEventEntry[] = [
    {
      id: "fallback-log-1",
      kind: "log",
      icon: "queue",
      tone: "sage",
      title: "Fallback shell ready",
      detail: "The monitoring page is rendering from the local fallback model.",
      meta: buildConsoleEntryMeta(new Date(now - 2 * 60 * 1000).toISOString(), "fallback", null, "Shell"),
      source: "fallback",
      severity: "info",
      eventType: "fallback.shell",
      timestamp: new Date(now - 2 * 60 * 1000).toISOString(),
      traceId: null,
      correlationId: null,
      payloadSummary: "Fallback monitoring console loaded.",
    },
    {
      id: "fallback-log-2",
      kind: "telemetry",
      icon: "chart",
      tone: "sky",
      title: "Telemetry snapshot",
      detail: "Sample telemetry rows keep the layout readable without backend data.",
      meta: buildConsoleEntryMeta(new Date(now - 7 * 60 * 1000).toISOString(), "fallback", null, "Telemetry"),
      source: "fallback",
      severity: "info",
      eventType: "telemetry.recorded",
      timestamp: new Date(now - 7 * 60 * 1000).toISOString(),
      traceId: null,
      correlationId: null,
      payloadSummary: "Fallback telemetry row.",
    },
    {
      id: "fallback-log-3",
      kind: "alert",
      icon: "alert",
      tone: "amber",
      title: "Open alert preview",
      detail: "A sample alert row keeps the alerting surface consistent in fallback mode.",
      meta: buildConsoleEntryMeta(new Date(now - 16 * 60 * 1000).toISOString(), "fallback", null, "Open"),
      source: "fallback",
      severity: "warning",
      eventType: "alert.opened",
      timestamp: new Date(now - 16 * 60 * 1000).toISOString(),
      traceId: null,
      correlationId: null,
      payloadSummary: "Fallback alert row.",
      status: "open",
      policyId: "fallback-policy",
      policyLabel: "Fallback policy",
      scopeLabel: "workspace",
      openedAt: new Date(now - 16 * 60 * 1000).toISOString(),
    },
    {
      id: "fallback-log-4",
      kind: "change-set",
      icon: "notebook",
      tone: "forest",
      title: "Change set preview",
      detail: "Change-set rows stay visible even when bootstrap data is unavailable.",
      meta: buildConsoleEntryMeta(new Date(now - 23 * 60 * 1000).toISOString(), "fallback", null, "Change set"),
      source: "fallback",
      severity: "info",
      eventType: "changeset.updated",
      timestamp: new Date(now - 23 * 60 * 1000).toISOString(),
      traceId: null,
      correlationId: null,
      payloadSummary: "Fallback change set row.",
    },
  ];
  const fallbackTelemetryEntries = sampleLogEntries.filter((entry) => entry.kind === "telemetry");
  const fallbackAlertEntries = sampleLogEntries.filter((entry) => entry.kind === "alert");
  const fallbackPolicyEntries: MonitoringConsolePolicyEntry[] = [
    {
      id: "fallback-policy-1",
      kind: "policy",
      icon: "bellOutline",
      tone: "amber",
      title: "Fallback critical alerts",
      detail: "Keep severe alerts visible.",
      meta: buildConsoleEntryMeta(new Date(now - 18 * 60 * 1000).toISOString(), "fallback", null, "Active"),
      source: "fallback",
      severity: "critical",
      eventType: "alert.policy",
      timestamp: new Date(now - 18 * 60 * 1000).toISOString(),
      traceId: null,
      correlationId: null,
      payloadSummary: "Fallback alert policy.",
      status: "Active",
      policyId: "fallback-policy-1",
      policyLabel: "Fallback critical alerts",
      rule: "severity >= critical",
      connectorKind: "notification",
    },
    {
      id: "fallback-policy-2",
      kind: "policy",
      icon: "bellOutline",
      tone: "forest",
      title: "Fallback telemetry warning",
      detail: "Keep warning telemetry on the screen.",
      meta: buildConsoleEntryMeta(new Date(now - 21 * 60 * 1000).toISOString(), "fallback", null, "Active"),
      source: "fallback",
      severity: "warning",
      eventType: "alert.policy",
      timestamp: new Date(now - 21 * 60 * 1000).toISOString(),
      traceId: null,
      correlationId: null,
      payloadSummary: "Fallback telemetry policy.",
      status: "Active",
      policyId: "fallback-policy-2",
      policyLabel: "Fallback telemetry warning",
      rule: "event_kind contains telemetry",
      connectorKind: "email",
    },
  ];
  const fallbackChannelEntries: MonitoringConsoleChannelEntry[] = [
    {
      id: "fallback-channel-1",
      kind: "channel",
      icon: "bell",
      tone: "forest",
      title: "Notifications",
      detail: "Push notification delivery for alerts.",
      meta: "notification · fallback · online only · Fallback",
      source: "fallback",
      severity: "info",
      eventType: "connector",
      timestamp: new Date(now - 5 * 60 * 1000).toISOString(),
      traceId: null,
      correlationId: null,
      payloadSummary: "Fallback notification channel.",
      status: "Live",
      connectorKind: "notification",
    },
    {
      id: "fallback-channel-2",
      kind: "channel",
      icon: "bellOutline",
      tone: "amber",
      title: "Email",
      detail: "Outbound email delivery for approvals and alerts.",
      meta: "email · fallback · online only · Fallback",
      source: "fallback",
      severity: "info",
      eventType: "connector",
      timestamp: new Date(now - 4 * 60 * 1000).toISOString(),
      traceId: null,
      correlationId: null,
      payloadSummary: "Fallback email channel.",
      status: "Live",
      connectorKind: "email",
    },
  ];
  const loggingPanel: MonitoringConsoleLoggingPanel = {
    tabLabel: "Logging",
    title: "Logs Explorer",
    status: "Fallback",
    detail: "Local sample rows keep the logging layout usable when the backend is offline.",
    queryLabel: "Query",
    queryPlaceholder: "Search logs, traces, event types, and sources",
    queryValue: "kind:telemetry OR kind:alert",
    savedQueries: buildConsoleSavedQueries(
      sampleLogEntries,
      fallbackTelemetryEntries,
      fallbackAlertEntries,
      sampleLogEntries.filter((entry) => entry.kind === "change-set"),
      sampleLogEntries.filter((entry) => entry.kind === "automation"),
    ),
    fields: buildConsoleFieldSummaries(sampleLogEntries),
    timeline: buildConsoleTimeline(sampleLogEntries.map((entry) => entry.timestamp), "forest"),
    entries: sampleLogEntries,
    metrics: [
      {
        kind: "metric",
        label: "Rows",
        value: String(sampleLogEntries.length),
        status: "Fallback",
        detail: "Sample rows only",
        icon: "queue",
        tone: "sage",
        progress: 24,
      },
      {
        kind: "metric",
        label: "Trace links",
        value: "0",
        status: "Fallback",
        detail: "No backend trace identifiers",
        icon: "spark",
        tone: "sky",
        progress: 0,
      },
      {
        kind: "metric",
        label: "Open alerts",
        value: "1",
        status: "Fallback",
        detail: "One sample alert keeps the shell legible",
        icon: "alert",
        tone: "amber",
        progress: 25,
      },
    ],
    actions: [
      { label: "Share query", primary: true, icon: "network" },
      { label: "Save view", icon: "notebook" },
      { label: "Preferences", icon: "settings" },
    ],
    calloutLabel: "Logs Explorer",
    calloutTitle: "Fallback shell",
    calloutBody: "A readable sample view appears until the live platform bootstrap is available.",
    calloutMeta: "Fallback shell snapshot",
  };
  const telemetryPanel: MonitoringConsoleTelemetryPanel = {
    tabLabel: "Telemetry",
    title: "Metrics Explorer",
    status: "Fallback",
    detail: "Sample telemetry keeps the chart scaffolding in place.",
    metrics: [
      {
        kind: "metric",
        label: "Signals",
        value: String(fallbackTelemetryEntries.length),
        status: "Fallback",
        detail: "Sample telemetry signals",
        icon: "chart",
        tone: "sky",
        progress: 32,
      },
      {
        kind: "metric",
        label: "Trace links",
        value: "0",
        status: "Fallback",
        detail: "No trace identifiers in sample data",
        icon: "spark",
        tone: "forest",
        progress: 0,
      },
      {
        kind: "metric",
        label: "Warnings",
        value: "0",
        status: "Fallback",
        detail: "Sample data stays calm",
        icon: "alert",
        tone: "amber",
        progress: 0,
      },
    ],
    timeline: buildConsoleTimeline(fallbackTelemetryEntries.map((entry) => entry.timestamp), "sky"),
    signals: fallbackTelemetryEntries,
    actions: [
      { label: "Open traces", primary: true, icon: "spark" },
      { label: "Correlate logs", icon: "queue" },
      { label: "Export sample", icon: "reports" },
    ],
    calloutLabel: "Trace Explorer",
    calloutTitle: "Fallback correlations",
    calloutBody: "When the backend is offline, the telemetry panel keeps the split-view shell and chart hierarchy intact.",
    calloutMeta: "Fallback shell snapshot",
  };
  const systemServicesPanelModel = buildSystemServicesPanel(systemServices, "just now");
  const monitoringPanel: MonitoringConsoleMonitoringPanel = {
    tabLabel: "Monitoring",
    title: "Cloud-style monitoring",
    status: "Fallback",
    detail: "Health cards and diagnostics stay visible without pretending the backend is live.",
    metrics: [
      {
        kind: "metric",
        label: "Services healthy",
        value: `${systemServicesPanelModel.services.filter((service) => service.tone === "forest").length}/${systemServicesPanelModel.services.length}`,
        status: "Fallback",
        detail: "Derived from the fallback service snapshot",
        icon: "health",
        tone: "forest",
        progress: 100,
      },
      {
        kind: "metric",
        label: "Incidents",
        value: String(fallbackAlertEntries.filter((entry) => entry.status === "open").length),
        status: "Fallback",
        detail: "Sample incident rows",
        icon: "alert",
        tone: "amber",
        progress: 25,
      },
      {
        kind: "metric",
        label: "Latest activity",
        value: "just now",
        status: "Fallback",
        detail: "Fallback snapshot",
        icon: "clock",
        tone: "sky",
        progress: 92,
      },
    ],
    dashboards: [
      {
        kind: "metric",
        label: "Catalog coverage",
        value: "Fallback",
        status: "Sample",
        detail: "Placeholder summary while offline",
        icon: "layers",
        tone: "forest",
        progress: 45,
      },
      {
        kind: "metric",
        label: "Telemetry volume",
        value: "Fallback",
        status: "Sample",
        detail: "Placeholder summary while offline",
        icon: "chart",
        tone: "sky",
        progress: 45,
      },
      {
        kind: "metric",
        label: "Automation coverage",
        value: "Fallback",
        status: "Sample",
        detail: "Placeholder summary while offline",
        icon: "spark",
        tone: "sage",
        progress: 45,
      },
      {
        kind: "metric",
        label: "Alert rules",
        value: "Fallback",
        status: "Sample",
        detail: "Placeholder summary while offline",
        icon: "alert",
        tone: "amber",
        progress: 45,
      },
    ],
    incidents: fallbackAlertEntries,
    services: systemServicesPanelModel.services,
    actions: [
      { label: "Review incidents", primary: true, icon: "alert" },
      { label: "Refresh diagnostics", icon: "health" },
      { label: "Open system services", icon: "network" },
    ],
    calloutLabel: "Monitoring",
    calloutTitle: "System services stay in the monitoring section",
    calloutBody: "This fallback view mirrors the production layout while waiting for live backend state.",
    calloutMeta: "Fallback shell snapshot",
  };
  const alertingPanel: MonitoringConsoleAlertingPanel = {
    tabLabel: "Alerting",
    title: "Alerting center",
    status: "Fallback",
    detail: "Alert rows, policy summaries, and channels stay visible without backend data.",
    metrics: [
      {
        kind: "metric",
        label: "Active alerts",
        value: String(fallbackAlertEntries.filter((entry) => entry.status === "open").length),
        status: "Fallback",
        detail: "Sample alerts only",
        icon: "alert",
        tone: "amber",
        progress: 25,
      },
      {
        kind: "metric",
        label: "Policies",
        value: String(fallbackPolicyEntries.length),
        status: "Fallback",
        detail: "Sample policy rows",
        icon: "bellOutline",
        tone: "forest",
        progress: 32,
      },
      {
        kind: "metric",
        label: "Channels",
        value: String(fallbackChannelEntries.length),
        status: "Fallback",
        detail: "Sample notification endpoints",
        icon: "network",
        tone: "sky",
        progress: 32,
      },
    ],
    alerts: fallbackAlertEntries,
    policies: fallbackPolicyEntries,
    channels: fallbackChannelEntries,
    incidents: fallbackAlertEntries,
    actions: [
      { label: "Create policy", primary: true, icon: "add" },
      { label: "Review channels", icon: "network" },
      { label: "Acknowledge", icon: "bellOutline" },
    ],
    calloutLabel: "Alerting",
    calloutTitle: "Fallback notification routes",
    calloutBody: "Notification and email channels remain represented so the shell keeps its operator flow.",
    calloutMeta: "Fallback shell snapshot",
  };
  const model: MonitoringConsoleModel = {
    modeSummaries: [],
    loggingPanel,
    telemetryPanel,
    monitoringPanel,
    alertingPanel,
    systemServicesPanel: systemServicesPanelModel,
  };

  model.modeSummaries = buildConsoleModeSummaries(model);
  return model;
}

export function buildMonitoringConsoleModel(
  context: GardenServiceContext | null = null,
): MonitoringConsoleModel {
  const systemServices = context?.workspace?.system_services ?? context?.platform?.catalog.system_services ?? null;

  if (context?.platform) {
    return buildConsoleMonitoringModel(context.platform, systemServices);
  }

  return createFallbackMonitoringConsoleModel(systemServices);
}

export function getMonitoringConsoleModel(
  context: GardenServiceContext | null = null,
): MonitoringConsoleModel {
  return buildMonitoringConsoleModel(context);
}
