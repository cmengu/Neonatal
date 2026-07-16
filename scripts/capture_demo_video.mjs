// Backup demo video for the MGC pitch (#53) — drives the exact walkthrough
// decided in #51 against the offline production build on localhost:3453,
// recording at 1920x1080.
import { chromium } from "playwright";

const BASE = process.env.DEMO_BASE ?? "http://localhost:3453";
const OUT_DIR = process.env.OUT_DIR ?? "./video";
const hold = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  recordVideo: { dir: OUT_DIR, size: { width: 1920, height: 1080 } },
  colorScheme: "dark",
});
const page = await ctx.newPage();

// 1 — ward grid: all beds render, Infant 07 pulsing RED
await page.goto(BASE + "/", { waitUntil: "networkidle" });
await page.waitForSelector(".animate-pulse-ring", { timeout: 15000 });
await hold(6000);

// 2 — click the RED bed → client-nav to the trace
await page.locator(".animate-pulse-ring").first().click();
await page.waitForURL("**/trace/infant7", { timeout: 10000 });

// 3 — staged reveal auto-runs (5 nodes x 700ms), then the playhead sweeps
await page.waitForSelector("#n-t1", { timeout: 15000 });
await hold(11000);

// 4 — fit the whole pipeline in view
await page.getByRole("button", { name: /fit all/ }).click();
await hold(4500);

// 5 — open the Tier 3 drawer: retrieve · reason · self-check + citations
await page.locator("#n-t3").click();
await hold(8000);

// 6 — verdict node → full report modal
await page.getByText("click for full report").click();
await page.getByText("How this verdict was reached").waitFor({ timeout: 5000 });
await hold(7000);

// close the modal (Escape, with a ✕/close-button fallback)
await page.keyboard.press("Escape");
await hold(400);
if (await page.getByText("How this verdict was reached").isVisible().catch(() => false)) {
  await page.locator("button", { hasText: /✕|×|Close/i }).first().click().catch(() => {});
}
await hold(1000);

// 7 — Escalate → "Attending paged" toast
await page.getByRole("button", { name: "Escalate" }).click();
await page.getByText("Attending paged").waitFor({ timeout: 5000 });
await hold(4000);

await ctx.close(); // flushes the video
const path = await page.video().path();
console.log("VIDEO:" + path);
await browser.close();
