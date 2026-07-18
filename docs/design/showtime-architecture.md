# Showtime — front-end architecture

A map of the immersive demo (map #56) for reviewers and future maintainers: the routes, the
shared-clock contract, the data flow, the component tree, and — load-bearing — the honesty model
that says exactly what on screen is real.

## Routes

| Route | Component | Role |
|---|---|---|
| `/` | `ShowtimeWard` (`components/showtime/ShowtimeWard.tsx`) | The opening "scale → drill-in" beat: calm beds + one turning infant (infant7). |
| `/showtime/[id]` | `ShowtimeShell` (`components/showtime/ShowtimeShell.tsx`) | The immersive stage — every tier + the 3-D on one clock. |

The legacy live-refresh ward (`WardGrid` / `PatientDrawer` / `useWardData`) still exists in the
tree but is no longer the entry point.

## The shared clock (the spine)

One `PlayheadProvider` (`components/trace/playhead.tsx`) owns a single fractional index `p ∈ [0,
n)` over the trace's `time_grid`. **Every** panel and the 3-D read it via `usePlayhead()`, so the
whole page scrubs, plays, and choreographs together — there is no per-panel clock.

`usePlayhead()` exposes: `p`, `setP`, `playing`/`togglePlay`, `phase`/`clock` (derived from the
grid), `reduced` (prefers-reduced-motion), and the demo-mode surface `demo`/`startDemo`/`stopDemo`
/`beat`. Three RAF drivers live in the provider: linear play, the choreographed **demo-mode**
(time-based via RAF timestamps → framerate-independent), and keyboard control (Space / ←→ / Home /
End / D). Manual interaction always takes over from demo-mode (`stopDemo`).

## Data flow

```
scripts/export_jepa_trace.py   (real, from models/jepa/jepa.pt on infant7 [1240,1419])
        │  world_model block (PCA-3D trajectory + novelty + surprise)
        ▼
dashboard/lib/world-model-infant7.json ──┐
                                          ├─► mock-trace.ts (MOCK_TRACE_INFANT7)
   (synthesised data_in/tier1/tier2/      │        │  schema 1.1.0
    tier3/verdict — a fixture for the     │        ▼
    recorder #31, not yet wired)          │   trace-client.getTrace(id)
                                          │        ▼
                                          └─►  ShowtimeShell(trace)
                                                   ├─ TierPanels        (data-in / Tier 1 / Tier 2)
                                                   ├─ EmbeddingWarp     (3-D hero ← trace.world_model)
                                                   ├─ AgentTheater      (Tier 3)
                                                   └─ Timeline          (scrubber + demo control)
```

The trace contract is mirrored in `lib/trace-types.ts` (the `world_model` block is the §7 addendum,
`docs/design/trace-contract-world-model.md`). `getTrace` serves `MOCK_TRACE_INFANT7` unless
`NEXT_PUBLIC_USE_REAL_API=true`, in which case it fetches the recorder's `GET /trace/{id}`.

## Component tree (immersive)

- **ShowtimeShell** — layout + `PlayheadProvider`; TopBar (verdict + the honesty marker), the three
  columns, the demo beat overlay, the Timeline.
  - **TierPanels** (`components/showtime/TierPanels.tsx`) — data-in, Tier 1 (concordance grid +
    Safety-Floor track), Tier 2 (C⁺-vs-h + quiet-gate table). Charts via the theme-aware
    `TraceChart` (`theme="dark"`).
  - **EmbeddingWarp** (`components/showtime/EmbeddingWarp.tsx`) — the 3-D hero. Hand-rolled Canvas-2D
    perspective projection (no three.js/r3f); the warp magnitude is driven by **novelty**, not the
    raw 3-D position drift (see below).
  - **AgentTheater** (`components/showtime/AgentTheater.tsx`) — the Tier-3 handover chain, retrieval
    reveal, streamed reasoning, escalate-only beat; sequenced off the playhead.
- Shared helpers: `lib/trace-format.ts` (`concernColor`/`fmt`/`valueAt`).

## The honesty model (read before changing anything on screen)

Map decision 3: **no fabricated clinical/accuracy numbers presented as real.** What holds:

- **Real:** the JEPA model, and therefore the 3-D trajectory / novelty / surprise (the `world_model`
  block, exported from the trained checkpoint on infant7's real recorded window). The cascade *logic*
  in `src/assessment` is real production code. The Tier-3 retrieved passages are real guideline text.
- **Fixture (representative):** everything else in the trace — `data_in`, `tier1`, `tier2`, `tier3`,
  `verdict` — is synthesised in `mock-trace.ts` as a stand-in for recorder #31. The TopBar shows a
  self-clearing **"recorded fixture"** marker (keyed off `source_commit === "mock-fixture"`) so this
  is visible; it vanishes when a real trace is served.
- **The clinical framing:** what is *detected* is a sustained **HRV departure from the infant's own
  baseline**. **Sepsis is a hypothesis** the guidelines surface, not a diagnosis — PICS has no sepsis
  labels. `AgentTheater` states this in an always-visible header; the 3-D caption carries no accuracy
  number. Don't add a claim the data can't support.

Why novelty (not the 3-D position) drives the warp: the departure is diffuse across embedding
dimensions, so the top-3 PCA position moves only ~0.5 cloud-widths, while the full-D Mahalanobis
**novelty** rises to ~2× the calm cloud-edge. Details in `docs/design/trace-contract-world-model.md`.

## Running it

```bash
cd dashboard && npx next build && npx next start   # offline prod (what the demo uses)
# dev:  npx next dev
```

Full demo-day procedure + the real-vs-mock tell: `docs/demo/showtime-runbook.md`.

## Extension points

- **Recorder #31** lands → `getTrace` serves a real end-to-end trace; the fixture marker self-clears.
- **JEPA assessor → runtime**: `JepaSurpriseAssessor` composes into `default_cascade()` (the #41
  runtime line) as a one-line add when that branch merges.
- **3-D**: swap `EmbeddingWarp`'s Canvas renderer for react-three-fiber if true WebGL depth is wanted
  (the data contract stays the same).
