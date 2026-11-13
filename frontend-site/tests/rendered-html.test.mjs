import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { createServer } from "vite";

let server;
let Dashboard;
let Layout;
let template;

before(async () => {
  server = await createServer({
    root: fileURLToPath(new URL("..", import.meta.url)),
    server: { middlewareMode: true, hmr: false, ws: false },
    appType: "custom",
  });
  Dashboard = (await server.ssrLoadModule("/app/page.tsx")).default;
  Layout = (await server.ssrLoadModule("/app/layout.tsx")).default;
  template = await readFile(new URL("../index.html", import.meta.url), "utf8");
});

after(async () => { await server?.close(); });

async function render(pathname = "/") {
  // Supply only the current URL; effects and API calls remain a browser-test concern.
  const previousWindow = globalThis.window;
  globalThis.window = { location: new URL(`http://localhost${pathname}`) };
  try {
    const markup = renderToString(createElement(Layout, null, createElement(Dashboard)));
    return new Response(template.replace('<div id="root"></div>', `<div id="root">${markup}</div>`), {
      headers: { "content-type": "text/html" },
    });
  } finally {
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
  }
}

test("renders the GardenOS dashboard shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>GardenOS<\/title>/i);
  assert.match(html, /Container Yard/i);
  assert.match(html, /Priority Tasks/i);
  assert.match(html, /Demo Garden/i);
  assert.match(html, /Health Score/i);
  assert.match(html, /72°F/);
  assert.match(html, /Partly Cloudy/i);
  assert.match(html, /Best irrigation window/i);
  assert.match(html, /Customize(?:\s*<!-- -->)?\s*Sage/i);
  assert.match(html, /Account settings/i);
  assert.match(html, /Signed out/i);
  assert.doesNotMatch(html, /GARDEN OS/i);
  assert.doesNotMatch(html, /Map-first control for nursery inventory, monitoring, and tasking\./);
  assert.doesNotMatch(html, /react-loading-skeleton|Building your site|Your site is taking shape/i);
  assert.doesNotMatch(html, /Phone preview|Theme foundation|Field mobile/i);
});

test("task manager route renders the triage layout", async () => {
  const response = await render("/?page=tasks");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Task Manager/i);
  assert.match(html, /Task service/i);
  assert.match(html, /Task controls/i);
  assert.match(html, /View all/i);
  assert.match(html, /Sign in to load and complete your tasks/i);
  assert.match(html, /Username/i);
  assert.match(html, /Password/i);
  assert.doesNotMatch(html, /Irrigate Greenhouse 3/i);
  assert.doesNotMatch(html, /Mark complete/i);
  assert.doesNotMatch(html, /Map-first control for nursery inventory, monitoring, and tasking\./);
});

test("monitoring route renders the realtime feed shell", async () => {
  const response = await render("/?page=monitoring");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Monitoring/i);
  assert.match(html, /Logging/i);
  assert.match(html, /Telemetry/i);
  assert.match(html, /Alerting/i);
  assert.match(html, /Realtime feed/i);
  assert.match(html, /Monitoring console/i);
  assert.match(html, /Live relay/i);
  assert.match(html, /Offline|Connecting to the event relay|Live/i);
});

test("plants route renders the inventory shell", async () => {
  const response = await render("/?page=plants");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Plant inventory/i);
  assert.match(html, /Inventory operations/i);
  assert.match(html, /Selected plant/i);
  assert.match(html, /Plant controls/i);
});

test("api route renders the stacked control panel layout", async () => {
  const response = await render("/?page=api");
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /API control center/i);
  assert.match(html, /Control panel/i);
  assert.match(html, /Focused route/i);
  assert.match(html, /Surface stats/i);
  assert.match(html, /Surface route quick picks/i);
  assert.match(html, /Route control is section-aware/i);
  assert.match(html, /Selected surface/i);
});

