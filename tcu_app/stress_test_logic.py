# =============================================================================
# stress_test_logic.py — AMAT0 Stress Test Logic
# =============================================================================
import os
import json
import glob
import numpy as np

from config import (
    STRESS_TEST_TOLERANCE, STRESS_TEST_SETTLE_S, STRESS_TEST_DURATION_S,
    STRESS_TEST_MIN_ENDURANCE_S,
    STRESS_TEST_MAX_DURATION_S, STRESS_TEST_DATA_DIR,
)
from settle_detection import find_settle_point

_MAX_SAMPLES = STRESS_TEST_MAX_DURATION_S + 1
_MAX_DATASET_RUNS = 10000


def detect_transient_times(temp_series, setpoint, tolerance, settle_s):
    return find_settle_point(temp_series, setpoint, tolerance, settle_s)


def compute_log_row_fields(temp_series, setpoint, tolerance, settle_s):
    in_tolerance = abs(temp_series[-1] - setpoint) <= tolerance
    start, end_time, end = detect_transient_times(temp_series, setpoint, tolerance, settle_s)
    return {
        'in_tolerance': in_tolerance,
        'transient_start_time': start,
        'test_end_time': end_time,
        'transient_end_time': end,
    }


def should_stop_fixed_duration(elapsed_s, duration_s=STRESS_TEST_DURATION_S):
    return elapsed_s >= duration_s


# =============================================================================
# Dataset persistence — reference_data/<pass|fail>/<run_id>.json
# No longer bucketed by duration: with relative-position alignment (see
# _pairwise_mse_aligned below), runs of different transient lengths are
# already comparable, and with the realistic size of this dataset (a
# handful to low hundreds of real runs, not thousands), splitting by
# duration just fragmented the reference set into buckets too small to
# produce a usable min/max range. duration_s is still recorded with each
# run for reference/display, just no longer used to decide what a run gets
# compared against.
# =============================================================================

def _verdict_dir(verdict: str) -> str:
    return os.path.join(STRESS_TEST_DATA_DIR, verdict)


def _ensure_verdict_dir(verdict: str):
    os.makedirs(_verdict_dir(verdict), exist_ok=True)


def save_run(run_id, duration_s, verdict, temp_series, flow_series,
             transient_start_time, test_end_time, transient_end_time,
             tcu_serial='', imported=False):
    """File one completed run into reference_data/<verdict>/<run_id>.json.
    verdict must be 'pass' or 'fail' — always an explicit operator choice,
    never inferred automatically by this function. duration_s is recorded
    for reference/display only; it no longer affects what this run gets
    compared against. imported=True marks a run added via CSV import
    rather than a live test, for display purposes only."""
    if verdict not in ('pass', 'fail'):
        raise ValueError(f"verdict must be 'pass' or 'fail', got {verdict!r}")
    _ensure_verdict_dir(verdict)
    path = os.path.join(_verdict_dir(verdict), f'{run_id}.json')
    data = {
        'run_id': run_id,
        'duration_s': int(duration_s) if duration_s is not None else None,
        'tcu_serial': tcu_serial,
        'imported': bool(imported),
        'temp_series': temp_series,
        'flow_series': flow_series,
        'transient_start_time': transient_start_time,
        'test_end_time': test_end_time,
        'transient_end_time': transient_end_time,
    }
    with open(path, 'w') as f:
        json.dump(data, f)
    return path


