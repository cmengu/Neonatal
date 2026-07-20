# NeonatalGuard — Showtime Demo Runbook (#67)

The demo-day operating manual for the map-#56 showtime experience. Ship it safely: a
pre-flight, the beat sheet, fallback triggers, and — non-negotiable per the owner's honesty
bar — the **real-vs-mock tell** you say out loud so nothing on screen is over-read.

> **The single most important fact to keep straight:** what NeonatalGuard *detects* is a
> **sustained HRV departure from this infant's own baseline** — that part is real and held-out.
> **Sepsis is the hypothesis the guidelines surface, not a diagnosis**, and this dataset (PICS)
> has **no sepsis labels at all**. Never say "the AI detected sepsis." Say "the AI detected the
> departure; the guidelines raise sepsis as the consideration."

---

## 1. Pre-flight (T-15 min)

Run the **offline production build** — no dev server, no network, nothing to go wrong live:

```bash
cd dashboard
npm ci                 # first time only
npx next build         # must print ✓ Compiled successfully
npx next start -p 3000 # serves the static bundle offline
```

Then verify the two entry points return 200 and the real spine is present:

```bash
curl -s -o /dev/null -w "ward   %{http_code}\n" http://localhost:3000/
curl -s -o /dev/null -w "stage  %{http_code}\n" http://localhost:3000/showtime/infant7
# the 3-D hero is driven by the REAL model export — confirm it's in the bundle:
curl -s http://localhost:3000/showtime/infant7 | grep -q "JEPA latent embedding" && echo "world-model hero OK"
```

Open `http://localhost:3000/` in a **Chromium** browser, full-screen (F11). Do one silent
dry-run of the beat sheet below. Confirm:

- [ ] Ward shows nine calm beds + **infant7 pulsing red**.
- [ ] Clicking infant7 lands on the immersive stage (`/showtime/infant7`).
- [ ] The **✨ demo** button (bottom-left of the scrubber) runs the full choreography and ends in "Explore".
- [ ] The 3-D embedding orbits; the novelty readout climbs past the cloud-edge in the sustained phase.
- [ ] Reduced-motion off (System Settings → Accessibility) so the auto-rotate + ripple play.

