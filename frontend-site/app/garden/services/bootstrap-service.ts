import { sidebarItems } from "../shared/data";
import type { IconName, SidebarItem } from "../shared";
import {
  fetchGardenApiJson,
  requestGardenApi,
} from "./api-client";

export type GardenBootstrapSource = "fallback" | "backend";

export type GardenPrincipal = {
  kind: "user" | "service_account";
  id: string;
  label: string;
  auth_method: "session" | "service_token";
  roles: string[];
  permissions: string[];
  group_ids: string[];
  scope_ids: string[];
  username: string | null;
  service_account_slug: string | null;
  is_admin: boolean;
};

export type GardenAuthContext = {
  authenticated: boolean;
  csrf_token: string;
  user: {
    id: string;
    username: string;
    full_name: string;
    role: string;
    is_admin: boolean;
  } | null;
  principal: GardenPrincipal | null;
};

export type GardenLocationPathNode = {
  id: string;
  name: string;
  type: string;
};

export type GardenLocationNode = {
  id: string;
  parent_id: string | null;
  name: string;
  location_type: string;
  description: string | null;
  latitude: number | null;
  longitude: number | null;
  elevation: number | null;
  sun_exposure: string | null;
  wind_exposure: string | null;
  irrigation_zone: string | null;
  microclimate_notes: string | null;
  depth: number;
  path: GardenLocationPathNode[];
  direct_plant_count: number;
  plant_count: number;
  child_count: number;
  is_selected: boolean;
  children: GardenLocationNode[];
};

export type GardenWorkspaceSummary = {
  plant_count: number;
  location_count: number;
  root_location_count: number;
  due_task_count: number;
  overdue_task_count: number;
  quarantine_plant_count: number;
  follow_up_plant_count: number;
};

export type GardenWorkspaceSidebarItem = SidebarItem;

export type GardenWorkspaceBootstrap = {
  authenticated: boolean;
  principal: GardenPrincipal | null;
  selected_location_id: string | null;
  summary: GardenWorkspaceSummary;
  sidebar: GardenWorkspaceSidebarItem[];
  navigation: {
    locations: GardenLocationNode[];
  };
  system_services?: GardenSystemServices | null;
  tasks: {
    due: GardenWorkspaceTaskRecord[];
    overdue: GardenWorkspaceTaskRecord[];
    completed: GardenWorkspaceTaskRecord[];
  };
};

export type GardenWorkspaceTaskRecord = {
  id: string;
  status: "pending" | "completed" | "skipped";
  title: string | null;
  task_type: string | null;
  priority: number | null;
  scheduled_for: string;
  completed_at: string | null;
  skipped_at: string | null;
  plant_id: string | null;
  location_id: string | null;
  zone: string | null;
  completion_notes: string | null;
  performed_by: string | null;
};

export type GardenPlatformCatalogSummary = {
  scope_count: number;
  skill_count: number;
  connector_count: number;
  service_action_count: number;
  automation_definition_count: number;
};

export type GardenSystemServiceRecord = {
  status: string;
  detail?: string | null;
  details?: string | null;
  summary?: string | null;
  endpoint?: string | null;
  last_checked_at?: string | null;
  latency_ms?: number | null;
  metadata?: Record<string, unknown>;
};

export type GardenSystemServices = {
  postgres: GardenSystemServiceRecord;
  api: GardenSystemServiceRecord;
  platform_catalog: GardenSystemServiceRecord;
  telemetry: GardenSystemServiceRecord;
  event_stream: GardenSystemServiceRecord;
};

export type GardenPlatformScopeNode = {
  id: string;
  parent_id: string | null;
  scope_type: string;
  name: string;
  slug: string;
  timezone: string | null;
  metadata: Record<string, unknown>;
  source_template_id: string | null;
  is_system_template: boolean;
  archived_at: string | null;
  depth: number;
  path: Array<{ id: string; name: string; type: string }>;
  member_count: number;
  child_count: number;
  children: GardenPlatformScopeNode[];
};

export type GardenPlatformSkillDefinition = {
  id: string;
  scope_node_id: string;
  key: string;
  name: string;
  skill_kind: string;
  description: string | null;
  source_template_id: string | null;
  is_system_template: boolean;
  metadata: Record<string, unknown>;
};

export type GardenPlatformConnectorDefinition = {
  id: string;
  scope_node_id: string;
  key: string;
  name: string;
  connector_kind: string;
  description: string | null;
  auth_kind: string;
  supports_offline: boolean;
  source_template_id: string | null;
  is_system_template: boolean;
  metadata: Record<string, unknown>;
};

export type GardenPlatformServiceAction = {
  id: string;
  scope_node_id: string;
  key: string;
  name: string;
  action_kind: string;
  description: string | null;
  mutates_data: boolean;
  requires_approval: boolean;
  skill_definition_id: string | null;
  connector_definition_id: string | null;
  metadata: Record<string, unknown>;
};

