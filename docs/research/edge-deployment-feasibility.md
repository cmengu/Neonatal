# Edge-Deployment Feasibility — Where the Learned Model Actually Runs

**Scope.** An honest, primary-sourced audit of NeonatalGuard's **edge-deployment claim** for the MGC
pitch, resolving GitHub issue **#34** under wayfinder map **#22**. The pitch needs exactly one defensible
statement about how the system runs at the bedside, backed by real hardware numbers, that survives a
technical investor's adversarial probe. Two candidate claims are on the table:

- **(a) On-device tiny model** — an ESP32-class MCU runs a small learned model *and/or* the Tier-1
  deviation math (rolling z-scores + CUSUM over vital-sign features) entirely on-device.
- **(b) Sensor-plus-gateway** — the ESP32 is a sensor front-end streaming vitals to a small model running
  on a nearby edge gateway (Raspberry Pi / NVIDIA Jetson / phone).

The framing fact this review anchors on and verifies: **an ESP32 has ~520 KB of on-chip SRAM (up to
~32 MB with external PSRAM) and cannot hold a billion-parameter model.** So the real question is not "MCU
or gateway" as a binary — it is *where the learned model lives* and *what genuinely fits on-device*.

**Question under review.** *Given real Espressif / NVIDIA / Raspberry Pi hardware numbers, which
edge-deployment claim is defensible under adversarial technical probing — and what is the exact wording?*

**Date:** 2026-07-15
**Author:** Research agent (edge-deployment feasibility)

---

## Bottom line (honest)

The evidence points to a **hybrid**, not a clean (a)-or-(b). The deterministic **Tier-1 safety-floor math
runs on the MCU on-device** — it is kilobytes of state and no matrix multiply, so it fits trivially and
runs always-on even if WiFi drops. The **learned tiers (Tier 2 world-model, Tier 3 LLM) run on a nearby
edge gateway** (Raspberry Pi 5 / Jetson Orin Nano) or a server — a billion-parameter model needs
~0.5–1 GB+ of RAM, which is impossible on an ESP32 and comfortable on a Pi/Jetson. A *tiny* neural net
(≤250 KB) *can* run on an ESP32-S3, but our learned tiers are not that small, so the honest split is
**deterministic-floor-on-device + intelligence-on-gateway.**

