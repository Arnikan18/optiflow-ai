#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}" || exit 1

COMPOSE_PROFILE="${COMPOSE_PROFILE:-full-stack}"
TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-3}"

load_env() {
  local env_file="${REPO_ROOT}/.env"
  [[ -f "${env_file}" ]] || return
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

RESULTS=()

record_result() {
  RESULTS+=("$1|$2|$3|$4|$5|$6")
}

check_http() {
  local name="$1"
  local url="$2"
  local parse_overall="${3:-0}"
  local body_file
  body_file="$(mktemp)"
  local metrics http_code time_total status message
  metrics="$(curl --silent --show-error --max-time "${TIMEOUT_SECONDS}" -o "${body_file}" -w '%{http_code} %{time_total}' "${url}" 2>"${body_file}.err")"
  local curl_code=$?
  if [[ ${curl_code} -ne 0 ]]; then
    message="$(cat "${body_file}.err")"
    record_result "${name}" "${url}" "UNHEALTHY" "" "" "${message}"
    rm -f "${body_file}" "${body_file}.err"
    return
  fi

  http_code="${metrics%% *}"
  time_total="${metrics#* }"
  if [[ "${http_code}" =~ ^2 ]]; then
    status="HEALTHY"
    message="HTTP ${http_code}"
  else
    status="UNHEALTHY"
    message="HTTP ${http_code}"
  fi

  if [[ "${parse_overall}" == "1" ]]; then
    if grep -q '"overall_status"[[:space:]]*:[[:space:]]*"HEALTHY"' "${body_file}"; then
      status="HEALTHY"
      message="aggregate overall_status=HEALTHY"
    elif grep -q '"overall_status"[[:space:]]*:[[:space:]]*"DEGRADED"' "${body_file}"; then
      status="DEGRADED"
      message="aggregate overall_status=DEGRADED"
    elif grep -q '"overall_status"[[:space:]]*:[[:space:]]*"UNHEALTHY"' "${body_file}"; then
      status="UNHEALTHY"
      message="aggregate overall_status=UNHEALTHY"
    fi
  fi

  record_result "${name}" "${url}" "${status}" "${time_total}s" "${http_code}" "${message}"
  rm -f "${body_file}" "${body_file}.err"
}

check_postgres() {
  local start end duration
  start="$(date +%s)"
  if docker compose --profile "${COMPOSE_PROFILE}" exec -T postgres pg_isready -U "${POSTGRES_USER:-optiflow}" -d "${POSTGRES_DB:-optiflow}" >/tmp/optiflow-pg-health.txt 2>&1; then
    end="$(date +%s)"
    duration=$((end - start))
    record_result "postgres" "docker compose exec pg_isready" "HEALTHY" "${duration}s" "" "pg_isready passed"
  else
    end="$(date +%s)"
    duration=$((end - start))
    record_result "postgres" "docker compose exec pg_isready" "UNHEALTHY" "${duration}s" "" "$(cat /tmp/optiflow-pg-health.txt)"
  fi
}

load_env

CORE_URL="$(core_url)"

check_postgres
check_http "core-api" "${CORE_URL}/health"
check_http "core-demo-health" "${CORE_URL}/api/v1/demo/health" 1
check_http "crm-service" "$(local_base_url CRM_SERVICE_PORT 8101)/health"
check_http "incident-service" "$(local_base_url INCIDENT_SERVICE_PORT 8102)/health"
check_http "workforce-service" "$(local_base_url WORKFORCE_SERVICE_PORT 8103)/health"
check_http "communication-service" "$(local_base_url COMMUNICATION_SERVICE_PORT 8104)/health"

overall="HEALTHY"
for result in "${RESULTS[@]}"; do
  IFS='|' read -r _name _check status _response _http _message <<< "${result}"
  if [[ "${status}" == "UNHEALTHY" ]]; then
    overall="UNHEALTHY"
  elif [[ "${status}" == "DEGRADED" && "${overall}" == "HEALTHY" ]]; then
    overall="DEGRADED"
  fi
done

echo "OptiFlow health check"
printf '%-24s %-52s %-10s %-12s %-8s %s\n' "Component" "Check" "Status" "Response" "HTTP" "Message"
for result in "${RESULTS[@]}"; do
  IFS='|' read -r name check status response http message <<< "${result}"
  printf '%-24s %-52s %-10s %-12s %-8s %s\n' "${name}" "${check}" "${status}" "${response}" "${http}" "${message}"
done
echo "Overall: ${overall}"

if [[ "${overall}" == "HEALTHY" ]]; then
  exit 0
fi
exit 1
