# minimax-m3-phase1

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

## Limits

- **The offline suites are fixture regressions, not end-to-end proof.** The 15+5 cases verify the K-conflict decision tree and soft-downgrade logic in isolation; they do not exercise a live M3 gateway.
- **Real LLM calls need credentials and network** (`DEEPSEEK_API_KEY`), and their outputs are nondeterministic — nothing in this repo claims reproducible LLM generations.
- **Phase 3 and later are not in this repository.** Read the phase reports before assuming a capability exists.
- **Documentation is Chinese-first.** The phase reports, CI integration notes, and the technical write-up are all Chinese; this README is the English surface.
- `_diag_*.py` scripts are one-off diagnostics kept for traceability, not supported entry points.

## License

MIT. See [LICENSE](LICENSE).
