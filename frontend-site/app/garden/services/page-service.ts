import { pageConfigs } from "../shared";
import type { AppPageKey, PageConfig } from "../shared";

export function getPageConfig(page: Exclude<AppPageKey, "map" | "plants">): PageConfig {
  return pageConfigs[page];
}
