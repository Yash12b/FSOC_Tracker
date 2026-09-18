"""Tests for the time/dt abstraction module."""

from __future__ import annotations

import time

import pytest

from fsoc_tracker.core.time import (
    FrameTimestamp,
    ProcessingClock,
    SimulationClock,
    compute_dt,
)


class TestComputeDt:
    """Tests for inter-frame dt computation."""

    def test_normal_dt(self) -> None:
        dt = compute_dt(current_ts=1.0 / 30, previous_ts=0.0, nominal_fps=30.0)
        assert abs(dt - 1.0 / 30) < 1e-9

    def test_different_fps_values(self) -> None:
        for fps in [24.0, 25.0, 30.0, 50.0, 60.0, 120.0]:
            dt = compute_dt(
                current_ts=1.0 / fps,
                previous_ts=0.0,
                nominal_fps=fps,
            )
            assert abs(dt - 1.0 / fps) < 1e-9

    def test_identical_timestamps_uses_nominal(self) -> None:
        dt = compute_dt(current_ts=1.0, previous_ts=1.0, nominal_fps=30.0)
        assert abs(dt - 1.0 / 30) < 1e-9

    def test_identical_timestamps_uses_fallback(self) -> None:
        dt = compute_dt(current_ts=1.0, previous_ts=1.0, fallback_dt=0.05)
        assert dt == 0.05

    def test_backwards_timestamp_uses_fallback(self) -> None:
        dt = compute_dt(current_ts=0.5, previous_ts=1.0, nominal_fps=30.0)
        assert abs(dt - 1.0 / 30) < 1e-9

    def test_large_gap_uses_fallback(self) -> None:
        dt = compute_dt(current_ts=100.0, previous_ts=0.0, nominal_fps=30.0)
        assert abs(dt - 1.0 / 30) < 1e-9

    def test_large_gap_no_nominal_uses_fallback(self) -> None:
        dt = compute_dt(current_ts=100.0, previous_ts=0.0, fallback_dt=0.1)
        assert dt == 0.1

    def test_reasonable_variable_fps(self) -> None:
        """Frames at irregular intervals should produce valid dt values."""
        timestamps = [0.0, 0.033, 0.070, 0.100, 0.125]
        dts = []
        for i in range(1, len(timestamps)):
            dt = compute_dt(timestamps[i], timestamps[i - 1])
            dts.append(dt)
        # All dt values should be positive and bounded
        assert all(0 < d <= 10.0 for d in dts)

    def test_dt_never_negative(self) -> None:
        dt = compute_dt(current_ts=0.0, previous_ts=1.0)
        assert dt > 0


class TestFrameTimestamp:
    def test_nominal_dt_from_fps(self) -> None:
        ft = FrameTimestamp(timestamp_s=0.0, nominal_fps=60.0)
        assert abs(ft.nominal_dt - 1.0 / 60) < 1e-9

    def test_nominal_dt_none_when_no_fps(self) -> None:
        ft = FrameTimestamp(timestamp_s=0.0)
        assert ft.nominal_dt is None

    def test_nominal_dt_none_when_zero_fps(self) -> None:
        ft = FrameTimestamp(timestamp_s=0.0, nominal_fps=0.0)
        assert ft.nominal_dt is None


class TestSimulationClock:
    def test_init_zero(self) -> None:
        clock = SimulationClock()
        assert clock.sim_time_s == pytest.approx(0.0, abs=0.01)

    def test_step(self) -> None:
        clock = SimulationClock()
        t = clock.step(0.1)
        assert abs(t - 0.1) < 1e-9
        t = clock.step(0.05)
        assert abs(t - 0.15) < 1e-9

    def test_pause_freezes_time(self) -> None:
        clock = SimulationClock()
        clock.step(1.0)
        clock.pause()
        t_before = clock.sim_time_s
        time.sleep(0.05)
        t_after = clock.sim_time_s
        assert abs(t_after - t_before) < 0.01

    def test_resume(self) -> None:
        clock = SimulationClock()
        clock.step(1.0)
        clock.pause()
        clock.resume()
        t = clock.step(0.5)
        assert abs(t - 1.5) < 1e-4

    def test_time_scale(self) -> None:
        clock = SimulationClock(time_scale=2.0)
        clock.step(1.0)
        assert abs(clock.sim_time_s - 1.0) < 1e-4

    def test_reset(self) -> None:
        clock = SimulationClock()
        clock.step(5.0)
        clock.reset()
        assert clock.sim_time_s == pytest.approx(0.0, abs=0.01)

    def test_negative_time_scale_raises(self) -> None:
        with pytest.raises(ValueError):
            SimulationClock(time_scale=-1.0)


class TestProcessingClock:
    def test_start_stop(self) -> None:
        clock = ProcessingClock()
        clock.start()
        clock.stop()
        assert clock.last_dt >= 0

    def test_average_dt(self) -> None:
        clock = ProcessingClock()
        for _ in range(5):
            clock.start()
            clock.stop()
        assert clock.average_dt > 0
        assert clock.average_fps > 0

    def test_reset(self) -> None:
        clock = ProcessingClock()
        clock.start()
        clock.stop()
        clock.reset()
        assert clock.last_dt == 0.0
        assert clock.average_dt == 0.0
