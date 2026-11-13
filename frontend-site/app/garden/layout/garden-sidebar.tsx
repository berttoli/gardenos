"use client";

import type { PointerEvent as ReactPointerEvent } from "react";

import type { AppPageKey, SidebarState } from "../shared";
import { DockShell, NurserySelector, SidebarItemButton } from "../shared";
import type { GardenBootstrapState } from "../services/bootstrap-service";
import { buildNurseryMenuModel, buildSidebarItems } from "../services/bootstrap-service";

type GardenSidebarProps = {
  bootstrap: GardenBootstrapState;
  activePage: AppPageKey;
  sidebarState: SidebarState;
  onPageChange: (page: AppPageKey) => void;
  onToggle: () => void;
  onPointerDown: (event: ReactPointerEvent<HTMLElement>) => void;
  onPointerMove: (event: ReactPointerEvent<HTMLElement>) => void;
  onPointerUp: (event: ReactPointerEvent<HTMLElement>) => void;
  onPointerCancel: (event: ReactPointerEvent<HTMLElement>) => void;
};

export function GardenSidebar({
  bootstrap,
  activePage,
  sidebarState,
  onPageChange,
  onToggle,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onPointerCancel,
}: GardenSidebarProps) {
  const sidebarItems = buildSidebarItems(bootstrap.workspace, bootstrap.platform);
  const nurseryMenu = buildNurseryMenuModel(bootstrap.workspace);

  return (
    <DockShell
      className="target-sidebar"
      bodyClassName="target-sidebar-body"
      toggleClassName="target-sidebar-toggle"
      toggleIconClassName="target-sidebar-toggle-icon"
      labelClosed="Expand sidebar"
      labelOpen="Hide sidebar"
      labelTucked="Show sidebar"
      onToggle={onToggle}
      side="left"
      state={sidebarState}
      onPointerCancel={onPointerCancel}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      <nav className="target-sidebar-nav" aria-label="Primary">
        {sidebarItems.map((item) => (
          <SidebarItemButton
            key={item.page}
            active={activePage === item.page}
            badge={item.badge}
            collapsed={sidebarState !== "open"}
            icon={item.icon}
            label={item.label}
            onSelect={() => onPageChange(item.page)}
          />
        ))}
      </nav>

      <div className="target-sidebar-footer">
        <NurserySelector
          collapsed={sidebarState !== "open"}
          title={nurseryMenu.title}
          subtitle={nurseryMenu.subtitle}
          options={nurseryMenu.options}
        />
      </div>
    </DockShell>
  );
}
