"""Write all clinical knowledge base text chunks to src/knowledge/clinical_texts/.

Run from any directory: python scripts/write_chunks.py
Idempotent — overwrites existing chunk files.
"""
from pathlib import Path

REPO_ROOT  = Path(__file__).resolve().parent.parent
CHUNKS_DIR = REPO_ROOT / "src" / "knowledge" / "clinical_texts"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# ── hrv_indicators.txt ────────────────────────────────────────────────────────
(CHUNKS_DIR / "hrv_indicators.txt").write_text("""\
RMSSD (Root Mean Square of Successive Differences) measures short-term heart rate variability and reflects parasympathetic vagal nervous system activity. In premature neonates under 30 weeks gestation, normal RMSSD is approximately 6-8ms at baseline, rising to 15-25ms by 32-36 weeks. Declining RMSSD over a 6-12 hour window indicates reduced vagal tone. A drop below the patient's personal 2-standard-deviation threshold represents a clinically significant early warning sign. RMSSD suppression combined with sympathetic dominance is a key pre-bradycardia and pre-sepsis HRV signature in premature infants.
Category: hrv_indicators. Risk tier: RED.

SDNN (Standard Deviation of Normal-to-Normal intervals) measures overall HRV and reflects both sympathetic and parasympathetic modulation. In neonates under 30 weeks gestation, SDNN is approximately 10ms; term newborns show median SDNN around 27ms. A declining SDNN trend over 8-12 hours, particularly when falling below the patient's personal 2-standard-deviation threshold, is associated with early physiological deterioration. SDNN is less sensitive than RMSSD for acute changes but provides context for sustained autonomic suppression.
Category: hrv_indicators. Risk tier: RED.

LF/HF ratio measures the balance between low-frequency sympathetic and high-frequency parasympathetic autonomic activity. A rising LF/HF ratio indicates sympathetic dominance and reduced parasympathetic tone. In healthy premature neonates, LF/HF typically ranges from 1.2 to 1.8, with more premature infants showing higher ratios. Values rising above the patient's personal 2.5-standard-deviation threshold indicate pathological sympathetic activation. Combined with falling RMSSD, a rising LF/HF ratio is a strong marker of early inflammatory response and impending bradycardia.
Category: hrv_indicators. Risk tier: RED.

pNN50 measures the percentage of successive RR interval differences exceeding 50ms. In premature neonates, pNN50 values are very low — typically under 2% for infants under 30 weeks and under 5% for 32-36 weeks, because neonatal RR intervals are short (~430ms) and rarely differ by 50ms consecutively. A sustained decline in pNN50 below the patient's personal threshold, when combined with declining RMSSD, provides additional evidence of parasympathetic withdrawal. pNN50 is most useful as a supporting indicator rather than a primary signal in neonates.
Category: hrv_indicators. Risk tier: YELLOW.
""")

# ── sepsis_early_warning.txt ──────────────────────────────────────────────────
(CHUNKS_DIR / "sepsis_early_warning.txt").write_text("""\
Pre-sepsis HRV signature in premature neonates consists of three concurrent changes detectable 12-24 hours before clinical signs appear. First, sustained reduction in short-term variability: RMSSD drops below the patient's personal 2-standard-deviation threshold. Second, sympathetic dominance shift: LF/HF ratio rises above the patient's personal 2.5-standard-deviation threshold. Third, increased bradycardia frequency — recurrent episodes preceding clinical sepsis diagnosis. When all three are present simultaneously, sensitivity for early sepsis detection exceeds 78% with specificity above 82% in published studies.
Category: sepsis_early_warning. Risk tier: RED.

The autonomic nervous system dysregulation that precedes clinical sepsis in neonates follows a predictable temporal pattern. Parasympathetic withdrawal begins first, typically 18-24 hours before fever, elevated CRP, or culture-positive blood draw. This manifests as declining RMSSD and pNN50. Sympathetic activation follows 6-12 hours later, visible as rising LF/HF ratio and heart rate baseline elevation. Any neonate showing personalised z-score deviations of -2.5 or worse on RMSSD AND +2.0 or worse on LF/HF simultaneously should be considered for blood culture.
Category: sepsis_early_warning. Risk tier: RED.

Recurrent bradycardia with HRV suppression is a distinct clinical pattern from isolated bradycardia. Isolated bradycardia in a premature neonate may reflect normal vagal reflexes. However, bradycardia events occurring alongside suppressed RMSSD (z-score below -2.0) and elevated LF/HF ratio represent pathological autonomic dysregulation. Three or more bradycardia events in a 6-hour window accompanied by HRV suppression warrants immediate clinical evaluation regardless of other vital signs.
Category: sepsis_early_warning. Risk tier: RED.

Early-stage sepsis in neonates under 32 weeks gestation presents differently from older infants. Temperature instability may be absent or show hypothermia rather than fever. CRP elevation lags HRV changes by 12-18 hours. Blood cultures may be negative at the point when HRV changes are most pronounced. This is why HRV monitoring targets a detection window that preclinical laboratory markers cannot. The personalised baseline approach is particularly important in this gestational age group because population-average thresholds miss the 30-40% of infants whose individual normal range falls outside population norms.
Category: sepsis_early_warning. Risk tier: RED.
""")

