# =============================================================================
# stress_test_logic.py — AMAT0 Stress Test Logic
# =============================================================================
# Contains:
#   - Transient start/end detection    from per-second temp series
#   - Reference dataset persistence    JSON files under reference_data/
#   - Per-timestep + scalar statistics (mean, std) over a growing dataset
#   - z-score evaluation               flags timesteps where |z| > threshold
#
# Test procedure (see wiki: AMAT0 Stress Test):
#   1. AMAT0 heated to ~80C on a separate 2kW heater, then connected to TCU
#   2. Operator presses Start — TCU start command sent, logging begins at t=0
#   3. Every second: record temp, flow_rate
#   4. transient_start_time := last t (scanning forward from t=0) where temp
#      was still out of tolerance (22 +/- STRESS_TEST_TOLERANCE)
#   5. test_end_time := first t where temp has been continuously in-tolerance
#      for STRESS_TEST_SETTLE_S seconds
#   6. transient_end_time := last t (scanning backward from test_end_time)
#      where temp was still out of tolerance
#   7. Logging continues until test_end_time has caught up to the dataset's
#      max(test_end_time) (or just its own, if dataset is empty), then
#      STRESS_TEST_TAIL_S more seconds are logged. This guarantees every
#      run has enough data to cover the comparison window in step 9.
#   8. Every per-second sample is logged with an in_tolerance flag, plus the
#      transient_start_time/test_end_time/transient_end_time markers as of
#      that second, so the full transient history is visible in the CSV —
#      not just the final scalar values.
#   9. Run is evaluated against the dataset's stats as they stood BEFORE this
#      run (per-timestep temp/flow z-scores over t=0..min(test_end_time)
#      across the dataset, plus scalar z-scores for the two transient
#      times), then appended to the dataset and stats are recomputed.
# =============================================================================

import os
import json
import glob
import numpy as np

from config import (
    STRESS_TEST_TOLERANCE, STRESS_TEST_SETTLE_S, STRESS_TEST_TAIL_S,
    STRESS_TEST_Z_THRESHOLD, STRESS_TEST_MAX_DURATION_S, STRESS_TEST_DATA_DIR,
)
from settle_detection import find_settle_point, should_stop_for_settle

_MAX_SAMPLES = STRESS_TEST_MAX_DURATION_S + 1   # fixed upper bound for any loop over a run's series


# =============================================================================
# Transient detection — thin wrapper over the shared settle_detection module,
# renaming the generic terms to this test's vocabulary (transient_start_time
# etc. instead of first_disturbance_time etc.)
# =============================================================================

def detect_transient_times(temp_series: list, setpoint: float,
                            tolerance: float, settle_s: int):
    """
    See settle_detection.find_settle_point — this is a thin renaming wrapper:
        transient_start_time = first_disturbance_time
        test_end_time         = settle_time
        transient_end_time    = last_disturbance_time
    """
    return find_settle_point(temp_series, setpoint, tolerance, settle_s)


def should_stop_logging(test_end_time, dataset_max_test_end_time, tail_s: int,
                         elapsed_s: int) -> bool:
    """See settle_detection.should_stop_for_settle — thin renaming wrapper."""
    return should_stop_for_settle(test_end_time, dataset_max_test_end_time, tail_s, elapsed_s)


def compute_log_row_fields(temp_series: list, setpoint: float, tolerance: float,
                            settle_s: int) -> dict:
    """
    Convenience wrapper for the GUI's per-second CSV logging. Given the
    series collected so far (inclusive of the just-arrived sample), returns
    the fields needed for that second's CSV row:
        in_tolerance         : bool — is the LATEST sample in tolerance
        transient_start_time : int or None — current value (see detect_transient_times)
        test_end_time         : int or None — current value
        transient_end_time    : int or None — current value
    Calls detect_transient_times on the full series-so-far each time; this
    is O(len(series)) per call but len(series) <= STRESS_TEST_MAX_DURATION_S,
    so it stays well within the 1Hz budget.
    """
    in_tolerance = abs(temp_series[-1] - setpoint) <= tolerance
    start, end_time, end = detect_transient_times(temp_series, setpoint, tolerance, settle_s)
    return {
        'in_tolerance': in_tolerance,
        'transient_start_time': start,
        'test_end_time': end_time,
        'transient_end_time': end,
    }


