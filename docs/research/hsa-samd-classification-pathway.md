# HSA Regulatory Classification & Registration Pathway — Neonatal AI CDS/Monitoring System

**What this is.** A viability-brief section for the MGC pitch: *what class of medical
product our system is under Singapore's Health Sciences Authority (HSA), and what rules we
must follow to pilot and to commercialise it.* The product in scope is an AI-based neonatal
clinical-decision-support / monitoring system — a multi-tier ML pipeline that watches NICU
vital-sign telemetry, detects deterioration/drift, and produces escalation verdicts for
clinicians.

**Date:** 2026-07-15
**Sources:** HSA primary guidance (GL-04, GL-07, GN-13, GN-15, fees schedule, dealer's-licence
and clinical-trials pages) and the IMDRF SaMD N12 framework. Every claim below is cited to a
primary source. Items I could **not** verify against a primary source are flagged explicitly.

---

## Executive summary (the verdict in 5 lines)

1. **It is a medical device (Software as a Medical Device / SaMD).** It analyses real-time,
   patient-specific telemetry and generates *new* clinical recommendations (deterioration +
   escalation verdicts) — so it is **not** an exempt "Non-MD CDSS", which only display info or
   echo established guidelines [GL-07 §3, pp.24–27].
2. **Most defensible risk class: Class C.** Under HSA's SaMD table, our tool sits at *drive
   clinical management* × *critical situation* (fragile neonatal population, time-critical
   deterioration) → **Class C** [GL-07 §2, p.12]. This is doubly anchored: GN-13 Rule 10(i)
   puts *continuous surveillance of vital physiological processes in intensive care* in
   **Class C** ("monitors/alarms for intensive care; apnoea monitors") [GN-13 Rule 10(i)].
3. **Plausible range B–C.** If the intended-use claim is written down to *inform* only (not
   drive) management, Critical × Inform = **Class B** [GL-07 §2, p.12]. Class D is not
   reachable for this product type. **Assume C for planning.**
4. **Registration route:** product registration in **MEDICS**; because it's Class C, it is
   **not** exempt (only Class A is). Route depends on prior reference-agency approvals — Full
   (~220 working days, S$6,250) if novel, down to Abridged/Expedited/Immediate if we hold
   overseas approvals [GN-15; HSA fees]. A **dealer's licence** (manufacturer/importer/
   wholesaler) + **ISO 13485 QMS** are required regardless [GN-02; QMS page].
5. **Before registration we can lawfully pilot** as a clinical trial under a **Clinical
   Research Materials (CRM) notification** to HSA (device stays unregistered for the study),
   with the trial itself under MOH's Human Biomedical Research Act [HSA CRM page; clinical-
   trials overview]. This is the compliant path to a pre-commercial NICU pilot.

---

## 1. Is it a medical device? (Qualification)

**Yes — it qualifies as SaMD, and specifically as a *medical-device* CDSS, not an exempt one.**

HSA's software guidance defines a **Standalone Medical Mobile Application / SaMD** as
"software … intended to be used for one or more medical purposes that function by itself and
are not intended for use to control or affect the operation of other hardware medical devices"
[GL-07 §1(ii) Definitions, p.5]. Software qualifies when its intended use meets the medical-
device definition in the First Schedule of the Health Products Act — i.e. it is for
"investigation, detection, diagnosis, prevention, monitoring, treatment or management of any
medical condition, disease, anatomy or physiological process" [GL-07 §3(ii) Intended Use,
p.23]. Our system's purpose (detecting deterioration and driving escalation) is squarely
*monitoring* + *detection* of a physiological process, so it is in scope.

**Why we are NOT an exempt "Non-MD CDSS".** HSA excludes CDSS from regulation only if one of
these holds [GL-07 §3(iv)–(v) and the qualification flowchart, pp.24–27]:
- it is *solely* for display/printing of medical information — **but this explicitly "does not
  include real-time patient information intended for patient monitoring or treatment
  decisions"** [GL-07 p.24, footnote]; ours is real-time monitoring, so this exclusion fails;
- OR its output/recommendations are *solely* based on established clinical guidelines and it
  "do[es] not generate new or modified clinical recommendations beyond what are established in
  the clinical guidelines" [GL-07 §3(iv), R2 addition, p.24/26]. Our ML pipeline generates
  *new* patient-specific risk/escalation outputs from telemetry, so this exclusion also fails.