If the model or data ever needs regenerating (they're committed, so normally skip):

```bash
PYTHONPATH=. python3 scripts/jepa_sweep.py            # retrain + pick the winner (~7 min, MPS)
PYTHONPATH=. python3 scripts/export_jepa_trace.py     # re-export the world_model block
```

---

## 2. The beat sheet (~75 s, one take)

Drive it with **✨ demo** (it choreographs itself on the shared clock), narrating over the top.
Everything below moves **together** — that's the whole point; there is one playhead.

| t (s) | Beat | On screen | Say |
|---|---|---|---|
| 0–8 | **The ward** | Dark NICU grid, nine calm, **infant7 turning red** | "Many babies, one turning. Everything else is stable." |
| 8–12 | **Drill-in** | Click infant7 → the stage assembles around one timeline | "Let's open the one that's turning." |
| 12–20 | **Baseline** | 3-D marker inside the learned-normal cloud; tiers calm | "This is the world model — infant7's cardiac state in a learned latent space. Right now it sits in its *own* normal." |
| 20–44 | **Onset → drift** | Tier 1 z-scores flag; **CUSUM C⁺ climbs to h**; the embedding **leaves the cloud**, surprise rises | "Tier 1 flags deviations against *this infant's* baseline. Tier 2's CUSUM confirms it's a sustained drift, not a blip. And the world model's state is physically leaving normal — novelty past the cloud edge." |
| 44–60 | **The reasoning** | Agent theater: supervisor → specialists hand off, pull **NICE / AAP / HeRO** passages, stream the reasoning | "Only now — never on a calm window — the reasoning tier runs. It retrieves guidelines and forms a **hypothesis**." |
| 60–70 | **The verdict** | Cascade merges to **RED**; the **Safety Floor holds**; escalate-only beat | "Concordant deviation sets a hard floor no later tier can lower. Tier 3 concurs — it can raise concern, never lower it." |
| 70+ | **Explore** | Free-scrub | "And any moment is inspectable — drag the timeline; every panel and the 3-D move together." |

Then take questions **in free-scrub** — grab any window and talk to it.

---

## 3. Fallback triggers (in order of preference)

1. **A panel looks wrong / you fat-fingered a scrub** → click **✨ demo** again. It resets to the
   start and replays the whole choreography deterministically. *This is the primary safety net —
   the demo-mode itself is the "flawless run."*
2. **The browser janks or the 3-D stutters** → it's cosmetic (Canvas 2-D, no GPU dependency);
   keep talking, hit **✨ demo** to restart clean. Turn on reduced-motion (Accessibility) to drop
   the auto-rotate + ripple if a projector is weak.
3. **`next start` died / laptop wedged** → play the **backup video** (`docs/demo/showtime-demo.mp4`,
   captured off this exact offline build — see §5). It is the same beat sheet, narrate over it.
4. **Total A/V failure** → the story in one breath: *"A real JEPA world model watches each infant's
   cardiac dynamics in a learned latent space; when the state leaves that infant's normal, a
   three-tier cascade — deterministic floor, CUSUM drift, guideline-grounded reasoning — escalates,
   and a hard Safety Floor guarantees the alarm can't be talked down."*

---

## 4. The real-vs-mock tell (say this; don't let it be over-read)

**Real (defensible, held-out, in-repo):**
- The **JEPA world model** — trained self-supervised, no labels, no collapse (`models/jepa/jepa.pt`).
  The **3-D trajectory, novelty, and surprise on screen are its actual outputs** on infant7's real
  recorded window `[2740,2919]` (`scripts/export_jepa_trace.py`).
- The honest numbers, if asked: onset-anticipation surprise **AUC 0.772**, embedding novelty
  **0.678 vs a linear VAR baseline 0.527**, held out across 10 infants (`docs/research/world-model-jepa-result.md`).
- The **cascade logic** — Tier 1 direction-aware deviation floor, Tier 2 CUSUM, the two-level
  Safety Floor + quiet gates, Tier 3 escalate-only/short-circuit — is the real production code.
- The Tier 3 **retrieved passages** (NICE NG195, AAP/COFN, HeRO/HRC) are real guideline content.

**Mock / illustrative (say so if asked):**
- The on-screen **trace is a recorded fixture** standing in for the live recorder (issue #31, on a
  separate branch). Its **data-in and tier-1/tier-2 series are synthesized** to a representative
  calm→sustained arc; the extra bedside channels are **tagged "simulated"** on screen. **The
  `world_model` block inside that fixture is the exception — it is the real model export.**
- The **ward's calm beds are context** — deliberately *no* fabricated per-infant risk numbers.
  Only infant7 carries a real trace, so only infant7 drills in.

**The honesty framing that is baked into the UI (point at it):**
- The Tier 3 header always reads: detects an **HRV departure**; sepsis is a **hypothesis**, grounded
  (HeRO/HRC, NICE) but **not a diagnosis**; culture remains the reference standard; escalate-only.
- The 3-D caption says exactly what the axes are (principal components of the JEPA embedding) and
  carries **no accuracy number**.

**If asked "why not just say sepsis?"** — lead with the precedent, not the apology:

> *"Because the FDA-cleared device in this space doesn't either. HeRO watches heart-rate
> characteristics and shows a risk score; the clinician decides about sepsis. That design cut
> mortality from 10.2% to 8.1% in a randomised trial of 2,989 very-low-birth-weight infants, and
> 30-day mortality after late-onset sepsis from 19.6% to 11.8%. Surfacing a physiological risk
> marker and leaving the diagnosis to a clinician isn't our limitation — it's the pattern with
> the evidence behind it. What we detect is departure from this infant's own autonomic baseline,
> held out at 0.77. Sepsis is the hypothesis that departure raises."*

**If pushed — "but you have no sepsis labels":** *"Correct, and neither does any public dataset.
We surveyed them (`docs/research/public-neonatal-datasets-survey.md`): the groups holding
beat-to-beat neonatal ECG with adjudicated infection outcomes have never deposited it, and
Pre-Vent — the NHLBI study built to close that gap, 730 infants under 29 weeks — kept its
waveforms at the sites and released only daily event counts. A labelled cohort under a data
agreement is the next step; on public data, this is the state of the art."*

**Do not say** "we predict sepsis", "validated for clinical use", or "would have saved N babies".
The first is unverifiable on this data, the second is untrue at 10 infants with no calibrated
operating point, and the third has no outcome data behind it at all.

---

## 5. Backup video

The backup is captured off the **offline prod build** so it mirrors the live run exactly. A
ready-to-run Playwright capture script is provided:

```bash
cd dashboard && npx next build && npx next start -p 3000 &   # serve offline
npx playwright install chromium                              # one-time
node ../scripts/capture_demo_video.mjs                       # writes docs/demo/showtime-demo.webm
```

`scripts/capture_demo_video.mjs` opens the ward, drills into infant7, clicks **✨ demo**, and
records the full choreography to `docs/demo/`. (The `.webm` it produces can be transcoded to
`.mp4` with `ffmpeg -i showtime-demo.webm showtime-demo.mp4` if the venue needs it.)

> **Status:** the script is committed and verified against the offline build's DOM; the binary
> `.mp4`/`.webm` is **not** committed from this environment (no browser/Playwright here). Capture
> it once on the demo laptop during pre-flight — or rely on the built-in **✨ demo** mode, which is
> the same deterministic run, live. The video is the belt to demo-mode's braces.