export type GardenPlatformAutomationDefinition = {
  id: string;
  scope_node_id: string;
  key: string;
  name: string;
  description: string | null;
  automation_kind: string;
  status: string;
  source_template_id: string | null;
  is_system_template: boolean;
  metadata: Record<string, unknown>;
  version_count: number;
};

export type GardenPlatformTelemetryEvent = {
  id: string;
  scope_node_id: string;
  source_kind: string;
  source_id: string | null;
  event_kind: string;
  severity: string;
  occurred_at: string;
  payload: Record<string, unknown>;
};

export type GardenPlatformAlert = {
  id: string;
  alert_policy_id: string;
  telemetry_event_id: string | null;
  automation_run_event_id: string | null;
  scope_node_id: string;
  status: string;
  summary: string | null;
  opened_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
};

export type GardenPlatformAlertPolicy = {
  id: string;
  scope_node_id: string;
  key: string;
  name: string;
  source_kind: string;
  rule: string;
  severity: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type GardenPlatformChangeSet = {
  id: string;
  created_at: string;
  scope_node_id: string | null;
  key: string;
  summary: string;
  status: string;
  requested_by_user_id: string | null;
  approved_by_user_id: string | null;
  requested_at: string | null;
  approved_at: string | null;
  committed_at: string | null;
  rolled_back_at: string | null;
  reason: string | null;
  metadata: Record<string, unknown>;
  entry_count: number;
};

export type GardenPlatformAutomationRun = {
  id: string;
  created_at: string;
  scope_node_id: string | null;
  automation_version_id: string;
  schedule_rule_id: string | null;
  triggered_by: string;
  status: string;
  requested_by_user_id: string | null;
  change_set_id: string | null;
  reason: string | null;
  started_at: string | null;
  ended_at: string | null;
  metadata: Record<string, unknown>;
  event_count: number;
};

export type GardenPlatformCalendarEntry = {
  id: string;
  kind: string;
  title: string;
  start_at: string;
  end_at: string | null;
  status: string;
  scope_node_id: string | null;
  source_kind: string;
  source_id: string;
  timezone: string | null;
  metadata: Record<string, unknown>;
};

export type GardenPlatformCalendarProjection = {
  window: {
    start_at: string;
    end_at: string;
    scope_node_id: string | null;
  };
  summary: {
    entry_count: number;
    schedule_entry_count: number;
    task_entry_count: number;
    automation_entry_count: number;
    truncated: boolean;
  };
  entries: GardenPlatformCalendarEntry[];
};

export type GardenPlatformCatalog = {
  scopes: GardenPlatformScopeNode[];
  skills: GardenPlatformSkillDefinition[];
  connectors: GardenPlatformConnectorDefinition[];
  service_actions: GardenPlatformServiceAction[];
  automation_definitions: GardenPlatformAutomationDefinition[];
  system_services?: GardenSystemServices | null;
  summary: GardenPlatformCatalogSummary;
};

export type GardenPlatformBootstrap = {
  catalog: GardenPlatformCatalog;
  calendar: GardenPlatformCalendarProjection | null;
  alertPolicies: GardenPlatformAlertPolicy[];
  telemetry: GardenPlatformTelemetryEvent[];
  alerts: GardenPlatformAlert[];
  automationRuns: GardenPlatformAutomationRun[];
  changeSets: GardenPlatformChangeSet[];
};

export type GardenBootstrapState = {
  source: GardenBootstrapSource;
  auth: GardenAuthContext | null;
  workspace: GardenWorkspaceBootstrap | null;
  platform: GardenPlatformBootstrap | null;
};

export type GardenAccountMenuModel = {
  title: string;
  subtitle: string;
  initials: string;
};

export type GardenNurseryOption = {
  id: string;
  label: string;
  detail: string;
  pill: string;
  icon: IconName;
  active: boolean;
};

export type GardenNurseryMenuModel = {
  title: string;
  subtitle: string;
  options: GardenNurseryOption[];
};

export function createFallbackBootstrap(): GardenBootstrapState {
  return {
    source: "fallback",
    auth: null,
    workspace: null,
    platform: null,
  };
}

async function loadGardenWorkspaceBootstrap(requireWorkspace = false): Promise<GardenWorkspaceBootstrap | null> {
  try {
    return await fetchGardenApiJson<GardenWorkspaceBootstrap>("/workspace");
  } catch (error) {
    if (requireWorkspace) {
      throw error;
    }
    return null;
  }
}

async function loadGardenPlatformBootstrap(): Promise<GardenPlatformBootstrap | null> {
  try {
    const catalog = await fetchGardenApiJson<GardenPlatformCatalog>("/platform/catalog");
    const [calendarResult, alertPoliciesResult, telemetryResult, alertsResult, runsResult, changeSetsResult] =
      await Promise.allSettled([
        fetchGardenApiJson<GardenPlatformCalendarProjection>("/platform/calendar"),
        fetchGardenApiJson<GardenPlatformAlertPolicy[]>("/platform/alert-policies"),
        fetchGardenApiJson<GardenPlatformTelemetryEvent[]>("/platform/telemetry"),
        fetchGardenApiJson<GardenPlatformAlert[]>("/platform/alerts"),
        fetchGardenApiJson<GardenPlatformAutomationRun[]>("/platform/automation-runs"),
        fetchGardenApiJson<GardenPlatformChangeSet[]>("/platform/change-sets"),
      ]);

    return {
      catalog,
      calendar: calendarResult.status === "fulfilled" ? calendarResult.value : null,
      alertPolicies: alertPoliciesResult.status === "fulfilled" ? alertPoliciesResult.value : [],
      telemetry: telemetryResult.status === "fulfilled" ? telemetryResult.value : [],
      alerts: alertsResult.status === "fulfilled" ? alertsResult.value : [],
      automationRuns: runsResult.status === "fulfilled" ? runsResult.value : [],
      changeSets: changeSetsResult.status === "fulfilled" ? changeSetsResult.value : [],
    };
  } catch {
    return null;
  }
}

export async function loadGardenBootstrap({ requireWorkspace = false } = {}): Promise<GardenBootstrapState> {
  try {
    const auth = await fetchGardenApiJson<GardenAuthContext>("/auth/context");

    if (!auth.authenticated || auth.principal == null) {
      if (requireWorkspace) {
        throw new Error("Sign in again to refresh your tasks.");
      }
      return { ...createFallbackBootstrap(), auth };
    }

    const [workspace, platform] = await Promise.all([
      loadGardenWorkspaceBootstrap(requireWorkspace),
      loadGardenPlatformBootstrap(),
    ]);

    return {
      source: "backend",
      auth,
      workspace,
      platform,
    };
  } catch (error) {
    if (requireWorkspace) {
      throw error;
    }
    return createFallbackBootstrap();
  }
}

export async function logoutGardenSession(csrfToken: string): Promise<void> {
  const response = await requestGardenApi("/auth/logout", {
    body: JSON.stringify({ csrf_token: csrfToken }),
    headers: {
      "content-type": "application/json",
      "x-csrf-token": csrfToken,
    },
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`GardenOS logout failed with status ${response.status}.`);
  }
}

export async function signInGardenSession(username: string, password: string): Promise<void> {
  const auth = await fetchGardenApiJson<GardenAuthContext>("/auth/context");
  if (!auth.csrf_token) {
    throw new Error("Could not start a secure sign-in session. Please try again.");
  }
  const response = await requestGardenApi("/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json", "x-csrf-token": auth.csrf_token },
    body: JSON.stringify({ username: username.trim(), password, csrf_token: auth.csrf_token }),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("The username or password was not accepted.");
    if (response.status === 429) throw new Error("Too many sign-in attempts. Wait before trying again.");
    throw new Error("Sign-in failed. Please try again.");
  }
}