> **Note on our RAG/guideline-grounding layer.** Even though part of the system grounds
> outputs in neonatal-sepsis guidelines, the escalation verdict is *computed* from the
> infant's own signals by ML — a "new or modified clinical recommendation beyond" the
> guideline text — so the guideline-only exemption does not apply. Being a device is the
> conservative, correct assumption.

**Sources:**
- GL-07: *Guidelines on Risk Classification of Software as a Medical Device (SaMD) and
  Qualification of Clinical Decision Support Software (CDSS)*, Revision 2, July 2025 —
  https://isomer-user-content.by.gov.sg/409/ae814059-a3ff-4ce3-8192-4534a43ddc6f/gl-07-r2-guidelines-risk-classification-samd-cdss-(2025-jul)-pub.pdf
- Health Products Act, First Schedule (medical-device definition) — referenced in GL-07 §3(ii).

---

## 2. Risk classification (Class A–D)

### 2.1 The HSA class scale

HSA classifies all general medical devices into four risk classes, based on intended purpose,
mode of operation, user and technology [GN-13 §Introduction]:

| Class | Risk level | Illustrative (non-software) examples | Registration? |
|-------|-----------|--------------------------------------|---------------|
| A | Low | wheelchairs, tongue depressors | **Exempt** from product registration |
| B | Low–moderate | hypodermic needles, suction equipment | Required |
| C | Moderate–high | ventilators, bone-fixation plates | Required |
| D | High | heart valves, implantable defibrillators | Required |

[GN-13-R2.1, classification-summary table, p.~11; class-registration rule confirmed on HSA's
*Risk classification of medical devices* page.] **Standalone software is deemed an active
medical device** [GN-13 note, "Standalone software is deemed to be an active medical device"].

### 2.2 The SaMD-specific rule (GL-07) — the primary tool

HSA classifies SaMD from a 3×3 matrix (IMDRF-derived): **significance of information**
(treat/diagnose · drive clinical management · inform clinical management) ×
**state of the healthcare situation** (critical · serious · non-serious) [GL-07 §2(i), pp.6–11].

**Non-IVD SaMD Risk Classification Table** [GL-07 §2(ii), p.12]:

| State \ Significance | Treat or diagnose | Drive clinical management | Inform clinical management |
|---|---|---|---|
| **Critical** | C | **C** | B |
| **Serious** | C | B | A |
| **Non-serious** | B | A\* | A |

\* Class B if it analyses/measures/monitors a *vital physiological process* (heart rate, BP,
respiratory rate, temperature) to drive management — "consistent with rule 10(i) of GN-13"
[GL-07 table footnote, p.12].

**Where our product lands:**

- **Significance = "drive clinical/patient management."** HSA defines this as information used
  "to triage or identify early signs of a disease or condition … [or] to guide next diagnostics
  or next treatment interventions" [GL-07 §2(i), p.8]. Our escalation verdict is exactly a
  triage / early-deterioration signal that guides the clinician's next action. (It is not
  "treat or diagnose" — we don't autonomously deliver therapy or render a definitive diagnosis;
  and it is more than "inform", which is passive aggregation of options [GL-07 §2(i), p.8].)
- **State = "critical."** HSA's *critical* definition is met when the situation is
  "time-critical" and, explicitly, when the **"intended target population is fragile with
  respect to the disease or condition (e.g., pediatrics, high-risk population)"** and the
  device is "intended for specialized trained users" [GL-07 §2(i) Critical, p.9]. A NICU
  deterioration/escalation tool hits every clause: neonates are the archetypal fragile
  population, deterioration is time-critical, and users are specialist clinicians.

→ **Critical × Drive clinical management = Class C** [GL-07 table, p.12].

**HSA's own worked example confirms this.** GL-07 §2(iii) classifies *"software … to collect
and analyse vital-sign readings to triage or risk-stratify patients for risk of Major Adverse
Cardiac Event (MACE) at the emergency department"* as **Class C** — reasoning: "drive clinical
management … triage/risk-stratify" × "critical condition; timely diagnosis or treatment action
is vital to avoid death…" [GL-07 §2(iii) Examples, p.20]. Our product is the neonatal analogue
of this example.

### 2.3 Cross-check against GN-13 Rule 10(i) — independent confirmation

