#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  installer="$(mktemp)"
  trap 'rm -f -- "$installer"' EXIT
  curl --fail --silent --show-error --location https://astral.sh/uv/0.13.3/install.sh -o "$installer"
  sh "$installer"
fi
PYTHON_VERSION="${SCALER_PYTHON_VERSION:-$(cat "$ROOT/.python-version")}"
ENV_DIRECTORY="${SCALER_ENV_DIRECTORY:-$HOME/scaler-py312}"
uv python install "$PYTHON_VERSION"
if [[ ! -x "$ENV_DIRECTORY/bin/python" ]]; then
  uv venv --python "$PYTHON_VERSION" "$ENV_DIRECTORY"
fi
"$ENV_DIRECTORY/bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Use a Python 3.12 environment"'
uv pip install --python "$ENV_DIRECTORY/bin/python" -r "$ROOT/requirements-linux-amd64.lock"
printf '\nEnvironment ready. Activate it with:\n  source %q/bin/activate\n' "$ENV_DIRECTORY"
