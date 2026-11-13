import type { IconName } from "./icons";

export type ShellTone = "sage" | "moss" | "amber" | "sky" | "forest";
export type MetricTone = "sage" | "forest" | "amber" | "sky";

export type AppPageKey =
  | "map"
  | "tasks"
  | "plants"
  | "monitoring"
  | "api"
  | "schedule"
  | "automations"
  | "people"
  | "inventory"
  | "reports"
  | "settings";

export type SidebarState = "open" | "closed" | "tucked";
export type ControlPanelState = "open" | "closed";

export type MetricItem =
  | {
      kind: "score";
      label: string;
      value: string;
      trend: string;
      meta: string;
    }
  | {
      kind: "metric";
      label: string;
      value: string;
      status: string;
      detail: string;
      icon: IconName;
      tone: MetricTone;
      progress?: number;
    };

export type PageMetric = Extract<MetricItem, { kind: "metric" }>;

export type PageCommandAction = {
  label: string;
  primary?: boolean;
  icon?: IconName;
};

export type PageConfig = {
  eyebrow: string;
  title: string;
  description: string;
  metrics: PageMetric[];
  focusLabel: string;
  focusTitle: string;
  focusStatus: string;
  focusDetail: string;
  noteLabel: string;
  noteBody: string;
  noteMeta: string;
  actions: ReadonlyArray<PageCommandAction>;
};

export type SidebarItem = {
  page: AppPageKey;
  label: string;
  icon: IconName;
  badge?: string;
};

export type TaskItem = {
  title: string;
  zone: string;
  priority: "High" | "Medium" | "Low";
  due: string;
  avatar: string;
  avatarTone: ShellTone;
  icon: IconName;
  tone: MetricTone;
};

export type TaskSummaryStat = {
  label: string;
  value: string;
  detail: string;
  icon: IconName;
  tone: MetricTone;
  contextKey?: TaskContextKey;
};

export type TaskServiceMeta = {
  name: string;
  version: string;
  scope: string;
};

export type TaskContextKey = "today" | "urgent" | "ready" | "past-due";

export type TaskFilterItem = {
  label: string;
  count?: string;
  icon: IconName;
  active?: boolean;
  tone: MetricTone;
};

export type TaskFilterGroup = {
  label: string;
  items: TaskFilterItem[];
};

export type TaskQueueEntry = {
  id?: string;
  status?: "pending" | "completed" | "skipped";
  completedAt?: string | null;
  completionNotes?: string | null;
  title: string;
  subtitle: string;
  zone: string;
  due: string;
  crew: string;
  crewOverflow?: string;
  priority: "Urgent" | "High" | "Medium" | "Low";
  icon: IconName;
  tone: MetricTone;
  crewMembers: Array<{
    initials: string;
    tone: ShellTone;
  }>;
  selected?: boolean;
};

export type TaskQueueSection = {
  label: string;
  count: string;
  rows: TaskQueueEntry[];
};