Because standalone software is an active device, GN-13's active-device rules also apply. **Rule
10(i)** places active devices for "monitoring of vital physiological parameters, where the
nature of variations is such that it could result in immediate danger to the patient, for
instance variations in cardiac performance, respiration, activity of central nervous system"
in **Class C**, and adds the decisive note:

> "Medical devices intended to be used for **continuous surveillance of vital physiological
> processes in anaesthesia, intensive care or emergency care are in Class C**, whilst medical
> devices intended … in routine check-ups and in self-monitoring are in Class B."
> Example given: **"monitors/alarms for intensive care; biological sensors; oxygen saturation
> monitors; apnoea monitors."**
> [GN-13-R2.1, Rule 10(i)]

A NICU is intensive care; our tool is continuous surveillance of vital physiological processes
there. Rule 10(i) and GL-07 therefore **both point to Class C** — the classification is
robust, not a single-source guess.

### 2.4 IMDRF N12 cross-reference

HSA's matrix is explicitly derived from **IMDRF/SaMD WG/N12FINAL:2014** [GL-07 §1(i) footnote 1].
N12 uses the same two axes (state of healthcare situation × significance of information to the
healthcare decision) and its highest category, **IV**, corresponds to *critical × treat-or-
diagnose*; our *critical × drive* falls one step below the top — consistent with a high-B/C
mapping, which HSA renders as **Class C**. *(I verified the N12 axes and their identity with
the GL-07 wording directly from GL-07; I was unable to fetch the N12 PDF itself from imdrf.org —
repeated fetch timeouts — so the N12 category-number mapping above is stated as corroboration,
not as a directly-quoted N12 cell. Flagged.)*

### 2.5 Verdict and uncertainty

- **Most defensible class: C.** Justification (one line): a NICU deterioration-escalation SaMD
  is *drive-clinical-management* information used in a *critical* setting for a *fragile*
  population — Class C by GL-07's table, GL-07's own MACE-triage example, and GN-13 Rule
  10(i)'s "intensive-care continuous surveillance" clause.
- **Plausible range: B–C.** The lever is the written **intended-use claim**:
  - If claimed as *inform* only (surfaces information; clinician independently decides) →
    Critical × Inform = **Class B** [GL-07 table]. This is defensible *only* if the product is
    genuinely non-triaging; an "escalation verdict" reads as *drive*, so B would likely be
    challenged by HSA.
  - *Drive* is the honest characterisation of an escalation output → **C**.
- **Class D is not applicable** — reserved for treat/diagnose in the highest-risk device
  categories; a decision-support monitor does not reach it.
- **Planning assumption: Class C.**

**Sources:**
- GN-13: *Guidance on the Risk Classification of General Medical Devices*, GN-13-R2.1, Sept
  2018 — https://isomer-user-content.by.gov.sg/409/5c0b7242-e829-4f8d-baca-0b9542170bb5/gn-13-r2-1-guidance-on-the-risk-classification-of-general-medical-devices-(18sep-pub).pdf (Rule 10(i), active-device section).
- GL-07 (as above), §2 Classification, table p.12, examples pp.13–21.
- HSA, *Risk classification of medical devices* — https://www.hsa.gov.sg/medical-devices/registration/risk-classification-rule (Class A exempt; B/C/D require registration).
- IMDRF/SaMD WG/N12FINAL:2014, *Software as a Medical Device (SaMD): Possible Framework for Risk
  Categorization and Corresponding Considerations*, 18 Sep 2014 — https://www.imdrf.org/documents/software-medical-device-possible-framework-risk-categorization-and-corresponding-considerations (axes verified via GL-07; PDF itself not fetched — flagged).

---

## 3. Registration route (MEDICS)

**Registration is mandatory** for Class B/C/D before the device is placed on the Singapore
market; **only Class A is exempt** [HSA *Risk classification* page; GN-13]. As Class C, we must
register. Product registration is submitted through HSA's **MEDICS** online system
(the medical-device module of PRISM/SHARE) [GN-15; HSA registration overview].

### 3.1 Evaluation routes and eligibility

HSA uses a confidence-based set of routes that leverage prior approvals by its overseas
**reference regulatory agencies** and safe-marketing history [GN-15-R12/R13; HSA registration
overview]:

| Route | Applies to | Eligibility (summary) |
|---|---|---|
| **Full evaluation** | B, C, D | No prior approval by any HSA reference agency (novel device) |
| **Abridged** | B, C, D | Approval by ≥1 reference agency |
| **Expedited** (ECR Class C / EDR Class D) | C, D | ECR-1: 1 overseas approval + ≥3 yrs marketed, no safety issues, no rejections; ECR-2/EDR: 2 approvals, no rejections |
| **Immediate** (IBR) | B (+ standalone apps B/C) | 1 approval +≥3 yrs history, or 2 approvals; no safety issues/rejections |
| **Priority Review Scheme** | Full-route devices | Faster processing for eligible full-route submissions |

For a *novel* neonatal AI product with no prior overseas clearance, the default is the **Full
evaluation route for Class C**. Securing an FDA/EU/reference-agency clearance first would open
the cheaper/faster Abridged or Expedited routes.

### 3.2 Published timelines and fees

Target turnaround times (working days) and fees, HSA fee schedule (fees effective 1 Jul 2024;
figures exclude applicant response time) [HSA *Fees and turnaround time for medical devices*]:

| Class C route | Target time | Evaluation fee | + Application fee |
|---|---|---|---|
| Immediate | immediate on submission | S$3,340 | S$560 |
| Expedited (ECR) | ~120 working days | S$3,340 | S$560 |
| Abridged | ~160 working days | S$3,900 | S$560 |
| **Full** | **~220 working days** | **S$6,250** | S$560 |

(For reference: Class B Full ≈160 days / S$3,900; Class D Full ≈310 days / S$12,000. Priority
Review adds a premium, e.g. Class C Full PRS-1 S$7,000.) The **S$560 application fee** is
charged on submission; evaluation fees on dossier acceptance.

### 3.3 Dealer's licence + QMS (required regardless of route)

To manufacture, import or supply the device, the company needs a **dealer's licence** —
**manufacturer's, importer's, and/or wholesaler's licence** [GN-02; HSA dealer's-licence page].
QMS requirements [HSA *QMS for Medical Devices* page; GN-02-R5]:
- **Manufacturers** in Singapore must maintain a QMS conforming to **ISO 13485**.
- **Importers/wholesalers** of Class B/C/D must hold **GDPMDS or ISO 13485** certification from
  a Singapore Accreditation Council (SAC)-accredited certification body (Class A may self-
  declare).
- GL-04 reiterates that *all* SaMD/MLMD design, development, training, validation, retraining
  and deployment "must be performed and managed under an ISO 13485 based QMS" [GL-04 §2; §9].

**Sources:**
- GN-15: *Guidance on Medical Device Product Registration* — R12 (Aug 2025) /
  R13 (Mar 2026) — https://www.hsa.gov.sg/docs/default-source/hprg-mdb/guidance-documents-for-medical-devices/gn-15-r13-guidance-on-medical-device-product-registration-(2026-mar)-pub.pdf
- HSA, *Registration overview of medical devices* — https://www.hsa.gov.sg/medical-devices/registration/overview
- HSA, *Fees and turnaround time for medical devices* — https://www.hsa.gov.sg/medical-devices/fees/
- GN-02: *Guidance on Licensing of Manufacturers, Importers and Wholesalers of Medical Devices*,
  R5 (Jul 2023) — https://www.hsa.gov.sg/docs/default-source/hprg-mdb/guidance-documents-for-medical-devices/gn-02-r5-guidance-on-licensing-of-manufacturers-importers-and-wholesalers-of-md-(2023-jul)-pub.pdf
- HSA, *Quality Management System (QMS) for Medical Devices* — https://www.hsa.gov.sg/medical-devices/dealers-licence/quality-management-system-(qms)-for-medical-devices

---

## 4. AI-specific standing rules (MLMD / AI-MD)

GL-04-R4 (Dec 2025) is the governing document. It defines an **AI-enabled Medical Device
(AIMD)** as "a medical device that uses artificial intelligence technology to achieve its
intended medical purpose," and a **Machine-Learning-enabled Medical Device (MLMD)** per
IMDRF/AIMD WG/N67 [GL-04 §Definitions, p.~7]. Our system is an MLMD/AIMD. Key standing
requirements for **pre-market registration of an MLMD** [GL-04 §9.1, Table 1, pp.34–35]:

- **Dataset provenance & training.** Submit the **source and size of the training dataset**;
  describe labelling, curation, annotation; describe **data cleaning and missing-data
  imputation**; and ensure **no duplication between training and validation sets**
  [GL-04 §9.1, "Model Training"].
