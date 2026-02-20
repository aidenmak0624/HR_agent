#!/usr/bin/env bash
set -u -o pipefail

# Verifies MCP server behavior and installed Codex skills (playwright + screenshot).
# Default mode is read-only. Use --write-mcp to run a mutating enrollment smoke test.

BASE_URL="${MCP_BASE_URL:-http://localhost:5050}"
RUN_WRITE_MCP=0
RUN_PLAYWRIGHT_BROWSER=1
RUN_SCREENSHOT_CAPTURE=0
MCP_TEST_EMPLOYEE_ID="${MCP_TEST_EMPLOYEE_ID:-1}"
MCP_TEST_PLAN_ID="${MCP_TEST_PLAN_ID:-2}"

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

usage() {
  cat <<'USAGE'
Usage: scripts/verify_mcp_and_skills.sh [options]

Options:
  --base-url <url>           MCP/API base URL (default: http://localhost:5050)
  --write-mcp                Run mutating MCP enrollment test and validate benefits in recent activity
  --skip-playwright-browser  Skip Playwright open+snapshot browser smoke
  --screenshot-capture       Run an actual screenshot capture smoke test (may require OS permissions)
  -h, --help                 Show this help text

Env overrides:
  MCP_TEST_EMPLOYEE_ID       Employee id for write-mode enrollment test (default: 1)
  MCP_TEST_PLAN_ID           Plan id for write-mode enrollment test (default: 2)
USAGE
}

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf '[PASS] %s\n' "$1"
}

warn() {
  WARN_COUNT=$((WARN_COUNT + 1))
  printf '[WARN] %s\n' "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf '[FAIL] %s\n' "$1"
}

need_cmd() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "Command available: $cmd"
  else
    fail "Missing required command: $cmd"
  fi
}

curl_json() {
  local method="$1"
  local url="$2"
  local body="${3:-}"
  if [[ "$method" == "GET" ]]; then
    curl -sS "$url"
  else
    curl -sS -X "$method" "$url" -H 'Content-Type: application/json' -d "$body"
  fi
}

run_with_timeout() {
  local timeout_seconds="$1"
  shift
  python3 - "$timeout_seconds" "$@" <<'PY'
import subprocess
import sys

timeout_seconds = int(sys.argv[1])
cmd = sys.argv[2:]

try:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout_seconds)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    sys.exit(proc.returncode)
except subprocess.TimeoutExpired as exc:
    if exc.stdout:
        sys.stdout.write(exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode(errors="ignore"))
    if exc.stderr:
        sys.stderr.write(exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode(errors="ignore"))
    sys.stderr.write(f"\nTimed out after {timeout_seconds}s: {' '.join(cmd)}\n")
    sys.exit(124)
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --write-mcp)
      RUN_WRITE_MCP=1
      shift
      ;;
    --skip-playwright-browser)
      RUN_PLAYWRIGHT_BROWSER=0
      shift
      ;;
    --screenshot-capture)
      RUN_SCREENSHOT_CAPTURE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 2
      ;;
  esac
done

BASE_URL="${BASE_URL%/}"
MCP_URL="${BASE_URL}/mcp/"
MCP_HEALTH_URL="${BASE_URL}/mcp/health"

echo "Verifying MCP and skills against: ${BASE_URL}"

need_cmd curl
need_cmd python3
need_cmd bash

echo
echo "== MCP checks =="

health_resp="$(curl_json GET "$MCP_HEALTH_URL" 2>/tmp/mcp_health_err.$$)" || health_resp=""
if [[ -z "$health_resp" ]]; then
  fail "MCP health request failed: $(cat /tmp/mcp_health_err.$$ 2>/dev/null)"
else
  if printf '%s' "$health_resp" | python3 -c "import json,sys; d=json.load(sys.stdin); ok=(d.get('status')=='ok' and isinstance(d.get('tools'),int) and d.get('tools')>0); sys.exit(0 if ok else 1)"; then
    tools_count="$(printf '%s' "$health_resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tools', 0))" 2>/dev/null)"
    pass "MCP health OK (tools=${tools_count})"
  else
    fail "MCP health JSON invalid or not OK: $health_resp"
  fi
fi

init_resp="$(curl_json POST "$MCP_URL" '{"jsonrpc":"2.0","id":"verify-init","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"verify-script","version":"1.0"}}}' 2>/tmp/mcp_init_err.$$)" || init_resp=""
if [[ -z "$init_resp" ]]; then
  fail "MCP initialize failed: $(cat /tmp/mcp_init_err.$$ 2>/dev/null)"
else
  if printf '%s' "$init_resp" | python3 -c "import json,sys; d=json.load(sys.stdin); ok=bool(d.get('result',{}).get('serverInfo',{}).get('name')); sys.exit(0 if ok else 1)"; then
    pass "MCP initialize handshake succeeded"
  else
    fail "MCP initialize returned unexpected payload: $init_resp"
  fi
