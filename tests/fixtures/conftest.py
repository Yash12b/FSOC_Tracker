"""Shared test fixtures for the FSOC Tracker test suite."""

from __future__ import annotations

import numpy as np
import pytest

from fsoc_tracker.core.models import ColorModel, Frame, SourceType


@pytest.fixture
def sample_frame() -> Frame:
    """Return a minimal valid Frame (64x48, 3-channel)."""
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    return Frame(
        image=image,
        width=64,
        height=48,
        channels=3,
        color_model=ColorModel.BGR,
        source_id="test",
        source_type=SourceType.SYNTHETIC,
        frame_index=0,
        timestamp_s=0.0,
    )


@pytest.fixture
def bright_frame() -> Frame:
    """Return a Frame with a bright white rectangle in the center."""
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    image[18:30, 26:38] = (255, 255, 255)  # 12x12 white block
    return Frame(
        image=image,
        width=64,
        height=48,
        channels=3,
        color_model=ColorModel.BGR,
        source_id="test",
        source_type=SourceType.SYNTHETIC,
        frame_index=0,
        timestamp_s=0.0,
    )
