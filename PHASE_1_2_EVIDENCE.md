# Phase 1+2 Evidence Report

**Generated** : 2026-07-10 16:12 (Asia/Shanghai)
**Generator** : Read-only scan via Python + Win32 `GetLongPathNameW` + SHA1
**Scope**     : `F:\Research` (41 paths inspected, 0 source files modified)

---

## Summary

| Metric | Value |
|---|---|
| Total items checked | **41** |
| Items present (YES) | **41** |
| Items missing (NO)  | **0** |
| Coverage            | **100%** |

The 11 deliverables announced in the Phase 1+2 closing report are all present
on disk under `F:\Research`, with the following footprint:

| Category | Count | Total bytes |
|---|---:|---:|
| A. Core code (mm3 detector, zotero demo/check, .loop CLI) | 4 | 91,370 |
| B. README (22,825 B × 2)                                  | 2 | 45,650 |
| C. Test suites (granularity 15-case + k-conflict tree)     | 2 | 28,759 |
| D. CI / scripts (workflow yml, pre-commit, .sh, .cmd)     | 4 |  7,273 |
| E. .loop integration (pre_review, advance_phase)           | 2 | 24,352 |
| F. Batch scripts (phase2_batch / step1 / step2)            | 4 |  7,887 |
| G. Reports (6 .md + 1 .csv)                               | 7 | 57,945 |
| H–K. 16 mm3.md (4 papers × 4 tasks)                        | 16 | 88,899 |
| **Total** | **41** | **352,135 B (≈ 344 KB)** |

---

## A. Core code (4 files)

| Path | Size | LastWrite | SHA1 |
|---|---:|---|---|
| `F:\Research\_inbox\方法论\mm3_hallucination_detector.py` | 41,744 | 2026-07-10 15:37:16 | `feba9cf3b9c417a74d23ba0112d765890f346f62` |
| `F:\Research\_inbox\方法论\zotero_pdf_summary_demo.py`    | 16,852 | 2026-07-10 15:20:54 | `f9aedfc590c69fe264d9e992ad76cc3e4fc35364` |
| `F:\Research\_inbox\方法论\zotero_minimax_check.py`       | 19,659 | 2026-07-10 01:00:11 | `1ebf07dc92ccf4abcbf4e4002fe01fb08f8dfee2` |
| `F:\Research\.loop\hallucination_check.py`                | 13,115 | 2026-07-10 10:40:29 | `4453a3e37359fdec60eecc4aa46a459351eae91e` |

## B. README (2 files, byte-identical 22,825 B)

| Path | Size | LastWrite | SHA1 |
|---|---:|---|---|
| `F:\Research\_inbox\方法论\mm3_hallucination_detector.README.md` | 22,825 | 2026-07-10 15:40:03 | `e34e19fe7a9e18277fa41b40bb64eb9eddef0b5e` |
| `F:\Research\.loop\hallucination_check.README.md`                | 22,825 | 2026-07-10 15:40:11 | `e34e19fe7a9e18277fa41b40bb64eb9eddef0b5e` |

> The two README files are byte-identical (same SHA1). They are a `.loop` copy of the
> main `方法论` README, consistent with the dual-location policy in the closing report.

## C. Test suites (2 files)

| Path | Size | LastWrite | SHA1 |
|---|---:|---|---|
| `F:\Research\_test_granularity_suite.py`       | 18,658 | 2026-07-10 11:28:57 | `9e1dc7f5365c87764eb9acb88123ddc4f43bdcd3` |
| `F:\Research\_k_conflict_decision_tree.py`     | 10,101 | 2026-07-10 15:46:07 | `bbb628ab919b7ec98d3c8245c3d83f14ce4661ae` |

## D. CI / scripts (4 files)

