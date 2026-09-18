---
stage: 11
title: GUI — Professional Aerospace Operator HUD
status: complete
---

# Stage 11 — GUI / Tactical HUD

**PySide6 desktop application with professional aerospace visual theme.**

## Overview

Professional multi-panel operator interface for the FSOC tracker system.
Presentation/control layer only — all business logic remains in subsystems.

## Architecture

```
gui/
├── __init__.py          # Package
├── theme.py             # Colors, Fonts, Spacing, stylesheet
├── state.py             # ApplicationViewState (read-only UI snapshot)
├── controller.py        # ApplicationController (thin facade)
├── worker.py            # ProcessingWorker (QThread background pipeline)
├── main_window.py       # MainWindow (multi-panel layout)
├── camera_view.py       # Camera feed with overlay
├── world_view.py        # 2000x2000 global radar view
├── telemetry.py         # System/Input/Perception/Tracking/Control telemetry
├── controls.py          # Tabbed control panel (SIM/CAM/PERC/DIST/VIDEO)
├── scorecard.py         # SIH scorecard (pass/fail)
├── plots.py             # Live error plots (QPainter)
├── event_log.py         # Scrollable event log
├── ai_panel.py          # AI perception status
├── benchmark_panel.py   # Benchmark results display
└── about.py             # About dialog
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| PySide6 | LGPL license, modern Qt bindings, maintained |
| QPainter for plots | Lightweight, no matplotlib dependency in GUI thread |
| Read-only state snapshot | Thread-safe: worker produces, GUI consumes |
| QThread worker | Pipeline runs in background, GUI stays responsive |
| Semantic colors | Central theme, all widgets reference `Colors.*` |
| aerospace dark theme | Professional operator interface, low eye strain |

## State Flow

```
Worker Thread                          GUI Thread
─────────────                          ──────────
[Pipeline] → StateSnapshot ──signal──→ [Widgets] → screen
                ↑
[Config] ←── signal ── [Controls]
```

## Launch

```bash
# GUI mode
python -m fsoc_tracker --gui

# Or with Xvfb (headless/CI)
QT_QPA_PLATFORM=offscreen python -m fsoc_tracker --gui
```

## Configuration

All controls write to `ApplicationController.config`. Config is passed to worker
on START. Save/load via File menu (JSON).

## Testing

```bash
QT_QPA_PLATFORM=offscreen pytest tests/unit/test_gui.py -v
```

89 GUI tests covering:
- State model (dataclasses, defaults, overflow)
- Controller (config save/load, mode switching)
- Theme (colors, fonts, stylesheet generation)
- Worker (pipeline init, step, pause/resume/stop)
- Widget state updates (camera, world, telemetry, scorecard, plots, log, AI, benchmark)
- Main window creation and lifecycle
- Integration flows
