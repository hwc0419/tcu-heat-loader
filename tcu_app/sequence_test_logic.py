# =============================================================================
# sequence_test_logic.py — 2kW Heat Load Sequence Test Logic
# =============================================================================
# Test procedure:
#   1. User defines a sequence of watt loads, e.g. (1000, 1234, 2000, 1000)
#   2. TCU starts, heater held at K=0. Wait for settle (temp continuously
#      within tolerance for seq_test_settle_duration_s).
#   3. For each load in the sequence: switch heater instantly to that load
#      (via watts_to_k, no ramping) -> wait for settle again -> record
#      (commanded_watts, settle_duration_seconds) as one dataset record.
#   4. After the last user-defined stage, an automatic trailing 0W stage is
#      appended (also waits for settle, also contributes a dataset record).
#   5. Each stage's settle_duration is evaluated against the dataset's
#      existing per-bin (10W wide) statistics for that stage's watts BEFORE
#      this run's stages are added, then the run's stages are appended and
#      bin statistics are recomputed.
#
# Unlike the AMAT0 test (which compares whole time-series per-timestep),
# this test's dataset unit is a single (watts, settle_duration) pair per
# stage — sequences can vary in length and content, so there's no shared
# wall-clock axis to align on. Settle time is binned by watts (bin width
# SEQ_TEST_BIN_WIDTH_W) and compared via a per-bin z-score instead.
# =============================================================================

import os
import json
import glob
import numpy as np

from config import (
    SEQ_TEST_Z_THRESHOLD, SEQ_TEST_BIN_WIDTH_W, SEQ_TEST_DATA_DIR,
    SEQ_TEST_MAX_DURATION_S, SEQ_TEST_MAX_STAGES,
)
from settle_detection import find_settle_point, should_stop_for_settle

__all__ = [
    'find_settle_point', 'should_stop_for_settle',  # re-exported for GUI convenience
    'watts_to_bin', 'save_stage', 'load_all_stages',
    'compute_bin_stats', 'save_bin_stats', 'load_bin_stats', 'evaluate_stage',
    'generate_random_sequence',
]


def watts_to_bin(watts: float) -> int:
    """Bin watts into a fixed-width bucket, e.g. 1247W -> bin 1240 (1240-1250W)."""
    return int(watts // SEQ_TEST_BIN_WIDTH_W) * SEQ_TEST_BIN_WIDTH_W


# =============================================================================
# Stage persistence — one JSON file per stage under sequence_test_data/
# =============================================================================

def _ensure_data_dir():
    os.makedirs(SEQ_TEST_DATA_DIR, exist_ok=True)


def save_stage(stage_id: str, commanded_watts: float, settle_duration_s: int,
               passed) -> str:
    """
    Persist one completed stage to sequence_test_data/<stage_id>.json.
    stage_id should be unique across the whole dataset, e.g.
    '<run_timestamp>_stage<N>'. passed: bool or None (no bin stats yet).
    """
    _ensure_data_dir()
    path = os.path.join(SEQ_TEST_DATA_DIR, f'{stage_id}.json')
    data = {
        'stage_id': stage_id,
        'commanded_watts': commanded_watts,
        'settle_duration_s': settle_duration_s,
        'passed': passed,
    }
    with open(path, 'w') as f:
        json.dump(data, f)
    return path


def load_all_stages() -> list:
    """
    Load every stage JSON from sequence_test_data/, excluding the bin
    stats file. Fixed bound: at most 50000 files scanned (sanity ceiling —
    100 stages/run x 500 runs, comfortably above realistic usage).
    """
    _ensure_data_dir()
    paths = sorted(glob.glob(os.path.join(SEQ_TEST_DATA_DIR, '*.json')))[:50000]
    stages = []
    for p in paths:   # bound: 50000 iterations
        if os.path.basename(p) == '_bin_stats.json':
            continue
        try:
            with open(p) as f:
                stages.append(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            print(f'sequence_test_logic: skipping corrupt file {p} — {e}')
    return stages


# =============================================================================
# Bin statistics
# =============================================================================

def compute_bin_stats(stages: list) -> dict:
    """
    Group stages by watts bin (SEQ_TEST_BIN_WIDTH_W wide) and compute
    mean/std settle_duration_s per bin.

    Returns dict: {bin_start_watts (int): {'mean': float, 'std': float, 'n': int}}
    Empty dict if stages is empty.
    """
    bins = {}
    for s in stages:   # bound: len(stages), already bounded by load_all_stages
        b = watts_to_bin(s['commanded_watts'])
        bins.setdefault(b, []).append(s['settle_duration_s'])

    result = {}
    for b, durations in bins.items():
        arr = np.array(durations, dtype=float)
        result[b] = {
            'mean': float(arr.mean()),
            'std':  float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
            'n':    len(arr),
        }
    return result


def save_bin_stats(bin_stats: dict) -> str:
    """Persist bin stats to sequence_test_data/_bin_stats.json."""
    _ensure_data_dir()
    path = os.path.join(SEQ_TEST_DATA_DIR, '_bin_stats.json')
    # JSON keys must be strings — bin_start_watts (int) converted on save,
    # converted back to int on load.
    serialisable = {str(k): v for k, v in bin_stats.items()}
    with open(path, 'w') as f:
        json.dump(serialisable, f)
    return path


def load_bin_stats() -> dict:
    """Load previously saved bin stats, or {} if not yet computed."""
    path = os.path.join(SEQ_TEST_DATA_DIR, '_bin_stats.json')
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = json.load(f)
    return {int(k): v for k, v in data.items()}


# =============================================================================
# Evaluation — z-score test against bin stats
# =============================================================================

def evaluate_stage(commanded_watts: float, settle_duration_s: int,
                    bin_stats: dict, z_threshold: float = SEQ_TEST_Z_THRESHOLD) -> dict:
    """
    Evaluate one completed stage against the dataset's bin stats as they
    stood BEFORE this stage was added.

    Returns dict: passed (bool or None), z (float or None), bin (int),
    n_in_bin (int). passed=None if this bin has fewer than 2 prior samples
    (std is undefined/meaningless with 0 or 1 sample, so no z-score test
    is attempted — a single prior point would make std=0 and any new
    value look like an extreme outlier purely from division by a near-zero
    epsilon, not because it's actually anomalous).
    """
    b = watts_to_bin(commanded_watts)
    stats = bin_stats.get(b)
    if stats is None or stats['n'] < 2:
        return {'passed': None, 'z': None, 'bin': b, 'n_in_bin': stats['n'] if stats else 0}

    std_safe = stats['std'] if stats['std'] > 0 else 1e-9
    z = (settle_duration_s - stats['mean']) / std_safe
    passed = abs(z) <= z_threshold
    return {'passed': passed, 'z': float(z), 'bin': b, 'n_in_bin': stats['n']}


# =============================================================================
# Random sequence generator
# =============================================================================

def generate_random_sequence(w_min: int, w_max: int,
                              len_min: int, len_max: int, rng=None) -> list:
    """
    Generate a random load sequence: length uniformly random in
    [len_min, len_max], each value uniformly random in [w_min, w_max].
    rng: optional random.Random instance (for testability); uses the
    module-level random if not provided.
    Fixed bound: length capped at SEQ_TEST_MAX_STAGES regardless of len_max.
    """
    import random
    r = rng if rng is not None else random
    length = r.randint(len_min, min(len_max, SEQ_TEST_MAX_STAGES))
    return [r.randint(w_min, w_max) for _ in range(length)]   # bound: SEQ_TEST_MAX_STAGES
