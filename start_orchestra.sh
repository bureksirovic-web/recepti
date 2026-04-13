#!/bin/bash
# Launch Orchestra — Dual-GPU Coding Pipeline
# Usage: ./start_orchestra.sh ~/MyProject

PROJECT_DIR="${1:-$(pwd)}"

echo "Starting Orchestra for: $PROJECT_DIR"

cd "$(dirname "$0")"
python3 -m orchestra --project "$PROJECT_DIR"
