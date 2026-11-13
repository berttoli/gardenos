"use client";

import { createPortal } from "react-dom";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type HTMLAttributes,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";

import type {
  ControlPanelState,
  MetricItem,
  PageCommandAction,
  ShellTone,
  SidebarState,
  TaskFilterItem,
  TaskItem,
  TaskQueueEntry,
  TaskQueueSection,
  TaskSummaryStat,
} from "./types";
import { Icon, type IconName } from "./icons";
import type { GardenNurseryOption } from "../services/bootstrap-service";

type ChipTone = "neutral" | ShellTone;
type DockState = SidebarState | ControlPanelState;
type DockSide = "left" | "right";

export function DockSurface({
  className = "",
  side,
  state,
  children,
  ...props
}: HTMLAttributes<HTMLElement> & {
  className?: string;
  side: DockSide;
  state: DockState;
  children: ReactNode;
}) {
  return (
    <aside
      {...props}
      className={["target-dock", className].filter(Boolean).join(" ")}
      data-collapsed={state === "open" ? "false" : "true"}
      data-side={side}
      data-state={state}
    >
      {children}
    </aside>
  );
}

export function DockBody({
  className = "",
  state,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  className?: string;
  state: DockState;
  children: ReactNode;
}) {
  return (
    <div
      {...props}
      className={["target-dock-body", className].filter(Boolean).join(" ")}
      data-collapsed={state === "open" ? "false" : "true"}
    >
      {children}
    </div>
  );
}

export function DockToggleButton({
  className = "",
  iconClassName = "",
  iconName = "arrow",
  side,
  state,
  onToggle,
  labelOpen,
  labelClosed,
  labelTucked,
}: {
  className?: string;
  iconClassName?: string;
  iconName?: IconName;
  side: DockSide;
  state: DockState;
  onToggle: () => void;
  labelOpen: string;
  labelClosed: string;
  labelTucked?: string;
}) {
  const label = state === "open" ? labelOpen : state === "tucked" ? labelTucked ?? labelClosed : labelClosed;

  return (
    <button
      className={["target-dock-toggle", className].filter(Boolean).join(" ")}
      data-side={side}
      data-state={state}
      aria-label={label}
      title={label}
      type="button"
      onClick={onToggle}
    >
      <Icon name={iconName} className={["target-dock-toggle-icon", iconClassName].filter(Boolean).join(" ")} />
    </button>
  );
}

export function DockShell({
  className = "",
  bodyClassName = "",
  headerClassName = "",
  side,
  state,
  onToggle,
  showToggle = true,
  toggleClassName = "",
  toggleIconClassName = "",
  toggleIconName = "arrow",
  labelOpen,
  labelClosed,
  labelTucked,
  header,
  children,
  ...props
}: HTMLAttributes<HTMLElement> & {
  className?: string;
  bodyClassName?: string;
  headerClassName?: string;
  side: DockSide;
  state: DockState;
  onToggle: () => void;
  showToggle?: boolean;
  toggleClassName?: string;
  toggleIconClassName?: string;
  toggleIconName?: IconName;
  labelOpen: string;
  labelClosed: string;
  labelTucked?: string;
  header?: ReactNode;
  children: ReactNode;
}) {
  const isRightDock = side === "right";

  return (
    <DockSurface {...props} className={["target-dock", className].filter(Boolean).join(" ")} side={side} state={state}>
      {isRightDock ? (
        <>
          <div className={["target-dock-head", headerClassName].filter(Boolean).join(" ")}>
            {header}
            {showToggle ? (
              <DockToggleButton
                className={toggleClassName}
                iconClassName={toggleIconClassName}
                iconName={toggleIconName}
                side={side}
                state={state}
                onToggle={onToggle}
                labelOpen={labelOpen}
                labelClosed={labelClosed}
                labelTucked={labelTucked}
              />
            ) : null}
          </div>

          <DockBody className={bodyClassName} state={state}>
            {children}
          </DockBody>
        </>
      ) : (
        <>
          <DockToggleButton
            className={toggleClassName}
            iconClassName={toggleIconClassName}
            iconName={toggleIconName}
            side={side}
            state={state}
            onToggle={onToggle}
            labelOpen={labelOpen}
            labelClosed={labelClosed}
            labelTucked={labelTucked}
          />

          <DockBody className={bodyClassName} state={state}>
            {children}
          </DockBody>
        </>
      )}
    </DockSurface>
  );
}

