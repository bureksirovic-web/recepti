#!/bin/bash
# Status checker — Brain uses this to check if a Coder task finished

if [ -z "$1" ]; then
  echo "📋 Recent task logs:"
  ls -lt /workspace/logs/task_*.log 2>/dev/null | head -10
  echo ""
  echo "Usage: ./check-status.sh /workspace/logs/task_XXXXX.log"
else
  echo "📄 Last 20 lines of $1:"
  echo "---"
  tail -n 20 "$1"
  echo "---"
  # Check if aider process is still running for this log
  if pgrep -f "aider.*$(basename $1 .log | sed 's/task_//')" > /dev/null 2>&1; then
    echo "⏳ Task still running..."
  else
    echo "✅ Task completed."
  fi
fi
