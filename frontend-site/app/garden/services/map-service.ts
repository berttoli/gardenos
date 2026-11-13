import type { GardenServiceContext } from "./context";
import { inspectorMetrics, inspectorTabs, mapBackgroundSrc, mapTabs, priorityTasks, quickActions } from "../shared";

export type GardenMapModel = {
  tabs: typeof mapTabs;
  inspectorTabs: typeof inspectorTabs;
  backgroundSrc: string;
  priorityTasks: typeof priorityTasks;
  inspectorMetrics: typeof inspectorMetrics;
  quickActions: typeof quickActions;
};

export function getMapModel(_context: GardenServiceContext | null = null): GardenMapModel {
  void _context;

  return {
    tabs: mapTabs,
    inspectorTabs,
    backgroundSrc: mapBackgroundSrc,
    priorityTasks,
    inspectorMetrics,
    quickActions,
  };
}
