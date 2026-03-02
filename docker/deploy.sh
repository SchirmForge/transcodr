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
DEFAULT_PUID="$(id -u)"
DEFAULT_PGID="$(id -g)"
DEFAULT_CONFIG="$HOME/.config/transcodr"
DEFAULT_MEDIA="$HOME/Videos"
DEFAULT_ROOT_MEDIA="/media"
DEFAULT_TEMP="/tmp/transcodr"
DEFAULT_LOGS="/tmp/logs"
DEFAULT_HW_ACCEL="auto"
DEFAULT_GPU_MODE="none"

# ─── Load existing .env as defaults (re-runs keep previous choices) ───────────
if [[ -f "$ENV_FILE" ]]; then
  while IFS='=' read -r key value; do
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    case "$key" in
      TRANSCODR_PORT)       DEFAULT_PORT="$value"   ;;
      TRANSCODR_PUID)       DEFAULT_PUID="$value"   ;;
      TRANSCODR_PGID)       DEFAULT_PGID="$value"   ;;
      TRANSCODR_CONFIG_VOL) DEFAULT_CONFIG="$value" ;;
      TRANSCODR_MEDIA_VOL)  DEFAULT_MEDIA="$value"  ;;
      TRANSCODR_ROOT_MEDIA) DEFAULT_ROOT_MEDIA="$value" ;;
      TRANSCODR_TEMP_VOL)   DEFAULT_TEMP="$value"   ;;
      TRANSCODR_LOGS_VOL)   DEFAULT_LOGS="$value"   ;;
      TRANSCODR_HW_ACCEL)   DEFAULT_HW_ACCEL="$value" ;;
      TRANSCODR_GPU_MODE)   DEFAULT_GPU_MODE="$value" ;;
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
PUID="$(      ask "User ID (uid)"      "$DEFAULT_PUID")"
PGID="$(      ask "Group ID (gid)"     "$DEFAULT_PGID")"
CONFIG_VOL="$(      ask "Config volume path"          "$DEFAULT_CONFIG")"
ROOT_MEDIA_HOST="$( ask "Root media (host path)"      "$DEFAULT_MEDIA")"
ROOT_MEDIA_INST="$( ask "Root media (container path)" "$DEFAULT_ROOT_MEDIA")"
TEMP_VOL="$(  ask "Temp volume path"   "$DEFAULT_TEMP")"
LOGS_VOL="$(  ask "Logs volume path"   "$DEFAULT_LOGS")"
HW_ACCEL="$(  ask "Hardware accel (auto|vaapi|nvenc|qsv|none)" "$DEFAULT_HW_ACCEL")"
GPU_MODE="$(  ask "GPU passthrough (none|vaapi|nvidia)" "$DEFAULT_GPU_MODE")"

CONFIG_VOL="$(      expand_path "$CONFIG_VOL")"
ROOT_MEDIA_HOST="$( expand_path "$ROOT_MEDIA_HOST")"
TEMP_VOL="$(  expand_path "$TEMP_VOL")"
LOGS_VOL="$(  expand_path "$LOGS_VOL")"

# Normalize and validate hardware choices
HW_ACCEL="$(echo "$HW_ACCEL" | tr '[:upper:]' '[:lower:]')"
GPU_MODE="$(echo "$GPU_MODE" | tr '[:upper:]' '[:lower:]')"
case "$HW_ACCEL" in
  auto|vaapi|nvenc|qsv|none) ;;
  *) echo "Unknown hardware accel '$HW_ACCEL', defaulting to auto"; HW_ACCEL="auto" ;;
esac
case "$GPU_MODE" in
  none|vaapi|nvidia) ;;
  *) echo "Unknown GPU mode '$GPU_MODE', defaulting to none"; GPU_MODE="none" ;;
esac

