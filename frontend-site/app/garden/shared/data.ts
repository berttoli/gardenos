// All records in this file are synthetic UI examples, not saved garden data.
import type {
  AppPageKey,
  MetricItem,
  PageConfig,
  SidebarItem,
  SidebarState,
  TaskFilterGroup,
  TaskItem,
  TaskQueueSection,
  TaskSummaryStat,
  TaskServiceMeta,
} from "./types";

export const sidebarItems: SidebarItem[] = [
  { page: "map", label: "Map", icon: "map" },
  { page: "tasks", label: "Tasks", icon: "tasks" },
  { page: "plants", label: "Plants", icon: "plants" },
  { page: "monitoring", label: "Monitoring", icon: "health" },
  { page: "api", label: "API", icon: "network", badge: "83" },
  { page: "schedule", label: "Schedule", icon: "calendar" },
  { page: "automations", label: "Automations", icon: "spark" },
  { page: "people", label: "People", icon: "people" },
  { page: "inventory", label: "Inventory", icon: "inventory" },
  { page: "reports", label: "Reports", icon: "reports" },
  { page: "settings", label: "Settings", icon: "settings" },
];

export const mapTabs = ["Health", "Irrigation", "Zones"] as const;
export const inspectorTabs = ["Overview", "Plants", "Metrics", "Notes"] as const;
export const mapBackgroundSrc = "/gardenos-demo-map.svg";

export const priorityTasks: TaskItem[] = [
  {
    title: "Irrigate Container Yard",
    zone: "Container Yard",
    priority: "High",
    due: "Due in 2h",
    avatar: "D1",
    avatarTone: "amber",
    icon: "water",
    tone: "amber",
  },
  {
    title: "Inspect for Aphids",
    zone: "Propagation House",
    priority: "Medium",
    due: "Due today",
    avatar: "D2",
    avatarTone: "moss",
    icon: "plants",
    tone: "sage",
  },
  {
    title: "Fertilize North Field",
    zone: "North Field",
    priority: "Medium",
    due: "Due tomorrow",
    avatar: "D3",
    avatarTone: "sky",
    icon: "leaf",
    tone: "sky",
  },
  {
    title: "Calibrate Moisture Sensors",
    zone: "2 zones",
    priority: "Low",
    due: "Due in 2 days",
    avatar: "D4",
    avatarTone: "forest",
    icon: "thermometer",
    tone: "forest",
  },
];

export const inspectorMetrics: MetricItem[] = [
  {
    kind: "score",
    label: "Health Score",
    value: "58",
    trend: "↓ 12%",
    meta: "vs last 7 days",
  },
  {
    kind: "metric",
    label: "Water Need",
    value: "High",
    status: "High",
    detail: "Irrigate in 2h",
    icon: "droplet",
    tone: "amber",
    progress: 72,
  },
  {
    kind: "metric",
    label: "Soil Moisture",
    value: "18%",
    status: "Low",
    detail: "",
    icon: "thermometer",
    tone: "sky",
    progress: 18,
  },
  {
    kind: "metric",
    label: "Temperature",
    value: "78°F",
    status: "Ideal",
    detail: "",
    icon: "chart",
    tone: "sage",
    progress: 78,
  },
];

export const quickActions = [
  { label: "Irrigate Now", primary: true, icon: "water" as const },
  { label: "Add Note", icon: "notebook" as const },
  { label: "Create Task", icon: "tasks" as const },
] as const;

