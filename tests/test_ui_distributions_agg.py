from __future__ import annotations


def test_stable_truncate_edge_cases() -> None:
    from latencylab_ui.distributions_agg import stable_truncate

    assert stable_truncate("abc", max_chars=0) == ""
    assert stable_truncate("abc", max_chars=1) == "…"
    assert stable_truncate("abc", max_chars=2) == "a…"
    assert stable_truncate("abc", max_chars=3) == "abc"


def test_percentile_sorted_edge_cases() -> None:
    import math

    from latencylab_ui.distributions_agg import _percentile_sorted

    assert math.isnan(_percentile_sorted([], 50.0))

    xs = [1.0, 2.0, 3.0]
    assert _percentile_sorted(xs, 0.0) == 1.0
    assert _percentile_sorted(xs, -1.0) == 1.0
    assert _percentile_sorted(xs, 100.0) == 3.0
    assert _percentile_sorted(xs, 101.0) == 3.0

    # lo == hi branch.
    assert _percentile_sorted(xs, 50.0) == 2.0


def test_freedman_diaconis_bins_deterministic_and_counts() -> None:
    from latencylab_ui.distributions_agg import freedman_diaconis_bins

    xs = [1.0, 2.0, 2.0, 3.0, 10.0, 10.0]
    bins1 = freedman_diaconis_bins(xs)
    bins2 = freedman_diaconis_bins(list(xs))

    assert bins1 == bins2
    assert sum(b.count for b in bins1) == len(xs)


def test_freedman_diaconis_bins_degenerate_iqr_single_bin() -> None:
    from latencylab_ui.distributions_agg import freedman_diaconis_bins

    # All values equal -> span=0.
    xs = [5.0, 5.0, 5.0]
    bins = freedman_diaconis_bins(xs)
    assert len(bins) == 1
    assert bins[0].count == 3


def test_freedman_diaconis_bins_len1() -> None:
    from latencylab_ui.distributions_agg import freedman_diaconis_bins

    bins = freedman_diaconis_bins([123.0])
    assert len(bins) == 1
    assert bins[0].lo == 123.0
    assert bins[0].hi == 123.0
    assert bins[0].count == 1


def test_freedman_diaconis_bins_iqr_zero_but_span_positive() -> None:
    from latencylab_ui.distributions_agg import freedman_diaconis_bins

    # When IQR is small but non-zero (depending on interpolation), FD binning may
    # still choose multiple bins. The invariant we require is that the histogram
    # counts exactly partition the observed values.
    xs = [0.0, 0.0, 0.0, 10.0]
    bins = freedman_diaconis_bins(xs)
    assert sum(b.count for b in bins) == len(xs)


def test_freedman_diaconis_bins_iqr_exactly_zero_single_bin() -> None:
    from latencylab_ui.distributions_agg import freedman_diaconis_bins

    # For n=5 the 25th and 75th percentiles are exact indices 1 and 3.
    # With four zeros, q1==q3==0 => IQR=0 while span>0.
    xs = [0.0, 0.0, 0.0, 0.0, 10.0]
    bins = freedman_diaconis_bins(xs)
    assert len(bins) == 1
    assert bins[0].count == len(xs)


def test_critical_path_frequency_top10_and_other_sorted_and_full_display() -> None:
    from latencylab.types import RunResult
    from latencylab_ui.distributions_agg import critical_path_frequency

    # 12 unique paths, descending frequency, plus a failed run which must be ignored.
    runs: list[RunResult] = []
    for i in range(12):
        path = f"P{i:02d}"
        for _ in range(12 - i):
            runs.append(
                RunResult(
                    run_id=len(runs),
                    first_ui_event_time_ms=None,
                    last_ui_event_time_ms=None,
                    makespan_ms=1.0,
                    critical_path_ms=1.0,
                    critical_path_tasks=path,
                    failed=False,
                    failure_reason=None,
                )
            )

    runs.append(
        RunResult(
            run_id=len(runs),
            first_ui_event_time_ms=None,
            last_ui_event_time_ms=None,
            makespan_ms=1.0,
            critical_path_ms=1.0,
            critical_path_tasks="P00",
            failed=True,
            failure_reason="boom",
        )
    )

    bars = critical_path_frequency(runs, top_n=10)
    assert len(bars) == 11
    assert bars[-1].label_display == "Other (long tail)"

    # v1 UI policy: label_display is the full path; the chart performs pixel-based
    # wrapping/eliding. The tooltip remains the full source of truth.
    assert bars[0].label_display == bars[0].label_full

    # Strict sort: highest count first.
    assert bars[0].count > bars[1].count

