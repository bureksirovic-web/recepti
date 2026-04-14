"""Entry point for the Orchestra dual-GPU pipeline.

Usage:
  python -m orchestra --project ~/MyProject
  python -m orchestra  # uses current directory
"""

import argparse
import signal
import sys
from pathlib import Path

from orchestra.brain_chat import BrainChat
from orchestra.coder_worker import CoderWorker
from orchestra.config import BRAIN_BASE_URL, CODER_BASE_URL, get_db_path
from orchestra.llm_client import is_endpoint_live
from orchestra.memory import ProjectMemory
from orchestra.task_queue import TaskQueue

BANNER = """\
\033[1;36m
╔══════════════════════════════════════════════════════════╗
║              🎼  O R C H E S T R A  🎼                  ║
║          Dual-GPU Parallel Coding Pipeline               ║
╠══════════════════════════════════════════════════════════╣
║  🧠 Brain (GPU0)  — Plans, reviews, coordinates         ║
║  🔧 Coder (GPU1)  — Aider executes tasks autonomously   ║
║                                                          ║
║  Chat with the Brain. Tasks auto-execute via Aider.      ║
║  Go idle → Brain reviews code and adds tasks.            ║
║                                                          ║
║  Commands: /status /tasks /help   Exit: Ctrl+C           ║
╚══════════════════════════════════════════════════════════╝
\033[0m"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Orchestra — Dual-GPU Coding Pipeline")
    parser.add_argument(
        "--project",
        "-p",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory)",
    )
    args = parser.parse_args()

    project_root = args.project.resolve()
    if not project_root.is_dir():
        print(f"Error: {project_root} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(BANNER)
    print(f"  📁 Project: {project_root}")

    # Check endpoints
    brain_ok = is_endpoint_live(BRAIN_BASE_URL)
    coder_ok = is_endpoint_live(CODER_BASE_URL)
    print(f"  🧠 Brain:   {'✅ LIVE' if brain_ok else '❌ DOWN'} ({BRAIN_BASE_URL})")
    print(f"  🔧 Coder:   {'✅ LIVE' if coder_ok else '❌ DOWN'} ({CODER_BASE_URL})")

    if not brain_ok:
        print("\n❌ Brain endpoint not responding. Start vllm-brain first.", file=sys.stderr)
        sys.exit(1)
    if not coder_ok:
        print(
            "\n⚠️  Coder endpoint not responding. Tasks will queue but not execute.", file=sys.stderr
        )

    # Initialize components
    queue = TaskQueue(get_db_path(project_root))
    memory = ProjectMemory(project_root)
    coder = CoderWorker(project_root, queue, memory)
    brain = BrainChat(project_root, queue, memory)

    # Graceful shutdown
    def shutdown(sig, frame):
        print("\n\n🛑 Shutting down...")
        brain.stop()
        coder.stop()
        counts = queue.get_counts()
        memory.log_event(
            "session_end", f"Final: ⏳{counts['pending']} ✅{counts['done']} ❌{counts['failed']}"
        )
        print(
            f"📊 Final: ⏳{counts['pending']} 🔧{counts['in_progress']} ✅{counts['done']} ❌{counts['failed']}"
        )
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start coder worker
    coder.start()
    print("  🔧 Coder worker: ✅ Started (Aider-backed, polling for tasks)")
    print()

    # Start brain chat (blocks — runs the interactive loop)
    brain.start()


if __name__ == "__main__":
    main()
