#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}" || exit 1

COMPOSE_PROFILE="${COMPOSE_PROFILE:-full-stack}"
RECREATE_VOLUMES=0
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --recreate-volumes)
      RECREATE_VOLUMES=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: ./scripts/reset-demo.sh [--recreate-volumes] [--force]"
      exit 2
      ;;
  esac
done

load_env() {
  local env_file="${REPO_ROOT}/.env"
  if [[ ! -f "${env_file}" ]]; then
    echo "No .env file found. Using current process environment."
    return
  fi

  while IFS='=' read -r key value || [[ -n "${key:-}" ]]; do
    key="$(printf '%s' "${key}" | tr -d '\r' | xargs)"
    value="$(printf '%s' "${value:-}" | tr -d '\r')"
    [[ -z "${key}" || "${key}" == \#* ]] && continue
    [[ "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    export "${key}=${value}"
  done < "${env_file}"
}

assert_docker_compose() {
  command -v docker >/dev/null 2>&1 || { echo "Docker CLI is not available on PATH."; exit 1; }
  docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is not available."; exit 1; }
}

local_base_url() {
  local port_var="$1"
  local default_port="$2"
  local port="${!port_var:-${default_port}}"
  printf 'http://localhost:%s' "${port}"
}

core_url() {
  if [[ -n "${VITE_CORE_API_URL:-}" ]]; then
    printf '%s' "${VITE_CORE_API_URL%/}"
  else
    local_base_url CORE_API_PORT 8000
  fi
}

assert_running_services() {
  local required=(postgres core-api frontend crm-service incident-service workforce-service communication-service)
  local running
  if ! running="$(docker compose --profile "${COMPOSE_PROFILE}" ps --services --filter status=running 2>/dev/null)"; then
    echo "Could not read Docker Compose service status."
    exit 1
  fi

  local missing=()
  for service in "${required[@]}"; do
    if ! printf '%s\n' "${running}" | grep -qx "${service}"; then
      missing+=("${service}")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Required services are not running: ${missing[*]}"
    echo "Start with: docker compose --profile ${COMPOSE_PROFILE} up --build -d"
    exit 1
  fi
}

post_json() {
  local url="$1"
  local body="${2:-{}}"
  shift 2 || true
  curl --fail --silent --show-error --max-time 10 \
    -H "Content-Type: application/json" \
    "$@" \
    -X POST "${url}" \
    --data "${body}"
}

wait_core_ready() {
  local url="$1"
  local deadline=$((SECONDS + 90))
  until curl --fail --silent --max-time 3 "${url}/health" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "Core API did not become healthy at ${url}/health."
      exit 1
    fi
    sleep 2
  done
}

admin_reset_fallback() {
  if [[ -z "${ADMIN_API_KEY:-}" ]]; then
    echo "Core reset failed and ADMIN_API_KEY is not available for fallback service resets."
    exit 1
  fi

  local request_id="reset-demo-$(date -u +%Y%m%d%H%M%S)"
  local services=(
    "crm $(local_base_url CRM_SERVICE_PORT 8101)/admin/reset"
    "incident $(local_base_url INCIDENT_SERVICE_PORT 8102)/admin/reset"
    "workforce $(local_base_url WORKFORCE_SERVICE_PORT 8103)/admin/reset"
    "communication $(local_base_url COMMUNICATION_SERVICE_PORT 8104)/admin/reset"
  )

  local item name url
  for item in "${services[@]}"; do
    name="${item%% *}"
    url="${item#* }"
    echo "Resetting ${name} through admin API..."
    post_json "${url}" "{}" -H "X-Admin-Key: ${ADMIN_API_KEY}" -H "X-Request-ID: ${request_id}" >/dev/null
  done
}

load_env
assert_docker_compose

if [[ "${APP_ENV:-}" == "production" && "${FORCE}" -ne 1 ]]; then
  echo "APP_ENV=production. Refusing to reset without --force."
  exit 1
fi

CORE_URL="$(core_url)"

echo "OptiFlow demo reset starting."
echo "Compose profile: ${COMPOSE_PROFILE}"
echo "Core API: ${CORE_URL}"

if [[ "${RECREATE_VOLUMES}" -eq 1 ]]; then
  echo "WARNING: this will stop the full stack and delete Docker Compose volumes for this project."
  if [[ "${FORCE}" -ne 1 ]]; then
    read -r -p "Type RECREATE to continue: " confirmation
    if [[ "${confirmation}" != "RECREATE" ]]; then
      echo "Destructive reset cancelled."
      exit 1
    fi
  fi
  docker compose --profile "${COMPOSE_PROFILE}" down -v || exit 1
  docker compose --profile "${COMPOSE_PROFILE}" up --build -d || exit 1
  wait_core_ready "${CORE_URL}"
fi

assert_running_services

# Normal path: ask Core to reset demo state. Core keeps admin credentials server-side.
echo "Calling Core demo reset endpoint..."
if ! reset_response="$(post_json "${CORE_URL}/api/v1/demo/simulation/reset" "{}" 2>/tmp/optiflow-reset-error.txt)"; then
  echo "Core reset failed: $(cat /tmp/optiflow-reset-error.txt)"
  echo "Trying direct service admin reset fallback..."
  admin_reset_fallback
else
  if printf '%s' "${reset_response}" | grep -q '"degraded"[[:space:]]*:[[:space:]]*true'; then
    echo "Core reset completed in degraded mode. Trying direct service admin reset fallback..."
    admin_reset_fallback
  fi
fi

if state_response="$(curl --fail --silent --show-error --max-time 10 "${CORE_URL}/api/v1/demo/simulation/state" 2>/tmp/optiflow-reset-state-error.txt)"; then
  if printf '%s' "${state_response}" | grep -q '"degraded"[[:space:]]*:[[:space:]]*true'; then
    echo "Simulation state is degraded after reset."
    exit 1
  fi
  echo "Simulation state checked."
else
  echo "Reset completed, but simulation state could not be read: $(cat /tmp/optiflow-reset-state-error.txt)"
fi

echo "Demo reset completed successfully."
exit 0
