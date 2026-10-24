#!/bin/bash
set -e
task_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$task_root"
export PYTHONFAULTHANDLER=1
exec ../.venv/bin/python -m vn_assistant.cli serve --host 127.0.0.1 --port "${PORT:-8001}"
