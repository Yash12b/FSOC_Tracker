"""Trajectory subpackage."""

from fsoc_tracker.simulation.trajectory.base import Trajectory
from fsoc_tracker.simulation.trajectory.circular import CircularTrajectory
from fsoc_tracker.simulation.trajectory.figure_eight import FigureEightTrajectory
from fsoc_tracker.simulation.trajectory.random import RandomTrajectory
from fsoc_tracker.simulation.trajectory.registry import TrajectoryRegistry
from fsoc_tracker.simulation.trajectory.sinusoidal import SinusoidalTrajectory
from fsoc_tracker.simulation.trajectory.spiral import SpiralTrajectory
from fsoc_tracker.simulation.trajectory.straight_line import StraightLineTrajectory

__all__ = [
    "CircularTrajectory",
    "FigureEightTrajectory",
    "RandomTrajectory",
    "SinusoidalTrajectory",
    "SpiralTrajectory",
    "StraightLineTrajectory",
    "Trajectory",
    "TrajectoryRegistry",
]
