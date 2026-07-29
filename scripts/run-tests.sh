#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}" || exit 1

MODE="all"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --mode=*)
      MODE="${1#--mode=}"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: ./scripts/run-tests.sh [--mode unit|integration|all]"
      exit 2
      ;;
  esac
done

if [[ "${MODE}" != "unit" && "${MODE}" != "integration" && "${MODE}" != "all" ]]; then
  echo "Mode must be one of: unit, integration, all"
  exit 2
fi

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

resolve_python() {
  local dir="$1"
  local candidates=()
  [[ -n "${PYTHON:-}" ]] && candidates+=("${PYTHON}")
  candidates+=("${dir}/.venv/Scripts/python.exe")
  candidates+=("${dir}/.venv/bin/python")
  candidates+=("${REPO_ROOT}/.venv/Scripts/python.exe")
  candidates+=("${REPO_ROOT}/.venv/bin/python")
  candidates+=("${REPO_ROOT}/tools/crm-service/.venv/Scripts/python.exe")
  candidates+=("${REPO_ROOT}/tools/crm-service/.venv/bin/python")
  candidates+=("${REPO_ROOT}/tools/incident-service/.venv/Scripts/python.exe")
  candidates+=("${REPO_ROOT}/tools/incident-service/.venv/bin/python")
  candidates+=("${REPO_ROOT}/tools/workforce-service/.venv/Scripts/python.exe")
  candidates+=("${REPO_ROOT}/tools/workforce-service/.venv/bin/python")
  candidates+=("${REPO_ROOT}/tools/communication-service/.venv/Scripts/python.exe")
  candidates+=("${REPO_ROOT}/tools/communication-service/.venv/bin/python")

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -x "${candidate}" || -f "${candidate}" ]]; then
      printf '%s' "${candidate}"
      return 0
    fi
  done
  command -v python || return 1
}

run_suite() {
  local name="$1"
  local dir="$2"
  local test_path="$3"

  if [[ ! -d "${dir}/${test_path}" ]]; then
    RESULTS+=("${name}|FAILED|0|Missing required test path: ${dir}/${test_path}")
    return
  fi

  local python
  if ! python="$(resolve_python "${dir}")"; then
    RESULTS+=("${name}|FAILED|0|Python is not available")
    return
  fi

  local start end duration status message
  start="$(date +%s)"
  echo
  echo "==> ${name}"
  local database_url_prefix=()
  if [[ "${name}" == *"-service" ]]; then
    db_dir="${RUNNER_TEMP:-${TEMP:-${TMPDIR:-/tmp}}}"
    if command -v cygpath >/dev/null 2>&1; then
      db_dir="$(cygpath -m "${db_dir}")"
    fi
    db_dir="${db_dir//\\//}"
    database_url_prefix=("DATABASE_URL=sqlite:///${db_dir}/optiflow-${name}-$$.db")
  fi
  (
    cd "${dir}" || exit 1
    env "${database_url_prefix[@]}" \
      PYTHONPATH="${REPO_ROOT}/shared/python${PYTHONPATH:+:${PYTHONPATH}}" \
      "${python}" -m pytest "${test_path}" -q -p no:cacheprovider --basetemp=".test-tmp-${name}-$$-$(date +%s)"
  )
  local exit_code=$?
  end="$(date +%s)"
  duration=$((end - start))
  if [[ ${exit_code} -eq 0 ]]; then
    status="PASSED"
    message=""
  else
    status="FAILED"
    message="pytest exited with ${exit_code}"
  fi
  RESULTS+=("${name}|${status}|${duration}|${message}")
}

declare -a RESULTS=()
echo "Running OptiFlow backend tests. Mode: ${MODE}"

if [[ "${MODE}" == "unit" || "${MODE}" == "all" ]]; then
  run_suite "crm-service" "${REPO_ROOT}/tools/crm-service" "tests"
  run_suite "incident-service" "${REPO_ROOT}/tools/incident-service" "tests"
  run_suite "workforce-service" "${REPO_ROOT}/tools/workforce-service" "tests"
  run_suite "communication-service" "${REPO_ROOT}/tools/communication-service" "tests"
  run_suite "core-api" "${REPO_ROOT}/core-api" "tests/unit"
fi

if [[ "${MODE}" == "integration" || "${MODE}" == "all" ]]; then
  run_suite "integration-tests" "${REPO_ROOT}" "integration-tests"
fi

passed=0
failed=0
skipped=0
total_duration=0

echo
echo "Test summary"
for result in "${RESULTS[@]}"; do
  IFS='|' read -r name status duration message <<< "${result}"
  printf '%-24s %-8s %6ss' "${name}" "${status}" "${duration}"
  [[ -n "${message}" ]] && printf '  %s' "${message}"
  printf '\n'
  total_duration=$((total_duration + duration))
  case "${status}" in
    PASSED) passed=$((passed + 1)) ;;
    FAILED) failed=$((failed + 1)) ;;
    SKIPPED) skipped=$((skipped + 1)) ;;
  esac
done
echo "Passed: ${passed}  Failed: ${failed}  Skipped: ${skipped}  Duration: ${total_duration}s"

if [[ ${failed} -gt 0 ]]; then
  exit 1
fi
exit 0
