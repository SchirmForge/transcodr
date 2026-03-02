#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

show_help() {
  cat <<'EOF'
Usage: ./deploy.sh [--no-cache] [--help]

Configure volumes, port, and user, then rebuild and (re)start the Docker Compose stack.
Settings are saved to docker/.env and reused as defaults on subsequent runs.

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

# ─── Defaults ────────────────────────────────────────────────────────────────
DEFAULT_PORT="8765"
DEFAULT_USER="$(id -u):$(id -g)"
DEFAULT_CONFIG="$HOME/.config/transcodr"
DEFAULT_MEDIA="$HOME/Videos/transcodr"
DEFAULT_TEMP="/tmp/transcodr"
DEFAULT_LOGS="/tmp/logs"

# ─── Load existing .env as defaults (re-runs keep previous choices) ───────────
if [[ -f "$ENV_FILE" ]]; then
  while IFS='=' read -r key value; do
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    case "$key" in
      TRANSCODR_PORT)       DEFAULT_PORT="$value"   ;;
      TRANSCODR_USER)       DEFAULT_USER="$value"   ;;
      TRANSCODR_CONFIG_VOL) DEFAULT_CONFIG="$value" ;;
      TRANSCODR_MEDIA_VOL)  DEFAULT_MEDIA="$value"  ;;
      TRANSCODR_TEMP_VOL)   DEFAULT_TEMP="$value"   ;;
      TRANSCODR_LOGS_VOL)   DEFAULT_LOGS="$value"   ;;
    esac
  done < "$ENV_FILE"
fi

# ─── Interactive prompts ──────────────────────────────────────────────────────
ask() {
  local prompt="$1" default="$2" reply
  read -r -p "$prompt [$default]: " reply
  echo "${reply:-$default}"
}

# Expand ~ to $HOME (Docker Compose does not expand ~ in .env values)
expand_path() {
  local p="$1"
  case "$p" in
    "~/"*) echo "$HOME/${p:2}" ;;
    "~")   echo "$HOME"        ;;
    *)     echo "$p"           ;;
  esac
}

echo ""
echo "=== Transcodr Docker Configuration ==="
echo "Press Enter to accept the value shown in brackets."
echo ""

PORT="$(      ask "Host port"          "$DEFAULT_PORT")"
USER_VAL="$(  ask "User (uid:gid)"     "$DEFAULT_USER")"
CONFIG_VOL="$(ask "Config volume path" "$DEFAULT_CONFIG")"
MEDIA_VOL="$( ask "Media volume path"  "$DEFAULT_MEDIA")"
TEMP_VOL="$(  ask "Temp volume path"   "$DEFAULT_TEMP")"
LOGS_VOL="$(  ask "Logs volume path"   "$DEFAULT_LOGS")"

CONFIG_VOL="$(expand_path "$CONFIG_VOL")"
MEDIA_VOL="$( expand_path "$MEDIA_VOL")"
TEMP_VOL="$(  expand_path "$TEMP_VOL")"
LOGS_VOL="$(  expand_path "$LOGS_VOL")"

# ─── Write .env ───────────────────────────────────────────────────────────────
cat > "$ENV_FILE" <<EOF
TRANSCODR_PORT=$PORT
TRANSCODR_USER=$USER_VAL
TRANSCODR_CONFIG_VOL=$CONFIG_VOL
TRANSCODR_MEDIA_VOL=$MEDIA_VOL
TRANSCODR_TEMP_VOL=$TEMP_VOL
TRANSCODR_LOGS_VOL=$LOGS_VOL
EOF

echo ""
echo "Saved to $ENV_FILE"
echo ""

# ─── Build and deploy ─────────────────────────────────────────────────────────
ORIG_DIR="$(pwd)"
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
