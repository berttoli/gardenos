const DEFAULT_GARDEN_API_BASE_URL = "http://127.0.0.1:8000/api/v1";

export type GardenApiPath =
  | "/auth/context"
  | "/auth/login"
  | "/auth/logout"
  | "/auth/session"
  | "/workspace"
  | `/tasks/${string}/complete`
  | "/platform/alerts"
  | "/platform/assistant/chat"
  | "/platform/alerts/{alert_id}"
  | "/platform/alerts/{alert_id}/acknowledge"
  | "/platform/alerts/{alert_id}/resolve"
  | "/platform/alerts/{alert_id}/mute"
  | "/platform/alerts/{alert_id}/unmute"
  | "/platform/automation-runs"
  | "/platform/calendar"
  | "/platform/catalog"
  | "/platform/alert-policies"
  | "/platform/change-sets"
  | "/platform/events"
  | "/platform/events/stream"
  | "/platform/telemetry/{telemetry_event_id}"
  | "/platform/system-services"
  | "/platform/telemetry";

export type GardenApiQueryValue = string | number | boolean | null | undefined;

function normalizeBaseUrl(value: string): string {
  return value.replace(/\/+$/, "");
}

export function getGardenApiBaseUrl(): string {
  const configured = import.meta.env.VITE_GARDENOS_API_BASE_URL?.trim();
  if (configured) {
    if (/^https?:\/\//i.test(configured)) {
      return normalizeBaseUrl(configured);
    }

    if (typeof window !== "undefined") {
      return normalizeBaseUrl(new URL(configured.replace(/^\//, ""), `${window.location.origin}/`).toString());
    }
  }

  return DEFAULT_GARDEN_API_BASE_URL;
}

export function getGardenApiRootUrl(): string {
  return getGardenApiBaseUrl().replace(/\/api\/v1$/, "");
}

export function buildGardenApiUrl(
  path: GardenApiPath,
  query: Record<string, GardenApiQueryValue> = {},
): URL {
  const url = new URL(path.replace(/^\//, ""), `${getGardenApiBaseUrl()}/`);

  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined) {
      continue;
    }

    url.searchParams.set(key, String(value));
  }

  return url;
}

function mergeHeaders(headers: HeadersInit | undefined): Headers {
  const merged = new Headers(headers);

  if (!merged.has("accept")) {
    merged.set("accept", "application/json");
  }

  return merged;
}

export async function requestGardenApi(path: GardenApiPath, init: RequestInit = {}): Promise<Response> {
  const { headers, ...rest } = init;

  return fetch(buildGardenApiUrl(path).toString(), {
    credentials: "include",
    mode: "cors",
    ...rest,
    headers: mergeHeaders(headers),
  });
}

export async function fetchGardenApiJson<T>(path: GardenApiPath, init: RequestInit = {}): Promise<T> {
  const response = await requestGardenApi(path, init);

  if (!response.ok) {
    throw new Error(`GardenOS API request failed with status ${response.status}.`);
  }

  return (await response.json()) as T;
}
