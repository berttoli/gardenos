import {
  getPageFromLocation,
  getSidebarClickState,
  sidebarItems,
  stepSidebarState,
} from "../shared";
import type { SidebarItem, SidebarState } from "../shared";

export function listSidebarItems(): SidebarItem[] {
  return sidebarItems;
}

export { getPageFromLocation, getSidebarClickState, stepSidebarState };

export type { SidebarState };
