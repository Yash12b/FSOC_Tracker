"""Pipeline package — authoritative system integration layer.

Provides TrackingPipeline (the single runtime pipeline), mode-specific
source adapters, SessionController, and run-manager.
"""

from fsoc_tracker.pipeline.pipeline import TrackingPipeline
from fsoc_tracker.pipeline.session import SessionController, RunState
from fsoc_tracker.pipeline.sources import (
    FrameSource,
    SimulationSource,
    VirtualSimulationSource,
    VideoSource,
    LiveSource,
    DatasetSource,
)

__all__ = [
    "TrackingPipeline",
    "SessionController",
    "RunState",
    "FrameSource",
    "SimulationSource",
    "VirtualSimulationSource",
    "VideoSource",
    "LiveSource",
    "DatasetSource",
]
