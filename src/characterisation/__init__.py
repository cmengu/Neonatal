"""Detector characterisation — synthetic data as a measuring instrument (#83, D10).

This package measures **what the cascade can see**. It never produces evidence about
infants, and nothing in it may be cited in support of a clinical claim.

The separation this enforces has published precedent in this exact niche: Montazeri
Ghahjaverestan et al. (2021) characterised an apnea-bradycardia detector on simulated
data (Se 96.67%, Sp 98.98%), then validated the clinical claim on real preterm ECG
(Se 94.87%, Sp 96.52%, mean delay 0.73 s). Reviewers accepted it because simulation
characterised the *detector* and real data characterised the *claim*, and the paper never
conflated the two.

Lets the project say:
    "the watcher detects a sustained departure of magnitude δ within N windows,
     at X false alarms per patient-day."

Never lets it say:
    anything about sepsis, or about any real infant.
"""
