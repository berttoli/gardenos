import type { IconName, ShellTone } from "../shared";

export type ApiMethod = "GET" | "POST" | "PATCH" | "DELETE";

export type ApiSurfaceSectionId =
  | "access"
  | "auth"
  | "onboarding"
  | "platform-catalog"
  | "platform-operations"
  | "workspace"
  | "plants"
  | "tasks"
  | "utilities";

export type ApiSurfaceEndpoint = {
  method: ApiMethod;
  path: string;
  summary: string;
};

export type ApiSurfaceSection = {
  id: ApiSurfaceSectionId;
  label: string;
  title: string;
  description: string;
  icon: IconName;
  tone: ShellTone;
  endpoints: ApiSurfaceEndpoint[];
};

export type ApiSurfaceSummary = {
  sectionCount: number;
  routeCount: number;
  readCount: number;
  writeCount: number;
  streamCount: number;
};

const accessRoutes: ApiSurfaceEndpoint[] = [
  { method: "GET", path: "/api/v1/access/context", summary: "Access Context" },
  { method: "GET", path: "/api/v1/access/permissions", summary: "Permissions Index" },
  { method: "GET", path: "/api/v1/access/permissions/{permission_identifier}", summary: "Permissions Show" },
  { method: "GET", path: "/api/v1/access/roles", summary: "Roles Index" },
  { method: "POST", path: "/api/v1/access/roles", summary: "Roles Create" },
  { method: "GET", path: "/api/v1/access/roles/{role_identifier}", summary: "Roles Show" },
  { method: "GET", path: "/api/v1/access/groups", summary: "Groups Index" },
  { method: "POST", path: "/api/v1/access/groups", summary: "Groups Create" },
  { method: "GET", path: "/api/v1/access/groups/{group_identifier}", summary: "Groups Show" },
  { method: "POST", path: "/api/v1/access/groups/{group_identifier}/members", summary: "Groups Add Member" },
  { method: "POST", path: "/api/v1/access/groups/{group_identifier}/roles", summary: "Groups Add Role" },
  { method: "GET", path: "/api/v1/access/service-accounts", summary: "Service Accounts Index" },
  { method: "POST", path: "/api/v1/access/service-accounts", summary: "Service Accounts Create" },
  { method: "GET", path: "/api/v1/access/service-accounts/{service_account_identifier}", summary: "Service Accounts Show" },
  {
    method: "GET",
    path: "/api/v1/access/service-accounts/{service_account_identifier}/tokens",
    summary: "Service Account Tokens Index",
  },
  {
    method: "POST",
    path: "/api/v1/access/service-accounts/{service_account_identifier}/tokens",
    summary: "Service Account Tokens Create",
  },
  {
    method: "DELETE",
    path: "/api/v1/access/service-accounts/{service_account_identifier}/tokens/{token_identifier}",
    summary: "Service Account Tokens Delete",
  },
];

const authRoutes: ApiSurfaceEndpoint[] = [
  { method: "GET", path: "/api/v1/auth/session", summary: "Session Status" },
  { method: "GET", path: "/api/v1/auth/context", summary: "Auth Context" },
  { method: "POST", path: "/api/v1/auth/login", summary: "Login" },
  { method: "POST", path: "/api/v1/auth/logout", summary: "Logout" },
];

const onboardingRoutes: ApiSurfaceEndpoint[] = [
  { method: "POST", path: "/api/v1/onboarding/drafts", summary: "Onboarding Create Draft" },
  { method: "GET", path: "/api/v1/onboarding/drafts/{draft_token}", summary: "Onboarding Get Draft" },
  {
    method: "PATCH",
    path: "/api/v1/onboarding/drafts/{draft_token}/steps/{step}",
    summary: "Onboarding Save Step",
  },
  { method: "POST", path: "/api/v1/onboarding/drafts/{draft_token}/media", summary: "Onboarding Upload Media" },
  { method: "POST", path: "/api/v1/onboarding/drafts/{draft_token}/complete", summary: "Onboarding Complete" },
  { method: "POST", path: "/api/v1/onboarding/drafts/{draft_token}/abandon", summary: "Onboarding Abandon" },
];

const platformCatalogRoutes: ApiSurfaceEndpoint[] = [
  { method: "GET", path: "/api/v1/platform/catalog", summary: "Catalog Index" },
  { method: "GET", path: "/api/v1/platform/scopes", summary: "Scopes Index" },
  { method: "POST", path: "/api/v1/platform/scopes", summary: "Scopes Create" },
  { method: "GET", path: "/api/v1/platform/scope-memberships", summary: "Scope Memberships Index" },
  { method: "POST", path: "/api/v1/platform/scope-memberships", summary: "Scope Memberships Create" },
  { method: "GET", path: "/api/v1/platform/skills", summary: "Skills Index" },
  { method: "POST", path: "/api/v1/platform/skills", summary: "Skills Create" },
  { method: "GET", path: "/api/v1/platform/connectors", summary: "Connectors Index" },
  { method: "POST", path: "/api/v1/platform/connectors", summary: "Connectors Create" },
  { method: "GET", path: "/api/v1/platform/connector-instances", summary: "Connector Instances Index" },
  { method: "POST", path: "/api/v1/platform/connector-instances", summary: "Connector Instances Create" },
  { method: "GET", path: "/api/v1/platform/service-actions", summary: "Service Actions Index" },
  { method: "POST", path: "/api/v1/platform/service-actions", summary: "Service Actions Create" },
  { method: "GET", path: "/api/v1/platform/automations", summary: "Automations Index" },
  { method: "POST", path: "/api/v1/platform/automations", summary: "Automations Create" },
  {
    method: "POST",
    path: "/api/v1/platform/automations/{automation_definition_id}/versions",
    summary: "Automation Versions Create",
  },
];

