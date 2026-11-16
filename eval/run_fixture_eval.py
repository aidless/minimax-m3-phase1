#!/usr/bin/env python3
"""Score the six hallucination heuristics on eval/fixtures/snippets.jsonl.

Offline only. Labels are read from the fixture file; this script does not
invent them. Network lookups are patched to raise. The arXiv clock is pinned
to 2026-07-10 so the safe-month window does not follow the wall clock.

  python3 eval/run_fixture_eval.py            # print the report
  python3 eval/run_fixture_eval.py --write    # also write eval/fixture_metrics.json
  python3 eval/run_fixture_eval.py --check    # fail if the committed report or README block drifted
  python3 eval/run_fixture_eval.py --selftest # flip one label; metrics must change
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "eval" / "fixtures" / "snippets.jsonl"
METRICS_PATH = REPO / "eval" / "fixture_metrics.json"
DETECTORS = ("arxiv", "github", "internal", "doi", "precision", "terminology")
PINNED = (2026, 7, 10)
CURRENT_YEAR = 2026
BLOCK_START = "<!-- fixture-metrics:start -->"
BLOCK_END = "<!-- fixture-metrics:end -->"
README_PATHS = (REPO / "README.md", REPO / "README.zh-CN.md")
BLOCK_PATHS = README_PATHS + (REPO / "FAILURE_MODES.md", REPO / "PREREG.md")

# Severity that counts as "the internal detector called this a problem".
# INFO is the function's coexistence class.
INTERNAL_POSITIVE = {"HIGH", "MEDIUM", "LOW"}


class NetworkBlocked(RuntimeError):
    pass


def _forbid_network() -> None:
    def _boom(*_a, **_k):
        raise NetworkBlocked("network lookup attempted during offline fixture eval")

    urllib.request.urlopen = _boom  # type: ignore[assignment]

    class _Guard(socket.socket):
        def connect(self, address):  # type: ignore[override]
            raise NetworkBlocked(f"socket connect blocked: {address}")

        def connect_ex(self, address):  # type: ignore[override]
            raise NetworkBlocked(f"socket connect blocked: {address}")

    socket.socket = _Guard  # type: ignore[misc]
    socket.create_connection = _boom  # type: ignore[assignment]


def _load_detector():
    det_dir = REPO / "_inbox" / "方法论"
    if not det_dir.is_dir():
        sys.exit(f"[FATAL] detector directory missing: {det_dir}")
    sys.path.insert(0, str(det_dir))
    import mm3_hallucination_detector as det  # type: ignore

    # The arXiv safe window calls date.today() inside the module.
    class _Pinned(det.date):
        @classmethod
        def today(cls):
            return cls(*PINNED)

    det.date = _Pinned
    det.urllib.request.urlopen = urllib.request.urlopen
    return det


def load_fixtures(path: Path) -> list[dict]:
    rows = []
    seen = set()
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row["id"] in seen:
            sys.exit(f"[FATAL] duplicate fixture id {row['id']} at line {lineno}")
        seen.add(row["id"])
        missing = [k for k in DETECTORS if k not in row.get("labels", {})]
        if missing:
            sys.exit(f"[FATAL] {row['id']} missing labels {missing}")
        for key, value in row["labels"].items():
            if value not in (0, 1):
                sys.exit(f"[FATAL] {row['id']} label {key} is not 0/1")
        rows.append(row)
    if not rows:
        sys.exit("[FATAL] no fixtures")
    return rows


def predict(det, row: dict) -> dict[str, dict]:
    text = row["text"]
    pdf = row.get("pdf_text") or ""
    out = {}
    arxiv = det.detect_arxiv_year_issues(text, current_year=CURRENT_YEAR)
    out["arxiv"] = _pack(arxiv, positive=bool(arxiv))
    github = det.detect_github_issues(text, check_online=False)
    out["github"] = _pack(github, positive=bool(github))
    internal = det.detect_internal_contradictions(text, strict=False)
    fired = [i for i in internal if i.get("severity") in INTERNAL_POSITIVE]
    out["internal"] = _pack(internal, positive=bool(fired))
    doi = det.detect_doi_issues(text)
    out["doi"] = _pack(doi, positive=bool(doi))
    precise = det.detect_precise_number_issues(text)
    out["precision"] = _pack(precise, positive=bool(precise))
    terms = det.detect_undefined_terms(text, pdf_text=pdf)
    out["terminology"] = _pack(terms, positive=bool(terms))
    return out


def _pack(issues: list, positive: bool) -> dict:
    return {
        "pred": 1 if positive else 0,
        "n_issues": len(issues),
        "severities": [i.get("severity") for i in issues],
        "types": [i.get("type") for i in issues],
        "matches": [i.get("match") for i in issues],
        "reasons": [i.get("reason") for i in issues],
    }


def score(fixtures: list[dict], preds: list[dict]) -> dict:
    per = {}
    for name in DETECTORS:
        tp = fp = tn = fn = 0
        fp_ids, fn_ids = [], []
        for row, pred in zip(fixtures, preds):
            gold = row["labels"][name]
            got = pred[name]["pred"]
            if gold == 1 and got == 1:
                tp += 1
            elif gold == 0 and got == 1:
                fp += 1
                fp_ids.append(row["id"])
            elif gold == 0 and got == 0:
                tn += 1
            else:
                fn += 1
                fn_ids.append(row["id"])
        per[name] = {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": _rate(tp, tp + fp),
            "recall": _rate(tp, tp + fn),
            "fp_ids": fp_ids,
            "fn_ids": fn_ids,
            "confusion": {
                "gold0_pred0": tn,
                "gold0_pred1": fp,
                "gold1_pred0": fn,
                "gold1_pred1": tp,
            },
        }
    return per


def _rate(num: int, den: int):
    if den == 0:
        return None
    return {"num": num, "den": den, "value": round(num / den, 3)}


def fmt_rate(rate) -> str:
    if not rate:
        return "n/a"
    return f"{rate['num']}/{rate['den']} = {rate['value']:.3f}"


def metrics_block(per: dict, n: int) -> str:
    lines = [
        BLOCK_START,
        "| detector | tp | fp | fn | tn | precision | recall |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for name in DETECTORS:
        row = per[name]
        lines.append(
            f"| {name} | {row['tp']} | {row['fp']} | {row['fn']} | {row['tn']} | "
            f"{fmt_rate(row['precision'])} | {fmt_rate(row['recall'])} |"
        )
    lines.append(
        f"n={n} synthetic fixtures; clock=2026-07-10; current_year=2026; "
        "network=blocked; check_online=false; labels=same-author, written before the run; "
        "heuristic offline mode only; not live MiniMax M3; not a real-paper false-positive rate."
    )
    lines.append(BLOCK_END)
    return "\n".join(lines)


def side_probe(det) -> dict:
    """Measured facts that are not fixture scores."""
    sample = "https://github.com/openai/gpt-2"
    online = det.detect_github_issues(sample, check_online=True)
    offline = det.detect_github_issues(sample, check_online=False)
    return {
        "github_check_online_true_issue_count": len(online),
        "github_check_online_true_severities": [i.get("severity") for i in online],
        "github_check_online_false_severities": [i.get("severity") for i in offline],
        "github_check_online_true_opened_socket": False,
        "note": (
            "check_online=True still returns an issue and does not open a socket. "
            "The module docstring mentions a GitHub API and CrossRef; those calls are not in the functions."
        ),
    }


def build_report(fixtures: list[dict], det) -> dict:
    preds = [predict(det, row) for row in fixtures]
    per = score(fixtures, preds)
    cases = []
    for row, pred in zip(fixtures, preds):
        cases.append({
            "id": row["id"],
            "labels": row["labels"],
            "pred": {k: pred[k]["pred"] for k in DETECTORS},
            "detail": pred,
            "unscored": row.get("unscored", {}),
        })
    pointers = [c["id"] for c in cases if c["unscored"].get("section_pointer")]
    return {
        "kind": "synthetic-fixture heuristic eval",
        "detector": "_inbox/方法论/mm3_hallucination_detector.py",
        "n_fixtures": len(fixtures),
        "clock": "2026-07-10",
        "current_year": CURRENT_YEAR,
        "network": "blocked",
        "github_check_online": False,
        "internal_info_counts_as_negative": True,
        "label_protocol": "eval/fixtures/PROTOCOL.md",
        "fixtures": "eval/fixtures/snippets.jsonl",
        "limits": [
            "synthetic snippets authored for this file",
            "labels and scorer written by the same author; no second annotator",
            "detector heuristics only; no live MiniMax M3 call",
            "not a false-positive rate on real papers",
            "arXiv/GitHub/DOI existence was not looked up",
        ],
        "per_detector": per,
        "section_pointer_ids_unscored": pointers,
        "side_probe": side_probe(det),
        "cases": cases,
    }


def _canonical(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _extract_block(text: str, path: Path) -> str:
    start = text.find(BLOCK_START)
    end = text.find(BLOCK_END)
    if start < 0 or end < 0 or end < start:
        sys.exit(f"[FATAL] {path} is missing the fixture-metrics markers")
    return text[start:end + len(BLOCK_END)]


def check_readmes(block: str) -> list[str]:
    errors = []
    abouts = []
    for path in BLOCK_PATHS:
        if not path.is_file():
            errors.append(f"missing {path.name}")
            continue
        text = path.read_text(encoding="utf-8")
        got = _extract_block(text, path)
        if got != block:
            errors.append(f"{path.name} fixture-metrics block does not match the recomputed table")
    for path in README_PATHS:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in (
            "STATUS: WORK-IN-PROGRESS — not A yet",
            "_inbox/方法论/mm3_hallucination_detector.py",
            "make check",
            "not live MiniMax M3",
            "not a real-paper false-positive rate",
        ):
            if token not in text:
                errors.append(f"{path.name} missing required token: {token}")
        problem = _section(text, "problem")
        if problem is None:
            errors.append(f"{path.name} missing problem markers")
        else:
            n_lines = len([ln for ln in problem.splitlines() if ln.strip()])
            if n_lines > 3:
                errors.append(f"{path.name} problem section has {n_lines} lines (max 3)")
        about = _section(text, "about")
        if about is None:
            errors.append(f"{path.name} missing about markers")
        else:
            abouts.append(about.strip())
    if len(abouts) == 2 and abouts[0] != abouts[1]:
        errors.append("GitHub About replacement text differs between README.md and README.zh-CN.md")
    return errors


def _section(text: str, name: str):
    start = f"<!-- {name}:start -->"
    end = f"<!-- {name}:end -->"
    i = text.find(start)
    j = text.find(end)
    if i < 0 or j < 0 or j < i:
        return None
    return text[i + len(start):j].strip("\n")


def run_selftest(fixtures: list[dict], det) -> int:
    base = score(fixtures, [predict(det, row) for row in fixtures])
    flipped = json.loads(json.dumps(fixtures))
    flipped[0]["labels"]["arxiv"] = 1 - flipped[0]["labels"]["arxiv"]
    alt = score(flipped, [predict(det, row) for row in flipped])
    if base["arxiv"] == alt["arxiv"]:
        print("SELFTEST FAIL: flipping a label did not change the arxiv counts")
        return 3
    print("SELFTEST PASS: flipping one arxiv label changes the arxiv counts")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--print-block", action="store_true")
    args = parser.parse_args()

    _forbid_network()
    det = _load_detector()
    # The detector imported urllib before the patch. Point its module alias at the guard too.
    det.urllib.request.urlopen = urllib.request.urlopen

    fixtures = load_fixtures(FIXTURES)
    if args.selftest:
        return run_selftest(fixtures, det)

    report = build_report(fixtures, det)
    block = metrics_block(report["per_detector"], report["n_fixtures"])
    text = _canonical(report)

    if args.print_block or not (args.write or args.check):
        print(block)
        print()
        for name in DETECTORS:
            row = report["per_detector"][name]
            print(f"{name}: fp={row['fp_ids']} fn={row['fn_ids']}")

    if args.write:
        METRICS_PATH.write_text(text, encoding="utf-8")
        print(f"[wrote] {METRICS_PATH.relative_to(REPO)}", file=sys.stderr)

    if args.check:
        errors = []
        if not METRICS_PATH.is_file():
            errors.append("eval/fixture_metrics.json is missing")
        else:
            committed = METRICS_PATH.read_text(encoding="utf-8")
            if committed != text:
                errors.append("eval/fixture_metrics.json does not match a fresh recompute")
        errors.extend(check_readmes(block))
        modes = REPO / "FAILURE_MODES.md"
        if modes.is_file():
            modes_text = modes.read_text(encoding="utf-8")
            for name in DETECTORS:
                for fid in report["per_detector"][name]["fp_ids"] + report["per_detector"][name]["fn_ids"]:
                    if fid not in modes_text:
                        errors.append(f"FAILURE_MODES.md does not mention {fid} ({name})")
            if "fx15" not in modes_text:
                errors.append("FAILURE_MODES.md does not mention the unscored section pointer fx15")
        if errors:
            print("[FAIL] fixture eval drift:")
            for err in errors:
                print(f"  - {err}")
            return 1
        print(f"[PASS] fixture eval recomputed; n={report['n_fixtures']}; README blocks match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
