import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

let server;
let tasks;
let bootstrap;

before(async () => {
  server = await createServer({
    root: fileURLToPath(new URL("..", import.meta.url)),
    configFile: false,
    server: { middlewareMode: true, hmr: false, ws: false },
    appType: "custom",
  });
  tasks = await server.ssrLoadModule("/app/garden/services/task-service.ts");
  bootstrap = await server.ssrLoadModule("/app/garden/services/bootstrap-service.ts");
});

after(async () => { await server?.close(); });

const task = (id, overrides = {}) => ({
  id, title: "Inspect demo plant", task_type: "inspect", priority: 2,
  status: "pending", scheduled_for: "2026-01-01T10:00:00Z",
  completed_at: null, skipped_at: null, plant_id: null, location_id: null,
  zone: "Demo Garden", completion_notes: null, performed_by: null,
  ...overrides,
});

const workspace = (lists = {}) => ({
  authenticated: true,
  principal: null,
  selected_location_id: null,
  summary: { due_task_count: 0, overdue_task_count: 0 },
  sidebar: [], navigation: { locations: [] },
  tasks: { due: [], overdue: [], completed: [], ...lists },
});

const context = (value) => ({ workspace: value, auth: { authenticated: true } });
const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { "content-type": "application/json" },
});

function mockFetch(t, implementation) {
  const original = globalThis.fetch;
  globalThis.fetch = implementation;
  t.after(() => { globalThis.fetch = original; });
}

test("an empty live task queue stays empty instead of showing examples", () => {
  const model = tasks.getTaskModel(context(workspace()));
  assert.equal(model.available, true);
  assert.equal(model.queueSections.flatMap((section) => section.rows).length, 0);
  assert.equal(model.summaryStats[0].value, "0 tasks");
  assert.equal(tasks.getTaskModel().available, false);
  assert.equal(tasks.getTaskModel().queueSections.length, 0);
});

test("task IDs survive duplicate titles and overlapping due/overdue lists", () => {
  const overdue = task("task-a");
  const due = task("task-b");
  const completed = task("task-c", { completed_at: "2026-01-01T11:00:00Z", status: "completed" });
  const model = tasks.getTaskModel(context(workspace({ due: [overdue, due], overdue: [overdue], completed: [completed] })));
  const rows = model.queueSections.flatMap((section) => section.rows);
  assert.deepEqual(rows.map((row) => row.id), ["task-a", "task-b", "task-c"]);
  assert.deepEqual(rows.map((row) => row.status), ["pending", "pending", "completed"]);
  assert.equal(rows[2].completedAt, completed.completed_at);
  assert.equal(model.summaryStats[0].value, "2 tasks");
});

test("completion sends the selected ID with session cookies and CSRF", async (t) => {
  const id = "task/a?revision=1";
  const saved = task(id, { completed_at: "2026-01-01T11:00:00Z", status: "completed" });
  mockFetch(t, async (url, init) => {
    assert.equal(new URL(url).pathname, `/api/v1/tasks/${encodeURIComponent(id)}/complete`);
    assert.equal(new URL(url).search, "");
    assert.equal(init.method, "POST");
    assert.equal(init.credentials, "include");
    assert.equal(init.headers.get("x-csrf-token"), "synthetic-csrf");
    assert.deepEqual(JSON.parse(init.body), {});
    return json(saved);
  });
  assert.deepEqual(await tasks.completeGardenTask(id, "synthetic-csrf"), saved);
});

test("completion refuses unauthenticated input and failed server responses", async (t) => {
  let calls = 0;
  mockFetch(t, async () => { calls += 1; return json({}, 503); });
  await assert.rejects(tasks.completeGardenTask("task-a", ""), /Sign in/);
  await assert.rejects(tasks.completeGardenTask("", "synthetic-csrf"), /Sign in/);
  assert.equal(calls, 0);
  await assert.rejects(tasks.completeGardenTask("task-a", "synthetic-csrf"), /503/);
  assert.equal(calls, 1);
});

test("a successful HTTP response must confirm completion of the requested task", async (t) => {
  mockFetch(t, async () => json(task("task-a")));
  await assert.rejects(tasks.completeGardenTask("task-a", "synthetic-csrf"), /did not confirm/);
  globalThis.fetch = async () => json(task("different-task", { completed_at: "2026-01-01T11:00:00Z" }));
  await assert.rejects(tasks.completeGardenTask("task-a", "synthetic-csrf"), /did not confirm/);
});

test("sign-in obtains a CSRF token before submitting credentials", async (t) => {
  const calls = [];
  mockFetch(t, async (url, init) => {
    const path = new URL(url).pathname;
    calls.push(path);
    if (path.endsWith("/auth/context")) return json({ authenticated: false, csrf_token: "login-csrf" });
    assert.equal(init.headers.get("x-csrf-token"), "login-csrf");
    assert.equal(init.credentials, "include");
    assert.deepEqual(JSON.parse(init.body), { username: "demo", password: "synthetic-test-only", csrf_token: "login-csrf" });
    return json({ authenticated: true });
  });
  await bootstrap.signInGardenSession(" demo ", "synthetic-test-only");
  assert.deepEqual(calls, ["/api/v1/auth/context", "/api/v1/auth/login"]);
});

test("canonical refresh reports a failed workspace fetch instead of returning fallback", async (t) => {
  mockFetch(t, async (url) => {
    if (new URL(url).pathname.endsWith("/auth/context")) {
      return json({ authenticated: true, csrf_token: "new-csrf", principal: { id: "demo-user" } });
    }
    return json({}, 503);
  });
  await assert.rejects(bootstrap.loadGardenBootstrap({ requireWorkspace: true }), /503/);
});

test("a fresh bootstrap keeps saved completion and returns the refreshed session token", async (t) => {
  const completed = task("task-a", { completed_at: "2026-01-01T11:00:00Z", status: "completed" });
  mockFetch(t, async (url) => {
    const path = new URL(url).pathname;
    if (path.endsWith("/auth/context")) return json({ authenticated: true, csrf_token: "new-csrf", principal: { id: "demo-user" } });
    if (path.endsWith("/workspace")) return json(workspace({ completed: [completed] }));
    return json({}, 404);
  });
  const reloaded = await bootstrap.loadGardenBootstrap({ requireWorkspace: true });
  const model = tasks.getTaskModel(reloaded);
  assert.equal(reloaded.auth.csrf_token, "new-csrf");
  assert.equal(model.queueSections[2].rows[0].id, "task-a");
  assert.equal(model.queueSections[2].rows[0].status, "completed");
  assert.equal(model.summaryStats[0].value, "0 tasks");
});