export const pageConfigs: Record<Exclude<AppPageKey, "map" | "plants">, PageConfig> = {
  tasks: {
    eyebrow: "Task operations",
    title: "Task manager",
    description: "Plan, prioritize, and complete nursery work without losing the field context.",
    metrics: [
      {
        kind: "metric",
        label: "Overdue tasks",
        value: "8",
        status: "Urgent",
        detail: "3 in Container Yard",
        icon: "tasks",
        tone: "amber",
        progress: 84,
      },
      {
        kind: "metric",
        label: "Due today",
        value: "14",
        status: "Ready",
        detail: "6 queued for review",
        icon: "clock",
        tone: "sage",
        progress: 62,
      },
      {
        kind: "metric",
        label: "Assigned crews",
        value: "6",
        status: "Live",
        detail: "2 field teams on shift",
        icon: "people",
        tone: "forest",
        progress: 71,
      },
    ],
    focusLabel: "Daily focus",
    focusTitle: "Overdue actions",
    focusStatus: "Needs attention",
    focusDetail: "8 items across 3 zones",
    noteLabel: "Queue guidance",
    noteBody: "Surface irrigation and inspection items first so high-risk work does not get buried in the list.",
    noteMeta: "Updated 13:11 by dispatch",
    actions: [
      { label: "Create task", primary: true, icon: "add" },
      { label: "Reorder queue", icon: "queue" },
      { label: "Assign crew", icon: "people" },
    ],
  },
  monitoring: {
    eyebrow: "Monitoring",
    title: "Monitoring",
    description: "Keep sensors, platform services, and environmental conditions visible before a zone tips out of range.",
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
        label: "Active alerts",
        value: "4",
        status: "Watch",
        detail: "2 moisture spikes",
        icon: "bellOutline",
        tone: "amber",
        progress: 28,
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
    focusLabel: "Signal health",
    focusTitle: "Monitor drift",
    focusStatus: "Stable",
    focusDetail: "Real-time feedback from field sensors",
    noteLabel: "Monitoring note",
    noteBody: "Watch moisture and heat exposure together so the response is driven by the zone, not just a single reading.",
    noteMeta: "Refreshed 13:11",
    actions: [
      { label: "Review alerts", primary: true, icon: "alert" },
      { label: "Calibrate sensor", icon: "health" },
      { label: "Acknowledge", icon: "bellOutline" },
    ],
  },
  api: {
    eyebrow: "Documentation",
    title: "API control center",
    description:
      "Review the live OpenAPI surface and steer GardenOS routes from a single focused workspace.",
    metrics: [
      {
        kind: "metric",
        label: "Documented routes",
        value: "83",
        status: "Live",
        detail: "Across 9 API surfaces",
        icon: "network",
        tone: "forest",
        progress: 100,
      },
      {
        kind: "metric",
        label: "Writable routes",
        value: "23",
        status: "Mutating",
        detail: "POST, PATCH, and DELETE operations",
        icon: "spark",
        tone: "amber",
        progress: 28,
      },
      {
        kind: "metric",
        label: "Realtime stream",
        value: "1",
        status: "Live",
        detail: "Platform event stream available",
        icon: "queue",
        tone: "sky",
        progress: 100,
      },
    ],
    focusLabel: "API focus",
    focusTitle: "Surface index",
    focusStatus: "Aligned",
    focusDetail: "Access, auth, onboarding, platform, workspace, plants, tasks, and utilities",
    noteLabel: "Control note",
    noteBody: "Keep the full API grouped by surface so operators can move between docs, routes, and backend state without losing context.",
    noteMeta: "Loaded from the current v1 docs surface",
    actions: [
      { label: "Open docs", primary: true, icon: "network" },
      { label: "Inspect platform", icon: "layers" },
      { label: "Refresh surface", icon: "spark" },
    ],
  },
  schedule: {
    eyebrow: "Scheduling",
    title: "Schedule",
    description: "Balance crews, routing, and maintenance windows so the day stays predictable in the field.",
    metrics: [
      {
        kind: "metric",
        label: "Today",
        value: "18",
        status: "Planned",
        detail: "7 time-sensitive items",
        icon: "calendar",
        tone: "sage",
        progress: 72,
      },
      {
        kind: "metric",
        label: "Tomorrow",
        value: "11",
        status: "Queued",
        detail: "3 pending approvals",
        icon: "clock",
        tone: "sky",
        progress: 54,
      },
      {
        kind: "metric",
        label: "Coverage",
        value: "94%",
        status: "Good",
        detail: "Crews balanced",
        icon: "people",
        tone: "forest",
        progress: 94,
      },
    ],
    focusLabel: "Schedule focus",
    focusTitle: "Crew coverage",
    focusStatus: "Balanced",
    focusDetail: "Morning and afternoon shifts locked",
    noteLabel: "Scheduling note",
    noteBody: "Keep irrigation and inspection blocks adjacent so travel time stays low and handoffs stay clean.",
    noteMeta: "Updated 13:11 by ops",
    actions: [
      { label: "Adjust shift", primary: true, icon: "calendar" },
      { label: "Add block", icon: "add" },
      { label: "Publish schedule", icon: "queue" },
    ],
  },
  automations: {
    eyebrow: "Automation",
    title: "Automations",
    description: "Monitor rules, triggers, and field automations without losing sight of the live nursery state.",
    metrics: [
      {
        kind: "metric",
        label: "Active rules",
        value: "24",
        status: "Live",
        detail: "8 zone-specific rules",
        icon: "spark",
        tone: "sage",
        progress: 82,
      },
      {
        kind: "metric",
        label: "Paused rules",
        value: "3",
        status: "Review",
        detail: "Manual restart needed",
        icon: "offline",
        tone: "amber",
        progress: 18,
      },
      {
        kind: "metric",
        label: "Failures",
        value: "1",
        status: "Watch",
        detail: "Last 24 hours",
        icon: "bellOutline",
        tone: "forest",
        progress: 12,
      },
    ],
    focusLabel: "Rule health",
    focusTitle: "Trigger coverage",
    focusStatus: "Live",
    focusDetail: "1 rule waiting on a reconnect",
    noteLabel: "Automation note",
    noteBody: "Use a narrow alert window for irrigation so the system stays quiet unless the zone actually needs action.",
    noteMeta: "Refreshed 13:11",
    actions: [
      { label: "Create rule", primary: true, icon: "spark" },
      { label: "View logs", icon: "notebook" },
      { label: "Pause rule", icon: "offline" },
    ],
  },
  people: {
    eyebrow: "People",
    title: "People",
    description: "See who is on site, who is field ready, and which accounts need access before the next shift starts.",
    metrics: [
      {
        kind: "metric",
        label: "On site",
        value: "7",
        status: "Visible",
        detail: "2 visitors present",
        icon: "people",
        tone: "sage",
        progress: 68,
      },
      {
        kind: "metric",
        label: "Field ready",
        value: "4",
        status: "Ready",
        detail: "Mobile access verified",
        icon: "bell",
        tone: "sky",
        progress: 58,
      },
      {
        kind: "metric",
        label: "Trusted devices",
        value: "12",
        status: "Live",
        detail: "Account sessions active",
        icon: "clock",
        tone: "forest",
        progress: 86,
      },
    ],
    focusLabel: "Crew view",
    focusTitle: "Shift access",
    focusStatus: "Live",
    focusDetail: "Trusted sessions and on-site access",
    noteLabel: "People note",
    noteBody: "Keep field access simple: one signed session per crew lead, and the rest can follow the task queue.",
    noteMeta: "Updated 13:11 by admin",
    actions: [
      { label: "Invite person", primary: true, icon: "people" },
      { label: "Review access", icon: "settings" },
      { label: "Sign out all", icon: "offline" },
    ],
  },
  inventory: {
    eyebrow: "Inventory",
    title: "Inventory",
    description: "Balance stock, spot low zones, and keep nursery inventory aligned with what the map says is on hand.",
    metrics: [
      {
        kind: "metric",
        label: "Stocked zones",
        value: "9",
        status: "Healthy",
        detail: "11 zones need restock",
        icon: "inventory",
        tone: "sage",
        progress: 74,
      },
      {
        kind: "metric",
        label: "Low stock",
        value: "5",
        status: "Watch",
        detail: "Containers and tags",
        icon: "minus",
        tone: "amber",
        progress: 25,
      },
      {
        kind: "metric",
        label: "Discrepancies",
        value: "2",
        status: "Review",
        detail: "Needs reconciliation",
        icon: "chart",
        tone: "forest",
        progress: 18,
      },
    ],
    focusLabel: "Stock focus",
    focusTitle: "Zone balance",
    focusStatus: "Watch",
    focusDetail: "Low stock in 5 supply groups",
    noteLabel: "Inventory note",
    noteBody: "Track material movement by zone first, then reconcile the counts against the property map.",
    noteMeta: "Updated 13:11",
    actions: [
      { label: "Add stock", primary: true, icon: "inventory" },
      { label: "Count zone", icon: "map" },
      { label: "Review discrepancies", icon: "chart" },
    ],
  },
  reports: {
    eyebrow: "Reports",
    title: "Reports",
    description: "Collect weekly summaries, export clean logs, and keep management from digging through raw data.",
    metrics: [
      {
        kind: "metric",
        label: "Weekly reports",
        value: "6",
        status: "Ready",
        detail: "4 published this morning",
        icon: "reports",
        tone: "sage",
        progress: 64,
      },
      {
        kind: "metric",
        label: "Exports",
        value: "14",
        status: "Live",
        detail: "CSV and PDF ready",
        icon: "chart",
        tone: "sky",
        progress: 72,
      },
      {
        kind: "metric",
        label: "Open reviews",
        value: "3",
        status: "Watch",
        detail: "Pending approvals",
        icon: "bellOutline",
        tone: "amber",
        progress: 30,
      },
    ],
    focusLabel: "Reporting",
    focusTitle: "Weekly pulse",
    focusStatus: "Ready",
    focusDetail: "Fresh exports and review notes",
    noteLabel: "Report note",
    noteBody: "Summaries should stay operational first: what happened, where, and what needs follow-up next.",
    noteMeta: "Updated 13:11 by ops",
    actions: [
      { label: "Generate report", primary: true, icon: "reports" },
      { label: "Export PDF", icon: "chart" },
      { label: "Send review", icon: "bellOutline" },
    ],
  },
  settings: {
    eyebrow: "System",
    title: "Settings",
    description: "Tune roles, notifications, and offline behavior without forcing the nursery team into a different workflow.",
    metrics: [
      {
        kind: "metric",
        label: "Roles",
        value: "4",
        status: "Managed",
        detail: "Admin, crew, inspector, viewer",
        icon: "settings",
        tone: "sage",
        progress: 54,
      },
      {
        kind: "metric",
        label: "Offline sync",
        value: "On",
        status: "Ready",
        detail: "Local-first enabled",
        icon: "offline",
        tone: "sky",
        progress: 88,
      },
      {
        kind: "metric",
        label: "Devices",
        value: "12",
        status: "Connected",
        detail: "3 pending updates",
        icon: "people",
        tone: "forest",
        progress: 79,
      },
    ],
    focusLabel: "Admin",
    focusTitle: "System controls",
    focusStatus: "Live",
    focusDetail: "Roles, alerts, and offline-first sync",
    noteLabel: "Settings note",
    noteBody: "Keep defaults conservative so the field workflow stays simple and the UI remains familiar across devices.",
    noteMeta: "Updated 13:11 by Jordan",
    actions: [
      { label: "Edit roles", primary: true, icon: "settings" },
      { label: "Notifications", icon: "bellOutline" },
      { label: "Sync settings", icon: "offline" },
    ],
  },
};

