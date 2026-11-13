import { expect, test, type Page } from "@playwright/test";

const api = "http://127.0.0.1:8138/api/v1";

async function signIn(page: Page) {
  await page.goto("/?page=tasks");
  await page.getByLabel("Username", { exact: true }).fill("fixture-admin");
  await page.getByLabel("Password", { exact: true }).fill("fixture-admin-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("form", { name: "Sign in to GardenOS" })).toHaveCount(0);
}

test("completion is committed, survives reload and a new session, and retries stay idempotent", async ({ page, browser }) => {
  await signIn(page);
  const row = page.locator('article.target-task-queue-row[data-task-id="e2e-task"]');
  await row.getByRole("button").first().click();
  const inspector = page.getByTestId("task-inspector");
  await expect(inspector).toHaveAttribute("data-task-id", "e2e-task");
  await expect(inspector.getByTestId("task-status")).toHaveText("Pending");

  const completionResponse = page.waitForResponse((response) => response.url() === `${api}/tasks/e2e-task/complete` && response.request().method() === "POST");
  await inspector.getByRole("button", { name: "Mark complete", exact: true }).click();
  const response = await completionResponse;
  expect(response.status()).toBe(200);
  const saved = await response.json();
  expect(saved.id).toBe("e2e-task");
  expect(saved.completed_at).toBeTruthy();
  await expect(inspector.getByTestId("task-status")).toHaveText("Completed");
  await expect(row).toHaveAttribute("data-task-status", "completed");

  await page.reload();
  await expect(row).toHaveAttribute("data-task-status", "completed");
  const workspaceResponse = await page.request.get(`${api}/workspace`);
  expect(workspaceResponse.ok()).toBeTruthy();
  const workspace = await workspaceResponse.json();
  expect([...workspace.tasks.due, ...workspace.tasks.overdue].map((task: { id: string }) => task.id)).not.toContain("e2e-task");
  expect(workspace.tasks.completed.find((task: { id: string }) => task.id === "e2e-task").completed_at).toBe(saved.completed_at);

  const session = await (await page.request.get(`${api}/auth/context`)).json();
  const retry = await page.request.post(`${api}/tasks/e2e-task/complete`, {
    headers: { "x-csrf-token": session.csrf_token },
    data: {},
  });
  expect(retry.status()).toBe(200);
  expect((await retry.json()).completed_at).toBe(saved.completed_at);

  const freshContext = await browser.newContext();
  try {
    const freshPage = await freshContext.newPage();
    await signIn(freshPage);
    await expect(freshPage.locator('article.target-task-queue-row[data-task-id="e2e-task"]')).toHaveAttribute("data-task-status", "completed");
  } finally {
    await freshContext.close();
  }
});

test("a rejected save keeps the task pending and an empty live queue stays empty", async ({ page }) => {
  await signIn(page);
  const row = page.locator('article.target-task-queue-row[data-task-id="e2e-overdue"]');
  await row.getByRole("button").first().click();
  const inspector = page.getByTestId("task-inspector");
  await expect(inspector).toHaveAttribute("data-task-id", "e2e-overdue");
  await page.route(`${api}/tasks/e2e-overdue/complete`, (route) => route.fulfill({
    status: 503,
    contentType: "application/json",
    body: JSON.stringify({ detail: "Synthetic test outage" }),
  }));
  await inspector.getByRole("button", { name: "Mark complete", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(inspector.getByTestId("task-status")).toHaveText("Pending");
  await page.unroute(`${api}/tasks/e2e-overdue/complete`);
  await page.reload();
  await expect(row).toHaveAttribute("data-task-status", "pending");

  await page.route(`${api}/workspace`, async (route) => {
    const response = await route.fetch();
    const workspace = await response.json();
    workspace.tasks = { due: [], overdue: [], completed: [] };
    workspace.summary.due_task_count = 0;
    workspace.summary.overdue_task_count = 0;
    await route.fulfill({ response, json: workspace });
  });
  await page.reload();
  await expect(page.getByText("No tasks in this view.", { exact: true })).toBeVisible();
  await expect(page.locator("article.target-task-queue-row[data-task-id]")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Mark complete", exact: true })).toHaveCount(0);
});
