# Dual-GPU Local Coding Platform — Final Plan

## Goal

A fully local, "set it and forget it" coding platform that:
- Replaces cloud AI coding assistants permanently
- Uses **both GPUs in true parallel** (not sequential)
- Tracks progress and stores context across days
- Swap models in the future without changing anything else

## Hardware

| GPU | Model | Port | Role |
|-----|-------|------|------|
| GPU0 | Nemotron 120B (NVFP4) | 8002 | **Brain** — planning, review, orchestration |
| GPU1 | Qwen3-Coder-Next (NVFP4) | 8001 | **Coder** — code generation via Aider |

Both served via vLLM as systemd user services.

## Why OpenHands + Async Aider (Not CrewAI / LangGraph)

| Tool | What it is | Terminal/File/Git | Persistent State | Async Multi-GPU | Verdict |
|------|-----------|-------------------|-----------------|-----------------|---------|
| **OpenHands** | Complete coding agent | ✅ Built-in | ✅ Across sessions | ⚠️ Via async dispatch | **Best product** |
| **CrewAI** | Orchestration framework | ❌ Must build | ❌ Must build | ✅ Native `async_execution` | Framework, not product |
| **LangGraph** | Graph framework | ❌ Must build | ❌ Must build | ✅ Native asyncio | Framework, not product |
| **Aider** | Code editor CLI | ✅ Git/diffs | ❌ No cross-session | ❌ Sequential only | Tool, not platform |

**Decision:** CrewAI and LangGraph are frameworks — you'd need to build all the coding agent tooling (file editing, terminal, git, sandbox, UI) from scratch on top of them. That's months of work. OpenHands ships with all of it. The only gap is async dispatch, which is solved with a 15-line shell script.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│               OpenHands (Docker, port 3000)               │
│               Persistent state: ~/.openhands-state        │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ CodeActAgent (Brain — Nemotron 120B, GPU0)         │  │
│  │  • Plans architecture with user                    │  │
│  │  • Reviews code, runs tests, configures stack      │  │
│  │  • Dispatches coding tasks ASYNCHRONOUSLY          │  │
│  │  • Checks task completion, reviews results         │  │
│  └──────────┬──────────────────────────┬──────────────┘  │
│             │ dispatch (non-blocking)   │ check status    │
│  ┌──────────▼──────────────────────────▼──────────────┐  │
│  │ code-async.sh → nohup aider (Coder, GPU1)         │  │
│  │  • Runs in background, writes to log file          │  │
│  │  • Auto-commits to git with descriptive messages   │  │
│  │  • Brain is FREE to do other work while this runs  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  check-status.sh → tails the log file for completion     │
└──────────────────────────────────────────────────────────┘
```

### True Parallelism Flow

```
Timeline:
  Brain (GPU0): [Plan feature A] [Dispatch to Coder] [Review file B] [Check A status] [Plan C]...
  Coder (GPU1):                  [████ Writing A ████████████████████] [████ Writing C ████]
                                  ↑ non-blocking                       ↑ next task
```

Both GPUs are active simultaneously. Brain never blocks waiting for Coder.

## Implementation Steps

### Phase 1: Reconfigure OpenHands Container

Stop the current container and restart with proper workspace mounting:

```bash
docker stop openhands && docker rm openhands

docker run -d \
  --name openhands \
  --network=host \
  -e SANDBOX_RUNTIME_CONTAINER_IMAGE=ghcr.io/all-hands-ai/runtime:latest \
  -e SANDBOX_VOLUMES="/home/tomi/Recepti:/workspace:rw" \
  -e LOG_ALL_EVENTS=true \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /home/tomi/.openhands-state:/.openhands-state \
  ghcr.io/all-hands-ai/openhands:latest
```

Configure in UI (http://localhost:3000 → Settings):
```
Custom Model: openai/offline-brain
Base URL:     http://127.0.0.1:8002/v1
API Key:      local
```

### Phase 2: Install Aider + Async Scripts in Sandbox

From the OpenHands terminal:

```bash
pip install aider-chat
mkdir -p /workspace/logs
```

**Async dispatcher** (`/workspace/code-async.sh`):
```bash
#!/bin/bash
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
```

**Status checker** (`/workspace/check-status.sh`):
```bash
#!/bin/bash
if [ -z "$1" ]; then
  echo "Recent task logs:"
  ls -lt /workspace/logs/ | head -10
else
  tail -n 20 "$1"
fi
```

### Phase 3: System Prompt Directive

Add to `PROJECT.md` in the workspace root (Brain reads this):

```markdown
## Async Coding Delegation

You have a dedicated Coder AI on GPU1. Use these scripts:

### Dispatch a coding task (NON-BLOCKING):
./code-async.sh "Create src/main.py with FastAPI health check" --file src/main.py

### Check task status:
./check-status.sh /workspace/logs/task_XXXXX.log

### Rules:
- After dispatching, IMMEDIATELY continue with other work
- Do NOT wait for the Coder to finish
- Check status periodically (every 2-3 actions)
- Review completed code before moving to next feature
```

### Phase 4: Verify

1. Open http://localhost:3000
2. Tell Brain: "Create a requirements.txt with fastapi and python-telegram-bot"
3. Verify Brain dispatches via `code-async.sh` (non-blocking)
4. While Coder works, ask Brain to review the project structure
5. Brain checks status, confirms Coder committed
6. Run `nvidia-smi` — both GPUs should show load
7. Close browser, reopen — conversation history preserved

## Swapping Models in the Future

| What to change | Where |
|----------------|-------|
| Brain model | OpenHands UI → Settings → Custom Model + Base URL |
| Coder model | Edit `code-async.sh` → change `--model` and `--openai-api-base` |
| vLLM services | `~/.config/systemd/user/vllm-brain.service` / `vllm-coder.service` |

No code changes needed. Just update model names and restart services.

## Risks

| Risk | Mitigation |
|------|-----------|
| Brain forgets to check async logs | System prompt directive + periodic reminders |
| Aider not available in sandbox | Install via pip at container startup |
| Network isolation in sandbox | `--network=host` solves this |
| Context exhaustion on long sessions | Memory condenser enabled (120 events) |
| Sandbox loses installed packages | Use custom sandbox image or reinstall script |
