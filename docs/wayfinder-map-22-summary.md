# Wayfinder map #22 — closing summary

**Map:** [Cascade-on-the-runtime + demo-ready 3-tier trace + viability brief (MGC)](https://github.com/cmengu/Neonatal/issues/22)
**Charted:** 15 Jul 2026 · **Completed:** 16 Jul 2026 · 17 child tickets, all closed; fog empty; nothing left to decide.

## Destination — reached

1. **The Verdict Cascade is the production runtime.** `POST /assess` routes through the full
   cascade; the deterministic Tier-1 Safety Floor applies in production and no later tier —
   not even the LLM — can lower a verdict below it. Architecture candidates A–G all resolved
   (F consciously out of scope).
2. **A demo-ready 3-tier trace.** One real infant window (`infant7`, windows 113–292) recorded
   through the real cascade — real CUSUM, real Groq/Qdrant RAG run, real merge — replayed in a
   shipped dashboard trace view, with a 44 s backup video and a demo-day runbook.
3. **A cited viability brief** (pitch appendix): HSA Class C SaMD pathway, hybrid edge
   architecture (deterministic floor on-device, learned tiers on a gateway), SG
   neonatal-monitoring landscape.

## The route walked (by strand)

### Architecture — the cascade becomes real
| Decision | Ticket | PR |
|---|---|---|
| D — Verdict carries action, indicators & citations | [#23](https://github.com/cmengu/Neonatal/issues/23) | [#38](https://github.com/cmengu/Neonatal/pull/38) |
| B — Thread AssessmentContext through the Tier-3 seam | [#24](https://github.com/cmengu/Neonatal/issues/24) | [#39](https://github.com/cmengu/Neonatal/pull/39) |
| **A — Route production `/assess` through the cascade (keystone)** | [#25](https://github.com/cmengu/Neonatal/issues/25) | [#41](https://github.com/cmengu/Neonatal/pull/41) |
| C — One home for verdict policy | [#26](https://github.com/cmengu/Neonatal/issues/26) | [#42](https://github.com/cmengu/Neonatal/pull/42) |
| E — Soft-floor quieting authority made structural | [#27](https://github.com/cmengu/Neonatal/issues/27) | [#46](https://github.com/cmengu/Neonatal/pull/46) |
| G — Collapse the Context/View twins | [#28](https://github.com/cmengu/Neonatal/issues/28) | [#48](https://github.com/cmengu/Neonatal/pull/48) |

F (the world-model Surprise seam) stayed **out of scope** — unblocked by the #18 data fix
(Surprise AUC 0.635 on corrected data) but a fresh effort if reconsidered, not this map's.

### Demo — the trace, end to end on real data
| Decision | Ticket | Asset |
|---|---|---|
| Trace view prototyped (2 feedback rounds) | [#29](https://github.com/cmengu/Neonatal/issues/29) | throwaway prototypes + feedback log |
| Trace telemetry contract + honesty ledger | [#30](https://github.com/cmengu/Neonatal/issues/30) | [#40](https://github.com/cmengu/Neonatal/pull/40) · `docs/design/trace-telemetry-contract.md` |
| Recorder: real window → `trace.json` via the cascade | [#31](https://github.com/cmengu/Neonatal/issues/31) | [#49](https://github.com/cmengu/Neonatal/pull/49) |
| Cascade-trace view in the dashboard | [#32](https://github.com/cmengu/Neonatal/issues/32) | [#44](https://github.com/cmengu/Neonatal/pull/44) |
| Serving seam — recorded trace is the default | [#50](https://github.com/cmengu/Neonatal/issues/50) | [#52](https://github.com/cmengu/Neonatal/pull/52) |
| Showtime packaging: **live-driven + video backup, real data only** | [#51](https://github.com/cmengu/Neonatal/issues/51) | decision on ticket |
| Backup video (44 s @ 1080p) + demo-day runbook | [#53](https://github.com/cmengu/Neonatal/issues/53) | [#54](https://github.com/cmengu/Neonatal/pull/54) · `docs/demo/` |

### Viability — the pitch appendix
| Decision | Ticket | Asset |
|---|---|---|
| HSA: Class C SaMD, MEDICS route, pilot-legal-via-CRM | [#33](https://github.com/cmengu/Neonatal/issues/33) | `docs/research/hsa-samd-classification-pathway.md` |
| Edge: hybrid — floor on MCU, learned tiers on gateway | [#34](https://github.com/cmengu/Neonatal/issues/34) | `docs/research/` edge asset |
| SG landscape: complements Layer-1 monitors + HeRO | [#35](https://github.com/cmengu/Neonatal/issues/35) | `docs/research/sg-neonatal-monitoring-landscape.md` |
| Viability brief synthesized | [#36](https://github.com/cmengu/Neonatal/issues/36) | [#37](https://github.com/cmengu/Neonatal/pull/37) · `docs/research/viability-brief-mgc.md` |

Plus adopted along the way: perf fix for `_sampen` ([#45](https://github.com/cmengu/Neonatal/issues/45) → [#47](https://github.com/cmengu/Neonatal/pull/47)).

## What's NOT on `main` yet — the merge order

Everything above lives in a stack of draft PRs. Suggested merge order (each unblocks the next):

1. **[#21](https://github.com/cmengu/Neonatal/pull/21)** `feat/onnx-cutover` → `main` — the root; everything below stacks on it.
2. **[#38](https://github.com/cmengu/Neonatal/pull/38)** (D) → **[#39](https://github.com/cmengu/Neonatal/pull/39)** (B) → **[#41](https://github.com/cmengu/Neonatal/pull/41)** (A, keystone).
3. Siblings off A, any order: **[#42](https://github.com/cmengu/Neonatal/pull/42)** (C) · **[#46](https://github.com/cmengu/Neonatal/pull/46)** (E) · **[#48](https://github.com/cmengu/Neonatal/pull/48)** (G).
4. **[#49](https://github.com/cmengu/Neonatal/pull/49)** (recorder) → **[#52](https://github.com/cmengu/Neonatal/pull/52)** (serving seam) → **[#54](https://github.com/cmengu/Neonatal/pull/54)** (video + runbook).
5. Anytime after step 1: **[#37](https://github.com/cmengu/Neonatal/pull/37)** (viability brief) · **[#43](https://github.com/cmengu/Neonatal/pull/43)** (bradycardia data fix) · **[#47](https://github.com/cmengu/Neonatal/pull/47)** (sampen perf).
6. Docs PR direct to main: **[#40](https://github.com/cmengu/Neonatal/pull/40)** (trace contract).
7. **[#44](https://github.com/cmengu/Neonatal/pull/44)** (trace view → main) is **superseded by the stack** — #52's branch already merged it into the recorder line. Once step 4 lands, close #44 unmerged.

([#17](https://github.com/cmengu/Neonatal/pull/17) / issue #13 predates this map — judge it separately.)

## What's left for the human

- **Merge the stack** (order above), then re-run the suite on `main`.
- **Rehearse**: two timed passes against `docs/demo/demo-day-runbook.md` (3–5 min slot).
- **Embed** `docs/demo/demo-walkthrough-infant7.mp4` in the deck as the fallback slide.
