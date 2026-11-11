# minimax-m3-phase1

> **English TL;DR**: Phase 1 wires MiniMax M3 into a TMLR submission pipeline with a 6-sub-detector hallucination gate. Both offline regressions re-ran green in this pass (5 PASS / 0 FAIL on the K-conflict tree; 15/15 on the granularity suite), and the aggregated `run_k_conflict_tests.sh --all` reports PASS / PASS. Live-model claims (real M3 calls, 0-HIGH-false-positive) are **NOT YET MEASURED** here.

[![CI](https://github.com/aidless/minimax-m3-phase1/actions/workflows/test_k_conflict_decision_tree.yml/badge.svg)](https://github.com/aidless/minimax-m3-phase1/actions/workflows/test_k_conflict_decision_tree.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

🌐 简体中文说明：[README.zh-CN.md](README.zh-CN.md)

**Wiring MiniMax M3 into the TMLR submission pipeline, plus a hallucination detector that runs over generated drafts before they reach the revision loop.**

Concretely, phase 1 delivers the chain **Zotero → M3 LLM (via a DeepSeek-compatible gateway) → hallucination detection** over the extracted paper content. The detector (v5.1, ~700 lines, kept under `_inbox/方法论/mm3_hallucination_detector.py`) runs 6 sub-detectors (arXiv / GitHub / internal-reference / DOI / precision / terminology) across 4 severity levels (HIGH / MEDIUM / LOW / INFO), and — per the phase-1 report — does **not** mis-fire on papers that legitimately contain multiple coexisting designs.

## Quickstart (all three commands re-run clean on 2026-11-10)

```bash
git clone https://github.com/aidless/minimax-m3-phase1.git && cd minimax-m3-phase1

# 1) K-conflict decision-tree regression (offline, pure Python, 5 cases)
python3 _k_conflict_decision_tree.py
#    verified output: 测试结果: 5 PASS, 0 FAIL

# 2) Main test suite (offline, 15 cases, soft-downgrade logic)
python3 _test_granularity_suite.py
#    verified output: 共 15 个测试, 通过 15, 失败 0

# 3) One command for the full regression (both suites + aggregated exit code)
bash run_k_conflict_tests.sh --all
#    verified output: K Conflict Tests: PASS / Main Test Suite: PASS
```

Next steps after the offline suite:

- **CI**: `.github/workflows/test_k_conflict_decision_tree.yml` ships with the repo (push / PR / weekly).
- **pre-commit**: `pip install pre-commit && pre-commit install` — runs the regression before each commit that touches the detector.
- **Real M3 calls**: copy `.env.example` → `.env` and fill `DEEPSEEK_API_KEY` (the M3 gateway goes through the DeepSeek-compatible entry point); integration details in `MiniMax_M3_CI_集成说明.md`.

## Results

Numbers from `MiniMax_M3_Phase_1_metrics.csv` and `PHASE_1_2_EVIDENCE.md` (evidence scan generated 2026-07-10, read-only, SHA1-verified):

| Section | Metric | Value |
|---|---|---|
| Overview | scripts | 4 core Python scripts |
| Overview | integration points | 3 (CLI + pre_review + advance_phase) |
| Overview | test cases | 15 (15/15 passing, 100%) |
| Detector | sub-detectors | 6 (arXiv / GitHub / internal / DOI / precision / term) |
| Detector | severity levels | 4 (HIGH / MEDIUM / LOW / INFO) |

Phase 1 key outcome (from `MiniMax_M3_Phase_1_完成报告.md`): after M3 extracts `main.pdf`, the detector flags hallucinated content automatically **without** false positives on multi-design papers. Phase 2 (batch extension) is documented in `MiniMax_M3_Phase_2_总结.md` / `MiniMax_M3_Phase_2_汇报.md`.

## What is in here

| Path | Contents |
|---|---|
| `MiniMax_M3_CI_集成说明.md` | how M3 plugs into the CI gates |
| `MiniMax_M3_K冲突修复_技术文档.md` | the K-conflict fix write-up |
| `MiniMax_M3_Batch_诊断报告.md` | batch diagnostics |
| `PHASE_1_2_EVIDENCE.md` | phase 1 and 2 evidence |
| `MiniMax_M3_Phase_1_metrics.csv` | phase 1 metrics |
| `MiniMax_M3_Phase_1_完成报告.md` / `MiniMax_M3_Phase_2_总结.md` | phase reports |
| `_k_conflict_decision_tree.py` / `_test_granularity_suite.py` / `run_k_conflict_tests.sh` | the offline regression suites |
| `_diag_one.py` / `_diag_realtime.py` | ad-hoc diagnostics |
| `.env.example` | the environment variables to copy |

The reports are written in Chinese; this README is the English summary.

## Tests

```bash
cd minimax-m3-phase1
python _k_conflict_decision_tree.py   # 5 PASS, 0 FAIL
python _test_granularity_suite.py     # 15 PASS (all cases green)
python -m py_compile _inbox/方法论/mm3_hallucination_detector.py   # compiles
```

- `_k_conflict_decision_tree.py` verifies the detector's K-mode conflict decision
  tree (5 cases: K-explicit strong/no-strict, B-title purpose-distinct, K-table
  factorial, K-mode-mismatch, strict-force-HIGH).
- `_test_granularity_suite.py` verifies the granularity soft-demotion logic
  (5 granularity levels × 4 modes × strict/normal = 15 cases, all green).

## Related work and how this compares

This detector targets a narrow but concrete gap: **within-document contradictions
across different descriptions of the same concept**, in agent-generated paper drafts
before they enter a revision loop. It is not a general hallucination detector
(it does not verify a claim against external facts), so the closest prior work is
*internal-consistency* / *self-contradiction* checking over a single text.

Compared to the common alternative — a whole-document regex or LLM "does this
contradict" check — this repo's distinct choices are:

1. **Context-aware, not whole-doc**: a conflict only fires when both descriptions
   land in the *same* context (experiment / heading / table row / list item /
   paragraph). Two different experiments using different confidence scales is
   treated as legitimate multi-design coexistence, not a contradiction.
2. **Purpose heuristic**: two numbers in one context are demoted to `INFO` when
   they carry distinct purposes (e.g. "standard SE=5000" vs "paired CI=2000"),
   which is a common legitimate design, not a hallucination.
3. **Granularity soft-demotion**: a `HIGH` in a weak context (paragraph) is
   demoted to `MEDIUM` because paragraphs can span sections and are higher-noise;
   strong contexts (experiment) are not demoted.

The honest comparison: prior whole-doc checks over-flag cross-context coexistence
as contradiction; this repo trades recall for precision by only firing on
same-context conflicts and by soft-demoting weak contexts. It does **not** claim
higher detection of true hallucinations — that is untested here (real PDFs not
committed). See `PREREG.md` for the boundary statement.

## What this does and does not prove

**Proves:** the hallucination detector's K-conflict decision tree classifies
conflicts correctly across 5 curated cases, and the granularity soft-demotion
rule demotes HIGH→MEDIUM correctly across 15 cases. Both suites pass on this
tree.

**Does not prove:** the detector caught no real hallucinations on the author's
papers — the "PAPER-A 4 mm3.md, 0 HIGH 误报" figure lives in
`MiniMax_M3_Phase_1_完成报告.md` and depends on 4 real PDF summaries generated
by the M3 API, which are **not committed**. The 15-case suite is a synthetic
unit suite over hand-built snippets, not a benchmark over the real pipeline.
Phase 3+ capability is out of scope of this repository.

## Fail-closed behavior

The detector is **conservative by construction**: it is wired as a pre-revision
gate and, in `strict` mode, forces `HIGH` on any same-context conflict — it never
"lets a flagged conflict pass" to downgrade a genuine contradiction to safe.
Soft-demotion only applies in non-strict mode and only for weak (paragraph)
contexts; the `--strict` flag exists precisely so a reviewer can force the
conservative path. The test suites assert this direction (C9/C15 strict→HIGH,
C5/C8 soft-demotion), and the detector's default is to **flag**, not to clear.

## Reproducing the numbers

```bash
cd minimax-m3-phase1
python _k_conflict_decision_tree.py      # 5 PASS, 0 FAIL
python _test_granularity_suite.py        # 15 PASS
```

The "15 cases / 5 granularity / 4 modes / 100% pass" metrics in the phase report
correspond to the granularity suite's actual green run on this tree. The
"0 HIGH 误报" claim is **not** reproducible here (real PDFs not committed);
see the phase report for its provenance.

## Limits

- **The offline suites are fixture regressions, not end-to-end proof.** The 15+5 cases verify the K-conflict decision tree and soft-downgrade logic in isolation; they do not exercise a live M3 gateway.
- **Real LLM calls need credentials and network** (`DEEPSEEK_API_KEY`), and their outputs are nondeterministic — nothing in this repo claims reproducible LLM generations.
- **Phase 3 and later are not in this repository.** Read the phase reports before assuming a capability exists.
- **Documentation is Chinese-first.** The phase reports, CI integration notes, and the technical write-up are all Chinese; this README is the English surface.
- `_diag_*.py` scripts are one-off diagnostics kept for traceability, not supported entry points.

## License

MIT. See [LICENSE](LICENSE).

## U1 live regression results (executed for this pass)

| Command | Verified output (from this run) | Exit |
|---|---|---|
| `python3 _k_conflict_decision_tree.py` | `测试结果: 5 PASS, 0 FAIL` | 0 |
| `python3 _test_granularity_suite.py` | `共 15 个测试, 通过 15, 失败 0` + `✅ 全部测试通过! 软降级逻辑生效正确.` | 0 |
| `bash run_k_conflict_tests.sh --all` | `✅ K Conflict Tests: PASS` / `✅ Main Test Suite: PASS` | 0 |

Metrics re-parsed live from the committed CSV (not from memory):

| Metric (CSV `metric` field) | Value | Source (path:line) |
|---|---|---|
| scripts_count | 4 | `MiniMax_M3_Phase_1_metrics.csv:2` |
| integration_points | 3 | `MiniMax_M3_Phase_1_metrics.csv:3` |
| test_cases | 15 | `MiniMax_M3_Phase_1_metrics.csv:4` |
| test_pass_rate | 100 | `MiniMax_M3_Phase_1_metrics.csv:5` |
| severity_levels | 4 | `MiniMax_M3_Phase_1_metrics.csv:7` |
| detector_count | 6 | `MiniMax_M3_Phase_1_metrics.csv:8` |
| context_granularity | 5 | `MiniMax_M3_Phase_1_metrics.csv:9` |
| contradiction_patterns | 4 | `MiniMax_M3_Phase_1_metrics.csv:10` |

**NOT YET MEASURED in this pass**: any real M3 gateway call (needs
`DEEPSEEK_API_KEY` and is nondeterministic) and the "0 HIGH 误报" claim (real
PDFs are not committed). See `Limits` above for the full statement.

**Reproduce the live checks above**:

```bash
python3 _k_conflict_decision_tree.py
python3 _test_granularity_suite.py
bash run_k_conflict_tests.sh --all
```

<!-- figure: pending real measurement -->
