"""Benchmark panel — full benchmark GUI with mode/world selection, run/stop, results."""

from __future__ import annotations

import json
from pathlib import Path

from fsoc_tracker.gui.state import ApplicationViewState
from fsoc_tracker.gui.theme import Colors

try:
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QComboBox,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QProgressBar,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
    )
except ImportError:
    from PyQt5.QtCore import Qt, QThread, Signal  # type: ignore
    from PyQt5.QtWidgets import (  # type: ignore
        QAbstractItemView,
        QComboBox,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QProgressBar,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
    )


class BenchmarkWorker(QThread):
    """Background thread for running benchmarks (GUI stays responsive)."""

    progress = Signal(int, int)
    finished = Signal(dict)
    failed = Signal(str)
    log = Signal(str, str)

    def __init__(self, config, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._runner = None

    def run(self) -> None:
        from fsoc_tracker.benchmark.methods import MethodUnavailableError
        from fsoc_tracker.benchmark.runner import BenchmarkRunner
        self._runner = BenchmarkRunner()
        try:
            metrics = self._runner.run(
                self._config,
                progress_callback=lambda cur, total: self.progress.emit(cur, total),
                log_callback=lambda level, msg: self.log.emit(level, msg),
            )
        except MethodUnavailableError as e:
            self.failed.emit(str(e))
            return
        except Exception as e:  # noqa: BLE001 — surfaced to the status line
            self.failed.emit(f"Benchmark failed: {e}")
            return
        self.finished.emit(metrics.to_dict())

    def request_stop(self) -> None:
        if self._runner:
            self._runner.request_stop()


class BenchmarkPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._labels: dict[str, QLabel] = {}
        self._worker: BenchmarkWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        title = QLabel("BENCHMARK")
        title.setStyleSheet(f"color: {Colors.WARNING}; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        layout.addWidget(title)

        # Source selector (SIMULATION only: PS metrics need ground
        # truth, which monocular VIDEO/LIVE cannot provide).
        source_layout = QHBoxLayout()
        source_lbl = QLabel("SOURCE:")
        source_lbl.setStyleSheet(f"color: {Colors.MUTED}; font-size: 9px; background: transparent; border: none;")
        self._source_combo = QComboBox()
        self._source_combo.addItems(["SIMULATION", "VIDEO", "LIVE"])
        self._source_combo.setStyleSheet("QComboBox { font-size: 9px; }")
        try:
            model = self._source_combo.model()
            for i, tip in enumerate([
                "Closed-loop simulation with ground-truth scoring",
                "NOT AVAILABLE: monocular video has no depth/ground truth for PS metrics",
                "NOT AVAILABLE: live camera has no ground truth for PS metrics",
            ]):
                model.item(i).setEnabled(i == 0)
                model.item(i).setToolTip(tip)
        except Exception:
            pass
        self._source_combo.currentTextChanged.connect(self._on_source_changed)
        source_layout.addWidget(source_lbl)
        source_layout.addWidget(self._source_combo, 1)
        layout.addLayout(source_layout)

        # Mode selector
        mode_layout = QHBoxLayout()
        mode_lbl = QLabel("METHOD:")
        mode_lbl.setStyleSheet(f"color: {Colors.MUTED}; font-size: 9px; background: transparent; border: none;")
        self._mode_combo = QComboBox()
        self._mode_combo.setStyleSheet("QComboBox { font-size: 9px; }")
        self._refresh_methods()
        self._mode_combo.currentTextChanged.connect(self._on_method_changed)
        mode_layout.addWidget(mode_lbl)
        mode_layout.addWidget(self._mode_combo, 1)
        layout.addLayout(mode_layout)

        # Scene selector
        scene_layout = QHBoxLayout()
        scene_lbl = QLabel("WORLD:")
        scene_lbl.setStyleSheet(f"color: {Colors.MUTED}; font-size: 9px; background: transparent; border: none;")
        self._world_combo = QComboBox()
        from fsoc_tracker.simulation.world_builder import benchmark_profiles
        self._world_profiles = list(benchmark_profiles())
        self._world_combo.addItems([p.upper() for p in self._world_profiles])
        self._world_combo.setCurrentIndex(1)
        self._world_combo.setStyleSheet("QComboBox { font-size: 9px; }")
        scene_layout.addWidget(self._world_combo, 1)
        layout.addLayout(scene_layout)

        # Seed + Frames
        param_layout = QHBoxLayout()
        seed_lbl = QLabel("SEED:")
        seed_lbl.setStyleSheet(f"color: {Colors.MUTED}; font-size: 9px; background: transparent; border: none;")
        self._seed_input = QLineEdit("42")
        self._seed_input.setFixedWidth(50)
        self._seed_input.setStyleSheet("QLineEdit { font-size: 9px; }")
        frames_lbl = QLabel("FRAMES:")
        frames_lbl.setStyleSheet(f"color: {Colors.MUTED}; font-size: 9px; background: transparent; border: none;")
        self._frames_input = QLineEdit("300")
        self._frames_input.setFixedWidth(50)
        self._frames_input.setStyleSheet("QLineEdit { font-size: 9px; }")
        param_layout.addWidget(seed_lbl)
        param_layout.addWidget(self._seed_input)
        param_layout.addWidget(frames_lbl)
        param_layout.addWidget(self._frames_input)
        param_layout.addStretch()
        layout.addLayout(param_layout)

        # Run / Stop buttons
        btn_layout = QHBoxLayout()
        self._run_btn = QPushButton("RUN")
        self._run_btn.setFixedHeight(28)
        self._run_btn.setStyleSheet(f"QPushButton {{ color: {Colors.SUCCESS}; font-size: 9px; font-weight: bold; padding: 2px 12px; border: 1px solid {Colors.SUCCESS}; border-radius: 3px; }} QPushButton:hover {{ background: {Colors.SUCCESS}; color: #000; }}")
        self._run_btn.clicked.connect(self._on_run)
        self._stop_btn = QPushButton("STOP")
        self._stop_btn.setFixedHeight(28)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet(f"QPushButton {{ color: {Colors.ERROR}; font-size: 9px; font-weight: bold; padding: 2px 12px; border: 1px solid {Colors.ERROR}; border-radius: 3px; }} QPushButton:hover {{ background: {Colors.ERROR}; color: #000; }}")
        self._stop_btn.clicked.connect(self._on_stop)
        self._export_btn = QPushButton("EXPORT")
        self._export_btn.setFixedHeight(28)
        self._export_btn.setStyleSheet(f"QPushButton {{ color: {Colors.MUTED}; font-size: 9px; font-weight: bold; padding: 2px 12px; border: 1px solid {Colors.PANEL_BORDER}; border-radius: 3px; }} QPushButton:hover {{ color: {Colors.TEXT}; border-color: {Colors.ACCENT}; }}")
        self._export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(self._run_btn)
        btn_layout.addWidget(self._stop_btn)
        btn_layout.addWidget(self._export_btn)
        layout.addLayout(btn_layout)

        # Status
        self._status = QLabel("IDLE")
        self._status.setStyleSheet(f"color: {Colors.MUTED}; font-size: 9px; font-weight: bold; background: transparent; border: none;")
        layout.addWidget(self._status)

        # Progress
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        layout.addWidget(self._progress)

        # Results
        grp = QGroupBox("Results")
        grp.setStyleSheet(f"QGroupBox {{ color: {Colors.WARNING}; font-size: 9px; font-weight: bold; border: 1px solid {Colors.PANEL_BORDER}; border-radius: 3px; margin-top: 6px; padding-top: 8px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 6px; padding: 0 3px; }}")
        grid = QGridLayout(grp)
        grid.setSpacing(2)
        grid.setContentsMargins(4, 4, 4, 4)

        fields = [
            ("Acquisition", "acquisition_s"),
            ("RMSE", "rmse_px"),
            ("MAE", "mae_px"),
            ("P95", "p95_px"),
            ("MaxErr", "max_error_px"),
            ("Loss Rate", "loss_rate_pct"),
            ("Re-acquisition", "reacquisition_s"),
            ("Lock Ret.", "lock_retention_pct"),
            ("FOV Ret.", "fov_retention_pct"),
            ("Search Duration", "search_duration_s"),
            ("FPS", "fps"),
            ("Latency", "latency_ms"),
            ("Link Down", "link_downtime_s"),
            ("Messages", "messages"),
            ("Safety", "safety_events"),
            ("Frames", "frames_processed"),
            ("Losses", "target_losses"),
        ]
        for i, (label, key) in enumerate(fields):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {Colors.MUTED}; font-size: 9px; background: transparent; border: none;")
            val = QLabel("--")
            val.setStyleSheet(f"color: {Colors.TEXT}; font-size: 9px; font-weight: bold; background: transparent; border: none;")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._labels[key] = val
            grid.addWidget(lbl, i, 0)
            grid.addWidget(val, i, 1)

        layout.addWidget(grp)

        # Run-history table (every completed run, newest last)
        hist_grp = QGroupBox("Run History")
        hist_grp.setStyleSheet(f"QGroupBox {{ color: {Colors.WARNING}; font-size: 9px; font-weight: bold; border: 1px solid {Colors.PANEL_BORDER}; border-radius: 3px; margin-top: 6px; padding-top: 8px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 6px; padding: 0 3px; }}")
        hist_layout = QVBoxLayout(hist_grp)
        self._history = QTableWidget(0, 8)
        self._history.setHorizontalHeaderLabels(
            ["Method", "Scene", "Seed", "RMSE", "Loss%", "FPS", "LinkDn", "Msgs"]
        )
        self._history.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._history.setStyleSheet("QTableWidget { font-size: 9px; }")
        self._history.verticalHeader().setVisible(False)
        hist_layout.addWidget(self._history)
        layout.addWidget(hist_grp)
        layout.addStretch()

    def _refresh_methods(self) -> None:
        """Populate the method combo; unavailable methods are marked."""
        from fsoc_tracker.benchmark.methods import (
            METHOD_LABELS,
            METHOD_ORDER,
            check_method_availability,
        )
        self._mode_combo.clear()
        self._method_values: list[str | None] = []
        for value in METHOD_ORDER:
            availability = check_method_availability(value)
            if availability.available:
                self._mode_combo.addItem(METHOD_LABELS[value])
                self._method_values.append(value)
            else:
                self._mode_combo.addItem(f"{METHOD_LABELS[value]} — NOT AVAILABLE")
                self._method_values.append(None)
                try:
                    idx = self._mode_combo.count() - 1
                    self._mode_combo.model().item(idx).setEnabled(False)
                    self._mode_combo.model().item(idx).setToolTip(availability.reason)
                except Exception:
                    pass

    def _on_method_changed(self, text: str) -> None:
        from fsoc_tracker.benchmark.methods import METHOD_LABELS
        idx = self._mode_combo.currentIndex()
        value = self._method_values[idx] if 0 <= idx < len(self._method_values) else None
        if value is None:
            self._status.setText("METHOD NOT AVAILABLE")
        else:
            self._status.setText(f"READY — {METHOD_LABELS[value]}")

    def _on_source_changed(self, text: str) -> None:
        if text != "SIMULATION":
            self._status.setText("SOURCE NOT AVAILABLE FOR PS BENCHMARK")
            self._source_combo.setCurrentText("SIMULATION")

    def _on_run(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        if self._source_combo.currentText() != "SIMULATION":
            self._status.setText("SOURCE NOT AVAILABLE FOR PS BENCHMARK")
            return

        from fsoc_tracker.benchmark.runner import BenchmarkMode, BenchmarkRunConfig

        idx = self._mode_combo.currentIndex()
        value = self._method_values[idx] if 0 <= idx < len(self._method_values) else None
        if value is None:
            self._status.setText("METHOD NOT AVAILABLE — NOT RUN")
            return
        mode_map = {
            "classical_pid": BenchmarkMode.CLASSICAL_PID,
            "kalman_expert": BenchmarkMode.KALMAN_EXPERT,
            "learned_temporal_expert": BenchmarkMode.LEARNED_TEMPORAL_EXPERT,
            "learned_temporal_learned_policy": BenchmarkMode.LEARNED_TEMPORAL_LEARNED_POLICY,
            "full_ai_mission": BenchmarkMode.FULL_AI_MISSION,
        }

        try:
            seed = int(self._seed_input.text())
            frames = int(self._frames_input.text())
        except ValueError:
            self._status.setText("INVALID SEED/FRAMES")
            return
        config = BenchmarkRunConfig(
            mode=mode_map.get(value, BenchmarkMode.KALMAN_EXPERT),
            world_profile=self._world_profiles[self._world_combo.currentIndex()]
            if 0 <= self._world_combo.currentIndex() < len(self._world_profiles)
            else "nominal",
            seed=seed,
            max_frames=frames,
            output_dir="logs/benchmark",
        )

        self._worker = BenchmarkWorker(config)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.log.connect(self._on_log)

        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status.setText("RUNNING")
        self._status.setStyleSheet(f"color: {Colors.WARNING}; font-size: 9px; font-weight: bold; background: transparent; border: none;")

        self._worker.start()

    def _on_stop(self) -> None:
        if self._worker:
            self._worker.request_stop()

    def _on_progress(self, current: int, total: int) -> None:
        pct = int((current / max(total, 1)) * 100)
        self._progress.setValue(pct)
        self._status.setText(f"RUNNING — {current}/{total}")

    def _on_finished(self, metrics: dict) -> None:
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status.setText("COMPLETE")
        self._status.setStyleSheet(f"color: {Colors.SUCCESS}; font-size: 9px; font-weight: bold; background: transparent; border: none;")
        self._last_metrics = metrics
        self._update_results(metrics)
        self._append_history(metrics)

    def _on_failed(self, message: str) -> None:
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status.setText(message[:120])
        self._status.setStyleSheet(f"color: {Colors.ERROR}; font-size: 9px; font-weight: bold; background: transparent; border: none;")

    def _append_history(self, m: dict) -> None:
        row = self._history.rowCount()
        self._history.insertRow(row)
        cells = [
            str(m.get("method", "")),
            str(m.get("scenario", "")),
            str(m.get("seed", "")),
            f"{m.get('rmse_px', 0.0):.2f}",
            f"{m.get('loss_rate_pct', 0.0):.1f}",
            f"{m.get('fps', 0.0):.1f}",
            f"{m.get('link_downtime_s', 0.0):.2f}",
            f"{m.get('messages_delivered', 0)}/{m.get('messages_total', 0)}",
        ]
        for col, text in enumerate(cells):
            self._history.setItem(row, col, QTableWidgetItem(text))

    def _on_log(self, level: str, msg: str) -> None:
        pass

    def _update_results(self, m: dict) -> None:
        def set_val(key: str, text: str, color: str | None = None) -> None:
            if key in self._labels:
                self._labels[key].setText(text)
                if color:
                    self._labels[key].setStyleSheet(f"color: {color}; font-size: 9px; font-weight: bold; background: transparent; border: none;")

        set_val("acquisition_s", f"{m['acquisition_s']:.3f}s" if m.get('acquisition_s') is not None else "--",
                Colors.SUCCESS if m.get('acquisition_s', 999) <= 2.0 else Colors.ERROR)
        set_val("rmse_px", f"{m['rmse_px']:.2f} px",
                Colors.SUCCESS if m['rmse_px'] <= 10.0 else Colors.ERROR)
        set_val("mae_px", f"{m['mae_px']:.2f} px")
        set_val("p95_px", f"{m['p95_px']:.2f} px",
                Colors.SUCCESS if m['p95_px'] <= 15.0 else Colors.WARNING)
        set_val("max_error_px", f"{m.get('max_error_px', 0.0):.2f} px")
        set_val("loss_rate_pct", f"{m['loss_rate_pct']:.1f}%",
                Colors.SUCCESS if m['loss_rate_pct'] <= 5.0 else Colors.ERROR)
        set_val("reacquisition_s", f"{m['reacquisition_s']:.3f}s" if m.get('reacquisition_s') is not None else "--",
                Colors.SUCCESS if (m.get('reacquisition_s') or 999) <= 1.0 else Colors.ERROR)
        set_val("lock_retention_pct", f"{m.get('lock_retention_pct', 0.0):.1f}%")
        set_val("fov_retention_pct", f"{m.get('fov_retention_pct', 0.0):.1f}%")
        set_val("search_duration_s", f"{m['search_duration_s']:.3f}s")
        set_val("fps", f"{m['fps']:.1f}",
                Colors.SUCCESS if m['fps'] >= 20.0 else Colors.WARNING)
        set_val("latency_ms", f"{m['latency_ms']:.1f} ms")
        set_val("link_downtime_s", f"{m.get('link_downtime_s', 0.0):.3f}s")
        set_val("messages", f"{m.get('messages_delivered', 0)}/{m.get('messages_total', 0)}")
        set_val("safety_events", f"{m.get('safety_events', 0)}")
        set_val("frames_processed", f"{m['frames_processed']}/{m['total_frames']}")
        set_val("target_losses", f"{m['target_losses']}")

    def _on_export(self) -> None:
        if not hasattr(self, '_last_metrics') or not self._last_metrics:
            return
        try:
            from PySide6.QtWidgets import QFileDialog
        except ImportError:
            from PyQt5.QtWidgets import QFileDialog  # type: ignore
        m = self._last_metrics
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Results (JSON)", "benchmark_results.json", "JSON (*.json)"
        )
        if path:
            with open(path, 'w') as f:
                json.dump(m, f, indent=2)
            # The per-frame CSV is always auto-logged with the run; copy
            # it next to the exported JSON for a complete record.
            csv_src = Path(m.get("log_csv_path", ""))
            if csv_src.exists():
                csv_dst = Path(path).with_name(Path(path).stem + "_frames.csv")
                try:
                    csv_dst.write_bytes(csv_src.read_bytes())
                except OSError:
                    pass

    def update_state(self, state: ApplicationViewState) -> None:
        pass
