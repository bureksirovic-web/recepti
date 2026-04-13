"""Dual-GPU Pipeline Orchestrator — Orchestra

A parallel coding pipeline:
  Brain (Nemotron 120B, GPU0) → plans, reviews, creates tasks
  Coder (Qwen3-Coder-Next, GPU1) → autonomously executes tasks

Usage:
  python -m orchestra --project ~/MyProject
  python -m orchestra  # uses current directory
"""
