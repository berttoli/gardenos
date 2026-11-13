"use client";

import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import type { GardenServiceContext } from "../services/context";
import { completeGardenTask, getTaskModel } from "../services/task-service";
import { signInGardenSession } from "../services/bootstrap-service";
import type { PageWorkspaceView } from "./registry";
import {
  ActionNoticeCard,
  Chip,
  Icon,
  type TaskContextKey,
  TaskQueueSectionBlock,
  TaskStatRail,
  type TaskQueueEntry,
  useTimedNotice,
} from "../shared";

type TaskModel = ReturnType<typeof getTaskModel>;

function getInitialSelectedTask(queueSections: TaskModel["queueSections"]) {
  const selectedTask = queueSections.flatMap((section) => section.rows).find((task) => task.selected);

  if (selectedTask) {
    return selectedTask;
  }

  return getFirstTask(queueSections);
}

function getTaskById(queueSections: TaskModel["queueSections"], taskId: string | null) {
  return queueSections.flatMap((section) => section.rows).find((task) => task.id === taskId);
}

function getFirstTask(queueSections: TaskModel["queueSections"]) {
  return queueSections.flatMap((section) => section.rows)[0];
}

function getContextSections(
  queueSections: TaskModel["queueSections"],
  context: TaskContextKey,
  pastDueIds: string[],
) {
  if (context === "today") {
    return queueSections;
  }

  const matchesTask = (task: TaskQueueEntry) => {
    if (task.status !== "pending") {
      return false;
    }
    if (context === "urgent") {
      return task.priority === "Urgent";
    }

    if (context === "ready") {
      return task.priority === "Medium" || task.priority === "Low";
    }

    return task.id != null && pastDueIds.includes(task.id);
  };

  const rows = queueSections.flatMap((section) => section.rows).filter(matchesTask);

  return [
    {
      label: context === "urgent" ? "Urgent now" : context === "ready" ? "Ready now" : "Past due",
      count: String(rows.length),
      rows,
    },
  ];
}