const platformOperationsRoutes: ApiSurfaceEndpoint[] = [
  { method: "GET", path: "/api/v1/platform/schedule-rules", summary: "Schedule Rules Index" },
  { method: "POST", path: "/api/v1/platform/schedule-rules", summary: "Schedule Rules Create" },
  { method: "GET", path: "/api/v1/platform/telemetry", summary: "Telemetry Index" },
  { method: "POST", path: "/api/v1/platform/telemetry", summary: "Telemetry Create" },
  { method: "GET", path: "/api/v1/platform/system-services", summary: "System Services Snapshot" },
  { method: "POST", path: "/api/v1/platform/assistant/chat", summary: "Assistant Chat" },
  { method: "GET", path: "/api/v1/platform/telemetry/{telemetry_event_id}", summary: "Telemetry Show" },
  { method: "GET", path: "/api/v1/platform/calendar", summary: "Calendar Index" },
  { method: "GET", path: "/api/v1/platform/events", summary: "Events Index" },
  { method: "GET", path: "/api/v1/platform/events/stream", summary: "Events Stream" },
  { method: "GET", path: "/api/v1/platform/automation-runs", summary: "Automation Runs Index" },
  { method: "POST", path: "/api/v1/platform/automation-runs", summary: "Automation Runs Create" },
  { method: "GET", path: "/api/v1/platform/automation-run-events", summary: "Automation Run Events Index" },
  {
    method: "POST",
    path: "/api/v1/platform/automation-runs/{automation_run_id}/events",
    summary: "Automation Run Events Create",
  },
  { method: "GET", path: "/api/v1/platform/alert-policies", summary: "Alert Policies Index" },
  { method: "POST", path: "/api/v1/platform/alert-policies", summary: "Alert Policies Create" },
  { method: "GET", path: "/api/v1/platform/alerts", summary: "Alerts Index" },
  { method: "POST", path: "/api/v1/platform/alerts", summary: "Alerts Create" },
  { method: "GET", path: "/api/v1/platform/alerts/{alert_id}", summary: "Alerts Show" },
  { method: "POST", path: "/api/v1/platform/alerts/{alert_id}/acknowledge", summary: "Alerts Acknowledge" },
  { method: "POST", path: "/api/v1/platform/alerts/{alert_id}/resolve", summary: "Alerts Resolve" },
  { method: "POST", path: "/api/v1/platform/alerts/{alert_id}/mute", summary: "Alerts Mute" },
  { method: "POST", path: "/api/v1/platform/alerts/{alert_id}/unmute", summary: "Alerts Unmute" },
  { method: "GET", path: "/api/v1/platform/change-sets", summary: "Change Sets Index" },
  { method: "POST", path: "/api/v1/platform/change-sets", summary: "Change Sets Create" },
  {
    method: "POST",
    path: "/api/v1/platform/change-sets/{change_set_id}/entries",
    summary: "Change Set Entries Create",
  },
];

const workspaceRoutes: ApiSurfaceEndpoint[] = [{ method: "GET", path: "/api/v1/workspace", summary: "Workspace Bootstrap" }];

const plantRoutes: ApiSurfaceEndpoint[] = [
  { method: "GET", path: "/api/v1/plants", summary: "Plants Index" },
  { method: "POST", path: "/api/v1/plants", summary: "Plant Create" },
  { method: "GET", path: "/api/v1/plants/{plant_id}", summary: "Plant Detail" },
  { method: "PATCH", path: "/api/v1/plants/{plant_id}", summary: "Plant Update" },
  { method: "POST", path: "/api/v1/plants/{plant_id}/observations", summary: "Plant Observation Create" },
  { method: "POST", path: "/api/v1/plants/{plant_id}/measurements", summary: "Plant Measurement Create" },
  { method: "POST", path: "/api/v1/plants/{plant_id}/media", summary: "Plant Media Upload" },
  { method: "POST", path: "/api/v1/plants/{plant_id}/move", summary: "Plant Move" },
  { method: "POST", path: "/api/v1/plants/{plant_id}/treatments", summary: "Plant Treatment Create" },
  { method: "POST", path: "/api/v1/plants/{plant_id}/propagations", summary: "Plant Propagation Create" },
  { method: "GET", path: "/api/v1/plants/{plant_id}/timeline", summary: "Plant Timeline" },
];