# ── intervention_thresholds.txt ───────────────────────────────────────────────
(CHUNKS_DIR / "intervention_thresholds.txt").write_text("""\
Immediate clinical review is warranted when a neonate shows all three: RMSSD z-score below -2.5 from personal baseline, LF/HF z-score above +2.5 from personal baseline, AND two or more bradycardia events in the preceding 6 hours. This combination has a positive predictive value of approximately 0.71 for confirmed sepsis within 24 hours in infants under 32 weeks gestation. Blood culture and CBC with differential should be obtained within 1 hour of identifying this pattern.
Category: intervention_thresholds. Risk tier: RED.

Reassess in 2 hours when a single HRV feature shows z-score deviation between -2.0 and -2.5 from personal baseline without other concurrent features changing. Single-feature mild deviations can reflect positional changes, feeding state, or sleep state transitions rather than pathology. If the deviation persists or worsens at the 2-hour reassessment, escalate to clinical review. If it normalises, continue routine monitoring.
Category: intervention_thresholds. Risk tier: YELLOW.

Continue routine monitoring at the standard frequency when all HRV z-scores remain within 1.5 standard deviations of the patient's personal baseline and no bradycardia events have occurred in the preceding 6 hours. Document baseline stability in the patient record. Routine monitoring interval for premature neonates under 32 weeks is continuous HRV assessment with alerts reviewed every 4 hours.
Category: intervention_thresholds. Risk tier: GREEN.

Increase monitoring frequency to every 15 minutes when HRV shows a directional trend: any two features moving consistently toward their alert thresholds across three or more consecutive windows, even if individual values remain within 2 standard deviations of baseline. Trends that persist for 4 or more hours without reaching alert thresholds should be flagged to the attending neonatologist for awareness even if no immediate action is indicated.
Category: intervention_thresholds. Risk tier: YELLOW.
""")