export const taskServiceMeta: TaskServiceMeta = {
  name: "Task service",
  version: "v1",
  scope: "Task operations + triage",
};

export const taskSummaryStats: TaskSummaryStat[] = [
  {
    label: "Today",
    value: "18 tasks",
    detail: "Wednesday shift",
    icon: "calendar",
    tone: "sage",
    contextKey: "today",
  },
  {
    label: "Urgent tasks",
    value: "5",
    detail: "Due within 2 hrs",
    icon: "alert",
    tone: "amber",
    contextKey: "urgent",
  },
  {
    label: "Ready now",
    value: "11",
    detail: "Can start immediately",
    icon: "clock",
    tone: "forest",
    contextKey: "ready",
  },
  {
    label: "Past due",
    value: "8",
    detail: "Needs triage",
    icon: "alert",
    tone: "amber",
    contextKey: "past-due",
  },
];

export const taskPastDueStats: TaskSummaryStat[] = [
  {
    label: "Irrigate Greenhouse 3",
    value: "8:30 AM",
    detail: "GH3 · 12 min late",
    icon: "water",
    tone: "amber",
  },
  {
    label: "Inspect for Aphids",
    value: "9:00 AM",
    detail: "GH2 · 30 min late",
    icon: "health",
    tone: "amber",
  },
  {
    label: "Repot Japanese Maples",
    value: "9:30 AM",
    detail: "GH1 · 18 min late",
    icon: "inventory",
    tone: "amber",
  },
  {
    label: "Water Hanging Baskets",
    value: "10:15 AM",
    detail: "SH · 3 min late",
    icon: "water",
    tone: "sky",
  },
];

