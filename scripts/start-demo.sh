#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

FRESH=0
FORCE=0
SKIP_BUILD=0
SKIP_SEED=0
PREFERENCE_PROFILE="SLA_FIRST"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fresh) FRESH=1 ;;
    --force) FORCE=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    --skip-seed) SKIP_SEED=1 ;;
    --preference-profile)
      shift
      PREFERENCE_PROFILE="${1:-}"
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: ./scripts/start-demo.sh [--fresh] [--force] [--skip-build] [--skip-seed] [--preference-profile SLA_FIRST]"
      exit 2
      ;;
  esac
  shift
done

command -v docker >/dev/null 2>&1 || { echo "Docker is required."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required."; exit 1; }

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example."
fi

if [[ "${FRESH}" -eq 1 ]]; then
  echo "Fresh mode removes only this project's Docker volumes and recreates all demo databases."
  if [[ "${FORCE}" -ne 1 ]]; then
    read -r -p "Type FRESH to continue: " confirmation
    [[ "${confirmation}" == "FRESH" ]] || { echo "Fresh container setup cancelled."; exit 1; }
  fi
  docker compose --profile full-stack down --volumes --remove-orphans
fi

up_args=(--profile full-stack up -d --wait)
if [[ "${SKIP_BUILD}" -ne 1 ]]; then
  up_args+=(--build)
fi

echo "Starting the complete OptiFlow stack in containers..."
docker compose "${up_args[@]}"

if [[ "${SKIP_SEED}" -ne 1 ]]; then
  "${SCRIPT_DIR}/reset-demo.sh"
  if [[ -n "${PREFERENCE_PROFILE}" ]]; then
    docker compose --profile full-stack exec -T core-api \
      python -m scripts.seed_preference_demo \
      --profile "${PREFERENCE_PROFILE}" \
      --apply
  fi
fi

echo
echo "OptiFlow is ready. Every service is running in Docker."
echo "Application: http://localhost:3000"
echo "Core health: http://localhost:8000/health"
echo "Stop: docker compose --profile full-stack down"
echo "Start again: docker compose --profile full-stack up -d --wait"
