import { defineConfig } from "@playwright/test";

/**
 * Real-browser E2E lane for critical owner flows. It expects an already running API and web
 * client pointed at a disposable PostgreSQL database (see docs/phase-3/test-report.md).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_WEB_URL ?? "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    locale: "en-US",
  },
});