def load_runs(verdict: str) -> list:
    """Load every run JSON from reference_data/<verdict>/. Returns list of
    dicts, sorted by run_id (chronological). Fixed bound: at most
    _MAX_DATASET_RUNS files scanned."""
    if verdict not in ('pass', 'fail'):
        raise ValueError(f"verdict must be 'pass' or 'fail', got {verdict!r}")
    _ensure_verdict_dir(verdict)
    paths = sorted(glob.glob(os.path.join(_verdict_dir(verdict), '*.json')))[:_MAX_DATASET_RUNS]
    runs = []
    for p in paths:   # bound: _MAX_DATASET_RUNS iterations
        try:
            with open(p) as f:
                runs.append(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            print(f'stress_test_logic: skipping corrupt file {p} — {e}')
    return runs


def delete_run(run_id: str, verdict: str) -> bool:
    """Delete one run from reference_data/<verdict>/. Returns True if a
    file was actually removed, False if it didn't exist."""
    if verdict not in ('pass', 'fail'):
        raise ValueError(f"verdict must be 'pass' or 'fail', got {verdict!r}")
    path = os.path.join(_verdict_dir(verdict), f'{run_id}.json')
    if os.path.exists(path):
        os.remove(path)
        return True
    return False



# =============================================================================
# Range-based matching — simplified from an earlier p-value/distribution-fit
# design after reviewing real data: across several genuine runs from a known
# good TCU, transient shape and duration varied very little run-to-run, so
# fitting a distribution and computing p-values was solving a harder problem
# than the data actually presents. Replaced with a much simpler check: is
# the new value within the observed min/max range of the reference set?
# =============================================================================

def _in_range(value, reference_values):
    """True if value falls within [min(reference_values), max(reference_values)]
    inclusive. Returns None if reference_values is empty (nothing to compare
    against — caller should be gating on this before calling, same as the
    n>=2 bootstrap guard elsewhere)."""
    if not reference_values:
        return None
    return min(reference_values) <= value <= max(reference_values)


def _pairwise_mse_aligned(run_a, run_b, series_key):
    """
    MSE between two runs' temp_series/flow_series, aligned by RELATIVE
    position within each run's own transient — index 0 of the comparison
    is "first second of disturbance" for BOTH runs, even if their absolute
    transient_start_time differs (one run's disturbance can begin a few
    seconds later than another's purely from AMAT0-burst-arrival timing,
    not because anything is actually different about the unit). Each
    series is first sliced starting at its own transient_start_time, then
    both relative-aligned slices are truncated to the shorter of the two
    transient durations (end - start).
    """
    start_a, end_a = run_a['transient_start_time'], run_a['transient_end_time']
    start_b, end_b = run_b['transient_start_time'], run_b['transient_end_time']
    if start_a is None or end_a is None or start_b is None or end_b is None:
        return 0.0
    a_rel = run_a[series_key][start_a:end_a + 1]
    b_rel = run_b[series_key][start_b:end_b + 1]
    n = min(len(a_rel), len(b_rel))
    if n == 0:
        return 0.0
    a = np.asarray(a_rel[:n], dtype=float)
    b = np.asarray(b_rel[:n], dtype=float)
    return float(np.mean((a - b) ** 2))

def reference_pairwise_mse(pass_runs, series_key):
    """Pairwise MSE (aligned) for every N-choose-2 pair among pass_runs —
    this IS the reference range; no distribution fitting. Returns list of
    floats, or [] if fewer than 2 pass_runs."""
    n = len(pass_runs)
    if n < 2:
        return []
    distances = []
    for i in range(n):
        for j in range(i + 1, n):
            distances.append(_pairwise_mse_aligned(pass_runs[i], pass_runs[j], series_key))
    return distances


def shape_match_mse_values(new_run, pass_runs, series_key):
    """This run's aligned MSE against EACH pass-dataset run individually.
    Returns list of N values, or [] if pass_runs is empty."""
    return [_pairwise_mse_aligned(new_run, run, series_key) for run in pass_runs]


# =============================================================================
# Evaluation — the four independent must-all-pass checks
# =============================================================================

def evaluate_run(temp_series, flow_series, transient_start_time, test_end_time,
                  transient_end_time, duration_s, pass_runs=None,
                  min_endurance_s=STRESS_TEST_MIN_ENDURANCE_S):
    """
    Evaluate one run against the dataset's PASS-ONLY run list (pass_runs —
    caller loads this via load_runs('pass') BEFORE this run is filed
    anywhere, so pass_runs never includes the run being evaluated). The
    dataset is no longer split by duration — every pass-dataset run is a
    comparison candidate regardless of how long it ran, since relative-
    position alignment (see _pairwise_mse_aligned) already makes runs of
    different lengths comparable.

    duration_s here is THIS run's own configured STRESS_TEST_DURATION_S
    (how long this specific live test ran for) — only used in the
    Endurance check below, not for selecting which dataset runs to compare
    against.

    Four independent checks, ALL must pass for an overall pass:
      1. time_match     : this run's transient_duration falls within
                          [min, max] of the pass-dataset's transient
                          durations
      2. temp_match     : this run's aligned MSE against EVERY pass-dataset
                          run's temp curve falls within [min, max] of the
                          pass-dataset's own internal pairwise MSE range —
                          checked individually per reference run, not
                          combined
      3. flow_match     : same as temp_match, independently, for flow
      4. endurance_match : (duration_s - test_end_time) > min_endurance_s

    With fewer than 2 pass_runs, no verdict can be computed — returns
    passed=None (bootstrap case). In practice this shouldn't come up once
    the dataset is seeded with real known-good runs (see project docs).
    """
    transient_duration = (
        transient_end_time - transient_start_time
        if transient_start_time is not None and transient_end_time is not None
        else None
    )
    endurance_actual = (
        duration_s - test_end_time if test_end_time is not None else None
    )
    endurance_required = min_endurance_s
    endurance_match = (
        endurance_actual > endurance_required
        if endurance_actual is not None
        else None
    )

    if pass_runs is None or len(pass_runs) < 2 or transient_duration is None:
        return {
            'passed': None,
            'time_match': None, 'temp_match': None, 'flow_match': None,
            'endurance_match': endurance_match,
            'transient_duration': transient_duration,
            'temp_mse_values': [], 'flow_mse_values': [],
            'reference_duration_range': None,
            'reference_temp_mse_range': None,
            'reference_flow_mse_range': None,
            'endurance_actual': endurance_actual,
            'endurance_required': endurance_required,
        }

    durations = [r['transient_end_time'] - r['transient_start_time'] for r in pass_runs]
    time_match = _in_range(transient_duration, durations)

    new_run = {
        'temp_series': temp_series, 'flow_series': flow_series,
        'transient_start_time': transient_start_time,
        'transient_end_time': transient_end_time,
    }
    temp_reference_range = reference_pairwise_mse(pass_runs, 'temp_series')
    flow_reference_range = reference_pairwise_mse(pass_runs, 'flow_series')
    temp_mse_values = shape_match_mse_values(new_run, pass_runs, 'temp_series')
    flow_mse_values = shape_match_mse_values(new_run, pass_runs, 'flow_series')
    temp_match = all(_in_range(v, temp_reference_range) for v in temp_mse_values) if temp_mse_values else None
    flow_match = all(_in_range(v, flow_reference_range) for v in flow_mse_values) if flow_mse_values else None

    passed = bool(time_match and temp_match and flow_match and endurance_match)

    return {
        'passed': passed,
        'time_match': time_match, 'temp_match': temp_match, 'flow_match': flow_match,
        'endurance_match': endurance_match,
        'transient_duration': transient_duration,
        'temp_mse_values': temp_mse_values, 'flow_mse_values': flow_mse_values,
        'reference_duration_range': (min(durations), max(durations)) if durations else None,
        'reference_temp_mse_range': (min(temp_reference_range), max(temp_reference_range)) if temp_reference_range else None,
        'reference_flow_mse_range': (min(flow_reference_range), max(flow_reference_range)) if flow_reference_range else None,
        'endurance_actual': endurance_actual,
        'endurance_required': endurance_required,
    }


# =============================================================================
# Five-point summary — over whichever run list the caller passes in
# =============================================================================

def compute_five_point_summary(runs):
    """Five-number summary (min, Q1, median, Q3, max) of transient_duration
    across the given run list. Returns None if runs is empty."""
    if not runs:
        return None
    durations = np.array(
        [r['transient_end_time'] - r['transient_start_time'] for r in runs], dtype=float)
    return {
        'transient_duration': {
            'min':    float(np.min(durations)),
            'q1':     float(np.percentile(durations, 25)),
            'median': float(np.median(durations)),
            'q3':     float(np.percentile(durations, 75)),
            'max':    float(np.max(durations)),
        }
    }