fi

tools_resp="$(curl_json POST "$MCP_URL" '{"jsonrpc":"2.0","id":"verify-tools","method":"tools/list","params":{}}' 2>/tmp/mcp_tools_err.$$)" || tools_resp=""
if [[ -z "$tools_resp" ]]; then
  fail "MCP tools/list failed: $(cat /tmp/mcp_tools_err.$$ 2>/dev/null)"
else
  tools_check_output="$(printf '%s' "$tools_resp" | python3 -c "import json,sys; d=json.load(sys.stdin); names={t.get('name') for t in d.get('result',{}).get('tools',[]) if t.get('name')}; required={'list_benefits_plans','get_recent_activity','enroll_in_benefit'}; missing=sorted(required-names); print(','.join(missing)); print(len(names))" 2>/tmp/mcp_tools_parse_err.$$)" || tools_check_output=""
  if [[ -n "$tools_check_output" ]]; then
    missing_tools="$(printf '%s' "$tools_check_output" | sed -n '1p')"
    total_tools="$(printf '%s' "$tools_check_output" | sed -n '2p')"
    if [[ -z "$missing_tools" ]]; then
      pass "MCP tools/list includes required tools (total=${total_tools})"
    else
      fail "MCP tools/list missing required tools: ${missing_tools}"
    fi
  else
    fail "MCP tools/list response could not be parsed: $(cat /tmp/mcp_tools_parse_err.$$ 2>/dev/null)"
  fi
fi

plans_resp="$(curl_json POST "$MCP_URL" '{"jsonrpc":"2.0","id":"verify-plans","method":"tools/call","params":{"name":"list_benefits_plans","arguments":{}}}' 2>/tmp/mcp_plans_err.$$)" || plans_resp=""
if [[ -z "$plans_resp" ]]; then
  fail "MCP list_benefits_plans failed: $(cat /tmp/mcp_plans_err.$$ 2>/dev/null)"
else
  plans_count="$(printf '%s' "$plans_resp" | python3 -c "import json,sys; d=json.load(sys.stdin); text=d.get('result',{}).get('content',[{}])[0].get('text','{}'); inner=json.loads(text); print(inner.get('count',0));" 2>/tmp/mcp_plans_parse_err.$$)" || plans_count=""
  if [[ -n "$plans_count" && "$plans_count" -gt 0 ]]; then
    pass "MCP list_benefits_plans returns data (count=${plans_count})"
  else
    fail "MCP list_benefits_plans returned no plans or parse failed: $(cat /tmp/mcp_plans_parse_err.$$ 2>/dev/null)"
  fi
fi

if [[ "$RUN_WRITE_MCP" -eq 1 ]]; then
  enroll_body="{\"jsonrpc\":\"2.0\",\"id\":\"verify-enroll\",\"method\":\"tools/call\",\"params\":{\"name\":\"enroll_in_benefit\",\"arguments\":{\"employee_id\":\"${MCP_TEST_EMPLOYEE_ID}\",\"plan_id\":\"${MCP_TEST_PLAN_ID}\",\"coverage_level\":\"employee\"}}}"
  enroll_resp="$(curl_json POST "$MCP_URL" "$enroll_body" 2>/tmp/mcp_enroll_err.$$)" || enroll_resp=""
  if [[ -z "$enroll_resp" ]]; then
    fail "MCP enroll_in_benefit failed: $(cat /tmp/mcp_enroll_err.$$ 2>/dev/null)"
  else
    if printf '%s' "$enroll_resp" | python3 -c "import json,sys; d=json.load(sys.stdin); ok=(not d.get('result',{}).get('isError',False)); sys.exit(0 if ok else 1)" 2>/dev/null; then
      pass "MCP enroll_in_benefit write test succeeded"
    else
      fail "MCP enroll_in_benefit returned error payload: $enroll_resp"
    fi
  fi
fi

recent_resp="$(curl_json POST "$MCP_URL" '{"jsonrpc":"2.0","id":"verify-recent","method":"tools/call","params":{"name":"get_recent_activity","arguments":{"limit":20}}}' 2>/tmp/mcp_recent_err.$$)" || recent_resp=""
if [[ -z "$recent_resp" ]]; then
  fail "MCP get_recent_activity failed: $(cat /tmp/mcp_recent_err.$$ 2>/dev/null)"
else
  if printf '%s' "$recent_resp" | python3 -c "import json,sys; d=json.load(sys.stdin); text=d.get('result',{}).get('content',[{}])[0].get('text','{}'); inner=json.loads(text); acts=inner.get('activities',[]); has=any(a.get('type')=='benefits' for a in acts); sys.exit(0 if has else 1)" 2>/dev/null; then
    pass "MCP get_recent_activity includes benefits activity entries"
  else
    if [[ "$RUN_WRITE_MCP" -eq 1 ]]; then
      fail "MCP recent activity still missing benefits entries after write test"
    else
      warn "No benefits entries found in recent activity (run again with --write-mcp to force a write event)"
    fi
  fi