function TaskPageMain({
  model,
  activeContext,
  queueSections,
  selectedTask,
  notice,
  onNotice,
  onContextChange,
  onTaskSelect,
  error,
  pending,
  onRefresh,
  onSignIn,
}: {
  model: TaskModel;
  activeContext: TaskContextKey;
  queueSections: TaskModel["queueSections"];
  selectedTask: TaskQueueEntry | undefined;
  notice: string | null;
  onNotice: (message: string) => void;
  onContextChange: (context: TaskContextKey) => void;
  onTaskSelect: (taskId: string) => void;
  error: string | null;
  pending: boolean;
  onRefresh: () => void;
  onSignIn: (username: string, password: string) => Promise<void>;
}) {
  const { serviceMeta, summaryStats } = model;
  const [servicePopoverOpen, setServicePopoverOpen] = useState(false);
  const [queueViewMode, setQueueViewMode] = useState<"table" | "compact" | "all">("table");
  const servicePopoverTimer = useRef<number | null>(null);
  const servicePointerType = useRef<"mouse" | "pen" | "touch" | null>(null);
  const skipNextTouchClick = useRef(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  useEffect(
    () => () => {
      if (servicePopoverTimer.current != null) {
        window.clearTimeout(servicePopoverTimer.current);
      }
    },
    [],
  );

  useEffect(() => {
    const summaryRail = document.querySelector<HTMLElement>(".target-task-summary-rail");

    if (summaryRail) {
      summaryRail.scrollLeft = 0;
    }
  }, [activeContext]);

  const openServicePopover = () => setServicePopoverOpen(true);
  const closeServicePopover = () => setServicePopoverOpen(false);

  const handleTitlePointerEnter = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (event.pointerType === "mouse") {
      servicePointerType.current = "mouse";
      openServicePopover();
    }
  };

  const handleTitlePointerLeave = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (event.pointerType === "mouse") {
      closeServicePopover();
      servicePointerType.current = null;
    }

    if (servicePointerType.current !== "mouse" && servicePopoverTimer.current != null) {
      window.clearTimeout(servicePopoverTimer.current);
      servicePopoverTimer.current = null;
    }
  };

  const handleTitlePointerDown = (event: ReactPointerEvent<HTMLButtonElement>) => {
    servicePointerType.current = event.pointerType as "mouse" | "pen" | "touch";

    if (event.pointerType === "mouse") {
      return;
    }

    if (servicePopoverTimer.current != null) {
      window.clearTimeout(servicePopoverTimer.current);
    }

    servicePopoverTimer.current = window.setTimeout(() => {
      skipNextTouchClick.current = true;
      openServicePopover();
    }, 450);
  };

  const handleTitlePointerUp = () => {
    if (servicePopoverTimer.current != null) {
      window.clearTimeout(servicePopoverTimer.current);
      servicePopoverTimer.current = null;
    }
  };

  const handleTitleClick = () => {
    if (servicePointerType.current === "mouse") {
      return;
    }

    if (skipNextTouchClick.current) {
      skipNextTouchClick.current = false;
      return;
    }

    setServicePopoverOpen((current) => (current ? false : current));
  };

  const handleTitleBlur = () => {
    if (servicePointerType.current !== "mouse") {
      closeServicePopover();
    }
  };

  const queueRowsPerSection = queueViewMode === "compact" ? 3 : 4;
  const totalQueueCount = queueSections.reduce((total, section) => total + section.rows.length, 0);
  const visibleQueueCount = queueSections.reduce(
    (total, section) => total + (queueViewMode === "all" ? section.rows.length : Math.min(section.rows.length, queueRowsPerSection)),
    0,
  );
  const queueSectionDensity = queueViewMode === "compact" ? "compact" : "regular";

  return (
    <section className="target-center-stack target-task-main" aria-label="Task manager workspace">
      <article className="panel target-task-summary">
        <div className="target-task-summary-head">
          <div className="target-task-summary-title-wrap">
            <span className="section-label">Task operations</span>
            <button
              className="target-task-summary-title"
              type="button"
              aria-expanded={servicePopoverOpen}
              onBlur={handleTitleBlur}
              onClick={handleTitleClick}
              onFocus={openServicePopover}
              onPointerDown={handleTitlePointerDown}
              onPointerEnter={handleTitlePointerEnter}
              onPointerLeave={handleTitlePointerLeave}
              onPointerUp={handleTitlePointerUp}
              onPointerCancel={handleTitlePointerUp}
            >
              <span>Task Manager</span>
              <Icon name="chevron" className="target-task-summary-title-icon" />
            </button>

            <div className="target-task-service-popover" data-open={servicePopoverOpen ? "true" : "false"}>
              <span className="target-task-service-popover-label">Managed by</span>
              <strong>{serviceMeta.name}</strong>
              <span>
                {serviceMeta.version} · {serviceMeta.scope}
              </span>
            </div>
          </div>

          <div className="target-task-summary-head-actions">
            <Chip icon="queue" tone="forest" ariaLabel="Task activity" title="Task activity" />
          </div>
        </div>

        <TaskStatRail
          stats={summaryStats}
          label="Task metrics"
          className="target-task-summary-rail"
          activeStatLabel={summaryStats.find((stat) => stat.contextKey === activeContext)?.label}
          onStatClick={(stat) => {
            const context = stat.contextKey ?? "today";
            onContextChange(context);
          }}
        />
        <ActionNoticeCard label="Task update" title="Queue action" notice={notice} />
        {error ? <p role="alert">{error}</p> : null}
        {!model.authenticated ? (
          <form className="target-note-card" style={{ display: "grid", gap: 12, minWidth: 0 }} aria-label="Sign in to GardenOS" onSubmit={(event) => {
            event.preventDefault();
            const submittedPassword = password;
            setPassword("");
            void onSignIn(username, submittedPassword);
          }}>
            <p>Sign in to load and complete your tasks.</p>
            <label style={{ display: "grid", gap: 6 }}>Username <input name="username" autoComplete="username" required value={username} onChange={(event) => setUsername(event.target.value)} /></label>
            <label style={{ display: "grid", gap: 6 }}>Password <input name="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
            <button className="target-action-button" type="submit" disabled={pending}>{pending ? "Signing in…" : "Sign in"}</button>
          </form>
        ) : null}
        {model.authenticated && !model.available ? <p>Tasks could not be loaded. Refresh the queue to try again.</p> : null}
      </article>

      <section className="panel target-task-queue">
        <div className="target-task-queue-head">
          <div>
            <span className="section-label">Task operations</span>
            <h3>Queue control</h3>
          </div>

          <div className="target-task-queue-head-actions" role="tablist" aria-label="Queue view modes">
            <button type="button" disabled={pending} onClick={onRefresh}>Refresh queue</button>
            <button
              className="target-task-view-toggle"
              data-active={queueViewMode === "table" ? "true" : "false"}
              type="button"
              onClick={() => setQueueViewMode("table")}
            >
              Table
            </button>
            <button
              className="target-task-view-toggle"
              data-active={queueViewMode === "compact" ? "true" : "false"}
              type="button"
              onClick={() => setQueueViewMode("compact")}
            >
              Compact
            </button>
            <button
              className="target-task-view-toggle"
              data-active={queueViewMode === "all" ? "true" : "false"}
              type="button"
              onClick={() => setQueueViewMode("all")}
            >
              View all
            </button>
          </div>
        </div>

        <div className="target-task-queue-table-head" aria-hidden="true">
          <span>Task</span>
          <span>Zone</span>
          <span>Due</span>
          <span>Crew</span>
          <span>Priority</span>
          <span />
        </div>

        <div className="target-task-queue-sections" data-view-mode={queueViewMode}>
          {model.available && totalQueueCount === 0 ? <p role="status">No tasks in this view.</p> : null}
          {queueSections.map((section) => (
            <TaskQueueSectionBlock
              key={section.label}
              section={section}
              density={queueSectionDensity}
              maxRows={queueViewMode === "all" ? undefined : queueRowsPerSection}
              selectedTaskId={selectedTask?.id}
              onSelectTask={(taskId) => {
                onTaskSelect(taskId);
                const row = getTaskById(queueSections, taskId);
                onNotice(row ? `Selected ${row.title} for details.` : "Selected task.");
              }}
              onViewAll={() => {
                setQueueViewMode("all");
                onNotice("Expanded the queue to show all visible task rows.");
              }}
            />
          ))}
        </div>

        <div className="target-task-queue-footer">
          <span>
            {queueViewMode === "all" ? `Showing all ${totalQueueCount} tasks` : `Showing ${visibleQueueCount} of ${totalQueueCount} tasks`}
          </span>
          <button
            type="button"
            onClick={() => {
              setQueueViewMode("all");
              onNotice("Expanded the queue to show all tasks.");
            }}
          >
            {queueViewMode === "all" ? "All visible" : "View all"}
            <Icon name="chevron" />
          </button>
        </div>
      </section>
    </section>
  );
}

