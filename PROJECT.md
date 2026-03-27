# Recepti — Family Recipe Bot

## Overview
Telegram bot for recipe suggestions based on available ingredients.
Family of 9 (7 kids), balanced meals covering macro and micro nutrients for the whole day.

## Tech Stack
(To be decided during planning sessions)

## Architecture
(To be defined)

---

## System Directives for the Brain Agent

### Initialization
At the start of any new session, immediately run:
```bash
./init-env.sh
```
This ensures the Coder environment (Aider) is installed in the sandbox.

### Async Coding Delegation
You have a dedicated Coder AI running on GPU1 (Qwen3-Coder). Use these scripts:

**Dispatch a coding task (NON-BLOCKING):**
```bash
./code-async.sh "Create src/main.py with a FastAPI health check endpoint" --file src/main.py
```

**Check task status:**
```bash
./check-status.sh /workspace/logs/task_XXXXX.log
```

**List all recent tasks:**
```bash
./check-status.sh
```

### Delegation Rules
- After dispatching a task, **IMMEDIATELY** continue with other work (review, plan, test)
- Do **NOT** wait for the Coder to finish
- Check task status every 2-3 actions
- Review completed code by reading the file after checking status shows completion
- Use `git log --oneline -5` to see the Coder's commits

---

## Decisions Log
<!-- Brain adds architectural decisions here during sessions -->

## Progress
<!-- Brain updates this as features are completed -->