export const taskFilterGroups: TaskFilterGroup[] = [
  {
    label: "View",
    items: [
      { label: "Today’s tasks", count: "18", icon: "calendar", tone: "sage", active: true },
      { label: "Overdue", count: "8", icon: "alert", tone: "amber" },
      { label: "Scheduled", count: "14", icon: "clock", tone: "sky" },
      { label: "All tasks", count: "38", icon: "tasks", tone: "forest" },
    ],
  },
  {
    label: "Priority",
    items: [
      { label: "All", count: "38", icon: "tasks", tone: "forest", active: true },
      { label: "Urgent", count: "5", icon: "alert", tone: "amber" },
      { label: "High", count: "11", icon: "water", tone: "amber" },
      { label: "Medium", count: "15", icon: "health", tone: "sage" },
      { label: "Low", count: "7", icon: "leaf", tone: "forest" },
    ],
  },
  {
    label: "Task type",
    items: [
      { label: "Irrigation", count: "8", icon: "water", tone: "sky" },
      { label: "Inspection", count: "7", icon: "search", tone: "sage" },
      { label: "Pest Monitor", count: "6", icon: "health", tone: "forest" },
      { label: "Pruning", count: "5", icon: "spark", tone: "forest" },
      { label: "Repotting", count: "4", icon: "inventory", tone: "amber" },
      { label: "Weed Control", count: "3", icon: "leaf", tone: "sage" },
    ],
  },
  {
    label: "Zones",
    items: [
      { label: "Greenhouse 1", count: "8", icon: "map", tone: "sage" },
      { label: "Greenhouse 2", count: "7", icon: "map", tone: "forest" },
      { label: "Greenhouse 3", count: "6", icon: "map", tone: "amber" },
      { label: "Shade House", count: "5", icon: "map", tone: "sky" },
      { label: "Outdoor Rows", count: "7", icon: "map", tone: "sage" },
      { label: "Perennial Field", count: "5", icon: "map", tone: "forest" },
    ],
  },
];