# ── bradycardia_patterns.txt ──────────────────────────────────────────────────
(CHUNKS_DIR / "bradycardia_patterns.txt").write_text("""\
Isolated bradycardia in a premature neonate at rest, without concurrent HRV suppression, most often reflects normal vagal reflex activity. A single bradycardia event with heart rate falling below 100 bpm lasting fewer than 20 seconds, self-resolving, with RMSSD and pNN50 remaining within 1 standard deviation of personal baseline is not independently predictive of sepsis. Document the event and continue routine monitoring.
Category: bradycardia_patterns. Risk tier: GREEN.

Recurrent bradycardia is defined as three or more episodes within a 6-hour window. When recurrent bradycardia occurs without HRV suppression (RMSSD and pNN50 within normal range), it warrants increased surveillance but not immediate intervention. Common causes include feeding intolerance, gastroesophageal reflux, and positional apnoea. Reassess at 2-hour intervals and escalate if frequency increases or HRV changes emerge.
Category: bradycardia_patterns. Risk tier: YELLOW.

Bradycardia with concurrent HRV suppression represents pathological autonomic dysregulation. When a bradycardia event occurs alongside RMSSD z-score below -2.0 and LF/HF ratio above the patient's personal +2.0 threshold, the combination is not reflexive — it reflects central autonomic failure. This pattern in a neonate under 30 weeks is associated with early sepsis or necrotising enterocolitis and requires immediate clinical evaluation.
Category: bradycardia_patterns. Risk tier: RED.

Bradycardia with concurrent apnoea (apnoeic bradycardia) is a high-risk pattern in premature neonates. A bradycardia event lasting more than 20 seconds, particularly if self-recovery is delayed beyond 30 seconds, requires prompt assessment. When apnoeic bradycardia occurs with HRV suppression (RMSSD z-score below -2.5), the probability of an underlying infectious or metabolic cause exceeds 60% in infants under 28 weeks gestation.
Category: bradycardia_patterns. Risk tier: RED.

Bradycardia frequency trending upward over 12 hours is a sensitive early indicator even when individual episodes appear isolated. A patient experiencing 1 episode in the first 4-hour block, 2 in the second, and 4 in the third block shows a doubling pattern that warrants proactive escalation. HRV monitoring provides the baseline context to distinguish whether this trend accompanies autonomic deterioration.
Category: bradycardia_patterns. Risk tier: YELLOW.

Post-feeding bradycardia in premature neonates can be a normal variant. Bradycardia occurring within 30 minutes of enteral feed initiation, resolving spontaneously within 15 seconds, with stable RMSSD and LF/HF ratio, is most likely a vagal response to gut distension. Reducing feed volume or rate is appropriate first-line management. HRV monitoring differentiates this from pathological episodes by confirming preserved autonomic variability.
Category: bradycardia_patterns. Risk tier: GREEN.

Self-limited bradycardia resolved by light stimulation, occurring in the context of stable HRV metrics over the preceding 6 hours, is unlikely to represent sepsis onset. The neonatal autonomic nervous system is immature and vagal overactivity is common below 32 weeks gestation. Clinical significance increases when: episodes occur at rest without a clear trigger, HRV trends are deteriorating, or episodes require sustained intervention for recovery.
Category: bradycardia_patterns. Risk tier: GREEN.

Bradycardia presenting for the first time after 72 hours of stability in a previously well premature neonate is a high-sensitivity marker for clinical deterioration. Late-onset bradycardia without a recent feeding, positional, or procedural trigger, especially in the context of temperature instability or feeding intolerance, should prompt blood culture, CRP, and CBC even if RMSSD is only mildly suppressed (z-score -1.5 to -2.0).
Category: bradycardia_patterns. Risk tier: YELLOW.

Deep bradycardia — heart rate below 60 bpm persisting for more than 10 seconds — requires immediate bedside response regardless of HRV status. This threshold represents severe haemodynamic risk. HRV monitoring provides retrospective context about whether the autonomic pattern was deteriorating before the episode, which informs whether the event is isolated or part of a systemic pattern.
Category: bradycardia_patterns. Risk tier: RED.

Bradycardia associated with handling or procedures (endotracheal suctioning, cannula insertion, physiotherapy) is expected in extremely premature neonates. These episodes are vasovagal in origin and should not be conflated with spontaneous bradycardia in HRV risk scoring. Algorithmic risk calculation should exclude brady episodes occurring within 5 minutes of documented care interventions.
Category: bradycardia_patterns. Risk tier: GREEN.

Bradycardia cluster events — three or more episodes within 60 minutes — represent acute haemodynamic instability and require immediate physician assessment irrespective of HRV values. HRV-based risk scoring becomes secondary once cluster bradycardia is identified. The primary action is bedside clinical evaluation, blood gas, and consideration of respiratory support.
Category: bradycardia_patterns. Risk tier: RED.

Improving bradycardia frequency over 12 hours, in combination with stabilising or improving RMSSD z-score, is a positive prognostic sign. When a patient who showed recurrent bradycardia with mild HRV suppression shows fewer events and RMSSD trending back toward personal baseline, continuing current management and monitoring at routine frequency is appropriate. Document the trend for the attending team.
Category: bradycardia_patterns. Risk tier: GREEN.
""")

