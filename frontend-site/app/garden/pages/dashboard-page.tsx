"use client";

import { startTransition, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import type { AppPageKey, ControlPanelState, SidebarState } from "../shared";
import { GardenAppFrame } from "../layout/garden-app-frame";
import { pageWorkspaceRegistry, type PageWorkspaceFactory } from "./registry";
import { getPageFromLocation, getSidebarClickState, stepSidebarState } from "../services/navigation-service";
import {
  createFallbackBootstrap,
  loadGardenBootstrap,
  logoutGardenSession,
  type GardenBootstrapState,
} from "../services/bootstrap-service";
import { createGardenServiceContext } from "../services/context";

function TargetDashboard() {
  const [activePage, setActivePage] = useState<AppPageKey>(() => getPageFromLocation());
  const [sidebarState, setSidebarState] = useState<SidebarState>("open");
  const [controlPanelState, setControlPanelState] = useState<ControlPanelState>("open");
  const [bootstrap, setBootstrap] = useState<GardenBootstrapState>(() => createFallbackBootstrap());
  const sidebarGestureRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    suppressClick: boolean;
  } | null>(null);

  useEffect(() => {
    const handlePopState = () => {
      setActivePage(getPageFromLocation());
    };

    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    void loadGardenBootstrap().then((next) => {
      if (cancelled) {
        return;
      }

      startTransition(() => {
        setBootstrap(next);
      });
    });

    return () => {
      cancelled = true;
    };
  }, []);

  const handlePageChange = (page: AppPageKey) => {
    startTransition(() => {
      setActivePage(page);
    });

    if (typeof window === "undefined") {
      return;
    }

    const nextUrl = new URL(window.location.href);

    if (page === "map") {
      nextUrl.searchParams.delete("page");
    } else {
      nextUrl.searchParams.set("page", page);
    }

    window.history.pushState({}, "", `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`);
  };

  const handleSidebarToggle = () => {
    if (sidebarGestureRef.current?.suppressClick) {
      sidebarGestureRef.current = null;
      return;
    }

    setSidebarState((current) => getSidebarClickState(current));
  };

  const handleSidebarPointerDown = (event: ReactPointerEvent<HTMLElement>) => {
    if (event.button !== 0) {
      return;
    }

    const target = event.target;

    if (!(target instanceof Element)) {
      return;
    }

    const isHandle = Boolean(target.closest(".target-sidebar-toggle"));
    const isInteractive = Boolean(target.closest("button, a, input, textarea, select, summary")) && !isHandle;

    if (isInteractive) {
      return;
    }

    event.currentTarget.setPointerCapture(event.pointerId);
    sidebarGestureRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      suppressClick: false,
    };
  };

  const handleSidebarPointerMove = (event: ReactPointerEvent<HTMLElement>) => {
    const gesture = sidebarGestureRef.current;

    if (!gesture || gesture.pointerId !== event.pointerId) {
      return;
    }

    const deltaX = event.clientX - gesture.startX;
    const deltaY = event.clientY - gesture.startY;

    if (Math.abs(deltaX) < 10 && Math.abs(deltaY) < 10) {
      return;
    }

    if (Math.abs(deltaX) > Math.abs(deltaY) * 1.05) {
      event.preventDefault();
    }
  };

  const handleSidebarPointerUp = (event: ReactPointerEvent<HTMLElement>) => {
    const gesture = sidebarGestureRef.current;

    if (!gesture || gesture.pointerId !== event.pointerId) {
      return;
    }

    const deltaX = event.clientX - gesture.startX;
    const deltaY = event.clientY - gesture.startY;
    const movedHorizontally = Math.abs(deltaX) >= 18 && Math.abs(deltaX) > Math.abs(deltaY) * 1.15;

    if (movedHorizontally) {
      setSidebarState((current) => stepSidebarState(current, deltaX < 0 ? -1 : 1));
      sidebarGestureRef.current = {
        ...gesture,
        suppressClick: true,
      };
    } else {
      sidebarGestureRef.current = null;
    }

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const handleSidebarPointerCancel = (event: ReactPointerEvent<HTMLElement>) => {
    if (sidebarGestureRef.current?.pointerId === event.pointerId) {
      sidebarGestureRef.current = null;
    }
  };

  const handleControlPanelToggle = () => {
    setControlPanelState((current) => (current === "open" ? "closed" : "open"));
  };

  const handleSignOut = async () => {
    const csrfToken = bootstrap.auth?.csrf_token;

    if (!csrfToken) {
      startTransition(() => {
        setBootstrap(createFallbackBootstrap());
      });
      return;
    }

    try {
      await logoutGardenSession(csrfToken);
    } catch {
      // Fall back to the local shell even if the backend is unavailable.
    }

    const next = await loadGardenBootstrap();
    startTransition(() => {
      setBootstrap(next);
    });
  };

  const refreshBootstrap = async () => {
    const next = await loadGardenBootstrap({ requireWorkspace: true });
    setBootstrap(next);
    return next;
  };

  return (
    <TargetDashboardWorkspace
      bootstrap={bootstrap}
      refreshBootstrap={refreshBootstrap}
      activePage={activePage}
      controlPanelState={controlPanelState}
      onControlPanelToggle={handleControlPanelToggle}
      onPageChange={handlePageChange}
      onSignOut={handleSignOut}
      onSidebarPointerCancel={handleSidebarPointerCancel}
      onSidebarPointerDown={handleSidebarPointerDown}
      onSidebarPointerMove={handleSidebarPointerMove}
      onSidebarPointerUp={handleSidebarPointerUp}
      onSidebarToggle={handleSidebarToggle}
      sidebarState={sidebarState}
    />
  );
}

