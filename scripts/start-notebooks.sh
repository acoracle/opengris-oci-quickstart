#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
ENV_DIRECTORY="${SCALER_ENV_DIRECTORY:-$HOME/scaler-py312}"
if [[ ! -x "$ENV_DIRECTORY/bin/python" ]]; then
  echo "Install the environment first: bash scripts/install-environment.sh" >&2
  exit 1
fi
cd "$ROOT/examples/notebooks"
exec "$ENV_DIRECTORY/bin/python" -m jupyterlab --no-browser --ip=127.0.0.1 \
  --port="${JUPYTER_PORT:-8888}" --ServerApp.root_dir="$PWD" "$@"
