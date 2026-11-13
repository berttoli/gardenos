import type { GardenBootstrapState, GardenPlatformBootstrap, GardenWorkspaceBootstrap } from "./bootstrap-service";

export type GardenServiceContext = {
  bootstrap: GardenBootstrapState | null;
  source: GardenBootstrapState["source"] | "fallback";
  auth: GardenBootstrapState["auth"];
  workspace: GardenWorkspaceBootstrap | null;
  platform: GardenPlatformBootstrap | null;
  refreshBootstrap?: () => Promise<GardenBootstrapState>;
};

export function createGardenServiceContext(
  bootstrap: GardenBootstrapState | null = null,
  refreshBootstrap?: () => Promise<GardenBootstrapState>,
): GardenServiceContext {
  return {
    bootstrap,
    source: bootstrap?.source ?? "fallback",
    auth: bootstrap?.auth ?? null,
    workspace: bootstrap?.workspace ?? null,
    platform: bootstrap?.platform ?? null,
    refreshBootstrap,
  };
}
