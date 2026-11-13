import {
  taskPastDueStats,
  taskDetailStats,
  taskFilterGroups,
  taskQuickActions,
  taskServiceMeta,
  taskWeatherStats,
} from "../shared/data";
import type { TaskQueueEntry, TaskQueueSection, TaskSummaryStat } from "../shared/types";
import type { GardenServiceContext } from "./context";
import type { GardenWorkspaceBootstrap, GardenWorkspaceTaskRecord } from "./bootstrap-service";
import { requestGardenApi } from "./api-client";

export type GardenTaskModel = {
  available: boolean;
  authenticated: boolean;
  serviceMeta: typeof taskServiceMeta;
  summaryStats: TaskSummaryStat[];
  filterGroups: typeof taskFilterGroups;
  queueSections: TaskQueueSection[];
  detailStats: typeof taskDetailStats;
  pastDueStats: typeof taskPastDueStats;
  weatherStats: typeof taskWeatherStats;
  quickActions: typeof taskQuickActions;
};

const TASK_ICON_BY_TYPE: Record<string, TaskQueueEntry["icon"]> = {
  inspect: "health",
  water: "water",
  fertilize: "leaf",
  prune: "leaf",
  repot: "inventory",
  photograph: "camera",
  measure: "thermometer",
  treat: "alert",
  harvest: "reports",
  propagate: "spark",
  move: "map",
  winterize: "weather",
  clean: "notebook",
  custom: "tasks",
};

function priorityFromValue(priority: number | null | undefined): TaskQueueEntry["priority"] {
  if (typeof priority !== "number") {
    return "Medium";
  }

  if (priority <= 1) {
    return "Urgent";
  }

  if (priority === 2) {
    return "High";
  }

  if (priority === 3) {
    return "Medium";
  }

  return "Low";
}

function toneFromPriority(priority: TaskQueueEntry["priority"]): TaskQueueEntry["tone"] {
  if (priority === "Urgent" || priority === "High") {
    return "amber";
  }

  if (priority === "Medium") {
    return "sage";
  }

  return "forest";
}

function iconFromTaskType(taskType: string | null): TaskQueueEntry["icon"] {
  if (!taskType) {
    return "tasks";
  }

  return TASK_ICON_BY_TYPE[taskType.toLowerCase()] ?? "tasks";
}