function TargetDashboardWorkspace({
  bootstrap,
  refreshBootstrap,
  activePage,
  sidebarState,
  controlPanelState,
  onPageChange,
  onSignOut,
  onSidebarToggle,
  onControlPanelToggle,
  onSidebarPointerDown,
  onSidebarPointerMove,
  onSidebarPointerUp,
  onSidebarPointerCancel,
}: {
  bootstrap: GardenBootstrapState;
  refreshBootstrap: () => Promise<GardenBootstrapState>;
  activePage: AppPageKey;
  sidebarState: SidebarState;
  controlPanelState: ControlPanelState;
  onPageChange: (page: AppPageKey) => void;
  onSignOut: () => Promise<void>;
  onSidebarToggle: () => void;
  onControlPanelToggle: () => void;
  onSidebarPointerDown: (event: ReactPointerEvent<HTMLElement>) => void;
  onSidebarPointerMove: (event: ReactPointerEvent<HTMLElement>) => void;
  onSidebarPointerUp: (event: ReactPointerEvent<HTMLElement>) => void;
  onSidebarPointerCancel: (event: ReactPointerEvent<HTMLElement>) => void;
}) {
  const Workspace = pageWorkspaceRegistry[activePage];
  const serviceContext = createGardenServiceContext(bootstrap, refreshBootstrap);

  return (
    <TargetPageSurface
      key={activePage}
      activePage={activePage}
      bootstrap={bootstrap}
      controlPanelState={controlPanelState}
      onControlPanelToggle={onControlPanelToggle}
      onPageChange={onPageChange}
      onSignOut={onSignOut}
      onSidebarPointerCancel={onSidebarPointerCancel}
      onSidebarPointerDown={onSidebarPointerDown}
      onSidebarPointerMove={onSidebarPointerMove}
      onSidebarPointerUp={onSidebarPointerUp}
      onSidebarToggle={onSidebarToggle}
      serviceContext={serviceContext}
      sidebarState={sidebarState}
      workspaceFactory={Workspace}
    />
  );
}

function TargetPageSurface({
  activePage,
  bootstrap,
  controlPanelState,
  onControlPanelToggle,
  onPageChange,
  onSignOut,
  onSidebarPointerCancel,
  onSidebarPointerDown,
  onSidebarPointerMove,
  onSidebarPointerUp,
  onSidebarToggle,
  serviceContext,
  sidebarState,
  workspaceFactory,
}: {
  activePage: AppPageKey;
  bootstrap: GardenBootstrapState;
  controlPanelState: ControlPanelState;
  onControlPanelToggle: () => void;
  onPageChange: (page: AppPageKey) => void;
  onSignOut: () => Promise<void>;
  onSidebarPointerCancel: (event: ReactPointerEvent<HTMLElement>) => void;
  onSidebarPointerDown: (event: ReactPointerEvent<HTMLElement>) => void;
  onSidebarPointerMove: (event: ReactPointerEvent<HTMLElement>) => void;
  onSidebarPointerUp: (event: ReactPointerEvent<HTMLElement>) => void;
  onSidebarToggle: () => void;
  serviceContext: ReturnType<typeof createGardenServiceContext>;
  sidebarState: SidebarState;
  workspaceFactory: PageWorkspaceFactory;
}) {
  const workspace = workspaceFactory(serviceContext);

  return (
    <div className="target-page-surface" data-page={activePage}>
      <GardenAppFrame
        bootstrap={bootstrap}
        activePage={activePage}
        sidebarState={sidebarState}
        controlPanelState={controlPanelState}
        controlPanel={workspace.controlPanel}
        overlay={workspace.overlay}
        onPageChange={onPageChange}
        onSignOut={onSignOut}
        onSidebarToggle={onSidebarToggle}
        onControlPanelToggle={onControlPanelToggle}
        onSidebarPointerDown={onSidebarPointerDown}
        onSidebarPointerMove={onSidebarPointerMove}
        onSidebarPointerUp={onSidebarPointerUp}
        onSidebarPointerCancel={onSidebarPointerCancel}
      >
        {workspace.main}
      </GardenAppFrame>
    </div>
  );
}

export default function Home() {
  return <TargetDashboard />;
}

export { TargetDashboard };
