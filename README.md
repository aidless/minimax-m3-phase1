# minimax-m3-phase1

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Wiring **MiniMax M3** into the TMLR submission pipeline, plus a hallucination detector
that runs over generated drafts before they reach the revision loop.

## Quickstart

```bash
git clone https://github.com/aidless/minimax-m3-phase1.git && cd minimax-m3-phase1

# 1) K 冲突决策树回归（离线，纯 Python，5 case）
python3 _k_conflict_decision_tree.py

# 2) 主测试套件（离线，15 case，软降级逻辑）
python3 _test_granularity_suite.py

# 3) 一条命令跑完整回归（同上两个 + 退出码聚合）
bash run_k_conflict_tests.sh --all
```

后续接入：

- **CI**：`.github/workflows/test_k_conflict_decision_tree.yml` 已随仓库提供（push/PR/每周一自动跑）
- **pre-commit**：`pip install pre-commit && pre-commit install`，改 detector 后 commit 前自动回归
- **真实调用**：复制 `.env.example` → `.env` 并填 `DEEPSEEK_API_KEY`（M3 网关经 DeepSeek 兼容入口）；
  集成说明见 `MiniMax_M3_CI_集成说明.md`

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
