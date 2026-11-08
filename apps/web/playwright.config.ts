import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end journey on a phone viewport. Expects the API on :8000 (seeded DB)
 * and the web app on :3000:
 *   docker compose up -d postgres redis && (cd ../api && uv run uvicorn app.main:app)
 *   npm run dev
 *   npx playwright test
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 45_000 }, // dev server compiles pages on first visit
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "mobile", use: { ...devices["Pixel 7"] } }],
});
