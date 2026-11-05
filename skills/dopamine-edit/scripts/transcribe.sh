#!/usr/bin/env bash
# dopamine-edit — Whisper transcription wrapper.
#
# HyperFrames drives whisper.cpp locally. This wrapper fixes the common
# libwhisper.so.1 load failure for a user-local install (binaries in
# ~/.local/bin, libraries in ~/.local/lib) and falls back to the other
# installed engine when Whisper cannot start.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SKILL_DIR/scripts/hf.sh"

usage() {
  cat <<'EOF'
Usage: transcribe.sh <audio-or-video> [options]

  --model <name>        Whisper model (default: multilingual small)
                        tiny.en base.en small.en medium.en small medium large-v3
  --language <code>     Spoken language, e.g. en, hi, es, ja
  --to srt|vtt          Also write a caption sidecar
  --output <path>       Sidecar path (with --to)
  --engine <name>       whisper (default); auto/parakeet require --language en
  --no-fallback         Do not retry English speech with `auto` if Whisper fails
  --optional            Exit 0 with no transcript if ASR is unavailable
  --json                Machine-readable result
  --quiet               Less wrapper chatter

Examples:
  transcribe.sh assets/source.mp4 --json
  transcribe.sh assets/source.mp4 --language en --model medium.en --json \
    --to srt --output assets/audio/transcript.srt
  transcribe.sh assets/source.mp4 --language hi --engine whisper
EOF
}

[ "${1:-}" = '--help' ] && { usage; exit 0; }
[ $# -lt 1 ] && { usage; exit 2; }
INPUT="$1"; shift

MODEL="small"
LANGUAGE=""
TO=""
OUTPUT=""
ENGINE="whisper"
JSON=0
OPTIONAL=0
FALLBACK=1
QUIET=0

while [ $# -gt 0 ]; do
  case "$1" in
    --model|--language|--to|--output|--engine)
      [ $# -ge 2 ] && [[ "$2" != --* ]] && [ -n "$2" ] || {
        echo "ERROR: $1 requires a value" >&2; exit 2;
      } ;;
  esac
  case "$1" in
    --model) MODEL="${2:-}"; shift 2 ;;
    --language) LANGUAGE="${2:-}"; shift 2 ;;
    --to) TO="${2:-}"; shift 2 ;;
    --output) OUTPUT="${2:-}"; shift 2 ;;
    --engine) ENGINE="${2:-}"; shift 2 ;;
    --no-fallback) FALLBACK=0; shift ;;
    --optional) OPTIONAL=1; shift ;;
    --json) JSON=1; shift ;;
    --quiet) QUIET=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

case "$ENGINE" in whisper|auto|parakeet) ;; *) echo 'ERROR: invalid engine' >&2; exit 2 ;; esac
if [ "$ENGINE" != whisper ] && [ "$LANGUAGE" != en ]; then
  echo 'ERROR: auto/parakeet requires --language en in this wrapper; use multilingual Whisper for Hindi/mixed/unknown speech' >&2
  exit 2
fi
case "$TO" in ''|srt|vtt) ;; *) echo 'ERROR: --to must be srt or vtt' >&2; exit 2 ;; esac
if [[ "$MODEL" == *.en ]] && [ "$LANGUAGE" != 'en' ]; then
  echo 'ERROR: .en models require --language en; use small/medium for Hindi, mixed or unknown speech' >&2
  exit 2
fi
if [ -n "$OUTPUT" ]; then
  [ -n "$TO" ] || { echo 'ERROR: --output requires --to' >&2; exit 2; }
  mkdir -p "$(dirname "$OUTPUT")"
fi

command -v npx >/dev/null 2>&1 || { echo "ERROR: missing npx" >&2; exit 1; }
[ -f "$INPUT" ] || { echo "ERROR: input not found: $INPUT" >&2; exit 2; }

# whisper.cpp installed under ~/.local needs its private lib dir on the loader
# path. This is the difference between "installed" and "working".
if [ -e "$HOME/.local/lib/libwhisper.so.1" ] || [ -e "$HOME/.local/lib/libwhisper.so" ]; then
  export LD_LIBRARY_PATH="$HOME/.local/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

  # Newer whisper.cpp/ggml loads the CPU backend as a separate .so. Without
  # GGML_BACKEND_PATH it only searches /usr/lib/ggml and aborts with
  # "GGML_ASSERT(device) failed". Pick a backend this CPU can actually run.
  if [ -z "${GGML_BACKEND_PATH:-}" ] && [ -d "$HOME/.local/lib/ggml" ]; then
    if grep -qw avx2 /proc/cpuinfo 2>/dev/null && [ -e "$HOME/.local/lib/ggml/libggml-cpu-haswell.so" ]; then
      export GGML_BACKEND_PATH="$HOME/.local/lib/ggml/libggml-cpu-haswell.so"
    elif [ -e "$HOME/.local/lib/ggml/libggml-cpu-x64.so" ]; then
      export GGML_BACKEND_PATH="$HOME/.local/lib/ggml/libggml-cpu-x64.so"
    fi
  fi
fi

if [ "$ENGINE" = "whisper" ]; then
  if ! command -v whisper-cli >/dev/null 2>&1 && ! command -v whisper-cpp >/dev/null 2>&1; then
    [ "$FALLBACK" -eq 1 ] && [ "$LANGUAGE" = en ] || {
      echo 'ERROR: Whisper unavailable; refusing non-English/unknown-language engine fallback' >&2; exit 3;
    }
    echo "WARN: whisper-cli/whisper-cpp not found; trying --engine auto" >&2
    ENGINE="auto"
  fi
fi

ARGS=("${HF[@]}" transcribe "$INPUT" --engine "$ENGINE" --model "$MODEL" --no-runtime-install --json)
[ -n "$LANGUAGE" ] && ARGS+=(--language "$LANGUAGE")
[ -n "$TO" ] && ARGS+=(--to "$TO")
[ -n "$OUTPUT" ] && ARGS+=(--output "$OUTPUT")
[ "$OPTIONAL" -eq 1 ] && ARGS+=(--optional)

run() {
  set +e
  "${ARGS[@]}"
  local status=$?
  set -e
  return "$status"
}

[ "$QUIET" -eq 1 ] || echo "transcribe: engine=$ENGINE model=$MODEL input=$(basename "$INPUT")" >&2

if run; then
  exit 0
fi

if [ "$FALLBACK" -eq 1 ] && [ "$ENGINE" = "whisper" ] && [ "$LANGUAGE" = en ]; then
  echo "WARN: whisper failed; retrying with --engine auto (Parakeet if installed)" >&2
  ARGS=("${HF[@]}" transcribe "$INPUT" --engine auto --model "$MODEL" --no-runtime-install --json)
  [ -n "$LANGUAGE" ] && ARGS+=(--language "$LANGUAGE")
  [ -n "$TO" ] && ARGS+=(--to "$TO")
  [ -n "$OUTPUT" ] && ARGS+=(--output "$OUTPUT")
  [ "$OPTIONAL" -eq 1 ] && ARGS+=(--optional)
  if run; then
    exit 0
  fi
fi

if [ "$OPTIONAL" -eq 1 ]; then
  echo "transcribe: unavailable; continuing without a transcript (optional)" >&2
  exit 0
fi

echo "ERROR: transcription failed." >&2
echo "  Check: whisper-cli --version   (needs LD_LIBRARY_PATH=$HOME/.local/lib)" >&2
echo "  Or:    npx hyperframes models install parakeet" >&2
exit 3