# ── baseline_interpretation.txt ───────────────────────────────────────────────
(CHUNKS_DIR / "baseline_interpretation.txt").write_text("""\
Personalised baselines in neonatal HRV monitoring reflect each infant's individual autonomic set-point. Population-average thresholds for RMSSD, SDNN, or LF/HF ratio fail to account for the 30-40% of premature infants whose personal normal range falls outside one standard deviation of the population mean. A neonate whose baseline RMSSD is 5ms is not abnormal — their personal 2-standard-deviation alert threshold is approximately 2ms, not the population threshold of 7ms.
Category: baseline_interpretation. Risk tier: ALL.

The burn-in period for personalised baseline calculation requires a minimum of 10 consecutive windows of stable HRV before any z-score deviation is computed. This LOOKBACK=10 window approach provides enough history to estimate a rolling mean and standard deviation per feature, while being short enough to capture intra-day physiological shifts. Z-scores computed before 10 windows are excluded from risk scoring.
Category: baseline_interpretation. Risk tier: ALL.

Rolling z-score computation uses an exclusive lookback window: for window index i, the baseline is computed from windows i-10 through i-1 (10 windows). The current window is not included in its own baseline. This ensures that an acute deterioration does not immediately update the baseline and mask its own z-score. The baseline adapts to chronic state changes over time while remaining sensitive to acute shifts.
Category: baseline_interpretation. Risk tier: ALL.

Gestational age is the strongest predictor of baseline HRV values. A 26-week neonate will show RMSSD values in the range 5-9ms, SDNN 8-14ms, and LF/HF ratio 1.5-2.2. A 34-week neonate will show RMSSD 15-25ms, SDNN 22-35ms, and LF/HF 1.0-1.5. Applying a 34-week alert threshold to a 26-week patient will generate false positives. Personalised baselines implicitly correct for gestational age by measuring each patient against their own history.
Category: baseline_interpretation. Risk tier: ALL.

Post-procedure baseline disruption occurs when procedures (e.g., endotracheal suctioning, lumbar puncture, blood draw) acutely alter HRV for 15-30 minutes. These procedure-related HRV transients will enter the rolling baseline window and shift it transiently toward the patient's post-procedure state. If a procedure is documented, the baseline windows covering the 30 minutes post-procedure should be treated with caution in z-score interpretation.
Category: baseline_interpretation. Risk tier: ALL.

Baseline drift over days or weeks in a premature neonate reflects normal neurodevelopmental maturation. RMSSD and SDNN increase as gestational age advances. The personalised rolling baseline naturally tracks this maturation — the baseline mean rises gradually, preventing false-positive z-scores from a maturational RMSSD increase. This is a key advantage over fixed population thresholds, which would generate false negatives as the infant matures.
Category: baseline_interpretation. Risk tier: ALL.

A standard deviation of zero in the rolling baseline window indicates that all 10 preceding windows have identical values for that feature. This is physiologically implausible and indicates a data quality issue (e.g., signal loss, saturated measurement, or integer rounding). The z-score computation should return 0.0 (neutral) in this case rather than dividing by zero. The run_nb04.py implementation handles this with an explicit guard: if roll_std == 0, deviation = 0.0.
Category: baseline_interpretation. Risk tier: ALL.

Interpreting z-scores for LF/HF ratio requires understanding that LF/HF is already a ratio. A doubling of LF/HF from a personal baseline of 1.5 to 3.0 represents a z-score of approximately +2.5 standard deviations — the same clinical significance as a halving of RMSSD. The z-score framework normalises both additive and multiplicative changes into a common deviation scale.
Category: baseline_interpretation. Risk tier: ALL.

Concurrent z-score deviations across multiple features are more clinically significant than any single-feature deviation. Two features deviating by -2.0 standard deviations simultaneously is more concerning than one feature deviating by -3.0. The autonomic nervous system dysregulation that precedes sepsis affects multiple HRV dimensions simultaneously, so multi-feature deviation is a higher-specificity pattern than isolated feature deviation.
Category: baseline_interpretation. Risk tier: ALL.

Baseline interpretation requires awareness of sleep state. Active sleep in premature neonates is associated with lower RMSSD and higher LF/HF ratio compared to quiet sleep. Without sleep state information, a z-score during active sleep may appear as a mild deviation when it is actually normal for that state. In clinical practice, sustained deviations persisting across sleep state transitions are more reliable indicators than single-window deviations.
Category: baseline_interpretation. Risk tier: ALL.
""")

print(f"Written {len(list(CHUNKS_DIR.glob('*.txt')))} chunk files")
for f in sorted(CHUNKS_DIR.glob("*.txt")):
    n = len([c for c in f.read_text().split("\n\n") if c.strip()])
    print(f"  {f.name}: {n} chunks")
