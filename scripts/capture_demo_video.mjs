// Capture the showtime demo off the OFFLINE prod build → docs/demo/showtime-demo.webm (#67).
//
// Mirrors the map-#22 docs/demo/ pattern: drive the real page with Playwright so the backup
// video is the exact same run the audience would see live. It opens the ward, drills into
// infant7, clicks the ✨ demo control, and records the full choreography.
//
// Usage (from the repo root, with the offline prod server already running):
//   cd dashboard && npx next build && npx next start -p 3000 &
//   npx playwright install chromium
//   node scripts/capture_demo_video.mjs
//
// Env: DEMO_URL (default http://localhost:3000), DEMO_SECONDS (default 60 — matches the
// choreography's 52 s + a tail for the "Explore" beat).

import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mkdir, rename, readdir } from "node:fs/promises";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT_DIR = join(REPO_ROOT, "docs", "demo");
const RAW_DIR = join(OUT_DIR, ".raw");
const BASE = process.env.DEMO_URL ?? "http://localhost:3000";
const SECONDS = Number(process.env.DEMO_SECONDS ?? 60);

async function main() {
  await mkdir(RAW_DIR, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 2,
    reducedMotion: "no-preference", // let the auto-rotate + ripple play
    recordVideo: { dir: RAW_DIR, size: { width: 1920, height: 1080 } },
  });
  const page = await context.newPage();

  console.log(`→ ward ${BASE}/`);
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500); // hold on the "one turning" establishing shot

  console.log("→ drill into infant7");
  const bed = page.getByRole("link", { name: /Infant 07/i });
  if (await bed.count()) await bed.first().click();
  else await page.goto(`${BASE}/showtime/infant7`, { waitUntil: "networkidle" });

  await page.waitForSelector("text=JEPA latent embedding", { timeout: 15000 });
  await page.waitForTimeout(1500);

  console.log("→ start choreographed demo");
  const demoBtn = page.getByTitle("choreographed demo");
  await demoBtn.click();

  console.log(`→ recording ${SECONDS}s of choreography…`);
  await page.waitForTimeout(SECONDS * 1000);

  // Finalise: closing the context flushes the video file, then we give it a stable name.
  const video = page.video();
  await context.close();
  await browser.close();

  if (video) {
    const target = join(OUT_DIR, "showtime-demo.webm");
    try {
      await video.saveAs(target);
      console.log(`✓ wrote ${target}`);
    } catch {
      // fallback: grab whatever landed in RAW_DIR
      const files = (await readdir(RAW_DIR)).filter((f) => f.endsWith(".webm"));
      if (files[0]) {
        await rename(join(RAW_DIR, files[0]), target);
        console.log(`✓ wrote ${target}`);
      }
    }
  }
  console.log("Transcode to mp4 if the venue needs it:  ffmpeg -i docs/demo/showtime-demo.webm docs/demo/showtime-demo.mp4");
}

main().catch((err) => {
  console.error("capture failed:", err);
  process.exit(1);
});
