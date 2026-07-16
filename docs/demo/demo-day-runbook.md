# Demo-day runbook — MGC pitch trace demo

The showtime package decided in [#51](https://github.com/cmengu/Neonatal/issues/51):
**live-driven** from the presenter's laptop, offline production build, **real recorded
infant7 data only**, with the backup video (`docs/demo/demo-walkthrough-infant7.mp4`)
embedded in the deck as the instant fallback. The app stays open through Q&A.

## Pre-flight (the morning of, ~10 min)

- [ ] `cd dashboard && npm install && npx next build && npx next start -p 3000`
      — **production** build, never `next dev` (dev overlay / recompiles on stage).
- [ ] Env is **default** — `NEXT_PUBLIC_TRACE_MODE` unset (or `recorded`). Never `mock`.
- [ ] Open `http://localhost:3000` — ward renders, **Infant 07 pulsing CRITICAL**.
- [ ] Click Infant 07 → trace plays. **Real-data check: zero "simulated" badges
      anywhere in the drawers.** The synthetic fixture shows 4; the real recording
      shows none. If you see a "simulated" badge, you are in mock mode — stop and fix.
- [ ] Tier 3 drawer shows real reasoning + citations (NICE NG195, Griffin & Moorman).
- [ ] Wi-Fi can be OFF — nothing in the demo touches the network. Consider airplane
      mode to kill notification popups.
- [ ] Do Not Disturb ON; close every other app; hide the dock; browser full-screen
      (no bookmarks bar, no tabs).

## Projector / room check (before the session starts)

- [ ] Plug in, mirror displays, confirm the canvas is legible from the back of the room.
- [ ] The trace canvas is pan/zoom — if the projector is 720p, use **⤢ fit all** then
      zoom into one tier at a time rather than showing everything small.
- [ ] Set the laptop to never sleep; disable screen saver.

## The walkthrough (target 3–5 min; beats match the backup video)

1. **Ward grid** (~20 s) — ten beds, threshold-style triage at a glance; Infant 07
   pulsing RED. "Every bed is scored continuously against its own baseline."
2. **Click Infant 07** — the cascade trace opens and auto-plays: nodes light up
   left-to-right (Data In → Tier 1 → Tier 2 → Tier 3 → Verdict) with the
   **Safety-Floor track** pinned underneath. "Once Tier 1 sets RED, no later tier —
   not even the LLM — can lower it."
3. **Tier 1 — Instant math** (~40 s) — real HRV features vs the infant's own
   baseline; three concordant flags (mean_rr, sdnn, rmssd) set the HARD RED floor.
4. **Tier 2 — CUSUM drift** (~30 s) — the drift check and the quiet-gates table:
   why Tier 2 may *not* quiet this alarm.
5. **Tier 3 — Guideline grounding** (~60 s) — the real RAG run: query, retrieved
   guidelines (NICE NG195, Griffin & Moorman), reasoning, self-check. "This ran live
   against the guideline index; what you see is the recorded output, unedited."
6. **Verdict** (~40 s) — RED, risk 100%, per-tier trail. Click for the full report;
   **Escalate** → "Attending paged · report queued".
7. Return to the ward (**← Ward**) and leave it on screen for Q&A.

**Narration timing is HITL** — do at least two full rehearsal passes with a timer and
trim to fit the slot. The auto-reveal takes ~4 s; don't talk over all of it, let it land.

## Known quirks (so nothing surprises you on stage)

- In the **full report modal**, "Recommended action" is empty and "Grounding
  citations" reads *none*. Honest artifact: the verdict headline is the deterministic
  Tier-1 floor, which carries no action/citations by design — Tier 3's citations live
  in its own drawer. If asked: "the floor is deterministic math; the guideline
  citations belong to the reasoning tier, shown here."
- The trace auto-runs on page load; **▶ Run trace** replays it — useful if a judge
  asks to see the reveal again.
- Clicking a node toggles its drawer; a *drag* pans without toggling. Rehearse the
  difference so a pan doesn't accidentally collapse a tier.

## Fallback trigger — when to switch to the video

Switch the moment any of these happens; do not debug on stage:

- the page won't load / renders blank after one reload attempt (⌘R, once), or
- a "simulated" badge appears (wrong data mode), or
- display mirroring fails and can't be fixed in ~30 s.

**The video is `docs/demo/demo-walkthrough-infant7.mp4` (44 s, 1080p), embedded in the
deck at the slide right after the demo cue.** It shows the identical walkthrough on the
identical real data, so the narration script above works over it unchanged — just say
"let me play the recorded run" and keep talking. Also keep a copy on the desktop and
on a phone.

## Regenerating the video

`scripts/capture_demo_video.mjs` (Playwright) drives the exact walkthrough against a
running production build and records 1920×1080. After any UI or data change:

```bash
cd dashboard && npx next build && npx next start -p 3453 &
cd <scratch> && npm i playwright ffmpeg-static && npx playwright install chromium-headless-shell
node scripts/capture_demo_video.mjs   # DEMO_BASE=http://localhost:3453
# then transcode the webm to mp4 (see script header) and replace docs/demo/demo-walkthrough-infant7.mp4
```
