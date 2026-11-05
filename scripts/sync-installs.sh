#!/usr/bin/env bash
# Repo-level wrapper: refresh every installed agent copy from this checkout.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$ROOT/skills/dopamine-edit/scripts/sync-installs.sh" "$@"
