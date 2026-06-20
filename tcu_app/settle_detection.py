# =============================================================================
# settle_detection.py — Shared Settle-Detection Primitive
# =============================================================================
# Used by both stress_test_logic.py (AMAT0 burst-and-decay test) and
# sequence_test_logic.py (2kW multi-stage sequence test). Both tests need
# the same core question answered: given a per-second temp series (relative
# to some reference point, e.g. t=0 of a run or t=0 of a single stage), when
# has the temp been continuously within tolerance for long enough to call
# it "settled"?
# =============================================================================

_MAX_SAMPLES = 32400 + 1   # 9h hard ceiling — fixed upper bound for any series scan


def find_settle_point(temp_series: list, setpoint: float,
                       tolerance: float, settle_s: int):
    """
    Scan a per-second temp series (index = seconds since the series' own
    t=0 — caller decides what that reference point means) and return
    (first_disturbance_time, settle_time, last_disturbance_time):

    first_disturbance_time: the FIRST t (scanning forward from t=0) where
        temp is out of tolerance. None if the series never goes out of
        tolerance (already settled from t=0).
    settle_time: first t where temp has been continuously in-tolerance for
        settle_s consecutive seconds. This value KEEPS UPDATING as the
        series grows — a later disturbance that breaks an already-achieved
        clean run pushes settle_time forward again once a new clean run of
        settle_s seconds is achieved. None if never (yet) settled for long
        enough.
    last_disturbance_time: the FIRST t (scanning BACKWARD from settle_time)
        where temp is out of tolerance — i.e. the most recent disturbance
        before the settle window began. None until settle_time is found.
        Equal to first_disturbance_time unless there was a later wobble
        after the initial settle.

    Fixed bound: iterates at most _MAX_SAMPLES times.
    """
    n = len(temp_series)
    first_disturbance_time = None
    settle_time = None
    last_disturbance_time = None

    consecutive_in_tol = 0
    limit = min(n, _MAX_SAMPLES)
    for t in range(limit):   # bound: _MAX_SAMPLES iterations
        in_tol = abs(temp_series[t] - setpoint) <= tolerance
        if in_tol:
            consecutive_in_tol += 1
        else:
            consecutive_in_tol = 0
            if first_disturbance_time is None:
                first_disturbance_time = t   # first out-of-tolerance sample, forward scan
        if consecutive_in_tol == settle_s:
            settle_time = t - settle_s + 1   # start of the current clean run; locks here until the
                                              # next reset (consecutive_in_tol back to 0) and re-achievement

    if settle_time is not None:
        for t in range(settle_time, -1, -1):   # bound: settle_time+1 iterations, <= limit
            if abs(temp_series[t] - setpoint) > tolerance:
                last_disturbance_time = t
                break
        if last_disturbance_time is None:
            last_disturbance_time = 0   # never out of tolerance — settled immediately

    return first_disturbance_time, settle_time, last_disturbance_time


def should_stop_for_settle(settle_time, required_settle_time, tail_s: int,
                            elapsed_s: int) -> bool:
    """
    Generic live stopping check, called every second as new samples arrive.

    settle_time: current value from find_settle_point() on the data
        collected so far (None if not yet settled even once).
    required_settle_time: the minimum settle_time this run must reach
        before tail_s can start counting down (e.g. a dataset's historical
        max settle time, or None if there's no such floor yet).
    tail_s: seconds to log after the stopping condition is first satisfied.
    elapsed_s: seconds since this series' own t=0 (i.e. len(series) - 1).

    Stop only once settle_time is satisfied AND has caught up to
    required_settle_time (if any) — a fast-settling run keeps going until
    enough additional clean time accumulates to reach that floor, and any
    later wobble that resets settle_time to None delays stopping further.
    """
    if settle_time is None:
        return False
    floor = settle_time if required_settle_time is None else required_settle_time
    if settle_time < floor:
        return False
    return elapsed_s >= floor + tail_s
