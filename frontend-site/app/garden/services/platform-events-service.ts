import { buildGardenApiUrl, type GardenApiPath } from "./api-client";

export type GardenPlatformEvent = {
  id: string;
  scope_node_id: string | null;
  event_type: string;
  source_kind: string;
  source_id: string;
  schema_version: string;
  trace_id: string | null;
  correlation_id: string | null;
  occurred_at: string;
  payload: Record<string, unknown>;
  consumed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type GardenPlatformEventStreamOptions = {
  afterId?: string | null;
  limit?: number;
  scopeNodeId?: string | null;
};

type GardenPlatformEventPath = Extract<GardenApiPath, "/platform/events" | "/platform/events/stream">;

function buildPlatformEventsUrl(path: GardenPlatformEventPath, options: GardenPlatformEventStreamOptions = {}): URL {
  return buildGardenApiUrl(path, {
    after_id: options.afterId,
    limit: options.limit,
    scope_node_id: options.scopeNodeId,
  });
}

export async function loadGardenPlatformEvents(
  options: GardenPlatformEventStreamOptions = {},
): Promise<GardenPlatformEvent[]> {
  const response = await fetch(buildPlatformEventsUrl("/platform/events", options).toString(), {
    credentials: "include",
    headers: {
      accept: "application/json",
    },
    mode: "cors",
  });

  if (!response.ok) {
    throw new Error(`GardenOS platform events request failed with status ${response.status}.`);
  }

  return (await response.json()) as GardenPlatformEvent[];
}

export function subscribeGardenPlatformEvents(
  onEvent: (event: GardenPlatformEvent) => void,
  onError?: (error: Event) => void,
  options: GardenPlatformEventStreamOptions = {},
): EventSource | null {
  if (typeof window === "undefined") {
    return null;
  }

  const source = new EventSource(buildPlatformEventsUrl("/platform/events/stream", options).toString(), {
    withCredentials: true,
  });

  source.onmessage = (message) => {
    if (typeof message.data !== "string" || !message.data) {
      return;
    }

    try {
      onEvent(JSON.parse(message.data) as GardenPlatformEvent);
    } catch {
      // Ignore malformed frames and keep the stream alive.
    }
  };

  if (onError) {
    source.onerror = onError;
  }

  return source;
}