export function buildSidebarItems(
  workspace: GardenWorkspaceBootstrap | null,
  platform: GardenPlatformBootstrap | null = null,
): SidebarItem[] {
  const items = sidebarItems.map((item) => ({ ...item }));

  if (!workspace) {
    return items.map((item) => {
      if (item.page === "tasks") {
        return { ...item, badge: undefined };
      }

      if (item.page === "schedule") {
        const scheduleCount = platform?.calendar?.summary.entry_count ?? 0;
        return scheduleCount > 0 ? { ...item, badge: String(scheduleCount) } : item;
      }

      if (item.page === "automations") {
        const automationCount = platform?.catalog.summary.automation_definition_count ?? 0;
        return automationCount > 0 ? { ...item, badge: String(automationCount) } : item;
      }

      if (item.page === "monitoring") {
        const openAlertCount = platform?.alerts.filter((alert) => alert.status === "open").length ?? 0;
        return openAlertCount > 0 ? { ...item, badge: String(openAlertCount) } : item;
      }

      if (item.page === "reports") {
        const changeSetCount = platform?.changeSets.length ?? 0;
        return changeSetCount > 0 ? { ...item, badge: String(changeSetCount) } : item;
      }

      return item;
    });
  }

  const taskCount = workspace.summary.due_task_count;
  const scheduleCount = platform?.calendar?.summary.entry_count ?? 0;
  const automationCount = platform?.catalog.summary.automation_definition_count ?? 0;
  const openAlertCount = platform?.alerts.filter((alert) => alert.status === "open").length ?? 0;
  const changeSetCount = platform?.changeSets.length ?? 0;

  return items.map((item) => {
    if (item.page !== "tasks") {
      if (item.page === "schedule" && scheduleCount > 0) {
        return {
          ...item,
          badge: String(scheduleCount),
        };
      }

      if (item.page === "automations" && automationCount > 0) {
        return {
          ...item,
          badge: String(automationCount),
        };
      }

      if (item.page === "monitoring" && openAlertCount > 0) {
        return {
          ...item,
          badge: String(openAlertCount),
        };
      }

      if (item.page === "reports" && changeSetCount > 0) {
        return {
          ...item,
          badge: String(changeSetCount),
        };
      }

      return item;
    }

    return {
      ...item,
      badge: taskCount > 0 ? String(taskCount) : undefined,
    };
  });
}

