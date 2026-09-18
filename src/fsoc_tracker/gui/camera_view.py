"""Camera view widget — displays virtual camera feed with overlays."""

from __future__ import annotations


import numpy as np

from fsoc_tracker.gui.state import ApplicationViewState
from fsoc_tracker.gui.theme import Colors

try:
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QFrame
except ImportError:
    from PyQt5.QtCore import Qt, QPointF  # type: ignore
    from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor  # type: ignore
    from PyQt5.QtWidgets import QLabel, QVBoxLayout, QFrame  # type: ignore


class CameraViewWidget(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setObjectName("CameraViewport")
        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setMinimumSize(1, 1)
        self._overlay_label = QLabel(self)
        self._overlay_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._overlay_label.setStyleSheet("background: transparent; color: #e6edf3; font-size: 10px; font-family: monospace; padding: 6px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._image_label)
        self._overlay_label.setParent(self)

        self._current_pixmap: QPixmap | None = None
        self._state: ApplicationViewState | None = None

    def update_frame(self, image: np.ndarray | None, state: ApplicationViewState) -> None:
        self._state = state
        if image is None or image.size == 0:
            return
        if image.ndim == 2:
            h, w = image.shape
            bytes_per_line = w
            fmt = QImage.Format_Grayscale8
            qimg = QImage(image.data, w, h, bytes_per_line, fmt)
        else:
            h, w, ch = image.shape
            if ch == 3:
                rgb = image[:, :, ::-1].copy()
                fmt = QImage.Format_RGB888
            else:
                rgb = image.copy()
                fmt = QImage.Format_RGB888
            qimg = QImage(rgb.data, w, h, w * 3, fmt)

        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(self._image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._current_pixmap = scaled
        self._image_label.setPixmap(scaled)
        self._update_overlay()

    def _update_overlay(self) -> None:
        if self._state is None:
            return
        s = self._state
        lines = []
        if s.perception.detected:
            lines.append(f"DET conf={s.perception.confidence:.2f}")
        lines.append(f"TRK {s.tracking.state}")
        if s.tracking.locked:
            lines.append(f"ERR {s.tracking.residual:.1f}px")
        self._overlay_label.setText("\n".join(lines))
        self._overlay_label.adjustSize()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._state is None or self._current_pixmap is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        px = self._image_label.x()
        py = self._image_label.y()
        pw = self._image_label.width()
        ph = self._image_label.height()
        cx = px + pw // 2
        cy = py + ph // 2

        pen_ch = QPen(QColor(Colors.CROSSHAIR), 1, Qt.DashLine)
        painter.setPen(pen_ch)
        painter.drawLine(cx - 20, cy, cx + 20, cy)
        painter.drawLine(cx, cy - 20, cx, cy + 20)

        s = self._state
        if s.perception.detected:
            sx = pw / max(s.camera.image_width, 1)
            sy = ph / max(s.camera.image_height, 1)
            det_x = int(px + s.perception.detection_x * sx)
            det_y = int(py + s.perception.detection_y * sy)
            box_half = int(s.target.size_px * sx * 0.7)
            pen_det = QPen(QColor(Colors.TARGET), 2)
            painter.setPen(pen_det)
            painter.drawRect(det_x - box_half, det_y - box_half, box_half * 2, box_half * 2)
            painter.setBrush(QColor(Colors.TARGET))
            painter.drawEllipse(QPointF(det_x, det_y), 3, 3)

        if s.tracking.locked or s.tracking.state in ("TRACKING", "ACQUIRING"):
            sx = pw / max(s.camera.image_width, 1)
            sy = ph / max(s.camera.image_height, 1)
            trk_x = int(px + s.tracking.estimated_x * sx)
            trk_y = int(py + s.tracking.estimated_y * sy)
            pen_trk = QPen(QColor(Colors.SUCCESS), 2, Qt.DashDotLine)
            painter.setPen(pen_trk)
            painter.drawLine(trk_x - 8, trk_y, trk_x + 8, trk_y)
            painter.drawLine(trk_x, trk_y - 8, trk_x, trk_y + 8)

        painter.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._overlay_label.move(6, 6)
