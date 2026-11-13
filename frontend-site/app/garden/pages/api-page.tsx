"use client";

import { useEffect, useMemo, useState } from "react";

import type { GardenServiceContext } from "../services/context";
import type { PageWorkspaceView } from "./registry";
import {
  ActionButton,
  ActionNoticeCard,
  Chip,
  Icon,
  InspectorMetricCard,
  useTimedNotice,
} from "../shared";
import {
  apiSurfaceSections,
  getApiRouteTone,
  getApiSurfaceCounts,
  getApiSurfaceSection,
  summarizeApiSurfaceSections,
  type ApiMethod,
  type ApiSurfaceEndpoint,
  type ApiSurfaceSection,
  type ApiSurfaceSectionId,
} from "../services/api-surface-service";

const defaultSectionId: ApiSurfaceSectionId = "platform-catalog";

type ApiLiveSummary = {
  scopeCount: number;
  skillCount: number;
  connectorCount: number;
  serviceActionCount: number;
  automationDefinitionCount: number;
  dueTaskCount: number;
  overdueTaskCount: number;
  telemetryCount: number;
  alertCount: number;
  automationRunCount: number;
  changeSetCount: number;
  readyServiceCount: number;
  totalServiceCount: number;
};

function buildApiLiveSummary(context: GardenServiceContext | null): ApiLiveSummary | null {
  const workspace = context?.workspace ?? null;
  const platform = context?.platform ?? null;

  if (!workspace && !platform) {
    return null;
  }

  const systemServices = workspace?.system_services ?? null;
  const serviceRecords = systemServices ? Object.values(systemServices) : [];

  return {
    scopeCount: platform?.catalog.summary.scope_count ?? 0,
    skillCount: platform?.catalog.summary.skill_count ?? 0,
    connectorCount: platform?.catalog.summary.connector_count ?? 0,
    serviceActionCount: platform?.catalog.summary.service_action_count ?? 0,
    automationDefinitionCount: platform?.catalog.summary.automation_definition_count ?? 0,
    dueTaskCount: workspace?.summary.due_task_count ?? 0,
    overdueTaskCount: workspace?.summary.overdue_task_count ?? 0,
    telemetryCount: platform?.telemetry.length ?? 0,
    alertCount: platform?.alerts.length ?? 0,
    automationRunCount: platform?.automationRuns.length ?? 0,
    changeSetCount: platform?.changeSets.length ?? 0,
    readyServiceCount: serviceRecords.filter((service) => service.status === "ready").length,
    totalServiceCount: serviceRecords.length,
  };
}

function methodLabel(method: ApiMethod): string {
  switch (method) {
    case "GET":
      return "Read";
    case "PATCH":
      return "Patch";
    case "DELETE":
      return "Delete";
    case "POST":
    default:
      return "Write";
  }
}

function ApiRouteRow({
  route,
  active,
  onSelect,
}: {
  route: ApiSurfaceEndpoint;
  active?: boolean;
  onSelect?: () => void;
}) {
  return (
    <button
      className="target-api-route-row"
      data-method={route.method}
      data-selected={active ? "true" : "false"}
      type="button"
      aria-pressed={active ? "true" : "false"}
      onClick={onSelect}
    >
      <span className="target-api-route-method" data-tone={getApiRouteTone(route.method)}>
        {route.method}
      </span>

      <span className="target-api-route-copy">
        <strong>{route.summary}</strong>
        <span className="target-api-route-path">{route.path}</span>
      </span>

      <span className="target-api-route-tone">{methodLabel(route.method)}</span>

      <Icon name="chevron" className="target-api-route-chevron" />
    </button>
  );
}

function ApiSectionSummaryCard({
  section,
  active,
  onSelect,
}: {
  section: ApiSurfaceSection;
  active?: boolean;
  onSelect?: () => void;
}) {
  const counts = getApiSurfaceCounts(section);

  return (
    <button
      className="target-api-section-card"
      data-active={active ? "true" : "false"}
      data-tone={section.tone}
      type="button"
      aria-pressed={active ? "true" : "false"}
      onClick={onSelect}
    >
      <div className="target-api-section-head">
        <span className="target-api-section-icon" data-tone={section.tone}>
          <Icon name={section.icon} />
        </span>

        <div className="target-api-section-copy">
          <strong>{section.title}</strong>
          <span>{section.description}</span>
        </div>

        <Chip icon={section.icon} tone={section.tone} title={section.title} ariaLabel={section.title}>
          {counts.routeCount}
        </Chip>
      </div>

      <div className="target-api-section-meta">
        <span>{counts.readCount} read</span>
        <span>{counts.writeCount} write</span>
      </div>
    </button>
  );
}