function TaskPageControlPanel({
  selectedTask,
  pending,
  canComplete,
  onComplete,
}: {
  selectedTask: TaskQueueEntry | undefined;
  pending: boolean;
  canComplete: boolean;
  onComplete: () => void;
}) {
  if (!selectedTask) {
    return <article className="panel target-task-inspector"><p>Select a task to see its details.</p></article>;
  }

  const completed = selectedTask.status === "completed";
  return (
    <article className="panel target-task-inspector" data-testid="task-inspector" data-task-id={selectedTask.id}>
      <div className="target-task-inspector-head">
        <div><span className="section-label">Task details</span><h3>{selectedTask.title}</h3></div>
      </div>
      <div className="target-task-inspector-status">
        <span className="target-status-dot" />
        <span>{selectedTask.priority}</span>
        <span className="target-task-inspector-time">{selectedTask.due}</span>
      </div>
      <p>{selectedTask.subtitle} · {selectedTask.zone}</p>
      <p>{selectedTask.crew}</p>
      {selectedTask.completionNotes ? <p>{selectedTask.completionNotes}</p> : null}
      <div className="target-task-status-strip" aria-label="Task status">
        <strong data-testid="task-status">{completed ? "Completed" : selectedTask.status === "skipped" ? "Skipped" : "Pending"}</strong>
      </div>
      <button
        className="target-task-complete target-action-button"
        data-primary="true"
        type="button"
        disabled={!canComplete || pending || completed}
        aria-busy={pending}
        onClick={onComplete}
      >
        {pending ? "Saving…" : completed ? "Completed" : "Mark complete"}
      </button>
    </article>
  );
}

