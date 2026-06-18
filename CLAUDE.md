# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Dota 2 GSI Listener — a Python Flask HTTP server that receives real-time game state data pushed by the Dota 2 client. It logs structured JSON, pretty-prints game state to the console, tracks enemy vision on the minimap, monitors resource spawn timers, and provides Chinese TTS voice alerts on Windows.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server (development)
python src/server.py

# Run with a custom config path
python src/server.py path/to/config.yaml

# Build Windows executable
.\build.bat
# Output: dist/Dota2GSI.exe (single-file, includes config.yaml and speak.ps1 as bundled data)
```

There are no tests or linters configured in this project.

## Architecture

```
Dota 2 client ──POST JSON──▶ Flask (server.py) ──▶ GSIHandler (gsi_handler.py)
                                                    ├── VisionTracker (vision_tracker.py)
                                                    ├── GameTimer (game_timer.py)
                                                    └── TTS (tts.py → speak.ps1)
```

### Data flow

1. Dota 2 pushes JSON via HTTP POST to `http://localhost:3000/` (configured in `gamestate_integration_gsi_config.cfg`).
2. `server.py` receives it at the `/` endpoint and calls `handler.handle(request.data)`.
3. `GSIHandler.handle()` parses the JSON, then:
   - Detects new game sessions by clock_time reset (game time dropping from >30s to <5s).
   - Feeds `data["minimap"]` to `VisionTracker.update()` for enemy visibility events.
   - Feeds game time to `GameTimer.update()` for resource spawn warnings (15s ahead).
   - Writes each frame as a JSON line to `logs/gsi_session_<timestamp>.jsonl`.
   - Console pretty-printing of the summary line is currently disabled (the `print` in `_print_to_console` is commented out).

### Key modules

- **`src/server.py`** — Flask app with two routes (`/` POST, `/health` GET). Loads `config.yaml`, creates the `GSIHandler`, and starts the server. Suppresses Werkzeug access logs. Fixes Windows GBK terminal encoding for emoji output.

- **`src/gsi_handler.py`** — `GSIHandler` is the central orchestrator. It owns the `VisionTracker`, `GameTimer`, and session/file management. New game detection triggers session reset across all sub-modules. Vision events and timer events are routed to console print + TTS speak.

- **`src/vision_tracker.py`** — `VisionTracker` compares minimap hero objects frame-by-frame. Enemy heroes are identified by team ID (`2` = radiant, `3` = dire) relative to the player's team. When a hero disappears from minimap, it enters a 10-second `_pending_leave` grace period before emitting a `LEFT` event — this prevents false positives from brief fog-of-war loss. Kill detection: if the player's team score increases in the same frame, the hero is treated as dead rather than "left vision." A `MASS_LEFT` event fires when ≥4 enemies leave vision simultaneously (60s cooldown).

- **`src/game_timer.py`** — `GameTimer` tracks fixed-interval resource spawns: power runes (2min), lotus (3min), wisdom rune (7min), tormentor (20min), and shard (15min, one-time). Emits `TimerEvent` when within 15 seconds of the next spawn. Each spawn point is notified exactly once via a `_notified` set.

- **`src/tts.py`** — `SpeechQueue` runs a daemon thread that serializes text-to-speech requests through a `queue.Queue`, invoking `speak.ps1` via `subprocess.run` for each item. `hero_cn_name()` maps `npc_dota_hero_*` internal names to Chinese display names using a 150+ entry hardcoded dictionary. The `speak()` function is the global entry point (lazy-initializes the singleton queue).

- **`src/speak.ps1`** — PowerShell script that uses Windows SAPI `System.Speech.Synthesis.SpeechSynthesizer` to speak text. Bundled into the PyInstaller executable via `--add-data`.

### Configuration (`config.yaml`)

- `server.host` / `server.port` — HTTP listen address (must match the URI in the Dota 2 GSI `.cfg` file).
- `logging.log_dir` — directory for JSONL session files and vision event logs.
- `logging.console_pretty_print` — toggle console summary output (currently hard-disabled in code).
- `logging.session_file` — when true, creates a new `gsi_session_<timestamp>.jsonl` per game.
- `vision.enabled` — toggle enemy vision tracking.
- `vision.event_log_file` — path for vision event JSONL output.

### Build

PyInstaller single-file build (`build.bat` / `Dota2GSI.spec`). The spec bundles `config.yaml` (root) and `src/speak.ps1` (under `src/`) as data files. At runtime, `tts.py` checks `sys.frozen` to locate `speak.ps1` under `sys._MEIPASS`. The executable is a console application (not windowed).

### Platform

Windows-only due to TTS (`speak.ps1` / SAPI) and `subprocess.CREATE_NO_WINDOW`. The Flask server itself is cross-platform.
