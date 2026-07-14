# NeonatalGuard — Domain Glossary

The shared, canonical vocabulary for this project. Pure meaning — no implementation
details, no spec. When a term here conflicts with how a word is being used in
conversation or code, this file wins until deliberately changed.

Terms are added as they are resolved during design (grilling / domain-modeling sessions).

---

## The verdict pipeline

**Concern level**
The triage severity of a judgement about an infant's current state: **RED**, **YELLOW**,
or **GREEN**. The single unit of "how worried should the care team be right now." Already
present in code as `concern_level` / `risk_level`; this is its canonical name.

**Assessment**
One tier's judgement of an infant's current state — a concern level, how confident the
tier is in it, and the reasoning behind it. The *common currency* every tier speaks, so
that judgements from different tiers can be compared and merged. An Assessment always
names which tier produced it.

**Assessor**
Anything that can produce an **Assessment** from the current evidence. The three tiers are
each an Assessor. Because they all speak the same currency, they are interchangeable at the
seam — one can be swapped, faked, or tested without disturbing the others.

**Tier**
One of the three Assessors, ordered cheapest-and-most-certain first:
- **Tier 1 — Deviation** — *instantaneous, stateless* deterministic math on the infant's own baseline. Answers "is this moment abnormal?" Sets the [[Safety Floor]].
- **Tier 2 — Temporal** — everything "over time." Has a *deterministic half* (CUSUM **Drift** detection) and a *learned half* (the world-model **Surprise**). Answers "is this infant's trajectory departing from its own normal?"
- **Tier 3 — RAG** — guideline-grounded reasoning that produces the human-facing explanation.

**Drift**
The phenomenon of slow deterioration where no single window trips a threshold but the
cumulative trend is abnormal — an infant sliding downward over hours. Distinct from its
detectors (CUSUM, EWMA): Drift is *what happens*; those are *ways to catch it*.

**Surprise**
The world model's signal: how unexpected the current window is given the infant's own
learned normal dynamics. Sustained rising Surprise is the learned analogue of Drift.

**Verdict**
The single merged judgement emitted after the tiers' Assessments are combined — the thing
the clinician actually sees. Exactly one Verdict per assessment run.

**Verdict Cascade**
The module that runs the tiers in order and merges their Assessments into one **Verdict**
under fixed combination rules. It is the one place the verdict policy lives.

**Safety Floor**
A deterministic minimum **concern level**, computed from Tier 1's hard rules, that no
downstream tier may cross. Later tiers may refine the level up or down *above* the floor —
so the world model can quiet a noisy alarm — but nothing can de-escalate below it. This is
the mechanism that guarantees a critical alert is never talked down.