function getInitials(label: string, fallback: string): string {
  const parts = label
    .trim()
    .split(/\s+/)
    .map((part) => part[0]?.toUpperCase())
    .filter((part): part is string => Boolean(part));

  if (parts.length === 0) {
    return fallback;
  }

  return parts.slice(0, 2).join("");
}

export function buildAccountMenuModel(auth: GardenAuthContext | null): GardenAccountMenuModel {
  const principal = auth?.principal;
  if (!principal) {
    return {
      title: "Demo User",
      subtitle: "Signed out",
      initials: "DU",
    };
  }

  const title = principal.label.trim() || "Demo User";
  return {
    title,
    subtitle:
      principal.kind === "service_account"
        ? "Service account active"
        : principal.is_admin
          ? "Signed in as admin"
          : "Signed in and ready",
    initials: getInitials(title, principal.kind === "service_account" ? "SA" : "DU"),
  };
}

function collectLocationNodes(nodes: GardenLocationNode[]): GardenLocationNode[] {
  return nodes.flatMap((node) => [node, ...collectLocationNodes(node.children)]);
}

function findLocationNodeById(nodes: GardenLocationNode[], locationId: string | null | undefined): GardenLocationNode | null {
  if (!locationId) {
    return null;
  }

  for (const node of nodes) {
    if (node.id === locationId) {
      return node;
    }

    const match = findLocationNodeById(node.children, locationId);
    if (match) {
      return match;
    }
  }

  return null;
}

function countSubtreeLocations(node: GardenLocationNode): number {
  return 1 + node.children.reduce((total, child) => total + countSubtreeLocations(child), 0);
}

function fallbackNurseryOptions(): GardenNurseryOption[] {
  return [
    {
      id: "demo-garden",
      label: "Demo Garden",
      detail: "Primary operations",
      pill: "Active",
      icon: "leaf",
      active: true,
    },
    {
      id: "demo-annex",
      label: "Demo Annex",
      detail: "Shared access",
      pill: "Team",
      icon: "map",
      active: false,
    },
  ];
}

export function buildNurseryMenuModel(workspace: GardenWorkspaceBootstrap | null): GardenNurseryMenuModel {
  if (!workspace) {
    return {
      title: "Demo Garden",
      subtitle: "Example workspace",
      options: fallbackNurseryOptions(),
    };
  }

  const allLocations = collectLocationNodes(workspace.navigation.locations);
  const nurseries = allLocations.filter((node) => node.location_type === "nursery");
  const selectedNode = findLocationNodeById(workspace.navigation.locations, workspace.selected_location_id);
  const activeNurseryId = selectedNode?.path
    .slice()
    .reverse()
    .find((step) => step.type === "nursery")?.id;
  const activeNursery =
    findLocationNodeById(workspace.navigation.locations, activeNurseryId) ??
    nurseries[0] ??
    workspace.navigation.locations[0] ??
    null;

  if (!activeNursery) {
    return {
      title: "Demo Garden",
      subtitle: "Example workspace",
      options: fallbackNurseryOptions(),
    };
  }

  const nurseryOptions = (nurseries.length > 0 ? nurseries : workspace.navigation.locations)
    .slice()
    .sort((left, right) => left.name.localeCompare(right.name))
    .slice(0, 4)
    .map<GardenNurseryOption>((node) => ({
      id: node.id,
      label: node.name,
      detail: `${countSubtreeLocations(node)} locations · ${node.plant_count} plants`,
      pill: node.id === activeNursery.id ? "Active" : "Team",
      icon: node.id === activeNursery.id ? "leaf" : "map",
      active: node.id === activeNursery.id,
    }));

  return {
    title: activeNursery.name,
    subtitle: `${countSubtreeLocations(activeNursery)} locations · ${activeNursery.plant_count} plants`,
    options: nurseryOptions.length > 0 ? nurseryOptions : fallbackNurseryOptions(),
  };
}