const taskRoutes: ApiSurfaceEndpoint[] = [
  { method: "GET", path: "/api/v1/tasks", summary: "Tasks Index" },
  { method: "POST", path: "/api/v1/tasks/{task_id}/complete", summary: "Task Complete" },
];

const utilityRoutes: ApiSurfaceEndpoint[] = [
  { method: "GET", path: "/api/v1/labels/{plant_id}", summary: "Label Preview" },
  { method: "GET", path: "/api/v1/labels/{plant_id}/pdf", summary: "Label Pdf" },
  { method: "POST", path: "/api/v1/propagations/{event_id}/complete", summary: "Propagation Complete" },
  { method: "POST", path: "/api/v1/propagations/{event_id}/fail", summary: "Propagation Fail" },
  { method: "GET", path: "/api/v1/conversations", summary: "Conversations Index" },
  { method: "POST", path: "/api/v1/conversations", summary: "Conversation Create" },
  { method: "GET", path: "/api/v1/conversations/{conversation_id}", summary: "Conversation Detail" },
  {
    method: "POST",
    path: "/api/v1/conversations/{conversation_id}/messages",
    summary: "Conversation Message Create",
  },
];

export const apiSurfaceSections: ApiSurfaceSection[] = [
  {
    id: "access",
    label: "Access",
    title: "Access & identity",
    description: "Roles, groups, permissions, and service accounts for operational control.",
    icon: "people",
    tone: "forest",
    endpoints: accessRoutes,
  },
  {
    id: "auth",
    label: "Auth",
    title: "Authentication",
    description: "Session status, login, logout, and current auth context.",
    icon: "spark",
    tone: "sage",
    endpoints: authRoutes,
  },
  {
    id: "onboarding",
    label: "Onboarding",
    title: "Onboarding drafts",
    description: "Draft creation, step updates, media upload, and completion flow.",
    icon: "notebook",
    tone: "amber",
    endpoints: onboardingRoutes,
  },
  {
    id: "platform-catalog",
    label: "Catalog",
    title: "Platform catalog",
    description: "Scopes, skills, connectors, service actions, and automation definitions.",
    icon: "layers",
    tone: "forest",
    endpoints: platformCatalogRoutes,
  },
  {
    id: "platform-operations",
    label: "Ops",
    title: "Platform operations",
    description: "Telemetry, calendar, event stream, alerting, and change-set control.",
    icon: "health",
    tone: "sky",
    endpoints: platformOperationsRoutes,
  },
  {
    id: "workspace",
    label: "Workspace",
    title: "Workspace bootstrap",
    description: "Bootstrap payload that hydrates the shell and selected locations.",
    icon: "dashboard",
    tone: "sage",
    endpoints: workspaceRoutes,
  },
  {
    id: "plants",
    label: "Plants",
    title: "Plant lifecycle",
    description: "Inventory, measurements, media, moves, treatments, and timeline data.",
    icon: "leaf",
    tone: "forest",
    endpoints: plantRoutes,
  },
  {
    id: "tasks",
    label: "Tasks",
    title: "Task actions",
    description: "Task listing and completion routes for the work queue.",
    icon: "tasks",
    tone: "amber",
    endpoints: taskRoutes,
  },
  {
    id: "utilities",
    label: "Utilities",
    title: "Field utilities",
    description: "Label previews, propagation outcomes, and conversations.",
    icon: "network",
    tone: "sky",
    endpoints: utilityRoutes,
  },
];

function isWriteMethod(method: ApiMethod): boolean {
  return method !== "GET";
}

export function getApiSurfaceSection(sectionId: ApiSurfaceSectionId): ApiSurfaceSection {
  return apiSurfaceSections.find((section) => section.id === sectionId) ?? apiSurfaceSections[0];
}

export function summarizeApiSurfaceSections(sections: ApiSurfaceSection[] = apiSurfaceSections): ApiSurfaceSummary {
  const endpoints = sections.flatMap((section) => section.endpoints);

  return {
    sectionCount: sections.length,
    routeCount: endpoints.length,
    readCount: endpoints.filter((endpoint) => endpoint.method === "GET").length,
    writeCount: endpoints.filter((endpoint) => isWriteMethod(endpoint.method)).length,
    streamCount: endpoints.filter((endpoint) => endpoint.path.endsWith("/stream")).length,
  };
}

export function getApiSurfaceCounts(section: ApiSurfaceSection): { readCount: number; writeCount: number; routeCount: number } {
  const readCount = section.endpoints.filter((endpoint) => endpoint.method === "GET").length;
  const writeCount = section.endpoints.length - readCount;

  return {
    readCount,
    writeCount,
    routeCount: section.endpoints.length,
  };
}

export function getApiRouteTone(method: ApiMethod): ShellTone {
  if (method === "GET") {
    return "forest";
  }

  if (method === "PATCH") {
    return "sky";
  }

  if (method === "DELETE") {
    return "amber";
  }

  return "sage";
}
