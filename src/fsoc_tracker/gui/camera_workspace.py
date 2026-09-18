"""Camera Tracking Workspace — primary operational view.

Displays the live camera frame with overlays:
  - Target overlay (detection bounding box)
  - Centroid (detection center)
  - Camera center (crosshair)
  - FOV boundary (if applicable)
  - Prediction overlay (Kalman estimate)
  - Tracking state text

Also displays real telemetry values around/below the frame.
"""

from __future__ import annotations

import math

import numpy as np

from fsoc_tracker.gui.state import ApplicationViewState
from fsoc_tracker.gui.theme import Colors

try:
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtGui import (
        QImage, QPixmap, QPainter, QPen, QColor,
    )
    from PySide6.QtWidgets import (
        QLabel, QVBoxLayout, QFrame, QGridLayout,
        QSizePolicy,
    )
except ImportError:
    from PyQt5.QtCore import Qt, QPointF  # type: ignore
    from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor  # type: ignore
    from PyQt5.QtWidgets import (
        QLabel, QVBoxLayout, QFrame, QGridLayout,  # type: ignore
        QSizePolicy,  # type: ignore
    )


class CameraTrackingWorkspace(QFrame):
    """Primary mission view: live camera frame + overlays + telemetry."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CameraWorkspace")
        self.setMinimumSize(400, 300)
        self._state: ApplicationViewState | None = None
        self._current_pixmap: QPixmap | None = None
        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setMinimumSize(1, 1)
        self._image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._image_label.setStyleSheet("background: #050a0f;")
        self._build_telemetry()

    def _build_telemetry(self) -> None:
        """Build the telemetry labels around the camera frame."""
        self._telem: dict[str, QLabel] = {}
        # Will be populated on first update
        self._telemetry_built = False

    def _ensure_telemetry(self, layout: QVBoxLayout) -> None:
        """Lazily build telemetry grid below the camera frame."""
        if self._telemetry_built:
            return
        self._telemetry_built = True

        telem_frame = QFrame()
        telem_frame.setStyleSheet("QFrame { background: rgba(13,20,28,240); border-top: 1px solid #20303d; }")
        telem_grid = QGridLayout(telem_frame)
        telem_grid.setContentsMargins(8, 4, 8, 4)
        telem_grid.setSpacing(2)

        fields = [
            ("TARGET", "--"), ("STATE", "--"), ("CENTROID", "--"),
            ("X ERROR", "--"), ("Y ERROR", "--"), ("EUCL ERROR", "--"),
            ("CONFIDENCE", "--"), ("VELOCITY", "--"), ("PREDICTION", "--"),
            ("UNCERTAINTY", "--"), ("PAN", "--"), ("TILT", "--"),
            ("FPS", "--"), ("LATENCY", "--"),
        ]
        for i, (name, default) in enumerate(fields):
            row = i // 7
            col = (i % 7) * 2
            lbl_name = QLabel(name)
            lbl_name.setStyleSheet(f"color: {Colors.MUTED}; font-size: 9px; font-weight: bold; background: transparent; border: none;")
            lbl_val = QLabel(default)
            lbl_val.setStyleSheet(f"color: {Colors.TEXT}; font-size: 10px; font-weight: bold; background: transparent; border: none;")
            lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._telem[name] = lbl_val
            telem_grid.addWidget(lbl_name, row, col)
            telem_grid.addWidget(lbl_val, row, col + 1)

        layout.addWidget(telem_frame)

    def update_frame(self, image: np.ndarray | None, state: ApplicationViewState) -> None:
        """Update the camera frame and overlays."""
        self._state = state

        # Lazy build layout
        if not self._telemetry_built:
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
            root.addWidget(self._image_label)
            self._ensure_telemetry(root)

        if image is None or image.size == 0:
            return

        # Convert numpy to QPixmap
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
        self._update_telemetry()
        self.update()

    def _update_telemetry(self) -> None:
        """Update the telemetry labels with real values."""
        if self._state is None or not self._telem:
            return
        s = self._state

        def set_t(key: str, text: str, color: str | None = None) -> None:
            if key in self._telem:
                self._telem[key].setText(text)
                if color:
                    self._telem[key].setStyleSheet(
                        f"color: {color}; font-size: 10px; font-weight: bold; background: transparent; border: none;"
                    )

        # Target
        if s.perception.detected:
            set_t("TARGET", f"({s.perception.detection_x:.1f}, {s.perception.detection_y:.1f})", Colors.TARGET)
        else:
            set_t("TARGET", "NONE", Colors.MUTED)

        # State
        state_colors = {
            "NO_TRACK": Colors.MUTED, "SEARCHING": Colors.WARNING,
            "ACQUIRING": Colors.WARNING, "TRACKING": Colors.SUCCESS,
            "LOST": Colors.ERROR, "REACQUIRING": Colors.WARNING,
        }
        set_t("STATE", s.tracking.state, state_colors.get(s.tracking.state, Colors.TEXT))

        # Centroid
        if s.tracking.locked or s.tracking.state in ("TRACKING", "ACQUIRING"):
            set_t("CENTROID", f"({s.tracking.estimated_x:.1f}, {s.tracking.estimated_y:.1f})", Colors.SUCCESS)
        else:
            set_t("CENTROID", "--", Colors.MUTED)

        # Errors
        err_x = s.tracking.estimated_x - s.perception.detection_x if s.perception.detected else 0.0
        err_y = s.tracking.estimated_y - s.perception.detection_y if s.perception.detected else 0.0
        err_eucl = math.sqrt(err_x**2 + err_y**2) if s.perception.detected else 0.0
        err_color = Colors.SUCCESS if err_eucl < 10 else Colors.WARNING if err_eucl < 20 else Colors.ERROR
        set_t("X ERROR", f"{err_x:+.1f}px", err_color)
        set_t("Y ERROR", f"{err_y:+.1f}px", err_color)
        set_t("EUCL ERROR", f"{err_eucl:.1f}px", err_color)

        # Confidence
        conf_color = Colors.SUCCESS if s.perception.confidence > 0.7 else Colors.WARNING if s.perception.confidence > 0.3 else Colors.ERROR
        set_t("CONFIDENCE", f"{s.perception.confidence:.2f}", conf_color)

        # Velocity
        if s.tracking.locked:
            vel = math.sqrt(s.tracking.velocity_x**2 + s.tracking.velocity_y**2)
            set_t("VELOCITY", f"{vel:.1f}px/s", Colors.TEXT)
        else:
            set_t("VELOCITY", "--", Colors.MUTED)

        # Prediction
        if s.tracking.prediction_only:
            set_t("PREDICTION", "ACTIVE", Colors.WARNING)
        else:
            set_t("PREDICTION", "NONE", Colors.MUTED)

        # Uncertainty
        unc = math.sqrt(s.tracking.uncertainty_x**2 + s.tracking.uncertainty_y**2)
        unc_color = Colors.SUCCESS if unc < 5 else Colors.WARNING if unc < 15 else Colors.ERROR
        set_t("UNCERTAINTY", f"({s.tracking.uncertainty_x:.1f}, {s.tracking.uncertainty_y:.1f})", unc_color)

        # Pan/Tilt
        set_t("PAN", f"{s.camera.pan_deg:+.2f}\u00b0", Colors.TEXT)
        set_t("TILT", f"{s.camera.tilt_deg:+.2f}\u00b0", Colors.TEXT)

        # FPS
        fps_color = Colors.SUCCESS if s.camera.fps >= 20 else Colors.WARNING if s.camera.fps >= 10 else Colors.ERROR
        set_t("FPS", f"{s.camera.fps:.1f}", fps_color)

        # Latency
        lat_color = Colors.SUCCESS if s.performance.processing_ms < 50 else Colors.WARNING if s.performance.processing_ms < 100 else Colors.ERROR
        set_t("LATENCY", f"{s.performance.processing_ms:.1f}ms", lat_color)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._state is None or self._current_pixmap is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Compute image label geometry
        px = self._image_label.x()
        py = self._image_label.y()
        pw = self._image_label.width()
        ph = self._image_label.height()
        cx = px + pw // 2
        cy = py + ph // 2

        s = self._state
        img_w = max(s.camera.image_width, 1)
        img_h = max(s.camera.image_height, 1)
        sx = pw / img_w
        sy = ph / img_h

        # --- Camera center crosshair ---
        pen_ch = QPen(QColor(Colors.CROSSHAIR), 1, Qt.DashLine)
        painter.setPen(pen_ch)
        painter.drawLine(cx - 20, cy, cx + 20, cy)
        painter.drawLine(cx, cy - 20, cx, cy + 20)

        # --- FOV boundary (diamond at image edges) ---
        pen_fov = QPen(QColor(Colors.CENTERLINE), 1, Qt.DotLine)
        painter.setPen(pen_fov)
        margin = 4
        painter.drawRect(px + margin, py + margin, pw - 2 * margin, ph - 2 * margin)

        # --- Target overlay (detection) ---
        if s.perception.detected:
            det_x = int(px + s.perception.detection_x * sx)
            det_y = int(py + s.perception.detection_y * sy)
            box_half = int(s.target.size_px * sx * 0.7)

            # Bounding box
            pen_det = QPen(QColor(Colors.TARGET), 2)
            painter.setPen(pen_det)
            painter.setBrush(QColor(0, 0, 0, 0))
            painter.drawRect(det_x - box_half, det_y - box_half, box_half * 2, box_half * 2)

            # Centroid dot
            painter.setBrush(QColor(Colors.TARGET))
            painter.drawEllipse(QPointF(det_x, det_y), 4, 4)

        # --- Tracking estimate (Kalman) ---
        if s.tracking.locked or s.tracking.state in ("TRACKING", "ACQUIRING"):
            trk_x = int(px + s.tracking.estimated_x * sx)
            trk_y = int(py + s.tracking.estimated_y * sy)

            # Crosshair
            pen_trk = QPen(QColor(Colors.SUCCESS), 2, Qt.DashDotLine)
            painter.setPen(pen_trk)
            painter.setBrush(QColor(0, 0, 0, 0))
            painter.drawLine(trk_x - 10, trk_y, trk_x + 10, trk_y)
            painter.drawLine(trk_x, trk_y - 10, trk_x, trk_y + 10)

            # Uncertainty circle
            unc_r = max(int(s.tracking.uncertainty_x * sx), 3)
            painter.setPen(QPen(QColor(Colors.SUCCESS), 1, Qt.DotLine))
            painter.drawEllipse(QPointF(trk_x, trk_y), unc_r, unc_r)

        # --- Prediction marker (AI motion forecast from runtime state) ---
        pred_dx = float(s.ai_state.prediction_dx)
        pred_dy = float(s.ai_state.prediction_dy)
        if s.tracking.state in ("TRACKING", "ACQUIRING") and (pred_dx != 0.0 or pred_dy != 0.0):
            est_x = float(s.tracking.estimated_x)
            est_y = float(s.tracking.estimated_y)
            pred_x = int(px + (est_x + pred_dx) * sx)
            pred_y = int(py + (est_y + pred_dy) * sy)
            base_x = int(px + est_x * sx)
            base_y = int(py + est_y * sy)

            # Dashed connector: current estimate -> predicted position
            painter.setPen(QPen(QColor(Colors.PREDICTED), 1, Qt.DashLine))
            painter.setBrush(QColor(0, 0, 0, 0))
            painter.drawLine(base_x, base_y, pred_x, pred_y)

            # Diamond marker at the predicted position
            d = 5
            painter.setPen(QPen(QColor(Colors.PREDICTED), 2))
            painter.drawLine(pred_x - d, pred_y, pred_x, pred_y - d)
            painter.drawLine(pred_x, pred_y - d, pred_x + d, pred_y)
            painter.drawLine(pred_x + d, pred_y, pred_x, pred_y + d)
            painter.drawLine(pred_x, pred_y + d, pred_x - d, pred_y)

            # Prediction uncertainty circle
            pred_unc = math.sqrt(
                float(s.ai_state.prediction_uncertainty_x) ** 2
                + float(s.ai_state.prediction_uncertainty_y) ** 2
            )
            if pred_unc > 0.0:
                painter.setPen(QPen(QColor(Colors.PREDICTED), 1, Qt.DotLine))
                painter.drawEllipse(
                    QPointF(pred_x, pred_y),
                    max(int(pred_unc * sx), 2), max(int(pred_unc * sy), 2),
                )

            # Horizon tag (value straight from runtime state)
            painter.setPen(QPen(QColor(Colors.PREDICTED), 1))
            tag_font = painter.font()
            tag_font.setPointSize(8)
            tag_font.setBold(False)
            painter.setFont(tag_font)
            painter.drawText(
                pred_x + 8, pred_y - 6,
                f"PRED +{float(s.ai_state.prediction_horizon_s):.2f}s",
            )

        # --- Tracking state text overlay ---
        state_text = f"TRK: {s.tracking.state}"
        if s.tracking.locked:
            state_text += " | LOCKED"
        painter.setPen(QPen(QColor(Colors.ACCENT), 1))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(px + 8, py + 20, state_text)

        # --- Mode indicator ---
        mode_text = f"SRC: {s.system_mode.value.upper()}"
        painter.setPen(QPen(QColor(Colors.MUTED), 1))
        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(px + 8, py + 38, mode_text)

        # --- Distance status (for LIVE mode) ---
        if s.system_mode.value.upper() == "LIVE":
            distance_status = s.live_distance_status if hasattr(s, 'live_distance_status') else "UNAVAILABLE"
            distance_text = f"DIST: {distance_status}"
            painter.setPen(QPen(QColor(Colors.WARNING) if distance_status == "UNAVAILABLE" else Colors.SUCCESS, 1))
            painter.drawText(px + 8, py + 56, distance_text)

        painter.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Re-layout is handled by Qt
