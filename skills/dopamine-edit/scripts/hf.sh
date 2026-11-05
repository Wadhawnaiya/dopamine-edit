#!/usr/bin/env bash
# Source this from helpers: never call the possibly-desktop bare `hyperframes`.
export HYPERFRAMES_NO_OPTIONAL_INSTALL=1
HF=(npx hyperframes)
if [ -n "${DOPAMINE_HF_VERSION:-}" ]; then
  [[ "$DOPAMINE_HF_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-+][A-Za-z0-9.-]+)?$ ]] || {
    echo 'ERROR: DOPAMINE_HF_VERSION must be an exact version, e.g. 0.9.15' >&2
    exit 2
  }
  HF=(npx "hyperframes@$DOPAMINE_HF_VERSION")
fi
