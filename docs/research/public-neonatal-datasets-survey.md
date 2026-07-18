# Public Neonatal Datasets — Can We Validate Against Real Outcome Labels?

**What this is.** The resolution of wayfinder ticket ② ([#73](https://github.com/cmengu/Neonatal/issues/73)) on map [#71](https://github.com/cmengu/Neonatal/issues/71): an exhaustive survey of publicly available datasets that could let NeonatalGuard validate against clinically meaningful outcome labels using the **beat-to-beat cardiac signal** the system actually consumes.

**Date:** 2026-07-18
**Method:** PhysioNet's complete project index was scraped (427 entries — the topic search is misleadingly narrow, returning only PICS for both "neonatal" and "infant"), data dictionaries and file manifests pulled via API, and sample files downloaded to verify sampling rates rather than trusting prose. Claims are marked **[verified]** where a primary artifact was read, **[inferred]** where reasoning goes past the documentation.

---

## The verdict, first

> **No public dataset allows validation against sepsis, NEC, or IVH labels using beat-to-beat cardiac signal.** Not open, not credentialed, not under any data-use agreement found.

The gap is **structural, not accidental**. The groups holding beat-to-beat neonatal ECG alongside adjudicated infection outcomes — UVA (HeRO/HRC), Eindhoven MMC (DeepLOS), Northwestern (RALIS) — have never deposited their data. And the one large multi-centre study designed to close exactly this gap, **Pre-Vent** (NHLBI, 730 infants under 29 weeks, with blood-culture-proven sepsis, Bell-stage NEC and graded IVH all coded), **deliberately kept the waveforms at the sites** and released only daily event counts.

Pre-Vent's own investigators wrote why, and it is worth quoting because it is the whole problem in two sentences:

> *"For the analysis of HR, one way to minimize variability across sites is to work directly with the interbeat RR intervals derived from ECG waveforms. However, this often involves a significant amount of additional data processing and management that may not be practical."*

**Consequence for this project.** The honesty pivot already in place — *detected = HRV departure; sepsis = hypothesis, not diagnosis* — is **not a temporary limitation to be engineered around. On public data it is the permanent state of the art.** That reframes it from an apology into a correct description of the field.

---

## A. Meets all three criteria

Exactly one, and it is the one already in use.

### PICS — Preterm Infant Cardio-Respiratory Signals
`https://physionet.org/content/picsdb/1.0.0/` · **open**, ODC-By v1.0, 1.6 GB **[verified]**

- **10 preterm infants**, GA 29 3/7 – 34 2/7 weeks (mean 31 1/7), 843–2100 g, UMass Memorial NICU **[verified]**
- ECG **500 Hz** (infants 2–10); infants 1 and 5 are 250 Hz compound. Respiration **50 Hz** inductance bands; infant 1 is 500 Hz from the monitor. 20–70 h per infant **[verified]**
- `.qrsc` R-peaks (Pan-Tompkins, visually inspected) · `.resp` respiration peaks (**algorithmic, explicitly not manually vetted**) · `.atr` bradycardia onsets (HR < 100 bpm for ≥ 2 beats) **[verified]**

**A limitation we had not recorded:** the GA range is **moderate-to-late preterm**. There are **zero infants under 29 weeks** — precisely the population where HRV-based deterioration detection carries the most clinical value, and precisely the population HeRO was validated in. This should be stated when quoting our numbers.

---

## B. Meets two of three

### B1 · MIMIC-III Waveform Database, neonatal subset — best signal, zero labels
`https://physionet.org/content/mimic3wdb/1.0/` · index file `RECORDS-neonates` · **fully open**, ODbL v1.0 **[verified]**

- **8,486 neonatal record sets** (vs 59,344 adult; 67,830 total), headers carrying `# Location: nicu` **[verified — index downloaded and counted, individual headers pulled]**
- **125 Hz** waveforms: ECG leads **II, AVR, V**, plus **RESP** (impedance) and **PLETH** (PPG). 1 Hz numerics: HR, PULSE, NBP, RESP, SpO₂ **[verified from `3000358_layout.hea`]**

**Fails on labels, totally** — no outcome annotations, and no gestational age or birth weight either. The only route to labels would be the Waveform Matched Subset.

**That route was tested empirically and it fails.** 200 subjects were sampled across the matched subset's ID range, yielding 440 waveform record IDs; intersecting them with the 8,486 neonatal IDs gave **zero overlap**, despite both spanning the same numeric range. Proportional representation (~12.5%) would predict ~55 hits. **[verified by sampling; stated honestly as "<1% of the matched subset" rather than "exactly zero", since this was a ~2% sample]**

This effectively settles the long-unanswered [MIT-LCP/mimic-code#432](https://github.com/MIT-LCP/mimic-code/issues/432).

**Technical caveat:** 125 Hz gives **8 ms RR quantization**. For a neonate at 160 bpm (RR ≈ 375 ms) with RMSSD plausibly 5–20 ms, the quantization step is a large fraction of the measured quantity. Parabolic or cubic R-peak interpolation becomes mandatory, and sample entropy on coarsely quantized RR is known to be fragile. A real step down from PICS's 500 Hz. **[inferred]**

### B2 · UVA NICU vital signs archive — best scale, wrong resolution
`https://doi.org/10.18130/V3/VJXODP` (LibraData/Dataverse) · **fully open, CC-BY 2.0, no login, no access request** · 36.0 GB, 6,014 files **[verified via Dataverse API]**

- **5,997 infants**, UVA NICU, Jan 2009 – Dec 2019. GA distribution **[verified by tabulating the metadata file]**: 22 wk: 9 · 23: 73 · 24: 116 · 25: 132 · 26: 123 · 27: 136 · 28: 141 → **730 infants ≤ 28 weeks**, **2,645 ≤ 34 weeks**. Birth weight 351–6089 g
- Per-patient `.mat` with `vt`/`vdata`/`vname`. Channels: HR, RESP, SPO2-%, SPO2-R, PT-RR, AR-S/D/M/R, UAC-*, NBP-*
- **Sampling interval 2 seconds (0.5 Hz)** — verified as median `diff(vt)` across four files spanning 7.6 h to 9,427 h **[verified]**
- Metadata: `PatientID, BirthTime, BirthWeight, GestAge, GestAgeDays, Male, APGAR1/5/10, AgeatDeath` — **285 infants have a death date** **[verified]**

**Fails on inputs, partially on labels.** Mortality is a legitimate outcome and 285 events across 5,997 infants is a usable label set. But 0.5 Hz monitor-derived HR is **not beat-to-beat** — it is a smoothed, monitor-averaged number. RMSSD, SDNN and sample entropy computed on it measure a *different physical quantity* than the same statistics on RR intervals. Porting the pipeline unchanged would be scientifically invalid.

**This is the most under-exploited public resource found in this survey.**

### B3 · Pre-Vent via BioLINCC — best labels, no time series at all
`https://biolincc.nhlbi.nih.gov/studies/pre_vent/` · credentialed, **no fees** **[verified]**

- **730 infants < 29 weeks GA**, 5 level-IV NICUs, Mar 2018 – Jun 2021, UVA coordinating. **Exactly the target population.**
- Labels are genuinely excellent (32-page data dictionary read directly) **[verified]**: `bcsep_exit` (blood-culture-proven sepsis), `bcsep_nbr`, bacterial/fungal/viral splits · `necyn` (Bell stage 2 or 3) + `necdays` · head-ultrasound IVH coded by grade (`hus_results___2` through `___5`) · plus pulmonary haemorrhage, PDA, ROP, mortality, respiratory outcome at 40 weeks PMA, neurodevelopmental impairment

**Fails on inputs, badly.** The dictionary contains **zero occurrences** of "waveform", "ECG", or "RR interval" **[verified by grep]**. What is released is **daily aggregated counts and durations** — `apnea_count`, `apnea_dur`, `Brady_80_5_inf_event_count`, `Desat_80_10_300_*` — one row per infant per day. There is no time series.

**Second blocker:** BioLINCC records a **Specific Consent Restriction — "Use of data and/or biospecimens is restricted to research related to breathing problems in infants."** **[verified]** A sepsis-prediction application would likely be refused; an apnea/bradycardia/desaturation application would fit.

---

## C. Near-misses and dead ends

Documented so the work is not repeated.

| Candidate | Why it fails |
|---|---|
| **MIMIC-IV neonatal project** | **Has not shipped.** The v2.0 note ("Neonatal data will be released in a separate project") is still carried on v3.1 with **no timeline, no name, no registration page**. PhysioNet's full 427-project index plus the 2025 and 2026 news archives show no neonatal database and no announcement. **[verified]** Treat as vapourware for planning. |
| **MIMIC-III clinical neonates** (7,874 NICU admissions) | Real, but tabular EHR. The waveforms live in a separate database that does not link to them — see B1. |
| **PIC — Paediatric Intensive Care** (Zhejiang) | Includes an NICU, but documentation states high-resolution monitor vitals "are not available outside of surgery"; perioperative is one value per 5 min. Fails inputs outright. **[verified]** |
| **NCH Sleep DataBank** | 3,984 PSG studies. Sleep lab, not NICU; labels are sleep stages. Age range not stated on the landing page. **[partially verified]** |
| **Neurocritical care pediatric waveforms** (PhysioNet) | 12 subjects **aged 2–25 years**. ABP/ICP/CBFV, **no ECG**. **[verified]** |
| **Helsinki neonatal EEG seizure dataset** | 79 **term** neonates, **EEG only, no ECG channel**. Frequently miscited as a cardiac resource. **[verified]** |
| **Cork/INFANT HIE EEG dataset** | 53 term neonates, EEG. The related HRV work used a separate 120-infant ECG cohort that was **not** deposited. |
| **Leipzig Heart Center ECG** | 39 patients (29 children), EP-lab arrhythmia labels. Congenital heart disease, not neonatal deterioration. **[verified]** |
| **ZZU pECG** (11,643 children) | Ages 0–14 at 500 Hz, but **5–120 second resting snapshots** with ICD-10 codes. No continuous monitoring, so no HRV trend. |
| **NBHR** (257 newborns) | Video-based non-contact HR benchmark. No ECG, no outcomes, term newborns. |
| **NeoVault** | **11 neonates**, ~3,000 physiological entries (HR in bpm, SpO₂ in %). Far too small, not high-frequency. |
| **PhysioNet/CinC 2019 "Early Prediction of Sepsis"** | **Adult** ICU, hourly vitals. Fails on both population and input. |
| **PhysioNet fetal ECG family** (adfecgdb, nifecgdb, NInFEA, fecgsyndb …) | Antenatal. Wrong side of birth. |
| **Every published preterm sepsis/NEC HRV model** — HeRO/HRC (UVA), RALIS (Northwestern), DeepLOS (Eindhoven), Fairchild's 1,065-infant study | **None deposited.** DeepLOS states its data is confidential; HeRO's >1,000-infant development set predates data-sharing mandates. **This is the central structural fact of the literature.** |
| **Registries** — VON, Canadian Neonatal Network, ANZNN, EPIPAGE-2, UK NNRD, NICHD NRN | All are **outcome registries with no signal-level data**. NICHD NRN additionally requires Steering Committee approval, a DUA, IRB approval **and reimbursement of coordinating-centre costs**. None solve the input problem at any price. |

---

## D. Access paths worth pursuing

**1 · CHIME via NICHD DASH — the highest-value unresolved lead.**
The Collaborative Home Infant Monitoring Evaluation is confirmed present in NICHD DASH. Its monitor recorded **breathing waveforms by inductance plethysmography, transthoracic impedance, ECG, beat-to-beat heart rate, and SpO₂** — beat-to-beat cardiac timing, explicitly — across a cohort that **includes preterm infants**, with cardiorespiratory event annotations and neurodevelopmental follow-up. DASH generally reports no IRB and no study-specific approval required for most holdings.

**Unverified and decisive:** whether the deposited files include the waveform recordings or only tabular/derived data. The DASH record did not expose a file manifest, and NICHD is mid-migration. **One email settles it.** Caveats if it pans out: 1994–1998 vintage, home rather than NICU, post-discharge population — so it would validate apnea/bradycardia physiology, not in-unit sepsis.

**2 · Pre-Vent via BioLINCC.** Free. Register with an institutional email via Login.gov, submit a research plan plus IRB approval or non-human-subjects determination, execute the RMDA via DocuSign. Frame the application around **apnea/bradycardia/desaturation burden**, not sepsis, to respect the consent restriction. Worth doing as an **external label-prior** — checking whether our event rates track published per-day distributions in a genuinely extremely-preterm population.

**3 · Manually matching MIMIC-III neonatal waveforms to MIMIC-III clinical neonates.** 8,486 open waveform record sets exist; 7,874 neonatal ICU admissions exist in the clinical database; the official matched subset connects essentially none. Doing that matching would itself be a research contribution and would create the dataset this field lacks. Genuinely hard — the official effort achieved only 34% linkage on adults with far better metadata. High risk, high value, **not a dependency to plan around**.

**4 · A labelled signal+sepsis cohort DUA.** Already on the roadmap; this survey confirms it is the correct call. Realistic counterparties: UVA (Moorman/Fairchild/Lake), Eindhoven MMC, Northwestern.

---

## E. What this changes for the project

The survey failed to find what it went looking for and found something arguably more useful.

**The "ten infants" objection now has an answer.** The most damaging question a judge can ask is *"ten infants is nothing."* Between MIMIC-III's **8,486 open neonatal waveform record sets** and the UVA archive's **5,997 infants with 285 mortality events**, both fully open with no gatekeeping, there is a credible path from a 10-infant result to a scaled one — without a single data-use agreement or waiting period.

**A three-dataset story that requires no DUA and no waiting:**

1. **Self-supervised pretraining** on MIMIC-III's neonatal ECG — real beat-to-beat, 8,486 records, open. The JEPA needs no labels, so this corpus is directly usable.
2. **Mortality validation** on the UVA archive — 285 events, GA down to 22 weeks, open. Requires re-deriving features at 0.5 Hz and treating them as a distinct quantity.
3. **PICS retained as the high-fidelity 500 Hz anchor** — where the beat-to-beat features are trustworthy.

**What it cannot do, under any arrangement available today, is put a number on sepsis.**

That is not a gap in our work. It is the state of the field, and being able to say so precisely — with the survey behind it — is a stronger position than a borrowed label would have bought.