function ApiSurfaceFocusCard({
  section,
  selectedRoutePath,
  onSelectRoute,
}: {
  section: ApiSurfaceSection;
  selectedRoutePath: string;
  onSelectRoute: (path: string) => void;
}) {
  const counts = getApiSurfaceCounts(section);
  const selectedRoute = section.endpoints.find((route) => route.path === selectedRoutePath) ?? section.endpoints[0];

  return (
    <article className="target-api-focus-card">
      <div className="target-api-focus-head">
        <div className="target-api-focus-copy">
          <span className="section-label">Selected surface</span>
          <h3>{section.title}</h3>
          <p>{section.description}</p>
        </div>

        <Chip icon={section.icon} tone={section.tone} title={section.title} ariaLabel={section.title}>
          {counts.routeCount} routes
        </Chip>
      </div>

      <div className="target-api-focus-stats" aria-label={`${section.title} summary`}>
        <Chip icon="network" tone="forest" title={`${counts.readCount} read routes`} ariaLabel="Read routes">
          {counts.readCount} read
        </Chip>
        <Chip icon="spark" tone="amber" title={`${counts.writeCount} write routes`} ariaLabel="Write routes">
          {counts.writeCount} write
        </Chip>
        <Chip icon="queue" tone="sky" title={`${section.endpoints.length} total routes`} ariaLabel="Route count">
          {section.endpoints.length} total
        </Chip>
      </div>

      {selectedRoute ? (
        <article className="target-note-card target-api-route-note">
          <span className="target-note-label">Focused route</span>
          <div className="target-note-body">
            <strong>
              {selectedRoute.method} {selectedRoute.path}
            </strong>
            <span>{selectedRoute.summary}</span>
          </div>
          <div className="target-note-meta">{methodLabel(selectedRoute.method)} operation</div>
        </article>
      ) : null}

      <div className="target-api-route-list" aria-label={`${section.title} routes`}>
        {section.endpoints.map((route) => (
          <ApiRouteRow
            key={route.path}
            active={selectedRoute?.path === route.path}
            route={route}
            onSelect={() => onSelectRoute(route.path)}
          />
        ))}
      </div>
    </article>
  );
}

function ApiSurfaceMain({
  bootstrapSource,
  isAuthenticated,
  summary,
  section,
  selectedRoutePath,
  onSelectSection,
  onSelectRoute,
  notice,
}: {
  bootstrapSource: string;
  isAuthenticated: boolean;
  summary: ReturnType<typeof summarizeApiSurfaceSections>;
  section: ApiSurfaceSection;
  selectedRoutePath: string;
  onSelectSection: (sectionId: ApiSurfaceSectionId) => void;
  onSelectRoute: (path: string) => void;
  notice: string | null;
}) {
  return (
    <section className="target-center-stack target-api-main" aria-label="API workspace">
      <article className="panel target-api-panel">
        <div className="target-api-head">
          <div className="target-api-copy">
            <span className="section-label">Documentation</span>
            <h2>API control center</h2>
            <p>
              Review the live OpenAPI surface and keep access, auth, onboarding, platform, workspace, plants,
              tasks, and utility routes visible in one place.
            </p>
          </div>

          <div className="target-api-head-meta">
            <Chip icon="network" tone="forest" title="OpenAPI 3.1" ariaLabel="OpenAPI 3.1">
              OAS 3.1
            </Chip>
            <Chip
              icon={isAuthenticated ? "people" : "offline"}
              tone={isAuthenticated ? "forest" : "amber"}
              title={isAuthenticated ? "Authenticated backend" : "Fallback shell"}
              ariaLabel={isAuthenticated ? "Authenticated backend" : "Fallback shell"}
            >
              {bootstrapSource}
            </Chip>
            <Chip icon="layers" tone="sage" title={`${summary.sectionCount} surfaces`} ariaLabel="Surface count">
              {summary.sectionCount} surfaces
            </Chip>
          </div>
        </div>

        <div className="target-api-summary">
          {[
            {
              label: "Documented routes",
              value: String(summary.routeCount),
              status: "Live",
              detail: "Across the current v1 docs surface",
              icon: "network" as const,
              tone: "forest" as const,
              progress: 100,
            },
            {
              label: "Writable routes",
              value: String(summary.writeCount),
              status: "Mutating",
              detail: "POST, PATCH, and DELETE operations",
              icon: "spark" as const,
              tone: "amber" as const,
              progress: Math.min(100, Math.round((summary.writeCount / summary.routeCount) * 100)),
            },
            {
              label: "Read routes",
              value: String(summary.readCount),
              status: "Stable",
              detail: "GET endpoints available for shell hydration",
              icon: "health" as const,
              tone: "sage" as const,
              progress: Math.min(100, Math.round((summary.readCount / summary.routeCount) * 100)),
            },
          ].map((metric) => (
            <InspectorMetricCard key={metric.label} kind="metric" {...metric} />
          ))}
        </div>

        <ActionNoticeCard label="API update" title="Selection changed" notice={notice} />

        <ApiSurfaceFocusCard
          key={section.id}
          onSelectRoute={onSelectRoute}
          selectedRoutePath={selectedRoutePath}
          section={section}
        />

        <div className="target-api-section-grid" aria-label="API surfaces">
          {apiSurfaceSections.map((surface) => (
            <ApiSectionSummaryCard
              key={surface.id}
              active={surface.id === section.id}
              section={surface}
              onSelect={() => onSelectSection(surface.id)}
            />
          ))}
        </div>
      </article>
    </section>
  );
}