| Candidate claim | Status | One-line verdict |
|---|---|---|
| **(a) A billion-param model runs on the ESP32** | **False — do not claim** | An ESP32 has ~520 KB SRAM; a 1B-param 4-bit model needs ~0.5–1 GB. Off by ~1000×. Indefensible. [§1](#1-esp32-hardware-envelope-first-party-espressif), [§5](#5-what-a-billion-parameter-model-needs) |
| **(a′) The deterministic Tier-1 math runs on the ESP32** | **True — strongest on-device claim** | Rolling mean/SD → z-scores + CUSUM over ~10–12 features is a handful of floats of state per feature, O(1) per update, no matmul. Kilobytes on a 512 KB chip. [§3](#3-does-the-tier-1-deviation-math-fit-on-device-yes-easily) |
| **(a″) A *tiny* (≤250 KB) neural net runs on the ESP32-S3** | **True but not our model** | TFLM's 250 KB person-detection net runs in ~54 ms on ESP32-S3 with ESP-NN. Real, but our Tier-2/3 models are far larger. Cite as capability, not as our deployment. [§2](#2-tinyml-on-device-footprints-first-party) |
| **(b) ESP32 streams vitals to a gateway running the learned model** | **True — the home of Tier 2/3** | Pi 5 (up to 16 GB) / Jetson Orin Nano (8 GB, 67 TOPS) easily hold a small quantized model; vitals are low-bandwidth, well within ESP32 WiFi/BLE. [§4](#4-edge-gateway-model-serving-first-party), [§6](#6-streaming-bandwidth-reality) |
| **Recommended: hybrid (a′ + b)** | **Defensible** | Deterministic safety-floor on the MCU (always-on, WiFi-independent) + learned intelligence on the gateway. Each half is backed by first-party numbers. [Recommended claim](#recommended-claim-for-the-pitch) |

**The single most important honest point for the pitch:** the *learned* model does **not** run on the
microcontroller. What runs on the MCU is the **deterministic Tier-1 [[Safety Floor]]** — deviation
math, not a neural net — and that is a genuinely strong claim precisely because it is cheap, auditable,
and survives a network outage. The intelligence (Tier 2 world-model, Tier 3 RAG/LLM) lives on the
gateway. Claiming a big model runs on the ESP32 is false by three orders of magnitude and will not
survive the first competent question.

---

## 1. ESP32 hardware envelope (first-party, Espressif)

The relevant fact is the on-chip RAM ceiling — that is what bounds any resident model.

### 1.1 Original ESP32
- **520 KB on-chip SRAM** plus **16 KB SRAM in RTC**, Xtensa single-/dual-core 32-bit **LX6** microprocessor;
  Wi-Fi (802.11 b/g/n) + **Bluetooth v4.2 BR/EDR and BLE** dual-mode. (Espressif, *ESP32 Series Datasheet*,
  https://documentation.espressif.com/esp32_datasheet_en.pdf; product page https://www.espressif.com/en/products/socs/esp32.)
  This is the source of the "~520 KB SRAM" framing figure.

### 1.2 ESP32-S3 (the right MCU for any on-device ML on this platform)
- **512 KB internal SRAM** + **8 KB RTC SRAM**; **dual-core Xtensa LX7 at up to 240 MHz**; supports
  **up to 32 MB external PSRAM and up to 32 MB external flash** via octal SPI with cache. (Espressif,
  *ESP32-S3 Series Datasheet*, https://documentation.espressif.com/esp32-s3_datasheet_en.html; product page
  https://www.espressif.com/en/products/socs/esp32-s3.)
- **AI acceleration is real but modest:** the LX7 core adds **vector instructions that accelerate neural-network
  and DSP workloads**, exposed through the **ESP-DSP** and **ESP-NN** libraries. (Espressif ESP32-S3 product
  page, ibid.; *ESP32-S3 Datasheet* §"Processor Instruction Extensions (PIE)".) This is SIMD-style acceleration
  of small kernels — **not** a GPU/NPU capable of a large transformer.
- **Connectivity:** Wi-Fi 802.11 b/g/n (2.4 GHz) and **Bluetooth 5 (LE)** with long-range coded PHY. (ibid.)

### 1.3 ESP32-P4 (the current high-end MCU — still not a model host)
- **768 KB on-chip SRAM** + **8 KB zero-wait TCM**; **dual-core RISC-V at up to 400 MHz with AI instruction
  extensions** and single-precision FPU; external PSRAM supported via cache. (Espressif, *ESP32-P4 Datasheet*,
  https://documentation.espressif.com/esp32-p4_datasheet_en.html; product page
  https://www.espressif.com/en/products/socs/esp32-p4.) Even the P4's 768 KB is ~1000× short of a 1B-param model.

> **Mapping to NeonatalGuard.** The MCU ceiling is **hundreds of KB of fast SRAM**, extendable to tens of MB
> of slower PSRAM. That envelope hosts (i) the deterministic Tier-1 math with room to spare, and (ii) *tiny*
> (sub-MB) neural nets. It does **not** host the Tier-2 world-model at any useful size or the Tier-3 LLM. The
> S3's "vector instructions for neural networks" is a true feature to cite — but it accelerates ~KB-scale
> kernels, and must not be inflated into "runs AI models on-device" without the size qualifier.

---

## 2. TinyML on-device footprints (first-party)

Concrete, published numbers for what actually fits and runs on ESP32-class RAM/flash:

- **Person detection (the canonical TFLM vision example):** a **~250 KB** neural network doing binary
  "is there a person" classification on 96×96 grayscale frames. (Espressif, *esp-tflite-micro* →
  `examples/person_detection`, https://github.com/espressif/esp-tflite-micro; TensorFlow blog,
  *Announcing TensorFlow Lite Micro support on the ESP32*,
  https://blog.tensorflow.org/2020/08/announcing-tensorflow-lite-micro-esp32.html.)
- **Measured latency, same repo (first-party benchmark):**
  - **ESP32-S3:** person detection **54 ms with ESP-NN** (vs **2300 ms without**) at 240 MHz — a ~40× speedup
    from the vector-instruction kernels.
  - **ESP32 (LX6):** **380 ms with ESP-NN** (vs **4084 ms without**) at 240 MHz.
  (Espressif, *esp-tflite-micro* README performance table, https://github.com/espressif/esp-tflite-micro.)
- **Runtime overhead is small:** the TFLM core runtime is designed to fit in **tens of KB** (order ~16–22 KB
  with a small op set), leaving most of SRAM for the model's tensor arena. (TensorFlow, *TFLite for
  Microcontrollers* overview, https://www.tensorflow.org/lite/microcontrollers; now LiteRT for Microcontrollers,
  https://ai.google.dev/edge/litert/microcontrollers/overview.)
- The TensorFlow ESP32 blog reports single-core ESP32 person detection **under ~1 s (~700 ms)** before the
  ESP-NN optimizations — consistent with the numbers above. (TF blog, ibid.)

> **Mapping to NeonatalGuard.** A **≤250 KB** model *does* run on an ESP32-S3 in tens of milliseconds — this
> is the honest ceiling of "on-device learned model." Our Tier-2 world-model (even a linear Kalman/VAR
> per-infant model may be small, but the neural variants are not) and our Tier-3 LLM are **not** in this size
> class. So this section supports a **capability** claim ("the platform *can* run tiny nets on-device") but
> **not** the claim that *our* learned tiers run on the MCU. Use it to show technical literacy, not to overclaim.

---

## 3. Does the Tier-1 deviation math fit on-device? Yes, easily

This is the load-bearing on-device claim, and it is **not a neural network** — so the TinyML footprint
question does not even apply. Per the project's [[Tier]] 1 definition (CONTEXT.md; `detection-methodology.md`
§1–2), Tier 1 is: personalized **z-scores** of ~10–12 HRV/vitals features against the infant's own rolling
mean/SD, plus a **CUSUM** change-detector for [[Drift]] (tuning `k ≈ 0.5σ`, `h ≈ 4–5σ`; `detection-methodology.md`
§2.2). Its compute/memory footprint:

- **Rolling mean/SD per feature is O(1) state and O(1) per update.** Welford's online algorithm keeps just
  `(count, mean, M2)` — three scalars — and updates each in a few floating-point ops per sample, with no stored
  history required for the moments. (Welford, B. P. (1962), "Note on a method for calculating corrected sums of
  squares and products," *Technometrics* 4(3):419–420, doi:10.1080/00401706.1962.10490022; Knuth, *TAOCP* Vol 2
  §4.2.2.) A z-score is then one subtract-and-divide.
- **CUSUM is O(1) state and O(1) per update.** A one-sided CUSUM keeps a single running sum
  `S = max(0, S + (x − target − k))` and compares it to `h` — a couple of floats and a compare per feature per
  update. (Page, E. S. (1954), "Continuous inspection schemes," *Biometrika* 41(1–2):100–115,
  doi:10.1093/biomet/41.1-2.100; NIST/SEMATECH *e-Handbook* §6.3.2.3,
  https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc3231.htm.)
- **Total resident state, concretely:** ~12 features × a handful of floats each (running mean, variance
  accumulator, count, high-side CUSUM, low-side CUSUM) ≈ **a few hundred bytes**. Even carrying a raw ring
  buffer of one feature-window of RR intervals for the HRV features (a few hundred floats per feature) is
  **single-digit kilobytes** — against **512 KB** of SRAM on an ESP32-S3. **No matrix multiply, no learned
  weights, no tensor arena.**

> **Mapping to NeonatalGuard.** The deterministic **[[Safety Floor]]** — the auditable minimum concern level
> that no later tier may cross — is **trivially on-device on an ESP32/ESP32-S3**, with three-plus orders of
> magnitude of headroom, and it runs **always-on and WiFi-independent**. This is the strongest *true* on-device
> claim the pitch has, and it is the clinically load-bearing one: the safety floor is exactly the part you want
> local, deterministic, and immune to a dropped network link. It also fits the project's honest posture — Tier 1
> is an SPC-style abnormality gate (`detection-methodology.md` §1), and SPC math is *made* to run on cheap
> hardware.

---

## 4. Edge-gateway model serving (first-party)

Where the learned tiers actually run. Both mainstream gateways clear the bar for a small quantized model by
a wide margin.

### 4.1 Raspberry Pi 5
- **Broadcom BCM2712, quad-core Arm Cortex-A76 at 2.4 GHz** (512 KB L2/core, 2 MB shared L3); **LPDDR4X-4267
  SDRAM in 1 / 2 / 4 / 8 / 16 GB** options; VideoCore VII GPU. (Raspberry Pi Ltd, product page
  https://www.raspberrypi.com/products/raspberry-pi-5/ and *Raspberry Pi 5 product brief*,
  https://pip.raspberrypi.com/documents/RP-008348-DS-raspberry-pi-5-product-brief.pdf.)
- **8–16 GB of RAM** comfortably holds a 1–3B-param 4-bit model plus the OS; classical ML and small transformers
  run on the CPU. No accelerator required for the Tier-1/Tier-2 workloads.

### 4.2 NVIDIA Jetson Orin Nano (8 GB)
- **67 INT8 TOPS** (the 2024 "Super" spec; the original Orin Nano 8 GB was rated **40 TOPS**); **NVIDIA Ampere
  GPU with 1024 CUDA cores + 32 tensor cores**; **6-core Arm Cortex-A78AE at up to 1.7 GHz**; **8 GB 128-bit
  LPDDR5** at **102 GB/s** (68 GB/s pre-Super); **7 W–25 W** power envelope. (NVIDIA, *Jetson Orin Nano Super
  Developer Kit*, https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/;
  *Jetson Orin Nano Series* datasheet via distributor, https://connecttech.com/ftp/pdf/nvidia_jetson_orin_datasheet.pdf.)
- The tensor cores + 8 GB LPDDR5 make this the platform NVIDIA explicitly positions for **small LLMs, vision
  transformers, and vision-language models** at the edge (NVIDIA product page, ibid.) — i.e., exactly the
  Tier-3 reasoning workload, at the bedside, without a cloud round-trip.

> **Mapping to NeonatalGuard.** The **learned intelligence (Tier 2 world-model, Tier 3 RAG/LLM) belongs on the
> gateway.** A Pi 5 (8–16 GB) or Jetson Orin Nano (8 GB, 67 TOPS) is the natural host: it holds a small quantized
> model in RAM with room to spare and can serve it at the bedside. The choice between Pi and Jetson is a
> cost/latency/power tradeoff (Pi = cheapest, CPU-only; Jetson = tensor-core acceleration for the LLM tier), not
> a feasibility question — both clear the memory bar the ESP32 cannot.

---

## 5. What a billion-parameter model needs (the off-by-1000× check)

The arithmetic that kills claim (a):

- **Weights alone at 4-bit quantization:** ~1B params × 0.5 byte ≈ **0.5 GB**, before KV-cache, activations,
  and runtime overhead — realistically **~0.5–1 GB+ of RAM** to serve. (Standard quantization arithmetic; see
  e.g. llama.cpp / GGUF quantization notes, https://github.com/ggml-org/llama.cpp; the 4-bit ≈ 0.5 byte/param
  figure is definitional.)
- **ESP32-S3 has 512 KB SRAM** (≤32 MB with PSRAM); **ESP32-P4 has 768 KB.** A 0.5 GB model is **~1000×** the
  S3's SRAM and **~16×** its *maximum* 32 MB PSRAM. It does not fit at any quantization. (Espressif datasheets,
  §1.)
- **A Pi 5 (up to 16 GB) or Jetson Orin Nano (8 GB)** holds a 0.5–1 GB model with the OS and headroom to spare.
  (§4.)

> **Mapping to NeonatalGuard.** This is the number to have ready for the probe: **~0.5–1 GB for a 1B-param
> 4-bit model vs 0.5 MB of SRAM on the MCU.** It is the clean, unarguable reason the learned model is a gateway
> job, not an MCU job — and stating it *first, unprompted* is what makes the hybrid claim read as honest
> engineering rather than marketing.

---

## 6. Streaming / bandwidth reality

If the model is on the gateway, the MCU has to ship vitals to it — and that is well within its envelope.

- **Vitals are low-bandwidth.** A typical ICU ECG is sampled at ~250–500 Hz per channel; at 16-bit that is
  **~0.5–1 KB/s of raw samples per channel**, and the derived HRV/vitals **features** (a handful of floats per
  ~20–25 min window — the HeRO window scale, `detection-methodology.md` §3.1) are **orders of magnitude smaller
  still**. Even a couple of raw ECG/respiration channels is a few KB/s.
- **The ESP32 radio is built for far more.** Wi-Fi 802.11 b/g/n (tens of Mbps) and **Bluetooth 5 LE** on the
  ESP32-S3 (Espressif datasheet, §1.2) carry a few-KB/s vitals stream with enormous margin — this is the
  MCU's designed-for use case (sensor telemetry), not a stretch.

> **Mapping to NeonatalGuard.** The **sensor-front-end half of the hybrid is trivially within the ESP32's
> connectivity envelope.** The MCU can stream raw windows *or* just the computed features/Tier-1 verdict to the
> gateway. Streaming only features/verdicts also has a privacy/robustness upside: the always-on Tier-1 floor is
> computed locally, so a network drop degrades to "deterministic local alarms still fire," not "monitoring
> offline."

---

## Recommended claim for the pitch

Adopt the **hybrid** claim. Exact wording:

> **"NeonatalGuard runs its deterministic safety-floor on the bedside microcontroller itself and its learned
> intelligence on a small edge gateway. The ESP32-S3 sensor node computes the Tier-1 deviation math — rolling
> per-infant z-scores and a CUSUM drift detector over the HRV features — entirely on-device: it is a few
> kilobytes of state with no matrix multiply, so it runs always-on and keeps raising deterministic alarms even
> if the network drops. The learned tiers — the Tier-2 world-model and the Tier-3 guideline-grounded LLM
> reasoning — run on a nearby Raspberry Pi 5 or NVIDIA Jetson Orin Nano, which have the gigabytes of RAM a
> real model needs. We do not claim a large model runs on the microcontroller — it can't, and it doesn't need
> to. The safety-critical floor is local and deterministic; the intelligence is on the gateway."**

Why this is the defensible one, on the numbers:
- **On-device half:** Tier-1 state ≈ a few hundred bytes to single-digit KB against **512 KB SRAM** on an
  ESP32-S3 (§1.2, §3). True with ~1000× headroom.
- **Gateway half:** a 1B-param 4-bit model needs **~0.5–1 GB** RAM (§5), sitting inside a **Pi 5 (up to 16 GB)**
  or **Jetson Orin Nano (8 GB, 67 TOPS)** (§4). True with wide margin.
- **Streaming half:** vitals are **~KB/s**, inside the ESP32's Wi-Fi/BLE-5 envelope (§6). True with wide margin.
- **What it refuses to claim:** a big model on the MCU (§5). This refusal is the credibility.

---

## Adversarial Q&A — what a technical investor will probe, and the honest answer

**Q: "You say it runs on the edge — does the AI model run on that little ESP32 chip?"**
A: No, and we're explicit about that. The ESP32-S3 has ~512 KB of SRAM; a billion-parameter model needs
~0.5–1 GB of RAM even at 4-bit — about 1000× more. What runs *on* the MCU is the deterministic Tier-1
safety-floor math (z-scores + CUSUM), which is a few kilobytes of state. The learned model runs on a Pi 5 or
Jetson gateway. (§1, §5.)

**Q: "Then why put anything on the MCU at all — why not stream everything to the gateway?"**
A: Because the safety floor must survive a network outage. Tier 1 is the deterministic minimum concern level
that no later tier can talk down (the [[Safety Floor]]). Running it locally means a dropped WiFi link degrades
to "local deterministic alarms still fire," not "monitoring offline." It's also cheap — O(1) per sample, no
matmul — so there's no reason *not* to. (§3.)

**Q: "Isn't 'CUSUM on a microcontroller' just marketing for 'we couldn't fit a real model'?"**
A: The opposite — it's a deliberate architectural split. CUSUM and per-infant z-scores are the *auditable,
regulator-friendly* part of the system (Page 1954; tuned via ARL); we *want* that part deterministic and local.
The learned world-model and LLM are the research-frontier part, and they belong on hardware that can actually
host them and be updated. Putting the auditable floor local and the learned tiers on the gateway is the honest
division of labor. (§3, §4.)

**Q: "The ESP32-S3 has 'AI vector instructions' — so it can run neural nets, right?"**
A: Small ones. Espressif's own benchmark runs a 250 KB person-detection net in ~54 ms on the S3 with ESP-NN.
That's real, and it shows we understand the platform — but our Tier-2/Tier-3 models are far larger than
250 KB, so we don't run *them* there. We cite the vector instructions as platform literacy, not as where our
model lives. (§2.)

**Q: "Can the MCU even keep up with the ECG sample rate and still stream?"**
A: Easily. ECG is ~250–500 Hz per channel (~0.5–1 KB/s raw at 16-bit); the derived features are far smaller.
The ESP32-S3's Wi-Fi (tens of Mbps) and BLE 5 carry that with orders of magnitude of margin — sensor telemetry
is its designed use case. (§6.)

**Q: "Pi or Jetson — and does it have to be at the bedside, or is this cloud?"**
A: Either gateway works; it's a cost/latency/power tradeoff, not a feasibility one. A Pi 5 (8–16 GB, CPU-only)
is cheapest; a Jetson Orin Nano (8 GB, 67 TOPS, tensor cores) accelerates the LLM tier. Both hold a small
quantized model locally, so the intelligence can live *at the bedside* with no cloud round-trip — which matters
for latency and for keeping patient data local. Cloud is an option, not a requirement. (§4.)

**Q: "What's the one thing you'd never claim?"**
A: That a large language model, or any billion-parameter model, runs on the microcontroller. It can't (§5),
and saying so would be the fastest way to lose a technical audience. The claim is deliberately narrower and
therefore true.

---

## Open / unverified items

- **Exact ESP32-S3 SRAM partitioning.** The product page and datasheet feature list state **512 KB internal
  SRAM**; a datasheet memory-map extract broke this into a **448 KB** main block plus additional RTC/instruction
  SRAM. The **512 KB total** figure is the one to cite; the internal sub-block breakdown was only partially
  machine-readable from the PDF. The order-of-magnitude argument is unaffected. **[UNVERIFIED — exact sub-block map]**
- **Jetson Orin Nano TOPS.** Two figures are both first-party and correct for different SKUs/software: the
  **original Orin Nano 8 GB = 40 TOPS / 68 GB/s**, and the **2024 "Super" update = 67 TOPS / 102 GB/s** on the
  same module via software. Cite the pair, not one number, to avoid a "which is it?" gotcha. Both dwarf the
  ESP32 regardless. **[VERIFIED both; SKU-dependent]**
- **Raspberry Pi 5 product-brief PDF** rendered as binary and was not fully machine-read; the CPU/RAM/GPU
  figures were taken from the **official raspberrypi.com product page** and the search-surfaced brief. The
  16 GB SKU is the current top option. **[VERIFIED via product page; PDF not text-extracted]**
- **The exact size of *our* Tier-2/Tier-3 models is not yet fixed** (the world-model may start as a small
  linear Kalman/VAR per `world-model-surprise-validation.md`, which could be small; the Tier-3 LLM is
  unambiguously gateway-scale). The claim above is robust either way: it only asserts the *deterministic* Tier-1
  runs on-device and the *LLM* runs on the gateway. If the linear world-model turns out to fit in <250 KB, that
  becomes an *additional* on-device option to test — not a change to the recommended claim. **[OPEN — our model
  sizes TBD]**
- **1B-param ≈ 0.5 GB (4-bit) arithmetic** is definitional (0.5 byte/param) rather than a fetched datasheet
  number; real serving overhead (KV-cache, activations, runtime) pushes it higher, which only strengthens the
  "not on the MCU" conclusion. **[VERIFIED by construction]**

---

## References

**ESP32 / ESP32-S3 / ESP32-P4 (Espressif, first-party)**
1. Espressif Systems. *ESP32 Series Datasheet.* https://documentation.espressif.com/esp32_datasheet_en.pdf
   (520 KB SRAM + 16 KB RTC SRAM; LX6; Wi-Fi b/g/n + BT 4.2/BLE). Product page:
   https://www.espressif.com/en/products/socs/esp32
2. Espressif Systems. *ESP32-S3 Series Datasheet.* https://documentation.espressif.com/esp32-s3_datasheet_en.html
   (512 KB internal SRAM + 8 KB RTC; dual LX7 @240 MHz; up to 32 MB PSRAM/flash; PIE vector instructions).
   Product page (vector instructions for NN via ESP-DSP/ESP-NN; Wi-Fi b/g/n; BLE 5):
   https://www.espressif.com/en/products/socs/esp32-s3
3. Espressif Systems. *ESP32-P4 Datasheet.* https://documentation.espressif.com/esp32-p4_datasheet_en.html
   (768 KB SRAM + 8 KB TCM; dual RISC-V @400 MHz with AI extensions). Product page:
   https://www.espressif.com/en/products/socs/esp32-p4

**TinyML on-device footprints (first-party)**
4. Espressif Systems. *esp-tflite-micro* (TFLM port + ESP-NN benchmarks). https://github.com/espressif/esp-tflite-micro
   (person detection ~250 KB; ESP32-S3 54 ms / ESP32 380 ms with ESP-NN).
5. TensorFlow Blog (2020). *Announcing TensorFlow Lite Micro support on the ESP32.*
   https://blog.tensorflow.org/2020/08/announcing-tensorflow-lite-micro-esp32.html (250 KB net; ~700 ms single-core ESP32).
6. TensorFlow / Google. *TensorFlow Lite for Microcontrollers* → *LiteRT for Microcontrollers.*
   https://www.tensorflow.org/lite/microcontrollers ; https://ai.google.dev/edge/litert/microcontrollers/overview
   (KB-scale runtime + tensor-arena model).

**Deterministic Tier-1 math footprint**
7. Welford, B. P. (1962). "Note on a method for calculating corrected sums of squares and products."
   *Technometrics* 4(3):419–420. doi:10.1080/00401706.1962.10490022 (O(1) online mean/variance).
8. Page, E. S. (1954). "Continuous inspection schemes." *Biometrika* 41(1–2):100–115.
   doi:10.1093/biomet/41.1-2.100 (CUSUM — O(1) running sum). NIST/SEMATECH *e-Handbook* §6.3.2.3,
   https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc3231.htm (k, h, ARL tuning).

**Edge-gateway serving (first-party)**
9. Raspberry Pi Ltd. *Raspberry Pi 5.* https://www.raspberrypi.com/products/raspberry-pi-5/ and product brief
   https://pip.raspberrypi.com/documents/RP-008348-DS-raspberry-pi-5-product-brief.pdf
   (BCM2712 quad Cortex-A76 @2.4 GHz; LPDDR4X-4267 1–16 GB; VideoCore VII).
10. NVIDIA. *Jetson Orin Nano Super Developer Kit.*
    https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/
    (67 TOPS; 1024 CUDA + 32 tensor cores; 6-core A78AE; 8 GB LPDDR5 @102 GB/s; 7–25 W). *Jetson Orin Nano
    Series* datasheet (distributor mirror): https://connecttech.com/ftp/pdf/nvidia_jetson_orin_datasheet.pdf
    (original 40 TOPS / 68 GB/s).

**Model-size arithmetic**
11. llama.cpp / GGUF quantization (4-bit ≈ 0.5 byte/param). https://github.com/ggml-org/llama.cpp

**In-repo grounding**
12. `../../CONTEXT.md` (Tier / Safety Floor / Drift definitions); `detection-methodology.md` §1–3 (Tier-1 z-scores,
    CUSUM tuning k≈0.5/h≈4–5, HeRO window scale); `world-model-surprise-validation.md` (Tier-2 world-model, start-linear).

*Items flagged **[UNVERIFIED]** in the Open items section (exact ESP32-S3 internal SRAM sub-block map; exact
text-extraction of the Raspberry Pi 5 brief PDF) could not be fully machine-confirmed on 2026-07-15 and should
not be cited as precise internal figures; the order-of-magnitude conclusions do not depend on them.*
