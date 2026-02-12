#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
Usage: ./deploy.sh [--no-cache] [--help]

Rebuild and (re)start the Docker Compose stack.

Options:
  --no-cache  Rebuild the image without using the cache
  --help      Show this help message
EOF
}

NO_CACHE=0

for arg in "$@"; do
  case "$arg" in
    --no-cache)
      NO_CACHE=1
      ;;
    --help|-h)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      show_help >&2
      exit 1
      ;;
  esac
done

ORIG_DIR="$(pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
trap 'cd "$ORIG_DIR"' EXIT
cd "$SCRIPT_DIR"

run() {
  "$@"
  local status=$?
  if [[ $status -ne 0 ]]; then
    echo "Command failed with exit code $status: $*" >&2
    exit 1
  fi
}

BUILD_ARGS=()
if [[ "$NO_CACHE" -eq 1 ]]; then
  BUILD_ARGS+=(--no-cache)
fi

run docker compose down
run docker compose build "${BUILD_ARGS[@]}"
run docker compose up -d
