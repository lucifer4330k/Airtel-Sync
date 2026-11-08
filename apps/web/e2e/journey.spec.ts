import path from "node:path";

import { expect, test } from "@playwright/test";

const DOCS = path.resolve(__dirname, "../../../data/kyc_documents");
const K03 = { gstin: "27XUIXG0767D1ZP", udyam: "UDYAM-MH-00-9516696" };

test.beforeAll(async ({ browser }) => {
  // Warm up: the dev server compiles each route on first request.
  const page = await browser.newPage();
  for (const route of ["/", "/start", "/chat", "/quote", "/checkout", "/kyc", "/track"]) {
    await page.goto(route).catch(() => undefined);
  }
  await page.close();
});

test("landing page links to the live app", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Connect a small business");
  await page.getByRole("link", { name: "Try the owner app" }).click();
  await expect(page.getByRole("link", { name: "Start with the advisor" })).toBeVisible();
});

test("chat → quote → checkout → consent → KYC → tracker", async ({ page }) => {
  // 1. Advisor
  await page.goto("/chat");
  await expect(page.getByText("What kind of business do you run?")).toBeVisible();
  const answer = page.getByLabel("Type your answer");
  await answer.fill(`Furniture workshop in Nagpur with 12 workers, GSTIN ${K03.gstin}, need email`);
  await answer.press("Enter");
  await expect(page.getByText("How many locations")).toBeVisible();
  await page.getByRole("button", { name: "1", exact: true }).click();
  await expect(page.getByRole("button", { name: "See the full plan" })).toBeVisible();
  await expect(page.getByText(/a month, all-in/)).toBeVisible();

  // 2. Quote: toggle an add-on and see the price change
  await page.getByRole("button", { name: "See the full plan" }).click();
  await expect(page.getByRole("heading", { name: "Your monthly price" })).toBeVisible();
  const total = page.locator("p.money.text-\\[2\\.75rem\\]");
  const before = await total.textContent();
  await page.getByRole("switch", { name: "Cloud Backup 1 TB" }).click();
  await expect(total).not.toHaveText(before ?? "");
  await page.getByRole("link", { name: "Accept and pay" }).click();

  // 3. Checkout
  await page.getByLabel("Mobile number for order updates").fill("9876543210");
  await page.getByRole("button", { name: /and place order/ }).click();

  // 4. Consent and documents (K03 is a clean applicant)
  await expect(page.getByRole("heading", { name: "Business documents" })).toBeVisible();
  await page.getByLabel(/I agree to KYC verification/).check();
  await page.getByRole("button", { name: "Agree and continue" }).click();
  await page.getByLabel("Udyam number (optional)").fill(K03.udyam);
  await page.getByRole("button", { name: "Check registration" }).click();
  await expect(page.getByText(/Registered to/)).toBeVisible();
  for (const doc of ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]) {
    await page.locator(`#file-${doc}`).setInputFiles(path.join(DOCS, `K03_${doc}.png`));
    await expect(page.locator(`label[for=file-${doc}]`)).toHaveText("Replace", { timeout: 60_000 });
  }
  await expect(page.getByText("Your business is verified.")).toBeVisible({ timeout: 90_000 });

  // 5. Tracker: KYC pass moved the order on by itself
  await page.getByRole("link", { name: "Continue to order status" }).click();
  await expect(page.getByRole("heading", { name: "Order status" })).toBeVisible();
  // "Order placed" is done (check mark); "Documents verified" is now the current step.
  await expect(page.locator("li", { hasText: "Order placed" }).locator("svg")).toBeVisible();
  await expect(page.locator("p.font-semibold", { hasText: "Documents verified" })).toBeVisible();
  await expect(page.getByText("Pick a visit time").first()).toBeVisible();
});