# =============================================================================
# Dataset persistence — one JSON file per run under reference_data/
# =============================================================================

def _ensure_data_dir():
    os.makedirs(STRESS_TEST_DATA_DIR, exist_ok=True)


def save_run(run_id: str, temp_series: list, flow_series: list,
             transient_start_time: int, test_end_time: int,
             transient_end_time: int, passed, tcu_serial: str = '') -> str:
    """
    Persist one completed run to reference_data/<run_id>.json.
    passed: bool or None (None if there was no dataset yet to compare against).
    tcu_serial: operator-entered serial number of the unit under test.
    Returns the file path written.
    """
    _ensure_data_dir()
    path = os.path.join(STRESS_TEST_DATA_DIR, f'{run_id}.json')
    data = {
        'run_id': run_id,
        'tcu_serial': tcu_serial,
        'temp_series': temp_series,
        'flow_series': flow_series,
        'transient_start_time': transient_start_time,
        'test_end_time': test_end_time,
        'transient_end_time': transient_end_time,
        'passed': passed,
    }
    with open(path, 'w') as f:
        json.dump(data, f)
    return path


def load_all_runs() -> list:
    """
    Load every run JSON from reference_data/, excluding the dataset stats
    file (_dataset_stats.json) which is not itself a run. Returns list of
    dicts, sorted by run_id (chronological if run_id is a timestamp string).
    Fixed bound: at most 10000 files scanned (sanity ceiling, not expected
    to ever be reached in practice).
    """
    _ensure_data_dir()
    paths = sorted(glob.glob(os.path.join(STRESS_TEST_DATA_DIR, '*.json')))[:10000]
    runs = []
    for p in paths:   # bound: 10000 iterations
        if os.path.basename(p) == '_dataset_stats.json':
            continue
        try:
            with open(p) as f:
                runs.append(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            print(f'stress_test_logic: skipping corrupt file {p} — {e}')
    return runs


# =============================================================================
# Dataset statistics
# =============================================================================

def compute_dataset_stats(runs: list) -> dict:
    """
    Compute statistics over the full dataset (list of run dicts as returned
    by load_all_runs / produced by save_run's schema).

    Returns dict with:
        n_runs              : int
        min_test_end_time   : int — truncation point for per-timestep comparison
        max_test_end_time   : int — floor for how long a new run must log
                               (see should_stop_logging)
        temp_mean, temp_std : np.ndarray, length min_test_end_time+1
        flow_mean, flow_std : np.ndarray, length min_test_end_time+1
        start_mean, start_std : float — transient_start_time distribution
        end_mean, end_std      : float — transient_end_time distribution

    Returns None if runs is empty (nothing to compute yet).
    """
    if not runs:
        return None

    min_test_end_time = min(r['test_end_time'] for r in runs)
    max_test_end_time = max(r['test_end_time'] for r in runs)
    window = min_test_end_time + 1   # inclusive of t=min_test_end_time

    temp_matrix = np.array([r['temp_series'][:window] for r in runs], dtype=float)
    flow_matrix = np.array([r['flow_series'][:window] for r in runs], dtype=float)

    starts = np.array([r['transient_start_time'] for r in runs], dtype=float)
    ends   = np.array([r['transient_end_time']   for r in runs], dtype=float)

    return {
        'n_runs':            len(runs),
        'min_test_end_time': min_test_end_time,
        'max_test_end_time': max_test_end_time,
        'temp_mean':  temp_matrix.mean(axis=0),
        'temp_std':   temp_matrix.std(axis=0, ddof=1) if len(runs) > 1 else np.zeros(window),
        'flow_mean':  flow_matrix.mean(axis=0),
        'flow_std':   flow_matrix.std(axis=0, ddof=1) if len(runs) > 1 else np.zeros(window),
        'start_mean': float(starts.mean()),
        'start_std':  float(starts.std(ddof=1)) if len(runs) > 1 else 0.0,
        'end_mean':   float(ends.mean()),
        'end_std':    float(ends.std(ddof=1))   if len(runs) > 1 else 0.0,
    }


def compute_five_point_summary(runs: list) -> dict:
    """
    Five-number summary (min, Q1, median, Q3, max) of transient_start_time
    and transient_end_time across every run in the dataset. Computed fresh
    from runs rather than cached, since it's cheap and load_all_runs()
    already does the only expensive part (reading the JSON files).

    Returns None if runs is empty.
    """
    if not runs:
        return None
    starts = np.array([r['transient_start_time'] for r in runs], dtype=float)
    ends   = np.array([r['transient_end_time']   for r in runs], dtype=float)

    def _five(arr):
        return {
            'min':    float(np.min(arr)),
            'q1':     float(np.percentile(arr, 25)),
            'median': float(np.median(arr)),
            'q3':     float(np.percentile(arr, 75)),
            'max':    float(np.max(arr)),
        }

    return {'transient_start_time': _five(starts), 'transient_end_time': _five(ends)}


def save_dataset_stats(stats: dict) -> str:
    """Persist computed stats to reference_data/_dataset_stats.json."""
    _ensure_data_dir()
    path = os.path.join(STRESS_TEST_DATA_DIR, '_dataset_stats.json')
    serialisable = dict(stats)
    for key in ('temp_mean', 'temp_std', 'flow_mean', 'flow_std'):
        serialisable[key] = serialisable[key].tolist()
    with open(path, 'w') as f:
        json.dump(serialisable, f)
    return path


def load_dataset_stats():
    """Load previously saved stats, or None if not yet computed."""
    path = os.path.join(STRESS_TEST_DATA_DIR, '_dataset_stats.json')
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    for key in ('temp_mean', 'temp_std', 'flow_mean', 'flow_std'):
        data[key] = np.array(data[key], dtype=float)
    return data


# =============================================================================
# Evaluation — z-score test against dataset stats
# =============================================================================

def evaluate_run(temp_series: list, flow_series: list,
                  transient_start_time: int, transient_end_time: int,
                  stats: dict, z_threshold: float = STRESS_TEST_Z_THRESHOLD) -> dict:
    """
    Evaluate one run's data against dataset stats computed BEFORE this run
    was added. Returns dict:
        passed              : bool or None
        failing_timesteps   : list of int — seconds (relative to t=0) where
                               |z| > z_threshold for temp or flow
        temp_z, flow_z      : np.ndarray, length = stats['min_test_end_time']+1
        start_z, end_z      : float — scalar z-scores for the two transient times
    If stats is None (empty dataset) or stats['n_runs'] < 2 (std undefined
    or meaningless from a single prior run — a 1-run dataset has std=0
    everywhere, which would make any new value look like an extreme
    outlier purely from dividing by a near-zero epsilon, not because it's
    actually anomalous), returns passed=None and all other fields None/empty.
    """
    if stats is None or stats['n_runs'] < 2:
        return {
            'passed': None, 'failing_timesteps': [],
            'temp_z': None, 'flow_z': None,
            'start_z': None, 'end_z': None,
        }

    window = stats['min_test_end_time'] + 1
    temp_arr = np.array(temp_series[:window], dtype=float)
    flow_arr = np.array(flow_series[:window], dtype=float)

    # Avoid divide-by-zero on a std of 0 (e.g. a timestep where every prior
    # run happened to log an identical value, despite n_runs >= 2 overall)
    temp_std_safe = np.where(stats['temp_std'] == 0, 1e-9, stats['temp_std'])
    flow_std_safe = np.where(stats['flow_std'] == 0, 1e-9, stats['flow_std'])

    temp_z = (temp_arr - stats['temp_mean']) / temp_std_safe
    flow_z = (flow_arr - stats['flow_mean']) / flow_std_safe

    start_std_safe = stats['start_std'] if stats['start_std'] > 0 else 1e-9
    end_std_safe   = stats['end_std']   if stats['end_std']   > 0 else 1e-9
    start_z = (transient_start_time - stats['start_mean']) / start_std_safe
    end_z   = (transient_end_time   - stats['end_mean'])   / end_std_safe

    failing_timesteps = sorted(set(
        np.where(np.abs(temp_z) > z_threshold)[0].tolist() +
        np.where(np.abs(flow_z) > z_threshold)[0].tolist()
    ))

    passed = (
        len(failing_timesteps) == 0
        and abs(start_z) <= z_threshold
        and abs(end_z) <= z_threshold
    )

    return {
        'passed': passed,
        'failing_timesteps': failing_timesteps,
        'temp_z': temp_z,
        'flow_z': flow_z,
        'start_z': float(start_z),
        'end_z': float(end_z),
    }