function TaskPageWorkspace(context: GardenServiceContext | null = null): PageWorkspaceView {
  const model = getTaskModel(context);
  const initialSelectedTask = getInitialSelectedTask(model.queueSections);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(initialSelectedTask?.id ?? null);
  const [taskContext, setTaskContext] = useState<TaskContextKey>("today");
  const [notice, setNotice] = useTimedNotice();
  const [error, setError] = useState<string | null>(null);
  const [pendingTaskId, setPendingTaskId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const operationInFlight = useRef(false);
  const pastDueIds = context?.workspace?.tasks.overdue.map((task) => task.id) ?? [];
  const queueSections = getContextSections(model.queueSections, taskContext, pastDueIds);
  const selectedTask = getTaskById(queueSections, selectedTaskId) ?? getFirstTask(queueSections);

  const startOperation = () => {
    if (operationInFlight.current) return false;
    operationInFlight.current = true;
    setBusy(true);
    setError(null);
    setNotice(null);
    return true;
  };
  const finishOperation = () => {
    operationInFlight.current = false;
    setBusy(false);
    setPendingTaskId(null);
  };

  const refresh = async () => {
    if (!context?.refreshBootstrap) throw new Error("Reload this page to refresh your tasks.");
    return context.refreshBootstrap();
  };

  const handleRefresh = async () => {
    if (!startOperation()) return;
    try {
      await refresh();
      setNeedsRefresh(false);
      setNotice("Task queue refreshed.");
    } catch {
      setError("Could not refresh tasks. Check your connection and session, then try again.");
    } finally {
      finishOperation();
    }
  };

  const handleSignIn = async (username: string, password: string) => {
    if (!startOperation()) return;
    try {
      await signInGardenSession(username, password);
      await refresh();
      setNeedsRefresh(false);
      setNotice("Signed in. Your task queue is up to date.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign in. Please try again.");
    } finally {
      finishOperation();
    }
  };

  const handleComplete = async () => {
    const task = selectedTask;
    const csrfToken = context?.auth?.csrf_token;
    if (!task?.id || task.status !== "pending" || !context?.auth?.authenticated || !csrfToken || !context.auth.principal?.permissions.includes("tasks.write") || needsRefresh) return;
    if (!startOperation()) return;
    setPendingTaskId(task.id);
    let saved = false;
    try {
      await completeGardenTask(task.id, csrfToken);
      saved = true;
      setNeedsRefresh(true);
      const next = await refresh();
      if (!next.workspace?.tasks.completed.some((row) => row.id === task.id && row.completed_at)) {
        throw new Error("Completion is not present in the refreshed queue.");
      }
      setNeedsRefresh(false);
      setTaskContext("today");
      setSelectedTaskId(task.id);
      setNotice(`${task.title} completed and saved.`);
    } catch (cause) {
      setError(saved
        ? "Task completion was saved, but the queue could not refresh. Refresh the queue to confirm its current status."
        : cause instanceof Error ? cause.message : "Could not complete the task. Refresh the queue before retrying.");
    } finally {
      finishOperation();
    }
  };

  const handleContextChange = (nextContext: TaskContextKey) => {
    setTaskContext(nextContext);
    const nextSections = getContextSections(model.queueSections, nextContext, pastDueIds);
    setSelectedTaskId(getFirstTask(nextSections)?.id ?? null);
  };

  return {
    main: (
      <TaskPageMain
        model={model}
        activeContext={taskContext}
        queueSections={queueSections}
        notice={notice}
        error={error}
        pending={busy}
        onRefresh={() => { void handleRefresh(); }}
        onSignIn={handleSignIn}
        onContextChange={handleContextChange}
        onNotice={setNotice}
        onTaskSelect={setSelectedTaskId}
        selectedTask={selectedTask}
      />
    ),
    controlPanel: {
      eyebrow: "Control panel",
      title: "Task controls",
      content: (
        <TaskPageControlPanel
          selectedTask={selectedTask}
          pending={pendingTaskId === selectedTask?.id}
          canComplete={Boolean(model.available && context?.auth?.authenticated && context.auth.csrf_token && context.auth.principal?.permissions.includes("tasks.write") && context.refreshBootstrap && !busy && !needsRefresh && selectedTask?.status === "pending")}
          onComplete={() => { void handleComplete(); }}
        />
      ),
    },
  };
}

export function TaskPage(context: GardenServiceContext | null = null): PageWorkspaceView {
  return TaskPageWorkspace(context);
}