- **Performance validation.** Provide test protocols/reports with metrics (accuracy, confusion
  matrix, log-loss, **AUC**); a breakdown of the test dataset and collection protocol that
  **addresses potential biases and is representative of the local population**; and outlier/
  extreme-value controls [GL-04 §9.1, "Performance Validation"].
- **Clinical evaluation / clinical association.** Present a **valid clinical association between
  the MLMD's output and the target clinical condition**; clinical validation data **must be
  independent of training/tuning data**, and the study population must represent the local
  population (age, sex, race, condition) [GL-04 §9.1 "Clinical Evaluation" + §3.5]. For **novel
  intended purposes or new target populations, clinical studies are expected** [GL-04 §3.5,
  Table 4] — relevant to us, since neonatal deterioration prediction is a novel claim.
- **Human-in-the-loop / workflow.** State the intended clinical workflow and the **degree of
  human intervention**, and the performance of the ML-human interaction [GL-04 §9.1, "Clinical
  Workflow"]. (Keeping a clinician in the loop is also what holds us at *drive*, not *diagnose*
  — see §2.5.)
- **Risk management.** Risk assessment must cover ML-specific risks: **overfitting, unintended
  bias, degradation, model drift**, with controls [GL-04 §9.1 "Risk/Benefit"; §3.6 per ISO
  14971].
- **Locked vs continuous-learning.** For **continuous-learning** MLMD (models that change
  post-deployment), HSA requires additional submissions: description of the learning process
  and process controls; **safety mechanisms to detect anomalies and to roll back to a previous
  algorithm version** against a defined **baseline**; identical inclusion/exclusion criteria to
  the original training set; and data-integrity controls [GL-04 §9.2, pp.35–37]. **Locked
  models carry a lighter burden** — a practical steer: **ship a locked model first**, add
  continuous learning later under change control.
- **Post-market obligations.** Active real-world **performance monitoring, concept-drift
  detection, traceability** between training data / model version / output, and the ability to
  trace a bad output back to specific data, remove it, and retrain [GL-04 §9.3, pp.37]. All
  registered MLMD must monitor real-world performance post-deployment.
- **Change management.** Any change to a registered MLMD needs a **Change Notification**
  (categorised Technical / Review / Notification by change type and class) per **GN-21**; HSA
  also offers a **Change Management Program (CMP)** pathway that pre-authorises a defined
  envelope of SaMD/ML changes so updates don't each need fresh approval [GL-04 §9.4 and §10,
  pp.38–40].

**Sources:**
- GL-04: *Regulatory Guidelines for Software Medical Devices — A Life Cycle Approach* (incl.
  machine-learning features), **GL-04-R4, December 2025** — https://isomer-user-content.by.gov.sg/409/26808a93-6a7a-4551-8c66-13046c6124c5/gl-04-r4-regulatory-guidelines-for-software-medical-devices---a-life-cycle-approach-(2025-dec)-pub.pdf (§2 QMS; §3.5 Clinical Evaluation; §3.6 Risk; §9 MLMD; §10 CMP).
- GN-21: *Guidance on Change Notification for Registered Medical Devices*, R6 (Jul 2025) — referenced by GL-04 §9.4.

---

## 5. Pre-market vs pilot — what we may lawfully do before registration

We can run a **pre-commercial NICU pilot/clinical trial with the unregistered device** without
completing product registration, provided we use the clinical-trials route:

- **Clinical Research Materials (CRM) notification to HSA.** Importing or supplying an
  unregistered medical device for clinical research requires a **CRM notification** to HSA
  before use, unless the device is already registered and you hold the appropriate licence
  [HSA *Submit a Clinical Research Materials notification*]. CRM = "any registered or
  unregistered … medical device … manufactured, imported or supplied for the purpose of being
  used in clinical research" [HSA clinical-trials overview]. For medical-device trials (which
  don't need a CTA/CTN), **the CRM importer or local manufacturer submits the notification
  directly**; it is valid for one year, renewable via PRISM [HSA CRM page].
- **The trial itself is governed by MOH's Human Biomedical Research Act (HBRA), not HSA
  product law.** "Medical device clinical trials, observational clinical trials … are required
  to comply with the requirements of the Human Biomedical Research Act, regulated under the
  Ministry of Health" [HSA clinical-trials overview] — in practice via IRB/DSRB ethics
  approval at the trial site. HSA's role in a device trial is the CRM control over the
  investigational material.
