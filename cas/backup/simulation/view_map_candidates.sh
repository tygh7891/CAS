#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CAS_REPO="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
CAS_SIM_WS="${CAS_SIM_WS:-$HOME/CAS_sim_ws}"
exec python3 "$SCRIPT_DIR/../operator_app/launch.py" \
  --map "${CAS_MAP_YAML:-$CAS_REPO/map/fleet_world_new.yaml}" \
  --mask "${CAS_MASK_YAML:-$CAS_REPO/map/fleet_x_keepout_new.yaml}" \
  --mask-role allowed --candidates "$CAS_SIM_WS/generated_map/scenario.candidates.json" "$@"