export function Chip({
  icon,
  children,
  tone = "neutral",
  title,
  ariaLabel,
}: {
  icon?: Parameters<typeof Icon>[0]["name"];
  children?: ReactNode;
  tone?: ChipTone;
  title?: string;
  ariaLabel?: string;
}) {
  return (
    <span className="chip" data-tone={tone} title={title} aria-label={ariaLabel}>
      {icon ? <Icon name={icon} className="chip-icon" /> : null}
      {children != null ? <span>{children}</span> : null}
    </span>
  );
}

export function Avatar({
  initials,
  tone,
  size = "sm",
  src,
  alt,
  fallback = "initials",
}: {
  initials: string;
  tone: ShellTone;
  size?: "sm" | "md" | "lg";
  src?: string | null;
  alt?: string;
  fallback?: "initials" | "smiley";
}) {
  if (src) {
    return (
      <span className="target-avatar target-avatar-photo" data-tone={tone} data-size={size}>
        <img alt={alt ?? ""} draggable="false" src={src} />
      </span>
    );
  }

  if (fallback === "smiley") {
    return (
      <span className="target-avatar target-avatar-smiley" data-tone={tone} data-size={size} aria-hidden="true">
        <svg viewBox="0 0 100 100" aria-hidden="true">
          <circle cx="50" cy="50" r="50" fill="rgba(255, 255, 255, 0.14)" />
          <circle cx="37" cy="41" r="4.4" fill="currentColor" />
          <circle cx="63" cy="41" r="4.4" fill="currentColor" />
          <path d="M34 57c4.5 9.2 27.5 9.2 32 0" fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
          <path d="M29 31c4.1-4.7 10.6-7.1 17-7.1" fill="none" stroke="white" strokeOpacity=".42" strokeWidth="3.5" strokeLinecap="round" />
          <circle cx="31" cy="63" r="4.8" fill="white" opacity=".12" />
          <circle cx="69" cy="63" r="4.8" fill="white" opacity=".08" />
        </svg>
      </span>
    );
  }

  return (
    <span className="target-avatar" data-tone={tone} data-size={size}>
      {initials}
    </span>
  );
}

export function ActionButton({
  label,
  icon,
  primary,
  onClick,
}: {
  label: string;
  icon: Parameters<typeof Icon>[0]["name"];
  primary?: boolean;
  onClick?: () => void;
}) {
  return (
    <button className="action-button" data-primary={primary ? "true" : "false"} type="button" onClick={onClick}>
      <Icon name={icon} className="action-icon" />
      <span>{label}</span>
    </button>
  );
}

export function ActionNoticeCard({
  label = "Workspace update",
  title = "Action queued",
  notice,
}: {
  label?: string;
  title?: string;
  notice: string | null;
}) {
  if (!notice) {
    return null;
  }

  return (
    <article className="target-note-card target-action-notice" aria-live="polite">
      <span className="target-note-label">{label}</span>
      <div className="target-note-body">
        <strong>{title}</strong>
        <span>{notice}</span>
      </div>
    </article>
  );
}

export type CommandPopoverAction = PageCommandAction & {
  onClick: () => void;
};

