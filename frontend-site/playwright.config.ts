import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";

const repositoryRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3138",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${process.env.GARDENOS_E2E_PYTHON || "python"} -m scripts.e2e_server`,
      cwd: repositoryRoot,
      url: "http://127.0.0.1:8138/health/ready",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npm run preview -- --host 127.0.0.1 --port 3138 --strictPort",
      url: "http://127.0.0.1:3138",
      reuseExistingServer: false,
    },
  ],
});
