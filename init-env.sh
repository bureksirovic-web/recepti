#!/bin/bash
# Bootstrap script — run at start of every new session
# Survives sandbox resets because it lives in /workspace (persistent mount)

if ! command -v aider &> /dev/null; then
    echo "🔧 Aider not found in sandbox. Installing..."
    pip install aider-chat
else
    echo "✅ Aider is ready."
fi

# Ensure scripts are executable
chmod +x /workspace/code-async.sh 2>/dev/null
chmod +x /workspace/check-status.sh 2>/dev/null

# Ensure logs directory exists
mkdir -p /workspace/logs

echo "✅ Environment initialized."