test("theme files define a reusable GardenOS shell", async () => {
  const [
    page,
    dashboardPage,
    registryPage,
    layoutFrame,
    layoutTopbar,
    layoutSidebar,
    navigationService,
    topbarService,
    bootstrapService,
    mapService,
    taskService,
    pageService,
    mapPage,
    taskPage,
    genericPage,
    apiPage,
    monitoringPage,
    monitoringService,
    apiSurfaceService,
    sharedIndex,
    data,
    sharedShell,
    sharedIcons,
    sharedTypes,
    layoutIndex,
    pagesIndex,
    servicesIndex,
    apiClient,
    platformEventsService,
    layout,
    css,
    favicon,
  ] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/pages/dashboard-page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/pages/registry.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/layout/garden-app-frame.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/layout/garden-topbar.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/layout/garden-sidebar.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/services/navigation-service.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/services/topbar-service.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/services/bootstrap-service.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/services/map-service.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/services/task-service.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/services/page-service.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/pages/map-page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/pages/task-page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/pages/generic-page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/pages/api-page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/pages/monitoring-page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/services/monitoring-service.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/services/api-surface-service.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/shared/index.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/shared/data.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/shared/shell.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/shared/icons.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/shared/types.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/layout/index.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/pages/index.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/services/index.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/services/api-client.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/garden/services/platform-events-service.ts", import.meta.url), "utf8"),
    readFile(new URL("../index.html", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
    readFile(new URL("../public/favicon.svg", import.meta.url), "utf8"),
  ]);

  assert.match(page, /garden\/pages\/dashboard-page/);
  assert.match(page, /TargetDashboard/);
  assert.match(dashboardPage, /TargetDashboard/);
  assert.match(dashboardPage, /pageWorkspaceRegistry/);
  assert.match(registryPage, /pageWorkspaceRegistry/);
  assert.match(layoutFrame, /GardenAppFrame/);
  assert.match(layoutFrame, /GardenWorkspaceFrame/);
  assert.match(layoutTopbar, /GardenTopbar/);
  assert.match(layoutSidebar, /GardenSidebar/);
  assert.match(navigationService, /listSidebarItems/);
  assert.match(navigationService, /getPageFromLocation/);
  assert.match(navigationService, /stepSidebarState/);
  assert.match(topbarService, /getTopbarModel/);
  assert.match(bootstrapService, /loadGardenBootstrap/);
  assert.match(bootstrapService, /buildSidebarItems/);
  assert.match(bootstrapService, /buildNurseryMenuModel/);
  assert.match(bootstrapService, /logoutGardenSession/);
  assert.match(bootstrapService, /workspace\.summary\.due_task_count/);
  assert.match(mapService, /getMapModel/);
  assert.match(taskService, /getTaskModel/);
  assert.match(taskService, /buildTaskSummaryStats/);
  assert.match(taskService, /workspace\.summary/);
  assert.match(pageService, /getPageConfig/);
  assert.match(mapPage, /MapPage/);
  assert.match(mapPage, /MapIllustration/);
  assert.match(mapPage, /InspectorPreview/);
  assert.match(taskPage, /TaskPage/);
  assert.match(taskPage, /TaskQueueSectionBlock/);
  assert.match(taskPage, /completeGardenTask/);
  assert.match(genericPage, /GenericPage/);
  assert.match(genericPage, /InspectorMetricCard/);
  assert.match(apiPage, /ApiPage/);
  assert.match(apiPage, /API control center/);
  assert.match(apiPage, /OpenAPI 3\.1/);
  assert.match(apiPage, /buildApiLiveSummary/);
  assert.match(apiPage, /system_services/);
  assert.match(monitoringPage, /MonitoringPage/);
  assert.match(monitoringPage, /subscribeGardenPlatformEvents/);
  assert.match(monitoringPage, /loadGardenPlatformEvents/);
  assert.match(monitoringPage, /payloadString/);
  assert.match(monitoringPage, /selectedTelemetryTraceId/);
  assert.match(monitoringPage, /selectedTelemetryCorrelationId/);
  assert.match(monitoringPage, /Monitoring console/);
  assert.match(monitoringPage, /Live relay/);
  assert.match(monitoringPage, /target-monitoring-layout/);
  assert.match(monitoringPage, /target-monitoring-control/);
  assert.match(monitoringService, /buildMonitoringStreamEntries/);
  assert.match(monitoringService, /buildMonitoringStreamSummary/);
  assert.match(monitoringService, /buildMonitoringConsoleModel/);
  assert.match(monitoringService, /getMonitoringConsoleModel/);
  assert.match(monitoringService, /MonitoringConsoleModeSummary/);
  assert.match(monitoringService, /MonitoringConsoleAlertingPanel/);
  assert.match(monitoringService, /systemServicesPanel/);
  assert.match(monitoringService, /system_services/);
  assert.match(monitoringService, /\/api\/v1\/platform\/system-services/);
  assert.match(apiSurfaceService, /apiSurfaceSections/);
  assert.match(apiSurfaceService, /summarizeApiSurfaceSections/);
  assert.match(apiSurfaceService, /\/api\/v1\/platform\/system-services/);
  assert.match(sharedIndex, /ActionButton/);
  assert.match(sharedIndex, /ControlPanelShell/);
  assert.match(sharedIndex, /DockShell/);
  assert.match(sharedIndex, /TaskSummaryCard/);
  assert.match(sharedIndex, /TopbarServiceWidget/);
  assert.match(sharedIndex, /NurserySelector/);
  assert.match(sharedShell, /Avatar/);
  assert.match(sharedShell, /ControlPanelCollapseButton/);
  assert.match(sharedShell, /ControlPanelShell/);
  assert.match(sharedShell, /DockShell/);
  assert.match(sharedShell, /PageCommandStrip/);
  assert.match(sharedShell, /TaskQueueSectionBlock/);
  assert.match(sharedIcons, /iconGlyphs/);
  assert.match(sharedTypes, /AppPageKey/);
  assert.match(sharedTypes, /ControlPanelState/);
  assert.match(layoutIndex, /GardenAppFrame/);
  assert.match(pagesIndex, /pageWorkspaceRegistry/);
  assert.match(servicesIndex, /getTaskModel/);
  assert.match(servicesIndex, /loadGardenBootstrap/);
  assert.match(servicesIndex, /buildMonitoringStreamEntries/);
  assert.match(servicesIndex, /loadGardenPlatformEvents/);
  assert.match(servicesIndex, /subscribeGardenPlatformEvents/);
  assert.match(servicesIndex, /buildMonitoringConsoleModel/);
  assert.match(servicesIndex, /getMonitoringConsoleModel/);
  assert.match(servicesIndex, /MonitoringConsoleModeSummary/);
  assert.match(servicesIndex, /MonitoringConsoleAlertingPanel/);
  assert.match(servicesIndex, /buildGardenApiUrl/);
  assert.match(servicesIndex, /fetchGardenApiJson/);
  assert.match(servicesIndex, /getGardenApiBaseUrl/);
  assert.match(servicesIndex, /requestGardenApi/);
  assert.match(servicesIndex, /apiSurfaceSections/);
  assert.match(apiClient, /buildGardenApiUrl/);
  assert.match(apiClient, /fetchGardenApiJson/);
  assert.match(apiClient, /getGardenApiBaseUrl/);
  assert.match(apiClient, /requestGardenApi/);
  assert.match(apiClient, /\/platform\/events/);
  assert.match(apiClient, /\/auth\/context/);
  assert.match(platformEventsService, /loadGardenPlatformEvents/);
  assert.match(platformEventsService, /subscribeGardenPlatformEvents/);
  assert.match(data, /pageConfigs/);
  assert.match(data, /page: "api"/);
  assert.doesNotMatch(data, /badge: "8"/);
  assert.match(data, /taskQueueSections/);
  assert.match(data, /getPageFromLocation/);
  assert.match(data, /stepSidebarState/);
  assert.match(layout, /GardenOS/);
  assert.match(css, /target-monitoring-console/);
  assert.match(css, /target-monitoring-layout/);
  assert.match(css, /target-monitoring-control/);
  assert.match(css, /target-monitoring-detail-card/);
  assert.match(css, /target-monitoring-row/);
  assert.match(css, /target-monitoring-mode-card/);
  assert.match(css, /min-width: 0;/);
  assert.match(css, /overflow-wrap: anywhere;/);
  assert.match(css, /@media \(max-width: 1200px\)/);
  assert.match(layout, /name="description"/);
  assert.match(css, /--garden-page/);
  assert.match(css, /--radius-panel/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(css, /\.target-plants-panel \{[\s\S]*?overflow: hidden;/);
  assert.match(css, /\.target-plants-summary \{[\s\S]*?grid-template-columns: repeat\(4, minmax\(0, 1fr\)\);/);
  assert.match(css, /\.target-plants-workspace \{[\s\S]*?grid-template-columns: minmax\(0, 0\.84fr\) minmax\(0, 1\.16fr\);/);
  assert.match(css, /\.target-api-summary\s*\{/);
  assert.match(css, /\.target-api-section-grid\s*\{/);
  assert.match(css, /\.target-api-route-row\s*\{[\s\S]*?display: grid;/);
  assert.match(css, /\.target-api-route-rail\s*\{[\s\S]*?grid-template-columns: repeat\(auto-fit, minmax\(144px, 1fr\)\);/);
  assert.match(css, /\.target-api-control-view \.target-note-body\s*\{[\s\S]*?display: grid;/);
  assert.match(css, /\.target-api-rail-item\s*\{[\s\S]*?display: grid;/);
  assert.match(css, /\.target-api-route-path\s*\{[\s\S]*?overflow-wrap: anywhere;/);
  assert.match(favicon, /svg/i);
  assert.doesNotMatch(page, /SkeletonPreview|react-loading-skeleton/);
  assert.doesNotMatch(layout, /Starter Project|codex-preview/);

  const removedRootFiles = [
    "../app/garden-dashboard.tsx",
    "../app/garden-data.ts",
    "../app/garden-generic-page.tsx",
    "../app/garden-icons.tsx",
    "../app/garden-layout.tsx",
    "../app/garden-map-page.tsx",
    "../app/garden-pages.tsx",
    "../app/garden-services.ts",
    "../app/garden-shell.tsx",
    "../app/garden-task-page.tsx",
    "../app/garden-types.ts",
  ];

  for (const file of removedRootFiles) {
    await assert.rejects(access(new URL(file, import.meta.url)));
  }
});
