"""HRV feature computation — pure-function tests (issue #13).

Focus on the two HeRO discriminators added in #13:
  - ``sampen`` (sample entropy) — low-only; falls before sepsis; the nonlinear
    irregularity measure that replaces the role ``lf_hf_ratio`` was wrongly given.
  - ``sample_asymmetry`` (R2/R1 of the RR histogram) — high-only; rises before
    sepsis; the whole-histogram deceleration-burden statistic that ``rr_ms_max`` /
    ``rr_ms_75%`` only crudely proxied.

Research gate: docs/research/cardiorespiratory-feature-validation.md (issue #10).
SampEn defaults m=3, r=0.2×SD (Richman & Moorman 2000, PMID 10843903; Lake 2002,
PMID 12185014). Sample-asymmetry sign convention: Kovatchev R2/R1 on RR, rises
toward decelerations (Kovatchev 2003, PMID 12930915; Moorman 2011, PMID 22026974).
"""
import math

import numpy as np

from src.features.constants import HRV_FEATURE_COLS
from src.features.hrv import compute_hrv_features


def _rng(seed: int) -> np.random.Generator:
    # Deterministic RNG — tests must not depend on global random state.
    return np.random.default_rng(seed)


# --- SSOT invariant ------------------------------------------------------------


def test_feature_keys_match_ssot_exactly():
    feats = compute_hrv_features(np.full(50, 400.0) + _rng(0).normal(0, 5, 50))
    assert set(feats.keys()) == set(HRV_FEATURE_COLS)


def test_sampen_and_sample_asymmetry_are_present():
    feats = compute_hrv_features(np.full(50, 400.0) + _rng(1).normal(0, 5, 50))
    assert "sampen" in feats
    assert "sample_asymmetry" in feats


# --- SampEn: irregularity, low-only signal ------------------------------------


def test_sampen_lower_for_regular_than_irregular():
    # Entropy measures irregularity: a near-periodic RR series is more predictable
    # (lower SampEn) than a noisy one. SampEn *falls* toward regularity — the
    # direction that, in the RR domain, precedes sepsis.
    t = np.arange(600)
    regular = 400.0 + 8.0 * np.sin(2 * np.pi * t / 20.0)
    irregular = 400.0 + _rng(2).normal(0, 8.0, 600)

    s_regular = compute_hrv_features(regular[:50], rr_entropy=regular)["sampen"]
    s_irregular = compute_hrv_features(irregular[:50], rr_entropy=irregular)["sampen"]

    assert math.isfinite(s_regular) and math.isfinite(s_irregular)
    assert s_regular < s_irregular


def test_sampen_nan_when_entropy_window_too_short():
    # Cold-start contract: below a computable length SampEn is NaN, never a
    # fabricated value. NaN must not trigger the floor (see deviation tests).
    feats = compute_hrv_features(np.full(50, 400.0), rr_entropy=np.array([]))
    assert math.isnan(feats["sampen"])


def test_sampen_rejects_a_single_artifact_spike():
    # "Entropy inevitably falls in any record with spikes" — a missed/ectopic beat
    # masquerades as structure. Artifact rejection is mandatory (Lake 2002), so a
    # lone spike must not collapse SampEn toward zero.
    base = 400.0 + _rng(3).normal(0, 8.0, 600)
    spiked = base.copy()
    spiked[300] = 1200.0  # a single implausible interval (dropped-beat artifact)

    s_clean = compute_hrv_features(base[:50], rr_entropy=base)["sampen"]
    s_spiked = compute_hrv_features(spiked[:50], rr_entropy=spiked)["sampen"]

    # Rejection keeps the spiked estimate close to the clean one rather than
    # letting the spike crater the entropy.
    assert math.isfinite(s_spiked)
    assert abs(s_spiked - s_clean) < 0.5 * s_clean


# --- Sample asymmetry: sign convention (the [UNVERIFIED] flag #13 must pin) -----


def test_sample_asymmetry_rises_toward_decelerations():
    # Sign convention, PINNED: computed on RR with the Kovatchev R2/R1 convention,
    # a deceleration-heavy histogram (long-RR tail) yields a HIGH value, and an
    # acceleration-heavy one a LOW value. This is what makes it a correct high-only
    # trigger (Kovatchev 2003, PMID 12930915; Moorman 2011, PMID 22026974).
    base = 400.0 + _rng(6).normal(0, 15.0, 200)  # spread so the median split is populated

    decel = base.copy()
    decel[:20] = 700.0  # a tail of long RR intervals (decelerations)

    accel = base.copy()
    accel[:20] = 250.0  # a tail of short RR intervals (accelerations)

    a_decel = compute_hrv_features(decel)["sample_asymmetry"]
    a_accel = compute_hrv_features(accel)["sample_asymmetry"]

    assert a_decel > a_accel
    # Deceleration burden pushes R2/R1 above the symmetric ~1; acceleration below it.
    assert a_decel > 1.0
    assert a_accel < 1.0


