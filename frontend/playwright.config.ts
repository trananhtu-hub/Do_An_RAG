import { resolve } from "node:path";

import { defineConfig, devices } from "@playwright/test";

const FRONTEND_DIR = __dirname;
const REPO_ROOT = resolve(FRONTEND_DIR, "..");
const PYTHON = resolve(REPO_ROOT, ".venv", "Scripts", "python.exe");
const STORAGE_STATE = resolve(FRONTEND_DIR, "e2e", ".auth", "state.json");

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 240_000,
  expect: { timeout: 20_000 },
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  use: {
    baseURL: "http://localhost:3000",
    locale: "vi-VN",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "setup",
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], storageState: STORAGE_STATE },
      dependencies: ["setup"],
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"], storageState: STORAGE_STATE },
      dependencies: ["setup"],
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"], storageState: STORAGE_STATE },
      dependencies: ["setup"],
    },
  ],
  webServer: [
    {
      command: `"${PYTHON}" -m uvicorn app.main:app --port 8000`,
      cwd: resolve(FRONTEND_DIR, "..", "backend"),
      env: { PYTHONUTF8: "1" },
      url: "http://localhost:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "npm run dev",
      cwd: FRONTEND_DIR,
      url: "http://localhost:3000/login",
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
    },
  ],
});
