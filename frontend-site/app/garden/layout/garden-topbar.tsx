"use client";

import { useEffect, useRef, useState } from "react";

import { AccountMenu, Chip, Icon, TopbarServiceWidget } from "../shared";
import { ThemeMenu } from "../theme/theme-provider";
import { getTopbarModel } from "../services/topbar-service";
import type { GardenBootstrapState } from "../services/bootstrap-service";
import { buildAccountMenuModel } from "../services/bootstrap-service";

function NotificationsMenu({ unreadCount }: { unreadCount: number }) {
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
      className="target-popover target-notifications-popover"
      data-open={open ? "true" : "false"}
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="target-popover-trigger target-notifications-trigger" aria-label="Notifications">
        <Icon name="bell" />
      </summary>
      <div className="target-popover-panel" data-align="right" data-side="bottom">
        <div className="target-notifications-panel" role="group" aria-label="Recent notifications">
          <div className="target-notifications-head">
            <div>
              <span className="section-label">Notifications</span>
              <strong>Recent activity</strong>
            </div>
            <span className="target-notifications-meta">{unreadCount} open</span>
          </div>

          <div className="target-notifications-list">
            <article className="target-notification-item">
              <strong>Camellia japonica updated</strong>
              <span>Moisture check logged from the morning route.</span>
              <em>2 min ago · Fields team</em>
            </article>
            <article className="target-notification-item">
              <strong>Merge review ready</strong>
              <span>Two inventory records are ready to compare.</span>
              <em>11 min ago · Inventory service</em>
            </article>
            <article className="target-notification-item">
              <strong>Watering window opening</strong>
              <span>Best irrigation window still holds for the next 90 minutes.</span>
              <em>25 min ago · Weather service</em>
            </article>
          </div>
        </div>
      </div>
    </details>
  );
}

export function GardenTopbar({
  bootstrap,
  onSignOut,
}: {
  bootstrap: GardenBootstrapState;
  onSignOut: () => Promise<void>;
}) {
  const { weather } = getTopbarModel();
  const account = buildAccountMenuModel(bootstrap.auth);
  const platformSummary = bootstrap.platform?.catalog.summary;
  const openAlertCount = bootstrap.platform?.alerts.filter((alert) => alert.status === "open").length ?? 3;

  return (
    <header className="target-topbar">
      <div className="brand-lockup target-brand-lockup">
        <a className="brand-mark target-brand-mark" href="/" aria-label="Go to home" title="Home">
          <Icon name="leaf" />
        </a>
      </div>

      <label className="target-search" aria-label="Search plants, zones, tasks">
        <Icon name="search" />
        <input placeholder="Search plants, zones, or tasks..." />
        <span className="target-search-shortcut">⌘K</span>
      </label>

      <TopbarServiceWidget
        icon={weather.icon}
        value={weather.value}
        detail={weather.detail}
        meta={weather.meta}
        ariaLabel="Weather 72 degrees and partly cloudy"
      />

      <div className="target-topbar-actions" aria-label="Notifications and account">
        {platformSummary ? (
          <Chip
            icon="spark"
            tone="forest"
            title={`${platformSummary.skill_count} skills · ${platformSummary.connector_count} connectors · ${platformSummary.service_action_count} actions`}
            ariaLabel="Live platform catalog"
          >
            {platformSummary.scope_count} scopes
          </Chip>
        ) : null}
        <ThemeMenu />
        <NotificationsMenu unreadCount={openAlertCount} />
        <AccountMenu
          initials={account.initials}
          onSignOut={onSignOut}
          subtitle={account.subtitle}
          title={account.title}
        />
      </div>
    </header>
  );
}