function ApiControlPanel({
  context,
  section,
  selectedRoute,
  liveSummary,
  onSelectSection,
  onSelectRoute,
  onSetNotice,
}: {
  context: GardenServiceContext | null;
  section: ApiSurfaceSection;
  selectedRoute: ApiSurfaceEndpoint | null;
  liveSummary: ApiLiveSummary | null;
  onSelectSection: (sectionId: ApiSurfaceSectionId) => void;
  onSelectRoute: (path: string) => void;
  onSetNotice: (message: string) => void;
}) {
  const counts = getApiSurfaceCounts(section);
  const auth = context?.auth;
  const principal = auth?.principal;
  const serviceLabel = principal?.label ?? "Garden Administrator";
  const detailLabel = principal?.kind === "service_account" ? "Service account active" : auth?.authenticated ? "Signed in" : "Fallback shell";

  return (
    <section className="target-api-control-view">
      <div className="target-api-control-head">
        <div className="target-api-control-copy">
          <span className="section-label">Focused route</span>
          <h4>{section.title}</h4>
          <p>{selectedRoute ? selectedRoute.summary : section.description}</p>
        </div>

        <Chip icon={section.icon} tone={section.tone} title={section.title} ariaLabel={section.title}>
          {counts.routeCount} routes
        </Chip>
      </div>

      {selectedRoute ? (
        <article className="target-note-card target-api-route-card">
          <span className="target-note-label">{selectedRoute.method}</span>
          <div className="target-note-body">
            <strong>{selectedRoute.path}</strong>
            <span>{selectedRoute.summary}</span>
          </div>
          <div className="target-note-meta">{methodLabel(selectedRoute.method)} route in the v1 surface</div>
        </article>
      ) : null}

      <article className="target-note-card target-api-section-card-note">
        <span className="target-note-label">Surface stats</span>
        <div className="target-note-body">
          <strong>{counts.readCount} read · {counts.writeCount} write</strong>
          <span>{section.endpoints.length} total routes in this surface.</span>
        </div>
        <div className="target-note-meta">Matched against the current OpenAPI docs</div>
      </article>

      <article className="target-note-card target-api-live-card">
        <span className="target-note-label">Live backend snapshot</span>
        <div className="target-note-body">
          <strong>
            {liveSummary
              ? `${liveSummary.scopeCount} scopes · ${liveSummary.automationDefinitionCount} automations`
              : "Backend unavailable"}
          </strong>
          <span>
            {liveSummary
              ? `${liveSummary.dueTaskCount} due tasks · ${liveSummary.overdueTaskCount} overdue tasks · ${liveSummary.alertCount} alerts`
              : "Connect the shell to GardenOS to populate live counts."}
          </span>
        </div>
        <div className="target-note-meta">
          {liveSummary
            ? `${liveSummary.readyServiceCount}/${liveSummary.totalServiceCount} system services ready · ${liveSummary.telemetryCount} telemetry events · ${liveSummary.automationRunCount} automation runs · ${liveSummary.changeSetCount} change sets`
            : "Fallback shell"}
        </div>
      </article>

      <article className="target-note-card target-api-auth-card">
        <span className="target-note-label">Auth context</span>
        <div className="target-note-body">
          <strong>{serviceLabel}</strong>
          <span>
            {detailLabel}
            {principal ? ` · ${principal.roles.length} roles · ${principal.permissions.length} permissions` : ""}
          </span>
        </div>
        <div className="target-note-meta">
          {principal ? `${principal.group_ids.length} groups · ${principal.scope_ids.length} scopes` : "No authenticated principal"}
        </div>
      </article>

      <div className="target-api-control-actions">
        <ActionButton
          icon="layers"
          label="Reset platform focus"
          primary
          onClick={() => {
            onSelectSection(defaultSectionId);
            onSetNotice("Focused the platform catalog surface.");
          }}
        />
        <ActionButton
          icon="people"
          label="Inspect access"
          onClick={() => {
            onSelectSection("access");
            onSetNotice("Focused the access and identity surface.");
          }}
        />
        <ActionButton
          icon="health"
          label="Inspect ops"
          onClick={() => {
            onSelectSection("platform-operations");
            onSetNotice("Focused the platform operations surface.");
          }}
        />
      </div>

      <article className="target-note-card target-api-control-note">
        <span className="target-note-label">Selection behavior</span>
        <div className="target-note-body">
          <strong>Route control is section-aware</strong>
          <span>Click a surface in the main view to expand its routes, then pick a route to inspect it here.</span>
        </div>
        <div className="target-note-meta">{section.endpoints.length} routes in the active surface</div>
      </article>

      <div className="target-api-route-rail" aria-label="Surface route quick picks">
        {section.endpoints.slice(0, 4).map((route) => (
          <button
            key={route.path}
            className="target-api-rail-item"
            data-active={selectedRoute?.path === route.path ? "true" : "false"}
            type="button"
            aria-pressed={selectedRoute?.path === route.path ? "true" : "false"}
            onClick={() => {
              onSelectRoute(route.path);
              onSetNotice(`Selected ${route.method} ${route.path}.`);
            }}
          >
            <span className="target-api-rail-item-method" data-tone={getApiRouteTone(route.method)}>
              {route.method}
            </span>
            <span className="target-api-rail-item-copy">
              <strong>{route.summary}</strong>
              <span>{route.path}</span>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}

export function ApiPage(context: GardenServiceContext | null = null): PageWorkspaceView {
  const summary = summarizeApiSurfaceSections();
  const liveSummary = buildApiLiveSummary(context);
  const [activeSectionId, setActiveSectionId] = useState<ApiSurfaceSectionId>(defaultSectionId);
  const [selectedRoutePath, setSelectedRoutePath] = useState<string>(
    getApiSurfaceSection(defaultSectionId).endpoints[0]?.path ?? "",
  );
  const [notice, setNotice] = useTimedNotice();

  const activeSection = useMemo(() => getApiSurfaceSection(activeSectionId), [activeSectionId]);
  const selectedRoute = useMemo(
    () => activeSection.endpoints.find((route) => route.path === selectedRoutePath) ?? activeSection.endpoints[0] ?? null,
    [activeSection, selectedRoutePath],
  );

  useEffect(() => {
    if (!activeSection.endpoints.some((route) => route.path === selectedRoutePath)) {
      setSelectedRoutePath(activeSection.endpoints[0]?.path ?? "");
    }
  }, [activeSection, selectedRoutePath]);

  const bootstrapSource = context?.source === "backend" ? "Backend bootstrap" : "Fallback shell";
  const isAuthenticated = Boolean(context?.auth?.authenticated);

  return {
    main: (
      <ApiSurfaceMain
        bootstrapSource={bootstrapSource}
        isAuthenticated={isAuthenticated}
        notice={notice}
        onSelectRoute={(path) => {
          setSelectedRoutePath(path);
          const route = activeSection.endpoints.find((item) => item.path === path);
          if (route) {
            setNotice(`Focused ${route.method} ${route.path}.`);
          }
        }}
        onSelectSection={(sectionId) => {
          const nextSection = getApiSurfaceSection(sectionId);
          setActiveSectionId(sectionId);
          setSelectedRoutePath(nextSection.endpoints[0]?.path ?? "");
          setNotice(`Focused the ${nextSection.title} surface.`);
        }}
        section={activeSection}
        selectedRoutePath={selectedRoutePath}
        summary={summary}
      />
    ),
    controlPanel: {
      eyebrow: "API",
      title: "Control panel",
      content: (
        <ApiControlPanel
          context={context}
          liveSummary={liveSummary}
          onSelectRoute={(path) => {
            setSelectedRoutePath(path);
            const route = activeSection.endpoints.find((item) => item.path === path);
            if (route) {
              setNotice(`Focused ${route.method} ${route.path}.`);
            }
          }}
          onSelectSection={(sectionId) => {
            const nextSection = getApiSurfaceSection(sectionId);
            setActiveSectionId(sectionId);
            setSelectedRoutePath(nextSection.endpoints[0]?.path ?? "");
            setNotice(`Focused the ${nextSection.title} surface.`);
          }}
          onSetNotice={setNotice}
          section={activeSection}
          selectedRoute={selectedRoute}
        />
      ),
    },
  };
}
