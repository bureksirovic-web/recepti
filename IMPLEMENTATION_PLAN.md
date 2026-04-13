# Implementation Plan: Orchestra Pipeline

## Overview

Orchestra is a pipeline that orchestrates interactions between two LLMs — **Brain** (strategic planning, review, and coordination) and **Coder** (code generation and file editing) — to enable autonomous, human-guided software development. The system is designed to be lightweight, self-contained, and extensible.

---

## Project Goals

- ✅ **Autonomous Task Execution**: Enable Brain to generate and queue tasks, and Coder to execute them.
- ✅ **Human-in-the-Loop**: Support real-time chat with Brain, and periodic review mode when idle.
- ✅ **Reliable Task Queue**: Use SQLite with WAL mode for safe concurrent access and persistence.
- ✅ **Undo & Audit Trail**: Track all changes via an undo journal and task history.
- ✅ **Minimal Dependencies**: Use only Python stdlib for core components (LLM client, task queue).
- ✅ **Extensibility**: Modular design to support future features (e.g., test runner, git integration).

---

## Core Architecture