export function CommandPopoverButton({
  className = "",
  triggerClassName = "",
  panelClassName = "",
  title,
  eyebrow,
  triggerLabel,
  triggerIcon = "spark",
  actions,
  align = "right",
  side = "bottom",
  ariaLabel,
}: {
  className?: string;
  triggerClassName?: string;
  panelClassName?: string;
  title?: string;
  eyebrow?: string;
  triggerLabel: string;
  triggerIcon?: IconName;
  actions: ReadonlyArray<CommandPopoverAction>;
  align?: "left" | "right";
  side?: "top" | "bottom";
  ariaLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [panelStyle, setPanelStyle] = useState<CSSProperties>({});
  const menuRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  const updatePanelPosition = useCallback(() => {
    const trigger = triggerRef.current;

    if (!trigger) {
      return;
    }

    const rect = trigger.getBoundingClientRect();
    const topOffset = 12;
    const verticalStyle = side === "top" ? { bottom: Math.max(12, window.innerHeight - rect.top + topOffset) } : { top: rect.bottom + topOffset };
    const horizontalStyle =
      align === "left"
        ? { left: Math.max(12, rect.left) }
        : { right: Math.max(12, window.innerWidth - rect.right) };

    setPanelStyle({
      position: "fixed",
      opacity: 1,
      visibility: "visible",
      pointerEvents: "auto",
      transform: "translateY(0) scale(1)",
      transition: "none",
      ...verticalStyle,
      ...horizontalStyle,
    });
  }, [align, side]);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const node = menuRef.current;
      const panelNode = panelRef.current;
      const target = event.target;

      if (!node || !open) {
        return;
      }

      if (target instanceof Node && (node.contains(target) || panelNode?.contains(target))) {
        return;
      }

      setOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }

      if (open) {
        setOpen(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  useLayoutEffect(() => {
    if (!open) {
      return;
    }

    updatePanelPosition();

    const handleResize = () => {
      updatePanelPosition();
    };

    window.addEventListener("resize", handleResize);
    window.addEventListener("scroll", handleResize, true);

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("scroll", handleResize, true);
    };
  }, [open, updatePanelPosition]);

  return (
    <div
      ref={menuRef}
      className={["target-popover target-command-popover", className].filter(Boolean).join(" ")}
      data-open={open ? "true" : "false"}
    >
      <button
        ref={triggerRef}
        className={["target-popover-trigger target-command-trigger", triggerClassName].filter(Boolean).join(" ")}
        aria-label={ariaLabel ?? triggerLabel}
        aria-expanded={open}
        aria-haspopup="menu"
        type="button"
        onClick={() => setOpen((current) => !current)}
      >
        <span className="target-command-trigger-icon-wrap" aria-hidden="true">
          <Icon name={triggerIcon} className="target-command-trigger-icon" />
        </span>
        <span className="target-command-trigger-copy">
          <strong>{triggerLabel}</strong>
          <span>{actions.length} options</span>
        </span>
        <span className="target-command-trigger-chevron" aria-hidden="true">
          <Icon name="chevron" />
        </span>
      </button>
      {open && typeof document !== "undefined"
        ? createPortal(
            <div
              ref={panelRef}
              className={["target-popover-panel target-command-panel", panelClassName].filter(Boolean).join(" ")}
              data-align={align}
              data-side={side}
              style={panelStyle}
            >
              {eyebrow || title ? (
                <div className="target-command-panel-head">
                  <div className="target-command-panel-copy">
                    {eyebrow ? <span className="section-label">{eyebrow}</span> : null}
                    {title ? <strong>{title}</strong> : null}
                  </div>
                  <span className="target-command-panel-meta">{actions.length} actions</span>
                </div>
              ) : null}

              <div className="target-command-list" role="menu" aria-label={ariaLabel ?? triggerLabel}>
                {actions.map((action) => (
                  <button
                    key={action.label}
                    className="target-command-option"
                    data-primary={action.primary ? "true" : "false"}
                    role="menuitem"
                    type="button"
                    onClick={() => {
                      setOpen(false);
                      window.setTimeout(() => {
                        action.onClick();
                      }, 0);
                    }}
                  >
                    <span className={["target-command-option-icon", action.primary ? "is-primary" : ""].filter(Boolean).join(" ")} aria-hidden="true">
                      <Icon name={action.icon ?? "spark"} />
                    </span>
                    <span className="target-command-option-copy">
                      <strong>{action.label}</strong>
                      {action.primary ? <span>Primary action</span> : null}
                    </span>
                    <Icon name="chevron" className="target-command-option-chevron" aria-hidden="true" />
                  </button>
                ))}
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}

export function PageCommandStrip({
  outerClassName = "",
  panelClassName = "target-command-panel-wide",
  ...props
}: Omit<Parameters<typeof CommandPopoverButton>[0], "className" | "panelClassName"> & {
  outerClassName?: string;
  panelClassName?: string;
}) {
  return (
    <div className={["target-actions", outerClassName].filter(Boolean).join(" ")}>
      <CommandPopoverButton {...props} panelClassName={panelClassName} />
    </div>
  );
}

export function SidebarItemButton({
  label,
  icon,
  active,
  badge,
  collapsed,
  onSelect,
}: {
  label: string;
  icon: Parameters<typeof Icon>[0]["name"];
  active?: boolean;
  badge?: string;
  collapsed?: boolean;
  onSelect?: () => void;
}) {
  return (
    <button
      className="target-sidebar-item"
      data-active={active ? "true" : "false"}
      data-collapsed={collapsed ? "true" : "false"}
      aria-current={active ? "page" : undefined}
      aria-label={label}
      title={label}
      type="button"
      onClick={onSelect}
    >
      <span className="target-sidebar-icon">
        <Icon name={icon} />
      </span>
      <span className="target-sidebar-label">{label}</span>
      {badge ? <span className="target-sidebar-badge">{badge}</span> : null}
    </button>
  );
}

export function SidebarCollapseButton({
  state,
  onToggle,
}: {
  state: "open" | "closed" | "tucked";
  onToggle: () => void;
}) {
  return (
    <DockToggleButton
      className="target-sidebar-toggle"
      iconClassName="target-sidebar-toggle-icon"
      side="left"
      state={state}
      onToggle={onToggle}
      labelOpen="Hide sidebar"
      labelClosed="Expand sidebar"
      labelTucked="Show sidebar"
    />
  );
}

export function ControlPanelCollapseButton({
  state,
  onToggle,
}: {
  state: ControlPanelState;
  onToggle: () => void;
}) {
  return (
    <DockToggleButton
      className="target-control-panel-toggle"
      iconClassName="target-control-panel-toggle-icon"
      side="right"
      state={state}
      onToggle={onToggle}
      labelOpen="Hide control panel"
      labelClosed="Show control panel"
    />
  );
}

export function ControlPanelShell({
  className = "",
  state,
  onToggle,
  showToggle = true,
  eyebrow,
  title,
  headerAccessory,
  children,
}: {
  className?: string;
  state: ControlPanelState;
  onToggle: () => void;
  showToggle?: boolean;
  eyebrow: string;
  title: string;
  headerAccessory?: ReactNode;
  children: ReactNode;
}) {
  const collapsed = state === "closed";

  return (
    <DockShell
      className={["target-control-panel panel", className].filter(Boolean).join(" ")}
      bodyClassName="target-control-panel-body"
      header={
        <div className="target-control-panel-head-stack">
          <div className="target-control-panel-head-row">
            <div className="target-control-panel-copy" data-collapsed={collapsed ? "true" : "false"}>
              <span className="section-label">{eyebrow}</span>
              <h3>{title}</h3>
            </div>
            {headerAccessory ? <div className="target-control-panel-accessory">{headerAccessory}</div> : null}
          </div>
        </div>
      }
      headerClassName="target-control-panel-head"
      labelClosed="Show control panel"
      labelOpen="Hide control panel"
      aria-label={title}
      onToggle={onToggle}
      showToggle={showToggle}
      side="right"
      state={state}
      toggleClassName="target-control-panel-toggle"
      toggleIconClassName="target-control-panel-toggle-icon"
    >
      {children}
    </DockShell>
  );
}

export type DockTabItem = {
  id: string;
  label: string;
  icon: IconName;
  badge?: string;
};

export function DockButtonGroup({
  className = "",
  ariaLabel,
  activeButtonId,
  onButtonChange,
  buttons,
}: {
  className?: string;
  ariaLabel: string;
  activeButtonId: string;
  onButtonChange: (buttonId: string) => void;
  buttons: DockTabItem[];
}) {
  return (
    <div className={["target-dock-buttons", className].filter(Boolean).join(" ")} role="group" aria-label={ariaLabel}>
      {buttons.map((button) => {
        const active = button.id === activeButtonId;

        return (
          <button
            key={button.id}
            className="target-dock-button"
            data-active={active ? "true" : "false"}
            type="button"
            aria-pressed={active}
            aria-label={button.label}
            title={button.label}
            onClick={() => onButtonChange(button.id)}
          >
            <span className="target-dock-button-icon">
              <Icon name={button.icon} />
            </span>
            {button.badge ? <span className="target-dock-button-badge">{button.badge}</span> : null}
          </button>
        );
      })}
    </div>
  );
}

export function DockTabSwitcher({
  className = "",
  ariaLabel,
  activeTabId,
  idPrefix,
  onTabChange,
  tabs,
}: {
  className?: string;
  ariaLabel: string;
  activeTabId: string;
  idPrefix: string;
  onTabChange: (tabId: string) => void;
  tabs: DockTabItem[];
}) {
  const tabButtonRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!tabs.length) {
      return;
    }

    let nextIndex = -1;

    switch (event.key) {
      case "ArrowLeft":
      case "ArrowUp":
        nextIndex = (index - 1 + tabs.length) % tabs.length;
        break;
      case "ArrowRight":
      case "ArrowDown":
        nextIndex = (index + 1) % tabs.length;
        break;
      case "Home":
        nextIndex = 0;
        break;
      case "End":
        nextIndex = tabs.length - 1;
        break;
      default:
        return;
    }

    event.preventDefault();

    const nextTab = tabs[nextIndex];

    if (!nextTab) {
      return;
    }

    onTabChange(nextTab.id);
    tabButtonRefs.current[nextTab.id]?.focus();
  };

  return (
    <div className={["target-dock-tabs", className].filter(Boolean).join(" ")} role="tablist" aria-label={ariaLabel}>
      {tabs.map((tab, index) => {
        const active = tab.id === activeTabId;
        const tabButtonId = `${idPrefix}-${tab.id}-tab`;
        const tabPanelId = `${idPrefix}-${tab.id}-panel`;

        return (
          <button
            key={tab.id}
            ref={(node) => {
              tabButtonRefs.current[tab.id] = node;
            }}
            className="target-dock-tab"
            data-active={active ? "true" : "false"}
            id={tabButtonId}
            role="tab"
            aria-selected={active}
            aria-controls={tabPanelId}
            tabIndex={active ? 0 : -1}
            type="button"
            onClick={() => onTabChange(tab.id)}
            onKeyDown={(event) => handleKeyDown(event, index)}
          >
            <span className="target-dock-tab-label">{tab.label}</span>
            {tab.badge ? <span className="target-dock-tab-badge">{tab.badge}</span> : null}
          </button>
        );
      })}
    </div>
  );
}

export function SegmentTab({
  label,
  active,
  onClick,
}: {
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button className="target-segment-tab" data-active={active ? "true" : "false"} type="button" aria-pressed={active ? "true" : "false"} onClick={onClick}>
      {label}
    </button>
  );
}

export function InspectorTab({
  label,
  active,
  onClick,
}: {
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button className="target-inspector-tab" data-active={active ? "true" : "false"} type="button" aria-pressed={active ? "true" : "false"} onClick={onClick}>
      {label}
    </button>
  );
}

export function PriorityTaskRow({
  task,
}: {
  task: TaskItem;
}) {
  return (
    <article className="target-task-row">
      <span className="target-task-icon" data-tone={task.tone}>
        <Icon name={task.icon} />
      </span>
      <div className="target-task-copy">
        <strong>{task.title}</strong>
        <span>{task.zone}</span>
      </div>
      <span className="target-task-pill" data-tone={task.tone}>
        {task.priority}
      </span>
      <span className="target-task-due">{task.due}</span>
      <Avatar initials={task.avatar} tone={task.avatarTone} />
      <Icon name="chevron" className="target-task-chevron" />
    </article>
  );
}

export function TaskSummaryCard({
  stat,
  compact = false,
  active = false,
  onClick,
}: {
  stat: TaskSummaryStat;
  compact?: boolean;
  active?: boolean;
  onClick?: () => void;
}) {
  const cardContent = (
    <>
      <span className="target-task-summary-icon">
        <Icon name={stat.icon} />
      </span>
      <div className="target-task-summary-copy">
        <span className="section-label">{stat.label}</span>
        <strong>{stat.value}</strong>
        <span>{stat.detail}</span>
      </div>
    </>
  );

  if (onClick) {
    return (
      <button
        className="target-task-summary-card"
        data-active={active ? "true" : "false"}
        data-tone={stat.tone}
        data-compact={compact ? "true" : "false"}
        type="button"
        aria-pressed={active}
        onClick={onClick}
      >
        {cardContent}
      </button>
    );
  }

  return (
    <article className="target-task-summary-card" data-tone={stat.tone} data-compact={compact ? "true" : "false"}>
      {cardContent}
    </article>
  );
}

export function TaskStatRail({
  stats,
  compact = false,
  label,
  className,
  activeStatLabel,
  onStatClick,
}: {
  stats: TaskSummaryStat[];
  compact?: boolean;
  label?: string;
  className?: string;
  activeStatLabel?: string;
  onStatClick?: (stat: TaskSummaryStat) => void;
}) {
  return (
    <div className={["target-task-stat-rail", className].filter(Boolean).join(" ")} aria-label={label}>
      {stats.map((stat) => (
        <TaskSummaryCard
          key={stat.label}
          stat={stat}
          compact={compact}
          active={activeStatLabel === stat.label}
          onClick={onStatClick ? () => onStatClick(stat) : undefined}
        />
      ))}
    </div>
  );
}

export function TaskFilterButton({ item, onClick }: { item: TaskFilterItem; onClick?: () => void }) {
  return (
    <button
      className="target-task-filter-button"
      data-active={item.active ? "true" : "false"}
      data-tone={item.tone}
      type="button"
      aria-pressed={item.active ? "true" : "false"}
      onClick={onClick}
    >
      <span className="target-task-filter-icon">
        <Icon name={item.icon} />
      </span>
      <span className="target-task-filter-copy">
        <strong>{item.label}</strong>
        {item.count ? <span>{item.count}</span> : null}
      </span>
    </button>
  );
}

export function TaskQueueRow({
  task,
  selected,
  onSelect,
}: {
  task: TaskQueueEntry;
  selected?: boolean;
  onSelect?: () => void;
}) {
  const isSelected = selected ?? task.selected ?? false;

  return (
    <article className="target-task-queue-row" data-task-id={task.id} data-task-status={task.status} data-tone={task.tone} data-selected={isSelected ? "true" : "false"}>
      <div className="target-task-queue-task">
        <span className="target-task-queue-icon" data-tone={task.tone}>
          <Icon name={task.icon} />
        </span>
        <div className="target-task-queue-copy">
          <strong>{task.title}</strong>
          <span>{task.status === "completed" ? "Completed" : task.subtitle}</span>
        </div>
      </div>
      <span className="target-task-queue-zone">{task.zone}</span>
      <span className="target-task-queue-due">{task.due}</span>
      <div className="target-task-queue-crew">
        <div className="target-task-queue-crew-stack">
          {task.crewMembers.map((member, index) => (
            <Avatar key={`${task.title}-${member.initials}-${index}`} initials={member.initials} tone={member.tone} />
          ))}
          {task.crewOverflow ? <span className="target-task-queue-crew-more">{task.crewOverflow}</span> : null}
        </div>
        <span>{task.crew}</span>
      </div>
      <span className="target-task-pill" data-tone={task.tone}>
        {task.priority}
      </span>
      <button className="target-task-select" data-selected={isSelected ? "true" : "false"} aria-label={`Select ${task.title}`} type="button" aria-pressed={isSelected} onClick={onSelect}>
        <span />
      </button>
    </article>
  );
}

export function TaskStatusOption({ label, active, onClick }: { label: string; active?: boolean; onClick?: () => void }) {
  return (
    <button className="target-task-status-option" data-active={active ? "true" : "false"} type="button" aria-pressed={active ? "true" : "false"} onClick={onClick}>
      {label}
    </button>
  );
}

export function TaskQueueSectionBlock({
  section,
  maxRows,
  density = "regular",
  onViewAll,
  selectedTaskId,
  onSelectTask,
}: {
  section: TaskQueueSection;
  maxRows?: number;
  density?: "regular" | "compact";
  onViewAll?: () => void;
  selectedTaskId?: string;
  onSelectTask?: (taskId: string) => void;
}) {
  const rows = typeof maxRows === "number" ? section.rows.slice(0, maxRows) : section.rows;
  const hiddenCount = section.rows.length - rows.length;

  return (
    <section className="target-task-queue-section" data-density={density} aria-label={`${section.label} tasks`}>
      <div className="target-task-queue-section-head">
        <div>
          <span>{section.label}</span>
          <strong>{section.count}</strong>
        </div>
        <button className="target-task-queue-view" type="button" onClick={onViewAll}>
          View all
          <Icon name="chevron" />
        </button>
      </div>

      <div className="target-task-queue-list">
        {rows.map((task) => (
          <TaskQueueRow key={task.id ?? task.title} selected={selectedTaskId ? task.id === selectedTaskId : task.selected} task={task} onSelect={onSelectTask && task.id ? () => onSelectTask(task.id!) : undefined} />
        ))}
      </div>

      {hiddenCount > 0 ? (
        <div className="target-task-queue-more" aria-label={`${hiddenCount} more tasks hidden`}>
          {hiddenCount} more hidden
        </div>
      ) : null}
    </section>
  );
}

export function InspectorScoreCard() {
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const strokeOffset = circumference * (1 - 0.58);

  return (
    <article className="target-score-card">
      <div className="target-score-head">
        <span className="target-metric-label">Health Score</span>
        <span className="target-score-trend">↓ 12%</span>
      </div>

      <div className="target-score-body">
        <svg aria-hidden="true" className="target-score-gauge" viewBox="0 0 100 100">
          <circle className="target-score-track" cx="50" cy="50" r={radius} />
          <circle
            className="target-score-progress"
            cx="50"
            cy="50"
            r={radius}
            strokeDasharray={`${circumference} ${circumference}`}
            strokeDashoffset={strokeOffset}
          />
          <text className="target-score-value" x="50" y="52" textAnchor="middle">
            58
          </text>
          <text className="target-score-unit" x="50" y="66" textAnchor="middle">
            /100
          </text>
        </svg>

        <div className="target-score-chart">
          <svg aria-hidden="true" viewBox="0 0 132 54">
            <path
              d="M4 42 18 38 28 32 42 34 54 25 68 27 82 18 94 21 108 13 128 16"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="3"
            />
            <path d="M4 42H128" fill="none" stroke="currentColor" strokeOpacity=".12" strokeWidth="2" />
          </svg>
          <span>vs last 7 days</span>
        </div>
      </div>
    </article>
  );
}

export function InspectorMetricCard({
  label,
  value,
  status,
  detail,
  icon,
  tone,
  progress,
}: Extract<MetricItem, { kind: "metric" }>) {
  return (
    <article className="target-metric-card" data-tone={tone}>
      <div className="target-metric-head">
        <span className="target-metric-icon">
          <Icon name={icon} />
        </span>
        <span className="target-metric-status">{status}</span>
      </div>

      <div className="target-metric-body">
        <strong>{value}</strong>
        <span>{label}</span>
      </div>

      {progress != null ? (
        <div className="target-progress">
          <span style={{ width: `${progress}%` }} />
        </div>
      ) : null}

      {detail ? <div className="target-metric-detail">{detail}</div> : null}
    </article>
  );
}

export function TopbarPopover({
  className,
  summary,
  children,
  label,
  align = "right",
  triggerClassName = "",
  side = "bottom",
}: {
  className: string;
  summary: ReactNode;
  children: ReactNode;
  label: string;
  align?: "left" | "right";
  triggerClassName?: string;
  side?: "top" | "bottom";
}) {
  return (
    <details className={`target-popover ${className}`}>
      <summary className={`target-popover-trigger ${triggerClassName}`.trim()} aria-label={label}>
        {summary}
      </summary>
      <div className="target-popover-panel" data-align={align} data-side={side}>
        {children}
      </div>
    </details>
  );
}

export function ServiceStatCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: "sage" | "forest" | "amber" | "sky";
}) {
  return (
    <article className="target-service-stat" data-tone={tone}>
      <span className="target-service-stat-label">{label}</span>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

export function TopbarServiceWidget({
  icon,
  value,
  detail,
  meta,
  ariaLabel,
}: {
  icon: Parameters<typeof Icon>[0]["name"];
  value: string;
  detail: string;
  meta?: string[];
  ariaLabel: string;
}) {
  return (
    <TopbarPopover
      className="target-service-popover"
      label={ariaLabel}
      triggerClassName="target-weather"
      summary={
        <>
          <span className="target-weather-icon-wrap" aria-hidden="true">
            <Icon name={icon} className="target-weather-icon" />
          </span>
          <span className="target-weather-copy">
            <strong>{value}</strong>
            <span className="target-weather-condition">{detail}</span>
          </span>
          {meta ? (
            <span className="target-weather-meta" aria-label={meta.join(", ")}>
              {meta.map((line) => (
                <span key={line}>{line}</span>
              ))}
            </span>
          ) : null}
          <span className="target-weather-chevron" aria-hidden="true">
            <Icon name="chevron" />
          </span>
        </>
      }
    >
      <div className="target-weather-panel" role="group" aria-label="Weather overview">
        <div className="target-weather-panel-head">
          <div>
            <span className="section-label">Weather service</span>
            <strong>Horticulture guidance</strong>
          </div>
          <span className="target-weather-panel-time">Updated 13:11</span>
        </div>

        <div className="target-weather-grid">
          <ServiceStatCard label="Air temp" value="72°F" detail="Cooling after 4pm" tone="sage" />
          <ServiceStatCard label="Humidity" value="68%" detail="Good spray window" tone="sky" />
          <ServiceStatCard label="Wind" value="6 mph" detail="NW breeze" tone="forest" />
          <ServiceStatCard label="Rain chance" value="18%" detail="Light afternoon chance" tone="amber" />
        </div>

        <div className="target-weather-callout">
          <strong>Best irrigation window</strong>
          <span>5:30-7:00 AM keeps evaporation low and gives foliage time to dry before dusk.</span>
        </div>

        <div className="target-weather-callout target-weather-callout-soft">
          <strong>Field note</strong>
          <span>Hydrate containers before 8 AM if the temperature is forecast to exceed 82°F.</span>
        </div>
      </div>
    </TopbarPopover>
  );
}

export function AccountMenu({
  title = "Garden Administrator",
  subtitle = "Signed in and ready",
  initials = "GA",
  onSignOut,
}: {
  title?: string;
  subtitle?: string;
  initials?: string;
  onSignOut?: () => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDetailsElement | null>(null);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const node = menuRef.current;

      if (!node || !node.open) {
        return;
      }

      if (event.target instanceof Node && node.contains(event.target)) {
        return;
      }

      node.open = false;
      setOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        const node = menuRef.current;

        if (node?.open) {
          node.open = false;
          setOpen(false);
        }
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  return (
    <details
      ref={menuRef}
      className="target-popover target-account-menu"
      data-open={open ? "true" : "false"}
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="target-popover-trigger target-account-trigger" aria-label="Account settings">
        <Avatar initials={initials} tone="forest" size="md" />
      </summary>
      <div className="target-popover-panel target-account-panel" data-align="right" data-side="bottom">
        <div className="target-account-header">
          <Avatar initials={initials} tone="forest" size="md" />
          <div>
            <strong>{title}</strong>
            <span>{subtitle}</span>
          </div>
        </div>
        <div className="target-account-actions">
          <button type="button">Profile settings</button>
          <button type="button">Keyboard shortcuts</button>
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              void onSignOut?.();
            }}
          >
            Sign out
          </button>
        </div>
      </div>
    </details>
  );
}

const FALLBACK_NURSERY_OPTIONS: GardenNurseryOption[] = [
  {
    id: "pineview-nursery",
    label: "Pineview Nursery",
    detail: "Primary operations",
    pill: "Active",
    icon: "leaf",
    active: true,
  },
  {
    id: "north-grove",
    label: "North Grove",
    detail: "Shared access",
    pill: "Team",
    icon: "map",
    active: false,
  },
];

export function NurserySelector({
  collapsed,
  title = "Pineview Nursery",
  subtitle = "12.4 acres",
  options = FALLBACK_NURSERY_OPTIONS,
}: {
  collapsed?: boolean;
  title?: string;
  subtitle?: string;
  options?: GardenNurseryOption[];
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDetailsElement | null>(null);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const node = menuRef.current;

      if (!node || !node.open) {
        return;
      }

      if (event.target instanceof Node && node.contains(event.target)) {
        return;
      }

      node.open = false;
      setOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        const node = menuRef.current;

        if (node?.open) {
          node.open = false;
          setOpen(false);
        }
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  return (
    <details
      ref={menuRef}
      className="target-popover target-nursery-popover"
      data-collapsed={collapsed ? "true" : "false"}
      data-open={open ? "true" : "false"}
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="target-popover-trigger target-nursery-trigger" aria-label="Switch nursery">
        <Avatar initials="PN" tone="sage" />
        <span className="target-nursery-copy">
          <strong>{title}</strong>
          <span>{subtitle}</span>
        </span>
        <Icon name="chevron" className="target-nursery-chevron" />
      </summary>
      <div className="target-popover-panel target-nursery-panel" data-align="left" data-side="top">
        <div className="target-nursery-options">
          {options.map((option) => (
            <button key={option.id} className="target-nursery-option" data-active={option.active ? "true" : "false"} type="button">
              <span className="target-nursery-option-mark">
                <Icon name={option.icon} />
              </span>
              <span className="target-nursery-option-copy">
                <strong>{option.label}</strong>
                <span>{option.detail}</span>
              </span>
              <span className="target-nursery-option-pill">{option.pill}</span>
            </button>
          ))}
        </div>
      </div>
    </details>
  );
}

export function IconButton({
  icon,
  label,
  onClick,
}: {
  icon: Parameters<typeof Icon>[0]["name"];
  label: string;
  onClick?: () => void;
}) {
  return (
    <button className="target-icon-button" type="button" aria-label={label} title={label} onClick={onClick}>
      <Icon name={icon} />
    </button>
  );
}

export function MapControls() {
  return (
    <div className="target-map-controls" aria-label="Map controls">
      <button type="button" aria-label="Locate current zone">
        <Icon name="compass" />
      </button>
      <button type="button" aria-label="Zoom in">
        <Icon name="add" />
      </button>
      <button type="button" aria-label="Zoom out">
        <Icon name="minus" />
      </button>
      <button type="button" aria-label="Map layers">
        <Icon name="layers" />
      </button>
    </div>
  );
}