fi

echo
echo "== Skills checks =="

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
PLAYWRIGHT_SKILL_DIR="${CODEX_HOME}/skills/playwright"
SCREENSHOT_SKILL_DIR="${CODEX_HOME}/skills/screenshot"
PWCLI="${PLAYWRIGHT_SKILL_DIR}/scripts/playwright_cli.sh"
SCREENSHOT_PY="${SCREENSHOT_SKILL_DIR}/scripts/take_screenshot.py"
SCREENSHOT_PREFLIGHT="${SCREENSHOT_SKILL_DIR}/scripts/ensure_macos_permissions.sh"

if [[ -f "${PLAYWRIGHT_SKILL_DIR}/SKILL.md" ]]; then
  pass "Playwright skill installed at ${PLAYWRIGHT_SKILL_DIR}"
else
  fail "Playwright skill missing at ${PLAYWRIGHT_SKILL_DIR}"
fi

if [[ -f "${SCREENSHOT_SKILL_DIR}/SKILL.md" ]]; then
  pass "Screenshot skill installed at ${SCREENSHOT_SKILL_DIR}"
else
  fail "Screenshot skill missing at ${SCREENSHOT_SKILL_DIR}"
fi

if command -v npx >/dev/null 2>&1; then
  pass "npx available for Playwright skill"
else
  fail "npx is missing; install Node.js/npm first"
fi

if [[ -x "$PWCLI" ]]; then
  pass "Playwright wrapper is executable"
else
  warn "Playwright wrapper is not executable. You can run: chmod +x ${PWCLI}"
fi

pw_help_out="$(bash "$PWCLI" --help 2>/tmp/pw_help_err.$$)" || pw_help_out=""
if [[ -n "$pw_help_out" ]]; then
  pass "Playwright wrapper responds to --help"
else
  fail "Playwright wrapper help failed: $(cat /tmp/pw_help_err.$$ 2>/dev/null)"
fi

if [[ "$RUN_PLAYWRIGHT_BROWSER" -eq 1 ]]; then
  session_id="verify-skill-$$"
  pw_open_ok=0
  run_with_timeout 120 bash "$PWCLI" --session "$session_id" open "${BASE_URL}/login" >/tmp/pw_open_$$.txt 2>/tmp/pw_open_err_$$.txt && pw_open_ok=1
  if [[ "$pw_open_ok" -eq 1 ]]; then
    if run_with_timeout 120 bash "$PWCLI" --session "$session_id" snapshot >/tmp/pw_snapshot_$$.txt 2>/tmp/pw_snapshot_err_$$.txt; then
      pass "Playwright browser smoke (open + snapshot) succeeded"
    else
      fail "Playwright snapshot failed: $(cat /tmp/pw_snapshot_err_$$.txt 2>/dev/null)"
    fi
    run_with_timeout 20 bash "$PWCLI" --session "$session_id" close >/tmp/pw_close_$$.txt 2>/dev/null || true
  else
    fail "Playwright open failed: $(cat /tmp/pw_open_err_$$.txt 2>/dev/null)"
  fi
fi

ss_help_out="$(python3 "$SCREENSHOT_PY" --help 2>/tmp/ss_help_err.$$)" || ss_help_out=""
if [[ -n "$ss_help_out" ]]; then
  pass "Screenshot helper responds to --help"
else
  fail "Screenshot helper help failed: $(cat /tmp/ss_help_err.$$ 2>/dev/null)"
fi

if [[ "$RUN_SCREENSHOT_CAPTURE" -eq 1 ]]; then
  if [[ "$(uname -s)" == "Darwin" && -f "$SCREENSHOT_PREFLIGHT" ]]; then
    bash "$SCREENSHOT_PREFLIGHT" >/tmp/ss_preflight_$$.txt 2>/tmp/ss_preflight_err_$$.txt || true
  fi
  ss_out="$(run_with_timeout 45 python3 "$SCREENSHOT_PY" --mode temp 2>/tmp/ss_capture_err.$$)" || ss_out=""
  shot_file="$(printf '%s\n' "$ss_out" | tail -n 1)"
  if [[ -n "$shot_file" && -f "$shot_file" ]]; then
    pass "Screenshot capture succeeded: ${shot_file}"
  else
    fail "Screenshot capture failed: $(cat /tmp/ss_capture_err.$$ 2>/dev/null)"
  fi
fi

echo
echo "== Summary =="
echo "Pass: ${PASS_COUNT}"
echo "Warn: ${WARN_COUNT}"
echo "Fail: ${FAIL_COUNT}"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi

exit 0
