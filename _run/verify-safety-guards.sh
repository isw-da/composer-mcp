#!/usr/bin/env bash
# Gate wrapper so the safety-guard test is DISCOVERED and run.
#
# Both hard guards existed with no test and no gate behind them, and guard 1
# spent an unknown period doing nothing: request() rewrote the path to
# /api/managed before the check, and the prefix tuple listed only /managed.
# The fix is one string. This wrapper is the part that stops it happening again,
# because the release workflow and the run gate both discover verify-* scripts
# and neither would have found a file under tests/.
set -uo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

PYTHONPATH=src "$PY" -m tests.test_safety_guards
rc=$?
echo "safety-guards exit: $rc"
exit $rc
