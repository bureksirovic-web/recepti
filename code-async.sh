#!/bin/bash
# Async dispatcher — sends coding tasks to the Coder GPU in the background
# Brain is FREE to continue planning/reviewing while Coder works

# Housekeeping: clean logs older than 7 days
find /workspace/logs/ -name "task_*.log" -type f -mtime +7 -delete 2>/dev/null

TASK_ID=$(date +%s)
LOG_FILE="/workspace/logs/task_${TASK_ID}.log"
mkdir -p /workspace/logs

echo "📋 Dispatched to Coder (GPU1). Task ID: ${TASK_ID}"
echo "📄 Log: ${LOG_FILE}"

nohup aider \
  --model openai/offline-coder \
  --openai-api-key local \
  --openai-api-base http://127.0.0.1:8001/v1 \
  --yes-always \
  --auto-commits \
  --no-show-model-warnings \
  --no-pretty \
  --analytics-disable \
  --message "$1" \
  "${@:2}" > "$LOG_FILE" 2>&1 &

echo "✅ Task $TASK_ID running in background (PID: $!)"