- **Net for the MGC pitch:** the compliant sequence is **(a)** build under an ISO-13485-aligned
  QMS → **(b)** run a NICU pilot as an HBRA/IRB-approved clinical trial with a **CRM
  notification** covering the unregistered device → **(c)** use pilot data as clinical evidence
  → **(d)** complete Class C product registration in MEDICS before any commercial supply. We do
  **not** need full registration to pilot; we **do** need it before selling/deploying
  commercially.

> **Flag / open items to confirm before relying on this in a submission:**
> - The exact HBRA/DSRB obligations and whether a specific ethics category applies to a
>   decision-support (non-interventional-therapy) device were **not** verified line-by-line
>   against the HBRA text — confirm with the pilot site's IRB. (The HSA clinical-trials page
>   states the HBRA/MOH governance; the statute itself was not fetched.)
> - GN-15 exact route-eligibility wording is cited from HSA's registration-overview page and
>   the fee schedule; the R12/R13 PDF clause numbers were not opened page-by-page. The route
>   *structure, timelines and fees* are from HSA primary pages and are reliable; treat specific
>   clause citations as "per GN-15" pending a page check.
> - IMDRF N12 PDF could not be fetched (timeouts); its framework is quoted via GL-04/GL-07,
>   which reproduce it. (See §2.4.)

**Sources:**
- HSA, *Submit a Clinical Research Materials notification* — https://www.hsa.gov.sg/clinical-trials/crm-notification
- HSA, *Regulatory overview of clinical trials* — https://www.hsa.gov.sg/clinical-trials/overview
- Human Biomedical Research Act (MOH) — named in HSA clinical-trials overview; statute not
  fetched (flagged).

---

## Appendix — primary documents used

| Doc | Title / version | URL |
|---|---|---|
| GL-07-R2 | Risk Classification of SaMD & Qualification of CDSS (Jul 2025) | https://isomer-user-content.by.gov.sg/409/ae814059-a3ff-4ce3-8192-4534a43ddc6f/gl-07-r2-guidelines-risk-classification-samd-cdss-(2025-jul)-pub.pdf |
| GL-04-R4 | Software Medical Devices — A Life Cycle Approach (Dec 2025) | https://isomer-user-content.by.gov.sg/409/26808a93-6a7a-4551-8c66-13046c6124c5/gl-04-r4-regulatory-guidelines-for-software-medical-devices---a-life-cycle-approach-(2025-dec)-pub.pdf |
| GN-13-R2.1 | Risk Classification of General Medical Devices (Sep 2018) | https://isomer-user-content.by.gov.sg/409/5c0b7242-e829-4f8d-baca-0b9542170bb5/gn-13-r2-1-guidance-on-the-risk-classification-of-general-medical-devices-(18sep-pub).pdf |
| GN-15 | Medical Device Product Registration (R13, Mar 2026) | https://www.hsa.gov.sg/docs/default-source/hprg-mdb/guidance-documents-for-medical-devices/gn-15-r13-guidance-on-medical-device-product-registration-(2026-mar)-pub.pdf |
| GN-02-R5 | Licensing of Manufacturers/Importers/Wholesalers (Jul 2023) | https://www.hsa.gov.sg/docs/default-source/hprg-mdb/guidance-documents-for-medical-devices/gn-02-r5-guidance-on-licensing-of-manufacturers-importers-and-wholesalers-of-md-(2023-jul)-pub.pdf |
| — | HSA Risk classification page | https://www.hsa.gov.sg/medical-devices/registration/risk-classification-rule |
| — | HSA Registration overview | https://www.hsa.gov.sg/medical-devices/registration/overview |
| — | HSA Fees & turnaround | https://www.hsa.gov.sg/medical-devices/fees/ |
| — | HSA QMS page | https://www.hsa.gov.sg/medical-devices/dealers-licence/quality-management-system-(qms)-for-medical-devices |
| — | HSA CRM notification | https://www.hsa.gov.sg/clinical-trials/crm-notification |
| — | HSA Clinical-trials overview | https://www.hsa.gov.sg/clinical-trials/overview |
| N12 | IMDRF SaMD risk-categorization framework (2014) | https://www.imdrf.org/documents/software-medical-device-possible-framework-risk-categorization-and-corresponding-considerations |
