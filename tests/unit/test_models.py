"""Tests for the Frame model and related domain models."""

from __future__ import annotations

import numpy as np
import pytest

from fsoc_tracker.core.models import (
    ColorModel,
    Frame,
    SourceType,
    TargetState,
)


class TestFrame:
    """Tests for the Frame dataclass."""

    def test_basic_construction(self) -> None:
        image = np.zeros((48, 64, 3), dtype=np.uint8)
        frame = Frame(
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
        assert frame.width == 64
        assert frame.height == 48
        assert frame.channels == 3
        assert frame.frame_index == 0
        assert frame.timestamp_s == 0.0
        assert frame.nominal_fps is None
        assert frame.metadata == {}
        assert frame.source_type == SourceType.SYNTHETIC

    def test_width_height_mismatch_raises(self) -> None:
        image = np.zeros((48, 64, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="does not match"):
            Frame(
                image=image,
                width=100,  # wrong
                height=48,
                channels=3,
                color_model=ColorModel.BGR,
                source_id="test",
                source_type=SourceType.SYNTHETIC,
                frame_index=0,
                timestamp_s=0.0,
            )

    def test_grayscale_frame(self) -> None:
        image = np.zeros((100, 200), dtype=np.uint8)
        frame = Frame(
            image=image,
            width=200,
            height=100,
            channels=1,
            color_model=ColorModel.GRAY,
            source_id="cam",
            source_type=SourceType.LIVE,
            frame_index=5,
            timestamp_s=0.1667,
        )
        assert frame.channels == 1
        assert frame.source_type == SourceType.LIVE

    def test_metadata_stored(self) -> None:
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        frame = Frame(
            image=image,
            width=10,
            height=10,
            channels=3,
            color_model=ColorModel.BGR,
            source_id="test",
            source_type=SourceType.SIMULATION,
            frame_index=0,
            timestamp_s=0.0,
            metadata={"custom_key": "custom_value"},
        )
        assert frame.metadata["custom_key"] == "custom_value"

    def test_nominal_fps_stored(self) -> None:
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        frame = Frame(
            image=image,
            width=10,
            height=10,
            channels=3,
            color_model=ColorModel.BGR,
            source_id="test",
            source_type=SourceType.VIDEO,
            frame_index=0,
            timestamp_s=0.0,
            nominal_fps=60.0,
        )
        assert frame.nominal_fps == 60.0


class TestTargetState:
    def test_defaults(self) -> None:
        t = TargetState(x=100, y=200)
        assert t.visible is True
        assert t.confidence == 1.0

    def test_hidden_target(self) -> None:
        t = TargetState(x=0, y=0, visible=False)
        assert t.visible is False


class TestColorModel:
    def test_values(self) -> None:
        assert ColorModel.BGR.value == "BGR"
        assert ColorModel.RGB.value == "RGB"
        assert ColorModel.GRAY.value == "GRAY"