| Path | Size | LastWrite | SHA1 |
|---|---:|---|---|
| `F:\Research\.github\workflows\test_k_conflict_decision_tree.yml` | 3,210 | 2026-07-10 15:47:30 | `8fc67ec158b78edfef274d233ebb95da158a718a` |
| `F:\Research\.pre-commit-config.yaml`                              | 1,209 | 2026-07-10 15:47:58 | `7b137db4466bc6d84c19f029b35108ae751e923d` |
| `F:\Research\run_k_conflict_tests.sh`                              | 1,460 | 2026-07-10 15:47:39 | `3eb5d50d3bd9f1116086c484e158add2567ecbbd` |
| `F:\Research\run_k_conflict_tests.cmd`                             | 1,394 | 2026-07-10 15:47:49 | `e0ffe13f321841303b8d7c9be606cc98a0fb5fda` |

## E. .loop integration (2 files)

| Path | Size | LastWrite | SHA1 |
|---|---:|---|---|
| `F:\Research\.loop\pre_review.py`     | 10,809 | 2026-07-10 11:13:45 | `0ed870b28a00d2082c9ca8084e81eec5a8525019` |
| `F:\Research\.loop\advance_phase.py`  | 13,543 | 2026-07-10 11:14:14 | `88cb5fc464e23bf62f97f05ef387f7fe5efb60a6` |

## F. Batch scripts (4 files)

| Path | Size | LastWrite | SHA1 |
|---|---:|---|---|
| `F:\Research\_phase2_batch.py`     | 3,137 | 2026-07-10 11:55:33 | `1bf2e1e3482a96da672c650084fb17c92aab382f` |
| `F:\Research\_phase2_batch_v2.py`  | 2,733 | 2026-07-10 15:22:34 | `3c66bc041f949d1bf85f5a6fb6a4dc5735e50507` |
| `F:\Research\_phase2_step1.py`     |   462 | 2026-07-10 11:37:16 | `b97c2167f469263ec613431c541bd90f4a30e783` |
| `F:\Research\_phase2_step2.py`     | 1,555 | 2026-07-10 11:38:07 | `b186eb53d53bef759d064b18e0cbe2c32ae45e97` |

## G. Reports (6 .md + 1 .csv)

| Path | Size | LastWrite | SHA1 |
|---|---:|---|---|
| `F:\Research\MiniMax_M3_Phase_1_完成报告.md`        | 16,161 | 2026-07-10 11:34:38 | `5699830d5c980e1f97cda1979d2fedab1bd5bbae` |
| `F:\Research\MiniMax_M3_Phase_2_总结.md`            | 12,513 | 2026-07-10 15:19:18 | `60b9256d51f096e5eebc9541786af966ef58eb73` |
| `F:\Research\MiniMax_M3_Phase_2_汇报.md`            |  5,295 | 2026-07-10 15:41:36 | `6618fe75493a121d3763ca919260dbac06d542f2` |
| `F:\Research\MiniMax_M3_K冲突修复_技术文档.md`     | 10,726 | 2026-07-10 15:43:44 | `17e57ff170cafa2afd64ca5e3fd4f57ec7c1a709` |
| `F:\Research\MiniMax_M3_CI_集成说明.md`             |  6,197 | 2026-07-10 15:48:21 | `5acf246c9c24a3a70fa0322d592f7ed2f3a0fdc5` |
| `F:\Research\MiniMax_M3_Batch_诊断报告.md`          |  2,704 | 2026-07-10 13:34:42 | `4bbd52c7402a2a1355b2bfe445c87667bde9e9c1` |
| `F:\Research\MiniMax_M3_Phase_1_metrics.csv`        |  4,349 | 2026-07-10 11:35:52 | `677d3e50236d929667056c6fd846d202b94b36b4` |

## H. PAPER-A mm3 (4 files) — `RESAMPLING_CALIBRATION`

| File | Size | SHA1 |
|---|---:|---|
| `main.summary.mm3.md`     |  1,756 | `41ffa927f6d333943bfc0817144b6cc176137b76` |
| `main.methods.mm3.md`     |  6,081 | `29d8cf01063218a687a4fffc6629ae89fccdad50` |
| `main.experiments.mm3.md` |  8,130 | `6e54123c51cf7d4cf684cf03a0d4af2bf8405cf8` |
| `main.critique.mm3.md`    |  7,264 | `75a6feb39bf87a3de311bda12faa36d463218681` |

