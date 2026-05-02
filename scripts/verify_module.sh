#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PYTHON="${BACKEND_PYTHON:-$ROOT_DIR/.venv/bin/python}"
MODULE_KEY="${1:-full}"

run_backend_check() {
  echo "[verify] backend check"
  (
    cd "$BACKEND_DIR"
    "$BACKEND_PYTHON" manage.py check
  )
}

run_backend_tests() {
  echo "[verify] backend tests: $*"
  (
    cd "$BACKEND_DIR"
    "$BACKEND_PYTHON" manage.py test "$@"
  )
}

run_frontend_build() {
  echo "[verify] frontend build"
  (
    cd "$FRONTEND_DIR"
    npm run build
  )
}

print_usage() {
  cat <<'EOF'
Usage:
  scripts/verify_module.sh <module-key>

Module keys:
  primary-approval
  cycle-task
  dashboard
  template
  demands
  masterdata
  version-analysis
  audit
  full
EOF
}

case "$MODULE_KEY" in
  primary-approval)
    run_backend_check
    run_backend_tests approvals budgets budget_cycles notifications
    run_frontend_build
    ;;
  cycle-task)
    run_backend_check
    run_backend_tests budget_cycles budgets approvals notifications
    run_frontend_build
    ;;
  dashboard)
    run_backend_check
    run_backend_tests analytics budgets masterdata
    run_frontend_build
    ;;
  template)
    run_backend_check
    run_backend_tests budget_templates budgets masterdata
    run_frontend_build
    ;;
  demands)
    run_backend_check
    run_backend_tests demands budgets budget_cycles notifications
    run_frontend_build
    ;;
  masterdata)
    run_backend_check
    run_backend_tests masterdata budgets analytics
    run_frontend_build
    ;;
  version-analysis)
    run_backend_check
    run_backend_tests budgets analytics approvals
    run_frontend_build
    ;;
  audit)
    run_backend_check
    run_backend_tests notifications approvals budgets analytics
    run_frontend_build
    ;;
  full)
    run_backend_check
    run_backend_tests
    run_frontend_build
    ;;
  -h|--help|help)
    print_usage
    ;;
  *)
    echo "Unknown module key: $MODULE_KEY" >&2
    print_usage
    exit 1
    ;;
esac