function formatTaskDue(task: GardenWorkspaceTaskRecord): string {
  const scheduledAt = new Date(task.scheduled_for);
  if (Number.isNaN(scheduledAt.getTime())) {
    return "Due soon";
  }

  const now = new Date();
  const sameDay =
    scheduledAt.getFullYear() === now.getFullYear() &&
    scheduledAt.getMonth() === now.getMonth() &&
    scheduledAt.getDate() === now.getDate();

  if (sameDay) {
    return `Due ${scheduledAt.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  }

  return scheduledAt.toLocaleDateString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function buildCrewMembers(task: GardenWorkspaceTaskRecord): TaskQueueEntry["crewMembers"] {
  const source = [task.zone, task.task_type, task.title]
    .filter((value): value is string => Boolean(value))
    .join(" ");
  const initials = source
    .split(/\s+/)
    .map((part) => part[0]?.toUpperCase())
    .filter((part): part is string => Boolean(part));

  const crewInitials = initials.slice(0, 3);
  if (crewInitials.length === 0) {
    return [{ initials: "GA", tone: "sage" }];
  }

  return crewInitials.map((initial, index) => ({
    initials: initial,
    tone: index === 0 ? "sage" : index === 1 ? "forest" : "amber",
  }));
}

function buildLiveQueueEntry(task: GardenWorkspaceTaskRecord, selected = false): TaskQueueEntry {
  const priority = priorityFromValue(task.priority);
  const zone = task.zone?.trim() || "Unassigned zone";
  const subtitle = task.task_type ? task.task_type.replace(/_/g, " ") : "Scheduled task";

  return {
    id: task.id,
    status: task.completed_at ? "completed" : task.skipped_at ? "skipped" : "pending",
    completedAt: task.completed_at,
    completionNotes: task.completion_notes,
    title: task.title?.trim() || "Untitled task",
    subtitle,
    zone,
    due: task.completed_at ? `Completed ${new Date(task.completed_at).toLocaleString()}` : formatTaskDue(task),
    crew: task.performed_by?.trim() || "Unassigned",
    priority,
    icon: iconFromTaskType(task.task_type),
    tone: toneFromPriority(priority),
    crewMembers: buildCrewMembers(task),
    selected,
  };
}

function buildLiveQueueSections(workspace: GardenWorkspaceBootstrap | null): TaskQueueSection[] {
  if (!workspace) {
    return [];
  }

  const overdueRows = workspace.tasks.overdue.map((task) => buildLiveQueueEntry(task));
  const overdueIds = new Set(workspace.tasks.overdue.map((task) => task.id));
  const dueRows = workspace.tasks.due.filter((task) => !overdueIds.has(task.id)).map((task) => buildLiveQueueEntry(task));

  const completedRows = (workspace.tasks.completed ?? []).map((task) => buildLiveQueueEntry(task));

  const firstSelected = overdueRows[0] ?? dueRows[0] ?? completedRows[0];
  if (firstSelected) {
    firstSelected.selected = true;
  }

  return [
    {
      label: "Past due",
      count: String(overdueRows.length),
      rows: overdueRows,
    },
    {
      label: "Due now",
      count: String(dueRows.length),
      rows: dueRows,
    },
    {
      label: "Completed",
      count: String(completedRows.length),
      rows: completedRows,
    },
  ];
}

function buildTaskSummaryStats(workspace: GardenWorkspaceBootstrap | null): TaskSummaryStat[] {
  if (!workspace) {
    return [
      {
        label: "Today",
        value: "0 tasks",
        detail: "Waiting for backend task data",
        icon: "calendar",
        tone: "sage",
        contextKey: "today",
      },
      {
        label: "Urgent tasks",
        value: "0",
        detail: "Waiting for backend task data",
        icon: "alert",
        tone: "amber",
        contextKey: "urgent",
      },
      {
        label: "Ready now",
        value: "0",
        detail: "Waiting for backend task data",
        icon: "clock",
        tone: "forest",
        contextKey: "ready",
      },
      {
        label: "Past due",
        value: "0",
        detail: "Waiting for backend task data",
        icon: "alert",
        tone: "amber",
        contextKey: "past-due",
      },
    ];
  }

  const liveTasks = [...new Map([...workspace.tasks.overdue, ...workspace.tasks.due].map((task) => [task.id, task])).values()];
  const urgentTasks = liveTasks.filter((task) => priorityFromValue(task.priority) === "Urgent");
  const readyTasks = liveTasks.filter((task) => {
    const priority = priorityFromValue(task.priority);
    return priority === "Medium" || priority === "Low";
  });

  return [
    {
      label: "Today",
      value: `${liveTasks.length} tasks`,
      detail: `${workspace.summary.due_task_count} due · ${workspace.summary.overdue_task_count} overdue`,
      icon: "calendar",
      tone: "sage",
      contextKey: "today",
    },
    {
      label: "Urgent tasks",
      value: String(urgentTasks.length),
      detail: "Derived from live task priority records",
      icon: "alert",
      tone: "amber",
      contextKey: "urgent",
    },
    {
      label: "Ready now",
      value: String(readyTasks.length),
      detail: "Derived from live task priority records",
      icon: "clock",
      tone: "forest",
      contextKey: "ready",
    },
    {
      label: "Past due",
      value: String(workspace.summary.overdue_task_count),
      detail: "Pulled from the workspace bootstrap payload",
      icon: "alert",
      tone: "amber",
      contextKey: "past-due",
    },
  ];
}

export function getTaskModel(context: GardenServiceContext | null = null): GardenTaskModel {
  const workspace = context?.workspace ?? null;
  const queueSections = buildLiveQueueSections(workspace);

  return {
    available: workspace != null,
    authenticated: context?.auth?.authenticated === true,
    serviceMeta: taskServiceMeta,
    summaryStats: buildTaskSummaryStats(workspace),
    filterGroups: taskFilterGroups,
    queueSections,
    detailStats: taskDetailStats,
    pastDueStats: taskPastDueStats,
    weatherStats: taskWeatherStats,
    quickActions: taskQuickActions,
  };
}

export async function completeGardenTask(taskId: string, csrfToken: string): Promise<GardenWorkspaceTaskRecord> {
  if (!taskId || !csrfToken) {
    throw new Error("Sign in before completing a task.");
  }

  const response = await requestGardenApi(`/tasks/${encodeURIComponent(taskId)}/complete`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-csrf-token": csrfToken },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Your session expired. Sign in again before completing this task.");
    }
    if (response.status === 403) {
      throw new Error("Task completion was not authorized. Refresh your session and check your access.");
    }
    if (response.status === 404) {
      throw new Error("This task is no longer available. Refresh the queue.");
    }
    throw new Error(`Task completion failed (${response.status}). Refresh the queue before retrying.`);
  }

  const task = (await response.json()) as GardenWorkspaceTaskRecord;
  if (task.id !== taskId || !task.completed_at) {
    throw new Error("The server did not confirm task completion. Refresh the queue before retrying.");
  }
  return task;
}
