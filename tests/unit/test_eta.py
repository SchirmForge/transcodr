"""Unit tests for ETA estimator."""

from src.jobs.eta import EtaEstimator


def test_no_eta_before_rough_gate():
    estimator = EtaEstimator(
        rough_min_elapsed_seconds=60.0,
        rough_progress_percent=20.0,
        stable_min_elapsed_seconds=120.0,
        stable_min_samples=5,
    )

    estimate = estimator.update(
        frame=100,
        fps=50.0,
        frames_total=10_000,
        progress_percent=1.0,
        now=0.0,
    )
    assert estimate.eta_seconds is None
    assert estimate.quality is None

    estimate = estimator.update(
        frame=500,
        fps=52.0,
        frames_total=10_000,
        progress_percent=5.0,
        now=30.0,
    )
    assert estimate.eta_seconds is None
    assert estimate.quality is None


def test_rough_eta_after_progress_gate():
    estimator = EtaEstimator(
        rough_min_elapsed_seconds=120.0,
        rough_progress_percent=20.0,
        stable_min_elapsed_seconds=300.0,
        stable_min_samples=10,
    )

    estimate = estimator.update(
        frame=2_500,
        fps=100.0,
        frames_total=10_000,
        progress_percent=25.0,
        now=10.0,
    )

    assert estimate.eta_seconds is not None
    assert estimate.quality == "rough"


def test_high_confidence_after_stable_window():
    estimator = EtaEstimator(
        window_seconds=120.0,
        rough_min_elapsed_seconds=30.0,
        rough_progress_percent=5.0,
        stable_min_elapsed_seconds=120.0,
        stable_min_samples=5,
        stable_cv_threshold=0.15,
        high_cv_threshold=0.10,
    )

    frames_total = 100_000
    frame = 0
    estimate = None

    for i in range(13):
        frame += 1_000
        estimate = estimator.update(
            frame=frame,
            fps=100.0,
            frames_total=frames_total,
            progress_percent=(frame / frames_total) * 100.0,
            now=float(i * 10),
        )

    assert estimate is not None
    assert estimate.eta_seconds is not None
    assert estimate.quality == "high"


def test_remains_rough_with_high_variance():
    estimator = EtaEstimator(
        window_seconds=120.0,
        rough_min_elapsed_seconds=30.0,
        rough_progress_percent=5.0,
        stable_min_elapsed_seconds=120.0,
        stable_min_samples=5,
        stable_cv_threshold=0.15,
        high_cv_threshold=0.10,
    )

    frames_total = 100_000
    frame = 0
    estimate = None
    fps_pattern = [60.0, 140.0, 55.0, 150.0, 65.0, 135.0, 58.0, 145.0, 62.0, 138.0, 57.0, 142.0, 61.0]

    for i, fps in enumerate(fps_pattern):
        frame += 1_000
        estimate = estimator.update(
            frame=frame,
            fps=fps,
            frames_total=frames_total,
            progress_percent=(frame / frames_total) * 100.0,
            now=float(i * 10),
        )

    assert estimate is not None
    assert estimate.eta_seconds is not None
    assert estimate.quality == "rough"
