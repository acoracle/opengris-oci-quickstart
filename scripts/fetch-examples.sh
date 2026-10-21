#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
COMMIT=c0068ccba6cd004944afbd2f1bc3ba54291cfecf
DESTINATION="$ROOT/_upstream/montecarlo"
mkdir -p "$ROOT/_upstream"
if [[ ! -d "$DESTINATION/.git" ]]; then
  git clone https://github.com/dezma/oci-monte-carlo-quickstart.git "$DESTINATION"
fi
if [[ -n "$(git -C "$DESTINATION" status --porcelain)" ]]; then
  echo "Upstream checkout has local changes; preserve them before fetching examples." >&2
  exit 1
fi
git -C "$DESTINATION" cat-file -e "$COMMIT^{commit}" 2>/dev/null || git -C "$DESTINATION" fetch origin "$COMMIT"
git -C "$DESTINATION" checkout --detach "$COMMIT"
printf 'Monte Carlo source pinned to %s\n' "$COMMIT"
