"""ETA estimation helpers for running jobs."""

from __future__ import annotations

import statistics
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class EtaEstimate:
    """Current ETA estimate and confidence quality."""

    eta_seconds: Optional[int]
    quality: Optional[str]


class EtaEstimator:
    """
    Estimate remaining time based on smoothed FPS and short-term variance.

    Quality levels:
    - rough: early estimate, still stabilizing
    - stable: variance is low over representative samples
    - high: very low variance over representative samples
    """

    _QUALITY_LEVELS = {
        "rough": 1,
        "stable": 2,
        "high": 3,
    }

    def __init__(
        self,
        window_seconds: float = 120.0,
        ema_alpha: float = 0.2,
        rough_min_elapsed_seconds: float = 90.0,
        rough_progress_percent: float = 20.0,
        stable_min_elapsed_seconds: float = 300.0,
        stable_min_samples: int = 20,
        stable_cv_threshold: float = 0.15,
        high_cv_threshold: float = 0.10,
    ) -> None:
        self.window_seconds = window_seconds
        self.ema_alpha = ema_alpha
        self.rough_min_elapsed_seconds = rough_min_elapsed_seconds
        self.rough_progress_percent = rough_progress_percent
        self.stable_min_elapsed_seconds = stable_min_elapsed_seconds
        self.stable_min_samples = stable_min_samples
        self.stable_cv_threshold = stable_cv_threshold
        self.high_cv_threshold = high_cv_threshold

        self._start_time: Optional[float] = None
        self._ema_fps: Optional[float] = None
        self._samples: deque[tuple[float, float]] = deque()
        self._best_quality: Optional[str] = None

    def update(
        self,
        *,
        frame: int,
        fps: float,
        frames_total: Optional[int],
        progress_percent: float,
        now: Optional[float] = None,
    ) -> EtaEstimate:
        """Update estimator with latest progress sample."""
        sample_time = now if now is not None else time.monotonic()
        if self._start_time is None:
            self._start_time = sample_time

        elapsed = max(sample_time - self._start_time, 0.0)

        if fps > 0:
            self._samples.append((sample_time, fps))
            self._trim_samples(sample_time)
            if self._ema_fps is None:
                self._ema_fps = fps
            else:
                self._ema_fps = (self.ema_alpha * fps) + ((1.0 - self.ema_alpha) * self._ema_fps)

        can_show_rough = (
            elapsed >= self.rough_min_elapsed_seconds
            or progress_percent >= self.rough_progress_percent
        )
        if not can_show_rough:
            return EtaEstimate(eta_seconds=None, quality=None)

        if not frames_total or frames_total <= frame or not self._ema_fps or self._ema_fps <= 0:
            return EtaEstimate(eta_seconds=None, quality=None)

        remaining_frames = max(frames_total - frame, 0)
        eta_seconds = max(int(round(remaining_frames / self._ema_fps)), 0)

        quality = "rough"
        cv = self._coefficient_of_variation()
        if (
            elapsed >= self.stable_min_elapsed_seconds
            and len(self._samples) >= self.stable_min_samples
            and cv is not None
            and cv < self.stable_cv_threshold
        ):
            quality = "high" if cv < self.high_cv_threshold else "stable"

        quality = self._latch_quality(quality)
        return EtaEstimate(eta_seconds=eta_seconds, quality=quality)

    def _trim_samples(self, now: float) -> None:
        """Keep only recent samples inside the configured rolling window."""
        cutoff = now - self.window_seconds
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def _coefficient_of_variation(self) -> Optional[float]:
        """Compute CV of recent FPS samples."""
        if len(self._samples) < 2:
            return None

        values = [sample[1] for sample in self._samples]
        mean = statistics.fmean(values)
        if mean <= 0:
            return None

        deviation = statistics.pstdev(values)
        return deviation / mean

    def _latch_quality(self, quality: str) -> str:
        """Avoid quality downgrades once confidence improves."""
        if self._best_quality is None:
            self._best_quality = quality
            return quality

        current_level = self._QUALITY_LEVELS.get(quality, 0)
        best_level = self._QUALITY_LEVELS.get(self._best_quality, 0)
        if current_level > best_level:
            self._best_quality = quality
            return quality
        return self._best_quality