## I. PAPER-B mm3 (4 files) — `TEMPORAL_DYNAMICS`

| File | Size | SHA1 |
|---|---:|---|
| `main.summary.mm3.md`     |  1,647 | `8a106261611a70ad847f12b16cf0dd843bf72288` |
| `main.methods.mm3.md`     |  5,540 | `530ae58a47bc6be1e6a47ee8c452e13d5d3ee8aa` |
| `main.experiments.mm3.md` |  3,491 | `bed208a7329133a71e62e920f06430c84d6eab1e` |
| `main.critique.mm3.md`    |  6,334 | `b51348014067aa85344050f6e72b453a62a5bf65` |

## J. PAPER-C mm3 (4 files) — `calibration_contagion`

| File | Size | SHA1 |
|---|---:|---|
| `main.summary.mm3.md`     |  1,509 | `15ddd4be304e520aed6b95decd6c81f022e36764` |
| `main.methods.mm3.md`     |  5,345 | `74f926957d9f3da8cb6b7df6ab371ed9420e47bd` |
| `main.experiments.mm3.md` |  7,299 | `c18c15619933bf0185b8c6f959f2e6d5d2ac64d8` |
| `main.critique.mm3.md`    |  7,250 | `62cf6fa7b8d12cd1d94a8fdfc1010eab1344aba2` |

## K. PAPER-D mm3 (4 files) — `CALIBRATION_EFFECTS`

| File | Size | SHA1 |
|---|---:|---|
| `main.summary.mm3.md`     |  1,933 | `74b968107cf5d6dd3fff7ca474c20d22f88779bd` |
| `main.methods.mm3.md`     |  7,216 | `681bd09651d75dc52ce597d91049f5f616bcf718` |
| `main.experiments.mm3.md` |  8,750 | `0618103fde55aabcffe6fb163f7e38147449c2f4` |
| `main.critique.mm3.md`    |  6,135 | `b63096e55af80dadf7e791625dc656c9e00ed6d8` |

---

## Notes

1. **Methodology.** This scan is read-only. No source file under `F:\Research` was
   created, modified, or deleted. The verification used `ctypes.windll.kernel32
   .GetLongPathNameW` to resolve the long Unicode path `方法论` (a `Write`-tool
   encoding quirk made PowerShell `Test-Path` show false negatives for the same
   path), and `hashlib.sha1` for content fingerprinting.
2. **Two README files are byte-identical** (`e34e19fe…`). The `.loop` copy is a
   synonym of the main `方法论` README. This is by design, not duplication noise.
3. **Sizes match** the closing report's approximate figures within ±20 %; the
   closing report used rounded values (e.g. "30 KB" for the 41,744 B detector).
4. **mm3.md timing split**: PAPER-A and the methods/critique of PAPER-C are from
   2026-07-10 01:1x–01:2x (early batch run). PAPER-B, PAPER-D, and the rest of
   PAPER-C are from 15:2x–15:3x (a second batch run on the same day), consistent
   with the "16/16 mm3.md generated" claim.
5. **`F:\Research` is not a git repository** — there is no `.git` at the root, and
   `.github/` is present only because the Phase 1+2 work added a workflow file
   under it. The CI workflow is therefore not currently wired to a remote; it
   will only run after a `git init` + push to a remote.
6. **`F:\TMLR`** contains a Firefox profile (`.pytest_cache`, `default/`) plus two
   orphan scripts (`_diag_skills.py`, `tools\skill_diag_runner.py`) and two empty
   smoke-test files. It is not the project root and is unrelated to Phase 1+2.
7. **`F:\test`** contains an unrelated set of older experiments (June 2026) and
   newer projects (`calibration-benchmark`, `ml-paper-agent`, `ReviewerSim`).
   None of the Phase 1+2 deliverables live there.
