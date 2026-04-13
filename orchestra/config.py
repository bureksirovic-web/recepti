"""Configuration constants for the orchestra pipeline."""

from pathlib import Path

# ── LLM Endpoints ──────────────────────────────────────────────────────────
BRAIN_BASE_URL = "http://127.0.0.1:8002/v1"
BRAIN_MODEL = "offline-brain"

CODER_BASE_URL = "http://127.0.0.1:8001/v1"
CODER_MODEL = "offline-coder"

API_KEY = "local"

# ── Timings ────────────────────────────────────────────────────────────────
CODER_POLL_INTERVAL_S = 2       # How often coder checks for new tasks
BRAIN_IDLE_THRESHOLD_S = 30     # Seconds of no user input before Brain enters review mode
BRAIN_REVIEW_INTERVAL_S = 60    # Seconds between review cycles
DASHBOARD_REFRESH_S = 2         # Dashboard refresh interval

# ── Paths (set at runtime via --project flag) ──────────────────────────────
ORCHESTRA_DIR_NAME = ".orchestra"  # Hidden dir inside project root


def get_orchestra_dir(project_root: Path) -> Path:
    """Return the .orchestra directory for a given project root."""
    d = project_root / ORCHESTRA_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_db_path(project_root: Path) -> Path:
    """Return path to the SQLite task queue database."""
    return get_orchestra_dir(project_root) / "tasks.db"


def get_undo_dir(project_root: Path) -> Path:
    """Return path to the undo journal directory."""
    d = get_orchestra_dir(project_root) / "undo"
    d.mkdir(parents=True, exist_ok=True)
    return d
