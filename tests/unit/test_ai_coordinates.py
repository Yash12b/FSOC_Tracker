from __future__ import annotations

import numpy as np

from fsoc_tracker.ai.coordinates import (
    decode_heatmap_center,
    model_to_source,
    source_to_model,
)


def test_coordinate_round_trip_for_center_and_corners() -> None:
    for x, y in ((0.0, 0.0), (320.0, 240.0), (639.0, 479.0)):
        mx, my = source_to_model(x, y, 640, 480, 128, 128)
        sx, sy = model_to_source(mx, my, 128, 128, 640, 480)
        assert sx == x
        assert sy == y


def test_heatmap_decoder_returns_subpixel_source_coordinate() -> None:
    heatmap = np.zeros((128, 128), dtype=np.float32)
    heatmap[48, 64] = 1.0
    heatmap[48, 65] = 0.5
    x, y, confidence = decode_heatmap_center(heatmap, 640, 480)
    assert 320.0 < x < 330.0
    assert y == 180.0
    assert confidence == 1.0