def test_sample_asymmetry_symmetric_series_is_near_one():
    # A symmetric distribution has balanced R1/R2 → ratio ≈ 1 (no asymmetry).
    sym = 400.0 + _rng(4).normal(0, 20.0, 400)
    a = compute_hrv_features(sym)["sample_asymmetry"]
    assert 0.5 < a < 2.0


def test_features_are_deterministic():
    x = 400.0 + _rng(5).normal(0, 8.0, 300)
    f1 = compute_hrv_features(x[:50], rr_entropy=x)
    f2 = compute_hrv_features(x[:50], rr_entropy=x)
    assert f1 == f2


# --- SampEn vectorisation equivalence (issue #45) ------------------------------
# The production _sampen replaces an O(n^2) Python row-loop with a chunked,
# fully-vectorised pair count. It must stay bit-identical to the original scan.
# _sampen_reference below is a verbatim copy of that original algorithm; the tests
# assert the production value equals it across sizes, seeds, and edge cases.


def _preprocess_reference(rr_ms):
    # Verbatim copy of the ORIGINAL _preprocess_for_entropy (pre-#45), so the
    # equivalence tests remain independent of the production implementation and
    # catch any drift when it is vectorised.
    _SAMPEN_ARTIFACT_FRAC = 0.20
    _SAMPEN_DETREND_WIN = 15
    x = np.asarray(rr_ms, dtype=np.float64)
    x = x[np.isfinite(x)]
    if len(x) < 5:
        return x
    win = min(_SAMPEN_DETREND_WIN, len(x))
    local_med = np.array(
        [np.median(x[max(0, i - win) : i + 1]) for i in range(len(x))]
    )
    keep = np.abs(x - local_med) <= _SAMPEN_ARTIFACT_FRAC * local_med
    x = x[keep]
    if len(x) < 5:
        return x
    kernel = np.ones(win) / win
    baseline = np.convolve(np.pad(x, win // 2, mode="edge"), kernel, mode="valid")
    baseline = baseline[: len(x)]
    return x - baseline


def test_preprocess_for_entropy_matches_reference():
    from src.features.hrv import _preprocess_for_entropy

    for seed in range(40):
        r = _rng(seed)
        n = int(r.integers(3, 900))
        rr = 400.0 + 40.0 * r.standard_normal(n)
        if r.random() < 0.5:  # inject artifact spikes to exercise the rejection mask
            idx = r.integers(0, n, size=max(1, n // 10))
            rr[idx] += r.uniform(200.0, 600.0, size=len(idx))
        got = _preprocess_for_entropy(rr)
        exp = _preprocess_reference(rr)
        assert got.shape == exp.shape, f"shape {got.shape} != {exp.shape} (seed {seed})"
        assert np.allclose(got, exp, rtol=0, atol=1e-9), f"values differ (seed {seed})"


def _sampen_reference(rr_ms, m=3, r_factor=0.2):
    x = _preprocess_reference(rr_ms)
    n = len(x)
    if n < m + 2:
        return float("nan")
    r = r_factor * np.std(x, ddof=1)
    if not np.isfinite(r) or r <= 0:
        return float("nan")

    def count(mm):
        templates = np.array([x[i : i + mm] for i in range(n - mm + 1)])
        total = 0
        for i in range(len(templates) - 1):
            dist = np.max(np.abs(templates[i + 1 :] - templates[i]), axis=1)
            total += int(np.count_nonzero(dist <= r))
        return total

    b = count(m)
    a = count(m + 1)
    if b == 0 or a == 0:
        return float("nan")
    return float(-np.log(a / b))


def _assert_sampen_equal(rr):
    from src.features.hrv import _sampen

    got, exp = _sampen(rr), _sampen_reference(rr)
    if math.isnan(exp):
        assert math.isnan(got), f"expected NaN, got {got}"
    else:
        assert math.isclose(got, exp, rel_tol=1e-12, abs_tol=1e-12), f"{got} != {exp}"


def test_sampen_matches_reference_across_sizes_and_seeds():
    # Varied lengths (incl. > block size to exercise chunking) and irregularity,
    # with occasional bradycardia-like jumps so long-RR structure is present.
    for seed in range(40):
        r = _rng(seed)
        n = int(r.integers(20, 900))
        rr = 400.0 + 40.0 * r.standard_normal(n)
        if r.random() < 0.5:
            idx = r.integers(0, n, size=max(1, n // 20))
            rr[idx] += r.uniform(150.0, 400.0, size=len(idx))
        _assert_sampen_equal(rr)


def test_sampen_matches_reference_large_window_over_block_boundary():
    # ~1200 beats forces multiple row-blocks in the vectorised count.
    rr = 420.0 + 30.0 * _rng(99).standard_normal(1200)
    _assert_sampen_equal(rr)


def test_sampen_matches_reference_on_edge_cases():
    _assert_sampen_equal(np.array([]))                      # empty -> NaN
    _assert_sampen_equal(np.array([400.0, 401.0, 402.0]))   # too short -> NaN
    _assert_sampen_equal(np.full(60, 400.0))                # constant -> r<=0 -> NaN
    _assert_sampen_equal(400.0 + _rng(3).standard_normal(50))  # small typical window
