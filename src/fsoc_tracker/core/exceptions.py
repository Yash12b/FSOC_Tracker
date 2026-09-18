"""Exception hierarchy for FSOC Tracker.

All project-specific exceptions inherit from FSOCTrackerError,
providing a single catch-all for application errors and enabling
clean error handling at module boundaries.
"""


class FSOCTrackerError(Exception):
    """Base exception for all FSOC Tracker errors."""


class ConfigurationError(FSOCTrackerError):
    """Raised when configuration is invalid or missing."""


class FrameSourceError(FSOCTrackerError):
    """Raised when a frame source fails to open, read, or release."""


class PerceptionError(FSOCTrackerError):
    """Raised when the perception/detection pipeline fails."""


class TrackingError(FSOCTrackerError):
    """Raised when the tracking subsystem encounters an error."""


class ControlError(FSOCTrackerError):
    """Raised when the control subsystem encounters an error."""


class SimulationError(FSOCTrackerError):
    """Raised when the simulation environment encounters an error."""


class BenchmarkError(FSOCTrackerError):
    """Raised when the benchmark engine encounters an error."""
