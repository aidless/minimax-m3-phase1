# minimax-m3-phase1

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Wiring **MiniMax M3** into the TMLR submission pipeline, plus a hallucination detector
that runs over generated drafts before they reach the revision loop.

## What is in here

| Path | Contents |
|---|---|
| `MiniMax_M3_CI_集成说明.md` | how M3 plugs into the CI gates |
| `MiniMax_M3_K冲突修复_技术文档.md` | the K-conflict fix write-up |
| `MiniMax_M3_Batch_诊断报告.md` | batch diagnostics |
| `PHASE_1_2_EVIDENCE.md` | phase 1 and 2 evidence |
| `MiniMax_M3_Phase_1_metrics.csv` | phase 1 metrics |
| `MiniMax_M3_Phase_1_完成报告.md` / `MiniMax_M3_Phase_2_总结.md` | phase reports |
| `_diag_one.py` / `_diag_realtime.py` | diagnostics |
| `.env.example` | the environment variables to copy |

The reports are written in Chinese; the repository description is the English summary.

## Status

Phases 1 and 2 are documented in the reports above. Phase 3 and later are not in this
repository — read the reports before assuming a capability exists.

## License

MIT. See [LICENSE](LICENSE).
