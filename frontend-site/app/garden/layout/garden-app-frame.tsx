"use client";

import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";

import type { AppPageKey, SidebarState } from "../shared";
import { ControlPanelShell } from "../shared";
import type { GardenBootstrapState } from "../services/bootstrap-service";
import { GardenSidebar } from "./garden-sidebar";
import { GardenTopbar } from "./garden-topbar";
import type { PageWorkspaceControlPanel } from "../pages/registry";

type GardenAppFrameProps = {
  bootstrap: GardenBootstrapState;
  activePage: AppPageKey;
  sidebarState: SidebarState;
  controlPanelState: "open" | "closed";
  controlPanel: PageWorkspaceControlPanel;
  overlay?: ReactNode;
  onPageChange: (page: AppPageKey) => void;
  onSignOut: () => Promise<void>;
  onSidebarToggle: () => void;
  onControlPanelToggle: () => void;
  onSidebarPointerDown: (event: ReactPointerEvent<HTMLElement>) => void;
  onSidebarPointerMove: (event: ReactPointerEvent<HTMLElement>) => void;
  onSidebarPointerUp: (event: ReactPointerEvent<HTMLElement>) => void;
  onSidebarPointerCancel: (event: ReactPointerEvent<HTMLElement>) => void;
  children: ReactNode;
};

export function GardenAppFrame({
  bootstrap,
  activePage,
  sidebarState,
  controlPanelState,
  controlPanel,
  overlay,
  onPageChange,
  onSignOut,
  onSidebarToggle,
  onControlPanelToggle,
  onSidebarPointerDown,
  onSidebarPointerMove,
  onSidebarPointerUp,
  onSidebarPointerCancel,
  children,
}: GardenAppFrameProps) {
  return (
    <main className="garden-page">
      <div className="garden-canvas target-dashboard">
        <div className="panel target-shell">
          <GardenTopbar bootstrap={bootstrap} onSignOut={onSignOut} />

          <div
            className="target-workspace"
            data-active-page={activePage}
            data-sidebar-collapsed={sidebarState === "open" ? "false" : "true"}
            data-sidebar-state={sidebarState}
            data-control-panel-state={controlPanelState}
          >
            <GardenSidebar
              bootstrap={bootstrap}
              activePage={activePage}
              sidebarState={sidebarState}
              onPageChange={onPageChange}
              onToggle={onSidebarToggle}
              onPointerDown={onSidebarPointerDown}
              onPointerMove={onSidebarPointerMove}
              onPointerUp={onSidebarPointerUp}
              onPointerCancel={onSidebarPointerCancel}
            />

            {children}

            <ControlPanelShell
              state={controlPanelState}
              onToggle={onControlPanelToggle}
              showToggle={controlPanel.showToggle}
              eyebrow={controlPanel.eyebrow}
              title={controlPanel.title}
              headerAccessory={controlPanel.headerAccessory}
            >
              {controlPanel.content}
            </ControlPanelShell>
          </div>
        </div>
        {overlay}
      </div>
    </main>
  );
}

export function GardenWorkspaceFrame({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
