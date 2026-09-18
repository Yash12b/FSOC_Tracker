"""Tests for the trajectory registry / factory."""

from __future__ import annotations

import pytest

from fsoc_tracker.core.exceptions import ConfigurationError
from fsoc_tracker.simulation.trajectory.base import Trajectory
from fsoc_tracker.simulation.trajectory.registry import TrajectoryRegistry


class TestTrajectoryRegistry:
    def test_builtins_registered(self) -> None:
        reg = TrajectoryRegistry()
        available = reg.available
        assert "straight_line" in available
        assert "circular" in available
        assert "figure_8" in available
        assert "random" in available
        assert "spiral" in available
        assert "sinusoidal" in available

    def test_create_straight_line(self) -> None:
        reg = TrajectoryRegistry()
        traj = reg.create("straight_line", {"vx": 10, "vy": 20})
        assert isinstance(traj, Trajectory)
        assert traj.position(0) == (0.0, 0.0, 0.0)

    def test_create_circular(self) -> None:
        reg = TrajectoryRegistry()
        traj = reg.create("circular", {"radius": 100})
        assert isinstance(traj, Trajectory)

    def test_unknown_type_raises(self) -> None:
        reg = TrajectoryRegistry()
        with pytest.raises(ConfigurationError, match="Unknown trajectory type"):
            reg.create("nonexistent")

    def test_from_dict(self) -> None:
        reg = TrajectoryRegistry()
        d = {"type": "straight_line", "vx": 42}
        traj = reg.from_dict(d)
        assert isinstance(traj, Trajectory)
        assert traj.velocity(0) == (42, 0, 0)

    def test_from_dict_missing_type(self) -> None:
        reg = TrajectoryRegistry()
        with pytest.raises(ConfigurationError, match="must contain a 'type' key"):
            reg.from_dict({"vx": 10})

    def test_register_custom(self) -> None:
        reg = TrajectoryRegistry()

        class MyTraj(Trajectory):
            def position(self, t: float) -> tuple[float, float, float]:
                return (t, 0, 0)
            def velocity(self, t: float) -> tuple[float, float, float]:
                return (1, 0, 0)
            def acceleration(self, t: float) -> tuple[float, float, float]:
                return (0, 0, 0)
            def to_dict(self) -> dict:
                return {"type": "my_traj"}
            def from_dict(cls, d: dict) -> Trajectory:
                return MyTraj()

        reg.register("my_traj", MyTraj)
        assert "my_traj" in reg.available
        traj = reg.create("my_traj")
        assert traj.position(5.0) == (5.0, 0.0, 0.0)

    def test_register_non_subclass_raises(self) -> None:
        reg = TrajectoryRegistry()
        with pytest.raises(TypeError):
            reg.register("bad", dict)  # type: ignore