export const taskQueueSections: TaskQueueSection[] = [
  {
    label: "Due within 2 hours",
    count: "5",
    rows: [
      {
        title: "Irrigate Greenhouse 3",
        subtitle: "Drip irrigation check & adjust",
        zone: "GH3",
        due: "8:30 AM",
        crew: "Luis M.",
        crewOverflow: "+1",
        priority: "Urgent",
        icon: "water",
        tone: "amber",
        crewMembers: [
          { initials: "D5", tone: "amber" },
          { initials: "D6", tone: "sky" },
        ],
        selected: true,
      },
      {
        title: "Inspect for Aphids",
        subtitle: "Scouting & treatment if needed",
        zone: "GH2",
        due: "9:00 AM",
        crew: "Sarah K.",
        priority: "Urgent",
        icon: "health",
        tone: "amber",
        crewMembers: [{ initials: "D7", tone: "moss" }],
      },
      {
        title: "Repot Japanese Maples",
        subtitle: "5 gal to 7 gal",
        zone: "GH1",
        due: "9:30 AM",
        crew: "Miguel A.",
        crewOverflow: "+2",
        priority: "High",
        icon: "inventory",
        tone: "amber",
        crewMembers: [
          { initials: "D8", tone: "forest" },
          { initials: "D9", tone: "sage" },
        ],
      },
      {
        title: "Prune Ornamental Grasses",
        subtitle: "Feather Reed grass bed",
        zone: "OR",
        due: "10:00 AM",
        crew: "Jenna R.",
        priority: "High",
        icon: "spark",
        tone: "forest",
        crewMembers: [{ initials: "D10", tone: "sky" }],
      },
      {
        title: "Water Hanging Baskets",
        subtitle: "Check moisture & water",
        zone: "SH",
        due: "10:15 AM",
        crew: "Evan T.",
        priority: "High",
        icon: "water",
        tone: "sky",
        crewMembers: [{ initials: "D11", tone: "sage" }],
      },
    ],
  },
  {
    label: "Due later",
    count: "33",
    rows: [
      {
        title: "Weed Control - Perennials",
        subtitle: "Hand pull weeds",
        zone: "PF",
        due: "11:00 AM",
        crew: "Olivia P.",
        priority: "Medium",
        icon: "leaf",
        tone: "sage",
        crewMembers: [{ initials: "D12", tone: "forest" }],
      },
      {
        title: "Inspection - Greenhouse 1",
        subtitle: "General crop health check",
        zone: "GH1",
        due: "12:00 PM",
        crew: "Tom S.",
        priority: "Medium",
        icon: "search",
        tone: "forest",
        crewMembers: [{ initials: "D13", tone: "amber" }],
      },
      {
        title: "Pest Monitor - Roses",
        subtitle: "Aphids & mites",
        zone: "OR",
        due: "1:30 PM",
        crew: "Sarah K.",
        crewOverflow: "+1",
        priority: "Medium",
        icon: "health",
        tone: "amber",
        crewMembers: [
          { initials: "D7", tone: "moss" },
          { initials: "D14", tone: "sky" },
        ],
      },
      {
        title: "Irrigate Shade House",
        subtitle: "Zone valves & emitters",
        zone: "SH",
        due: "2:00 PM",
        crew: "Luis M.",
        priority: "Low",
        icon: "water",
        tone: "sky",
        crewMembers: [{ initials: "D5", tone: "forest" }],
      },
      {
        title: "Repot Azaleas",
        subtitle: "3 gal to 5 gal",
        zone: "GH2",
        due: "3:00 PM",
        crew: "Miguel A.",
        crewOverflow: "+1",
        priority: "Low",
        icon: "inventory",
        tone: "sage",
        crewMembers: [
          { initials: "D8", tone: "amber" },
          { initials: "D15", tone: "forest" },
        ],
      },
    ],
  },
];

