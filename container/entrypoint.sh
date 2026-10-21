#!/usr/bin/env bash
set -euo pipefail
: "${COMMAND:?OCI Raw must supply COMMAND}"
: "${PYTHON_VERSION:=3.12.15}"
uv python install "$PYTHON_VERSION"
uv venv --allow-existing --python "$PYTHON_VERSION" /opt/opengris-scaler
if [[ -n "${PYTHON_REQUIREMENTS:-}" ]]; then
  printf '%s\n' "$PYTHON_REQUIREMENTS" > /tmp/worker-requirements.txt
  uv pip install --python /opt/opengris-scaler/bin/python -r /tmp/worker-requirements.txt
fi
export PATH="/opt/opengris-scaler/bin:$PATH"
echo "Starting Scaler OCI Raw workers"
exec bash -c "$COMMAND"
