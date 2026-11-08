import { expect, test } from "@playwright/test";

test("owner: what-if finds a fix and applies it", async ({ page }) => {
  // A plan for a 5-person clinic, built from the URL
  await page.goto("/quote?segment=prof&city_tier=1&employees=5&sites=1");
  await expect(page.getByRole("heading", { name: "Your monthly price" })).toBeVisible();

  await page.getByRole("button", { name: "What if my budget or needs change?" }).click();
  await page.getByRole("button", { name: "Backup 4G/5G Failover" }).click();
  await page.getByLabel("Monthly budget (₹)").fill("1500");
  await page.getByRole("button", { name: "Show me the options" }).click();

  await expect(page.getByText(/over your ₹1,500 budget/).first()).toBeVisible();
  const use = page.getByRole("button", { name: "Use this plan" }).first();
  await expect(use).toBeVisible();
  await use.click();
  await expect(page.getByText("Plan updated.")).toBeVisible();
});

test("judge: break a quote and see the rule and the re-check", async ({ page }) => {
  await page.goto("/judge");
  await page.getByRole("button", { name: "5-person clinic, Pune, GST active" }).click();
  await expect(page.getByRole("heading", { name: "2. Its quote" })).toBeVisible();

  await page.getByLabel("City tier").last().selectOption("2");
  await page.getByLabel("Add a service").selectOption("P03"); // Biz Fibre 1G: tier-1 cities only
  await page.getByRole("button", { name: "Run the rules" }).click();

  await expect(page.getByRole("heading", { name: "The system's decision" })).toBeVisible();
  await expect(page.locator("span.font-mono", { hasText: "city tier" }).first()).toBeVisible();
  await expect(page.getByText(/P0\d/)).toHaveCount(0); // names, never raw product codes
  await expect(page.getByText(/Rules engine re-check: 0 ineligible products/).first()).toBeVisible();
  await expect(page.getByText("Prototype test results")).toBeVisible();
});
