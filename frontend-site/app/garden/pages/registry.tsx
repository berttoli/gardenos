import type { ReactNode } from "react";

import type { AppPageKey } from "../shared";
import type { GardenServiceContext } from "../services/context";
import { GenericPage } from "./generic-page";
import { ApiPage } from "./api-page";
import { MapPage } from "./map-page";
import { MonitoringPage } from "./monitoring-page";
import { PlantsPage } from "./plants-page";
import { TaskPage } from "./task-page";

export type PageWorkspaceControlPanel = {
  eyebrow: string;
  title: string;
  headerAccessory?: ReactNode;
  showToggle?: boolean;
  content: ReactNode;
};

export type PageWorkspaceView = {
  main: ReactNode;
  controlPanel: PageWorkspaceControlPanel;
  overlay?: ReactNode;
};

export type PageWorkspaceFactory = (context: GardenServiceContext) => PageWorkspaceView;

export const pageWorkspaceRegistry: Record<AppPageKey, PageWorkspaceFactory> = {
  map: (context) => MapPage(context),
  tasks: TaskPage,
  plants: (context) => PlantsPage(context),
  monitoring: MonitoringPage,
  api: (context) => ApiPage(context),
  schedule: (context) => GenericPage({ pageKey: "schedule" }, context),
  automations: (context) => GenericPage({ pageKey: "automations" }, context),
  people: (context) => GenericPage({ pageKey: "people" }, context),
  inventory: (context) => GenericPage({ pageKey: "inventory" }, context),
  reports: (context) => GenericPage({ pageKey: "reports" }, context),
  settings: (context) => GenericPage({ pageKey: "settings" }, context),
};

export { GenericPage, MapPage, MonitoringPage, PlantsPage, TaskPage };
