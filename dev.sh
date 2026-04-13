#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_DIR="${ROOT_DIR}/.dev"
BACKEND_PID_FILE="${DEV_DIR}/backend.pid"
FRONTEND_PID_FILE="${DEV_DIR}/frontend.pid"
BACKEND_LOG="${DEV_DIR}/backend.log"
FRONTEND_LOG="${DEV_DIR}/frontend.log"

ensure_dev_dir() {
  mkdir -p "${DEV_DIR}"
}

is_running() {
  local pid_file="$1"
  if [[ ! -f "${pid_file}" ]]; then
    return 1
  fi

  local pid
  pid="$(cat "${pid_file}")"
  if kill -0 "${pid}" >/dev/null 2>&1; then
    return 0
  fi

  rm -f "${pid_file}"
  return 1
}

start_backend() {
  if is_running "${BACKEND_PID_FILE}"; then
    echo "backend already running (pid $(cat "${BACKEND_PID_FILE}"))"
    return
  fi

  if [[ ! -x "${ROOT_DIR}/backend/.venv/bin/mediareviewer-api" ]]; then
    echo "backend virtualenv missing. run: python3 -m venv backend/.venv && backend/.venv/bin/pip install -e \"backend[dev]\""
    exit 1
  fi

  echo "starting backend..."
  nohup "${ROOT_DIR}/backend/.venv/bin/mediareviewer-api" >"${BACKEND_LOG}" 2>&1 &
  echo $! >"${BACKEND_PID_FILE}"
  echo "backend started (pid $(cat "${BACKEND_PID_FILE}"))"
}

start_frontend() {
  if is_running "${FRONTEND_PID_FILE}"; then
    echo "frontend already running (pid $(cat "${FRONTEND_PID_FILE}"))"
    return
  fi

  if [[ ! -d "${ROOT_DIR}/frontend/node_modules" ]]; then
    echo "frontend dependencies missing. run: cd frontend && npm install"
    exit 1
  fi

  echo "starting frontend..."
  nohup bash -lc "cd '${ROOT_DIR}/frontend' && npm run dev -- --host 0.0.0.0" >"${FRONTEND_LOG}" 2>&1 &
  echo $! >"${FRONTEND_PID_FILE}"
  echo "frontend started (pid $(cat "${FRONTEND_PID_FILE}"))"
}

stop_process() {
  local name="$1"
  local pid_file="$2"

  if ! is_running "${pid_file}"; then
    echo "${name} not running"
    return
  fi

  local pid
  pid="$(cat "${pid_file}")"
  echo "stopping ${name} (pid ${pid})..."
  kill "${pid}" >/dev/null 2>&1 || true
  rm -f "${pid_file}"
}

status() {
  if is_running "${BACKEND_PID_FILE}"; then
    echo "backend: running (pid $(cat "${BACKEND_PID_FILE}"))"
  else
    echo "backend: stopped"
  fi

  if is_running "${FRONTEND_PID_FILE}"; then
    echo "frontend: running (pid $(cat "${FRONTEND_PID_FILE}"))"
  else
    echo "frontend: stopped"
  fi

  echo "logs:"
  echo "  ${BACKEND_LOG}"
  echo "  ${FRONTEND_LOG}"
}

run_lint() {
  echo "running backend lint..."
  "${ROOT_DIR}/backend/.venv/bin/ruff" check "${ROOT_DIR}/backend/src" "${ROOT_DIR}/backend/tests"

  echo "running frontend lint..."
  (cd "${ROOT_DIR}/frontend" && npm run lint)
}

run_test() {
  echo "running backend tests..."
  "${ROOT_DIR}/backend/.venv/bin/pytest" "${ROOT_DIR}/backend/tests"

  echo "running frontend tests..."
  (cd "${ROOT_DIR}/frontend" && npm run test)

  echo "running frontend build check..."
  (cd "${ROOT_DIR}/frontend" && npm run build)
}

start_all() {
  ensure_dev_dir
  start_backend
  start_frontend
  status
}

stop_all() {
  ensure_dev_dir
  stop_process "frontend" "${FRONTEND_PID_FILE}"
  stop_process "backend" "${BACKEND_PID_FILE}"
  status
}

restart_all() {
  stop_all
  start_all
}

usage() {
  cat <<EOF
usage: ./dev.sh <command>

commands:
  start      start backend and frontend dev servers
  stop       stop backend and frontend dev servers
  restart    restart backend and frontend dev servers
  status     print current dev process status and log file paths
  lint       run full backend and frontend lint suite
  test       run full backend and frontend test suite
EOF
}

main() {
  if [[ $# -lt 1 ]]; then
    usage
    exit 1
  fi

  case "$1" in
    start)
      start_all
      ;;
    stop)
      stop_all
      ;;
    restart)
      restart_all
      ;;
    status)
      ensure_dev_dir
      status
      ;;
    lint)
      run_lint
      ;;
    test)
      run_test
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
