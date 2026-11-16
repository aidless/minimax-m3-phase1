#!/usr/bin/env python3
"""Classify numbers in the phase-1 CSV and the phase-1/2 evidence scan.

A row is RECOMPUTED_MATCH only when this script derives the same value from
the current tree. Everything else is labeled UNVERIFIABLE, STALE,
CURATED_NOT_A_CENSUS, or NOT_A_MEASUREMENT. The script does not "fix" the
historical files.

  python3 eval/verify_cited_numbers.py --write
  python3 eval/verify_cited_numbers.py --check
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATUS_PATH = REPO / "eval" / "cited_status.json"
CSV_PATH = REPO / "MiniMax_M3_Phase_1_metrics.csv"
EVIDENCE_PATH = REPO / "PHASE_1_2_EVIDENCE.md"
DETECTOR = REPO / "_inbox" / "方法论" / "mm3_hallucination_detector.py"
README_PATHS = (REPO / "README.md", REPO / "README.zh-CN.md")

SHA_ROW = re.compile(
    r"`(?P<path>[^`]+)`\s*\|\s*(?P<size>[\d,]+)\s*\|"
    r"(?:\s*(?P<mid>[^`|\n]*)\|\s*)?"
    r"\s*`(?P<sha>[0-9a-f]{40})`"
)
LEGACY_START = "<!-- unverifiable-legacy:start -->"
LEGACY_END = "<!-- unverifiable-legacy:end -->"
# Phrases that must not appear in the READMEs outside the legacy section.
BANNED_OUTSIDE_LEGACY = ("0 HIGH", "0-HIGH", "0 HIGH 误报")


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def to_repo_rel(raw: str) -> str | None:
    text = raw.replace("\\", "/")
    prefix = "F:/Research/"
    if text.startswith(prefix):
        return text[len(prefix):]
    return None


def ast_assign_len(path: Path, name: str) -> int | None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name and isinstance(node.value, ast.List):
                    return len(node.value.elts)
    return None


def contradiction_pattern_count(path: Path) -> int | None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "contradiction_patterns":
                    if isinstance(node.value, ast.List):
                        return len(node.value.elts)
    return None


def analyze_file_detectors(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "analyze_file":
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Name)
                    and sub.func.id.startswith("detect_")
                ):
                    names.append(sub.func.id)
    return names


def granularity_keys(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "GRANULARITY" and isinstance(node.value, ast.Dict):
                    keys = []
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant):
                            keys.append(str(key.value))
                    return keys
    return []


def run_py(script: str) -> tuple[int, str]:
    env = dict(os.environ)
    # The suites print Chinese. On Windows, text=True otherwise decodes the
    # pipe with the ANSI code page (cp1252) and the reader thread dies.
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, script],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def classify_csv(rows: list[dict], facts: dict) -> list[dict]:
    out = []
    file_checks = {
        "mm3_hallucination_detector": DETECTOR,
        "zotero_pdf_summary_demo": REPO / "_inbox" / "方法论" / "zotero_pdf_summary_demo.py",
        "zotero_minimax_check": REPO / "_inbox" / "方法论" / "zotero_minimax_check.py",
        "hallucination_check": REPO / ".loop" / "hallucination_check.py",
        "_test_granularity_suite": REPO / "_test_granularity_suite.py",
        "mm3_hallucination_detector_README": REPO / "_inbox" / "方法论" / "mm3_hallucination_detector.README.md",
        "hallucination_check_README": REPO / ".loop" / "hallucination_check.README.md",
        "pre_review_py_modified": REPO / ".loop" / "pre_review.py",
        "advance_phase_py_modified": REPO / ".loop" / "advance_phase.py",
        "completion_report": REPO / "MiniMax_M3_Phase_1_完成报告.md",
        "metrics_csv": CSV_PATH,
    }
    for row in rows:
        section, metric, value = row["section"], row["metric"], row["value"]
        item = {
            "section": section,
            "metric": metric,
            "csv_value": value,
            "status": "UNVERIFIABLE",
            "detail": "",
        }
        if section == "real_data":
            item["detail"] = "Source mm3 texts and any live existence check are not in this checkout."
        elif section in {"v51_improvements", "phase_planning", "risk", "version"}:
            item["status"] = "NOT_A_MEASUREMENT"
            item["detail"] = "Planning note or changelog entry, not a recomputed result."
        elif section == "test_suite":
            item["status"] = "NOT_A_MEASUREMENT"
            item["detail"] = "Case nickname. The pass/fail rerun is repo_facts.granularity_suite."
        elif metric == "detector_count":
            got = len(facts["detector_functions"])
            item["recomputed"] = got
            item["status"] = "RECOMPUTED_MATCH" if str(got) == value else "RECOMPUTED_MISMATCH"
            item["detail"] = "Calls inside analyze_file: " + ", ".join(facts["detector_functions"])
        elif metric == "severity_levels":
            got = len(facts["sev_order"])
            item["recomputed"] = got
            item["status"] = "RECOMPUTED_MATCH" if str(got) == value else "RECOMPUTED_MISMATCH"
            item["detail"] = "sev_order=" + ",".join(facts["sev_order"])
        elif metric == "test_cases":
            got = facts["granularity_case_count"]
            item["recomputed"] = got
            item["status"] = "RECOMPUTED_MATCH" if str(got) == value else "RECOMPUTED_MISMATCH"
            item["detail"] = "len(TEST_CASES) in _test_granularity_suite.py"
        elif metric == "test_pass_rate":
            suite = facts["granularity_suite"]
            item["recomputed"] = suite
            match = suite.get("exit") == 0 and suite.get("passed") == 15 and suite.get("failed") == 0 and value == "100"
            item["status"] = "RECOMPUTED_MATCH" if match else "RECOMPUTED_MISMATCH"
            item["detail"] = "Reran _test_granularity_suite.py. 100 in the CSV means 15/15 on that suite only."
        elif metric == "context_granularity":
            got = len(facts["granularity_keys"])
            item["recomputed"] = got
            item["status"] = "RECOMPUTED_MATCH" if str(got) == value else "RECOMPUTED_MISMATCH"
            item["detail"] = "GRANULARITY keys: " + ",".join(facts["granularity_keys"])
        elif metric == "contradiction_patterns":
            got = facts["contradiction_patterns"]
            item["recomputed"] = got
            item["status"] = "RECOMPUTED_MATCH" if str(got) == value else "RECOMPUTED_MISMATCH"
            item["detail"] = "len(contradiction_patterns) in detect_internal_contradictions"
        elif metric == "scripts_count":
            item["status"] = "CURATED_NOT_A_CENSUS"
            item["detail"] = (
                "CSV inventory of 4 scripts. Those four files exist, and the tree also contains other Python files, "
                "so 4 is not a census."
            )
            item["named_files_exist"] = all(
                p.is_file() for p in (
                    DETECTOR,
                    REPO / "_inbox" / "方法论" / "zotero_pdf_summary_demo.py",
                    REPO / "_inbox" / "方法论" / "zotero_minimax_check.py",
                    REPO / ".loop" / "hallucination_check.py",
                )
            )
        elif metric == "integration_points":
            item["status"] = "CURATED_NOT_A_CENSUS"
            item["detail"] = "CSV says CLI + pre_review + advance_phase. The three files exist; 3 is not re-derived from a spec."
            item["named_files_exist"] = all(
                p.is_file() for p in (
                    REPO / ".loop" / "hallucination_check.py",
                    REPO / ".loop" / "pre_review.py",
                    REPO / ".loop" / "advance_phase.py",
                )
            )
        elif metric == "readme_size":
            readme = REPO / "_inbox" / "方法论" / "mm3_hallucination_detector.README.md"
            got = readme.stat().st_size if readme.is_file() else None
            item["recomputed_bytes"] = got
            item["status"] = "RECOMPUTED_MATCH" if str(got) == value else "RECOMPUTED_MISMATCH"
            item["detail"] = "Byte size of _inbox/方法论/mm3_hallucination_detector.README.md today, versus the CSV."
        elif metric in {"strict_mode", "soft_demotion", "purpose_heuristic"}:
            item["status"] = "NOT_A_MEASUREMENT"
            item["detail"] = "Flag that the heuristic exists in the source. Not a score."
        elif section == "file" and metric in file_checks:
            exists = file_checks[metric].is_file()
            item["recomputed"] = 1 if exists else 0
            item["status"] = "RECOMPUTED_MATCH" if exists and value == "1" else "RECOMPUTED_MISMATCH"
            item["detail"] = str(file_checks[metric].relative_to(REPO))
        elif section == "file":
            item["detail"] = "File-inventory row without a mapped path in this checker."
        else:
            item["detail"] = "No recomputation is defined for this cell."
        out.append(item)
    return out


def classify_evidence() -> list[dict]:
    text = EVIDENCE_PATH.read_text(encoding="utf-8")
    rows = []
    for match in SHA_ROW.finditer(text):
        raw = match.group("path").strip()
        claimed_sha = match.group("sha")
        claimed_size = int(match.group("size").replace(",", ""))
        rel = to_repo_rel(raw)
        item = {
            "evidence_path": raw,
            "claimed_sha1": claimed_sha,
            "claimed_bytes": claimed_size,
        }
        if rel is None:
            item["status"] = "UNVERIFIABLE"
            item["detail"] = "Path is not under F:\\Research in a form this checkout can map, or it is a bare filename."
        else:
            path = REPO / rel
            item["repo_path"] = rel
            if not path.is_file():
                item["status"] = "ABSENT"
                item["detail"] = "Mapped path is not in this checkout."
            else:
                got_sha = sha1_file(path)
                got_size = path.stat().st_size
                item["current_sha1"] = got_sha
                item["current_bytes"] = got_size
                if got_sha == claimed_sha and got_size == claimed_size:
                    item["status"] = "RECOMPUTED_MATCH"
                    item["detail"] = "SHA1 and size match the 2026-07-10 scan."
                else:
                    item["status"] = "STALE"
                    item["detail"] = "File is in the checkout but does not match the 2026-07-10 scan."
        rows.append(item)
    return rows


def suite_facts() -> dict:
    code, out = run_py("_k_conflict_decision_tree.py")
    k_match = re.search(r"测试结果:\s*(\d+)\s*PASS,\s*(\d+)\s*FAIL", out)
    g_code, g_out = run_py("_test_granularity_suite.py")
    g_match = re.search(r"共\s*(\d+)\s*个测试,\s*通过\s*(\d+),\s*失败\s*(\d+)", g_out)
    e_code, e_out = run_py("eval/run_cases.py")
    e_match = re.search(r"(\d+)/(\d+)\s+cases passed", e_out)
    return {
        "k_conflict": {
            "exit": code,
            "passed": int(k_match.group(1)) if k_match else None,
            "failed": int(k_match.group(2)) if k_match else None,
        },
        "granularity_suite": {
            "exit": g_code,
            "total": int(g_match.group(1)) if g_match else None,
            "passed": int(g_match.group(2)) if g_match else None,
            "failed": int(g_match.group(3)) if g_match else None,
        },
        "eval_cases": {
            "exit": e_code,
            "passed": int(e_match.group(1)) if e_match else None,
            "total": int(e_match.group(2)) if e_match else None,
        },
    }


def legacy_phrase_errors() -> list[str]:
    errors = []
    for path in README_PATHS:
        if not path.is_file():
            errors.append(f"missing {path.name}")
            continue
        text = path.read_text(encoding="utf-8")
        start = text.find(LEGACY_START)
        end = text.find(LEGACY_END)
        if start < 0 or end < 0 or end < start:
            errors.append(f"{path.name} is missing unverifiable-legacy markers")
            outside = text
        else:
            outside = text[:start] + text[end + len(LEGACY_END):]
        for phrase in BANNED_OUTSIDE_LEGACY:
            if phrase in outside:
                errors.append(f"{path.name} uses {phrase!r} outside the unverifiable-legacy section")
    return errors


def build() -> dict:
    src = DETECTOR.read_text(encoding="utf-8")
    sev = re.search(r"sev_order\s*=\s*\[([^\]]+)\]", src)
    sev_order = []
    if sev:
        sev_order = re.findall(r"'([^']+)'", sev.group(1))
    runs = suite_facts()
    facts = {
        "detector_functions": analyze_file_detectors(DETECTOR),
        "sev_order": sev_order,
        "granularity_case_count": ast_assign_len(REPO / "_test_granularity_suite.py", "TEST_CASES"),
        "k_conflict_case_count": ast_assign_len(REPO / "_k_conflict_decision_tree.py", "TEST_CASES"),
        "contradiction_patterns": contradiction_pattern_count(DETECTOR),
        "granularity_keys": granularity_keys(DETECTOR),
        "detector_splitlines": len(src.splitlines()),
        **runs,
    }
    with CSV_PATH.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    evidence_rows = classify_evidence()
    return {
        "kind": "cited-number classification",
        "rule": (
            "RECOMPUTED_MATCH means this script derived the same value from the current tree. "
            "STALE means the file is present and the 2026-07-10 fingerprint does not match. "
            "UNVERIFIABLE means the source of the number is not in this checkout. "
            "CURATED_NOT_A_CENSUS means the CSV counted a named subset. "
            "NOT_A_MEASUREMENT means the cell is a nickname, flag, or plan. "
            "None of these labels are live MiniMax M3 results."
        ),
        "repo_facts": facts,
        "csv_rows": classify_csv(csv_rows, facts),
        "evidence_fingerprint_rows": evidence_rows,
        "evidence_status_counts": _counts(evidence_rows),
        "csv_status_counts": _counts(classify_csv(csv_rows, facts)),
    }


def _counts(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return dict(sorted(counts.items()))


def canonical(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    write = "--write" in sys.argv
    check = "--check" in sys.argv
    report = build()
    text = canonical(report)
    if report["repo_facts"]["k_conflict"]["exit"] != 0:
        print("[FAIL] k-conflict rerun did not pass", file=sys.stderr)
        return 1
    if report["repo_facts"]["granularity_suite"]["exit"] != 0:
        print("[FAIL] granularity rerun did not pass", file=sys.stderr)
        return 1
    if report["repo_facts"]["eval_cases"]["exit"] != 0:
        print("[FAIL] eval/run_cases.py did not pass", file=sys.stderr)
        return 1
    if write:
        STATUS_PATH.write_text(text, encoding="utf-8")
        print(f"[wrote] {STATUS_PATH.relative_to(REPO)}", file=sys.stderr)
    if check:
        errors = legacy_phrase_errors()
        if not STATUS_PATH.is_file():
            errors.append("eval/cited_status.json is missing")
        elif STATUS_PATH.read_text(encoding="utf-8") != text:
            errors.append("eval/cited_status.json does not match a fresh classification")
        if errors:
            print("[FAIL] cited-number check:")
            for err in errors:
                print(f"  - {err}")
            return 1
        counts = report["evidence_status_counts"]
        print(f"[PASS] cited numbers classified; evidence rows {counts}")
    if not write and not check:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
