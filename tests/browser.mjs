import { createRequire } from "node:module";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
if (
  !["127.0.0.1", "localhost"].includes(
    new URL(process.env.RENTALBOARD_URL || "http://127.0.0.1:5174/").hostname,
  )
)
  throw Error("Browser fixtures are local-only");
const browser = await chromium.launch({ headless: true });
const artifacts = ".factory/runs/browser";
await fs.mkdir(artifacts, { recursive: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1512, height: 1100 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(process.env.RENTALBOARD_URL || "http://127.0.0.1:5174/");
  await page
    .getByRole("button", { name: "Demo çalışma alanını aç", exact: true })
    .waitFor();
  await page.screenshot({ path: artifacts + "/login.png", fullPage: true });
  await page
    .getByRole("button", { name: "Demo çalışma alanını aç", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Rezervasyon takvimi", exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Bildirimi kapat", exact: true })
    .click();
  assert.equal(await page.locator(".calendar-row").count(), 8);
  await page.screenshot({ path: artifacts + "/desktop.png", fullPage: true });
  await page.getByRole("button", { name: "Kameralar", exact: true }).click();
  assert.equal(await page.locator(".calendar-row").count(), 2);
  await page
    .getByRole("textbox", { name: "Ekipman ara", exact: true })
    .fill("A7");
  assert.equal(await page.locator(".calendar-row").count(), 1);
  await page
    .getByRole("textbox", { name: "Ekipman ara", exact: true })
    .fill("");
  await page.locator(".category-tabs button").first().click();
  const identity = String(Date.now()).slice(-7);
  const equipment = "Test Lens " + identity,
    customer = "Test Müşteri " + identity;
  await page.getByRole("button", { name: "Ekipmanlar", exact: true }).click();
  await page.getByRole("button", { name: "Ekipman ekle", exact: true }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("Ekipman adı", { exact: true }).fill(equipment);
  await dialog.getByLabel("Günlük ücret (₺)", { exact: true }).fill("5000");
  await dialog.getByLabel("Kategori", { exact: true }).selectOption("lens");
  await dialog.getByRole("button", { name: "Kaydet", exact: true }).click();
  await page.getByRole("heading", { name: equipment, exact: true }).waitFor();
  await page
    .getByRole("button", { name: equipment + " düzenle", exact: true })
    .click();
  dialog = page.getByRole("dialog");
  assert.equal(
    await dialog.getByLabel("Günlük ücret (₺)", { exact: true }).inputValue(),
    "5000",
  );
  await dialog.getByLabel("Günlük ücret (₺)", { exact: true }).fill("1000.75");
  await dialog.getByRole("button", { name: "Kaydet", exact: true }).click();
  await dialog.waitFor({ state: "hidden" });
  await page.getByRole("button", { name: "Müşteriler", exact: true }).click();
  await page.getByRole("button", { name: "Müşteri ekle", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByLabel("Müşteri / işletme adı", { exact: true })
    .fill(customer);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Kaydet", exact: true })
    .click();
  await page.getByText(customer, { exact: true }).waitFor();
  await page.getByRole("button", { name: "Takvim", exact: true }).click();
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + 21);
  const start = date.toISOString().slice(0, 10);
  date.setUTCDate(date.getUTCDate() + 2);
  const end = date.toISOString().slice(0, 10);
  async function fillBooking() {
    await page
      .getByRole("button", { name: "Yeni rezervasyon", exact: true })
      .click();
    dialog = page.getByRole("dialog");
    const gearId = await dialog
      .getByLabel("Ekipman", { exact: true })
      .locator("option")
      .evaluateAll(
        (options, name) =>
          options.find((o) => o.textContent.startsWith(name)).value,
        equipment,
      );
    await dialog.getByLabel("Ekipman", { exact: true }).selectOption(gearId);
    await dialog
      .getByLabel("Müşteri", { exact: true })
      .selectOption({ label: customer });
    await dialog.getByLabel("Teslim tarihi", { exact: true }).fill(start);
    await dialog.getByLabel("İade tarihi", { exact: true }).fill(end);
  }
  await fillBooking();
  assert.match(await dialog.locator(".quote strong").textContent(), /2\.001,5/);
  await dialog
    .getByRole("button", { name: "Rezervasyonu oluştur", exact: true })
    .click();
  await page
    .getByRole("status")
    .filter({ hasText: "Kayıt tamamlandı" })
    .waitFor();
  await fillBooking();
  await dialog
    .getByRole("button", { name: "Rezervasyonu oluştur", exact: true })
    .click();
  await dialog
    .getByRole("alert")
    .filter({ hasText: "zaten rezerve" })
    .waitFor();
  await page.screenshot({ path: artifacts + "/conflict.png", fullPage: true });
  assert.equal(
    await dialog.getByLabel("Teslim tarihi", { exact: true }).inputValue(),
    start,
  );
  await dialog
    .getByRole("button", { name: "Pencereyi kapat", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Rezervasyonlar", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Rezervasyon ara", exact: true })
    .fill(customer);
  assert.equal(await page.locator("tbody tr").count(), 1);
  await page.getByRole("button", { name: "Detay", exact: true }).click();
  await page
    .getByRole("button", { name: "Rezervasyonu iptal et", exact: true })
    .click();
  await page.locator(".status.cancelled").waitFor();
  await page.reload();
  await page
    .getByRole("heading", { name: "Rezervasyon takvimi", exact: true })
    .waitFor();
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      `Global overflow at ${width}`,
    );
  }
  await page.screenshot({ path: artifacts + "/mobile.png", fullPage: true });
  await page
    .getByRole("button", { name: "Menüyü aç/kapat", exact: true })
    .click();
  await page.getByRole("button", { name: /Deniz Aksoy/ }).click();
  await page
    .getByRole("button", { name: "Oturumu kapat", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Demo çalışma alanını aç", exact: true })
    .waitFor();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.keyboard.press("Tab");
  assert.notEqual(
    await page.evaluate(() => document.activeElement.tagName),
    "BODY",
  );
  assert.deepEqual(errors, []);
  console.log(
    "PASS: live Vue/FastAPI demo, inventory/customer creation, exact currency, booking/conflict/cancellation, persistence, mobile and logout.",
  );
} finally {
  await browser.close();
}
