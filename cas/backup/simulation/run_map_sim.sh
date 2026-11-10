#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CAS_REPO="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
export CAS_MAP_YAML="${CAS_MAP_YAML:-$CAS_REPO/map/fleet_world_new.yaml}"
export CAS_MASK_YAML="${CAS_MASK_YAML:-$CAS_REPO/map/fleet_x_keepout_new.yaml}"
exec bash "$SCRIPT_DIR/run_sim.sh" "$@"