export const taskDetailStats: TaskSummaryStat[] = [
  {
    label: "Zone",
    value: "GH3",
    detail: "Greenhouse 3",
    icon: "map",
    tone: "sage",
  },
  {
    label: "Due",
    value: "Today, 8:30 AM",
    detail: "Overdue risk in 12 min",
    icon: "clock",
    tone: "amber",
  },
  {
    label: "Crew",
    value: "Luis M. +1",
    detail: "Irrigation crew",
    icon: "people",
    tone: "forest",
  },
  {
    label: "Duration",
    value: "25 min",
    detail: "Estimated window",
    icon: "calendar",
    tone: "sky",
  },
];

export const taskWeatherStats: TaskSummaryStat[] = [
  {
    label: "Precip",
    value: "10%",
    detail: "Minimal rain risk",
    icon: "weather",
    tone: "sky",
  },
  {
    label: "Wind",
    value: "NE 6 mph",
    detail: "Stable for irrigation",
    icon: "spark",
    tone: "sage",
  },
  {
    label: "Humidity",
    value: "62%",
    detail: "Moderate",
    icon: "droplet",
    tone: "forest",
  },
  {
    label: "Optimal window",
    value: "Now - 11:00 AM",
    detail: "Best irrigation window",
    icon: "clock",
    tone: "amber",
  },
];

export const taskQuickActions = [
  { label: "Start task", primary: true, icon: "arrow" as const },
  { label: "Log note", icon: "notebook" as const },
  { label: "Add photo", icon: "camera" as const },
] as const;

export function listSidebarItems(): SidebarItem[] {
  return sidebarItems;
}

export function getTopbarModel() {
  return {
    weather: {
      icon: "weather" as const,
      value: "72°F",
      detail: "Partly Cloudy",
      meta: ["H 74°", "L 56°", "18% rain"],
    },
  };
}

export function getMapModel() {
  return {
    tabs: mapTabs,
    inspectorTabs,
    backgroundSrc: mapBackgroundSrc,
    priorityTasks,
    inspectorMetrics,
    quickActions,
  };
}

export function getTaskModel() {
  return {
    serviceMeta: taskServiceMeta,
    summaryStats: taskSummaryStats,
    filterGroups: taskFilterGroups,
    queueSections: taskQueueSections,
    detailStats: taskDetailStats,
    pastDueStats: taskPastDueStats,
    weatherStats: taskWeatherStats,
    quickActions: taskQuickActions,
  };
}

export function getPageConfig(page: Exclude<AppPageKey, "map" | "plants">): PageConfig {
  return pageConfigs[page];
}

export function getPageFromLocation(searchParams?: { get(name: string): string | null } | null): AppPageKey {
  const value =
    searchParams?.get("page") ??
    (typeof window === "undefined" ? null : new URL(window.location.href).searchParams.get("page"));

  if (
    value === "tasks" ||
    value === "plants" ||
    value === "monitoring" ||
    value === "api" ||
    value === "schedule" ||
    value === "automations" ||
    value === "people" ||
    value === "inventory" ||
    value === "reports" ||
    value === "settings"
  ) {
    return value;
  }

  return "map";
}

export function getSidebarClickState(state: SidebarState): SidebarState {
  switch (state) {
    case "open":
      return "closed";
    case "closed":
      return "open";
    case "tucked":
      return "closed";
  }
}

export function stepSidebarState(state: SidebarState, direction: -1 | 1): SidebarState {
  if (direction < 0) {
    switch (state) {
      case "open":
        return "closed";
      case "closed":
        return "tucked";
      case "tucked":
        return "tucked";
    }
  }

  switch (state) {
    case "open":
      return "open";
    case "closed":
      return "open";
    case "tucked":
      return "closed";
  }
}
