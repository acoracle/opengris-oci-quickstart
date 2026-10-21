#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "$0")" && pwd -P)"
exec "${MCQS_PYTHON:-python}" "${SCRIPT_DIRECTORY}/run_example.py" "$@"
