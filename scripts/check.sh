#!/usr/bin/env bash
# Offline entry point. Standard library only: no pip, no API key, no network.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

"$PY" _k_conflict_decision_tree.py
"$PY" _test_granularity_suite.py
"$PY" eval/run_cases.py
"$PY" eval/run_fixture_eval.py --selftest
"$PY" eval/run_fixture_eval.py --check
"$PY" eval/verify_cited_numbers.py --check