# ─── Write .env ───────────────────────────────────────────────────────────────
cat > "$ENV_FILE" <<EOF
TRANSCODR_PORT=$PORT
TRANSCODR_PUID=$PUID
TRANSCODR_PGID=$PGID
TRANSCODR_CONFIG_VOL=$CONFIG_VOL
TRANSCODR_MEDIA_VOL=$ROOT_MEDIA_HOST
TRANSCODR_ROOT_MEDIA=$ROOT_MEDIA_INST
TRANSCODR_TEMP_VOL=$TEMP_VOL
TRANSCODR_LOGS_VOL=$LOGS_VOL
TRANSCODR_HW_ACCEL=$HW_ACCEL
TRANSCODR_GPU_MODE=$GPU_MODE
EOF

echo ""
echo "Saved to $ENV_FILE"
echo ""

# ─── Ensure config file exists and update root_media ──────────────────────────
CONFIG_FILE="$CONFIG_VOL/config.yaml"
DEFAULT_CONFIG_TEMPLATE="$SCRIPT_DIR/../src/config/default-config.yml"

if [[ ! -f "$CONFIG_FILE" ]]; then
  mkdir -p "$CONFIG_VOL"
  if [[ -f "$DEFAULT_CONFIG_TEMPLATE" ]]; then
    cp "$DEFAULT_CONFIG_TEMPLATE" "$CONFIG_FILE"
  fi
fi

if [[ -f "$CONFIG_FILE" ]]; then
  TMP_FILE="$(mktemp)"
  awk -v root="$ROOT_MEDIA_INST" '
    function print_root(){ printf "  root_media: %s\n", root }
    BEGIN{in_storage=0; done=0}
    /^[[:space:]]*storage:[[:space:]]*$/ {in_storage=1; print; next}
    in_storage && !done && /^[[:space:]]*root_media:[[:space:]]*/ {
        sub(/root_media:[[:space:]]*.*/, "root_media: " root)
        done=1
        print
        next
    }
    in_storage && !done && /^[^[:space:]]/ {
        print_root()
        done=1
        in_storage=0
    }
    {print}
    END{
      if(in_storage && !done){ print_root() }
      else if(!done){ printf "\nstorage:\n  root_media: %s\n", root }
    }
  ' "$CONFIG_FILE" > "$TMP_FILE"
  mv "$TMP_FILE" "$CONFIG_FILE"
fi

if [[ -f "$CONFIG_FILE" ]]; then
  TMP_FILE="$(mktemp)"
  awk -v accel="$HW_ACCEL" '
    function print_hw(){ printf "  hardware_accel: %s\n", accel }
    BEGIN{in_ff=0; done=0}
    /^[[:space:]]*ffmpeg:[[:space:]]*$/ {in_ff=1; print; next}
    in_ff && !done && /^[[:space:]]*hardware_accel:[[:space:]]*/ {
        sub(/hardware_accel:[[:space:]]*.*/, "hardware_accel: " accel)
        done=1
        print
        next
    }
    in_ff && !done && /^[^[:space:]]/ {
        print_hw()
        done=1
        in_ff=0
    }
    {print}
    END{
      if(in_ff && !done){ print_hw() }
      else if(!done){ printf "\nffmpeg:\n  hardware_accel: %s\n", accel }
    }
  ' "$CONFIG_FILE" > "$TMP_FILE"
  mv "$TMP_FILE" "$CONFIG_FILE"
fi

# ─── Optional GPU passthrough override ───────────────────────────────────────
OVERRIDE_FILE="$SCRIPT_DIR/docker-compose.override.yml"
case "$GPU_MODE" in
  vaapi)
    cat > "$OVERRIDE_FILE" <<'EOF'
services:
  transcodr:
    devices:
      - /dev/dri:/dev/dri
EOF
    ;;
  nvidia)
    cat > "$OVERRIDE_FILE" <<'EOF'
services:
  transcodr:
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
EOF
    ;;
  none|"")
    rm -f "$OVERRIDE_FILE"
    ;;
esac

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
