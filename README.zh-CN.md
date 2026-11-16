# minimax-m3-phase1

STATUS: WORK-IN-PROGRESS — not A yet

下面的表是一次已经闭合的离线测量。A 档还差的一项是仓库元数据：GitHub About 的线上描述没有改。替换文案在 About 一节，中英文件使用同一段英文。

English: [README.md](README.md). 失败模式：[FAILURE_MODES.md](FAILURE_MODES.md).

<!-- problem:start -->
智能体写的 TMLR 草稿可能带有伪造引用、残缺标识符、同一段里的数值冲突、过精确的数字，以及生造的缩写。
本仓第一阶段的门禁是 `_inbox/方法论/mm3_hallucination_detector.py` 里的六条启发式，不是对 MiniMax M3 在线调用的测量。
闭合的结果是这些启发式在 `eval/fixtures/snippets.jsonl` 上的精确率与召回率；标签写在开跑之前。
<!-- problem:end -->

<!-- headline:start -->
标题结果：时钟固定为 2026-07-10、网络查询被阻断时，六条启发式的精确率和召回率见下表。界限：合成片段、标签与评分脚本同一作者、只跑离线启发式。不是 MiniMax M3 的在线调用，也不是真实论文上的误报率。
<!-- headline:end -->

<!-- fixture-metrics:start -->
| detector | tp | fp | fn | tn | precision | recall |
|---|---:|---:|---:|---:|---|---|
| arxiv | 3 | 1 | 3 | 25 | 3/4 = 0.750 | 3/6 = 0.500 |
| github | 1 | 1 | 1 | 29 | 1/2 = 0.500 | 1/2 = 0.500 |
| internal | 4 | 1 | 1 | 26 | 4/5 = 0.800 | 4/5 = 0.800 |
| doi | 1 | 1 | 1 | 29 | 1/2 = 0.500 | 1/2 = 0.500 |
| precision | 1 | 1 | 2 | 28 | 1/2 = 0.500 | 1/3 = 0.333 |
| terminology | 1 | 1 | 1 | 29 | 1/2 = 0.500 | 1/2 = 0.500 |
n=32 synthetic fixtures; clock=2026-07-10; current_year=2026; network=blocked; check_online=false; labels=same-author, written before the run; heuristic offline mode only; not live MiniMax M3; not a real-paper false-positive rate.
<!-- fixture-metrics:end -->

## 复现

```bash
git clone https://github.com/aidless/minimax-m3-phase1.git
cd minimax-m3-phase1
make check
```

`make check` 是离线入口。只需要 Python 3 标准库，不 `pip install`，不需要 API key，也不访问网络。它会重跑 K 冲突决策树、15 条粒度套件、`eval/run_cases.py`、合成片段评测（含翻转一条标签后必须变红的自检），以及旧数字的分类。新克隆应远少于 15 分钟；这套检查本身是几秒。

表与重新计算不一致时，`make check` 失败。同一张表写在 `README.md`、本文件、`FAILURE_MODES.md` 和 `PREREG.md`。

## 检测器放在哪

正在使用的检测器仍在 `_inbox/方法论/mm3_hallucination_detector.py`。回归和这次评测都从这条路径导入。设计笔记在 `_inbox/方法论/mm3_hallucination_detector.README.md` 和 `.loop/hallucination_check.README.md`。

## 数字从哪来

表由 `eval/run_fixture_eval.py` 从 `eval/fixtures/snippets.jsonl` 重算。逐条预测、严重度和检测器自己的匹配串在 `eval/fixture_metrics.json`。标签规则在 `eval/fixtures/PROTOCOL.md`。

`eval/verify_cited_numbers.py` 把 `MiniMax_M3_Phase_1_metrics.csv` 的每一行和 `PHASE_1_2_EVIDENCE.md` 的每一条 SHA1 分到 `eval/cited_status.json`。标题结果不用其中标成不可复核、过期、不一致、清点子集或非测量的行。

## 不能复核的旧声明

<!-- unverifiable-legacy:start -->
`MiniMax_M3_Phase_1_metrics.csv` 里 `real_data` 行（含 PAPER-A 计数和 arXiv 备注）指向本检出中没有的输出。`PHASE_1_2_EVIDENCE.md` 是 2026-07-10 对 `F:\Research` 的扫描；仓库里还在的文件被标成 match 或 stale，16 个 `mm3.md` 文件名不在本检出。阶段报告里的「0 HIGH 误报」依赖未提交的 M3 输出，不是本仓的结果。CSV 的 `readme_size` 与检测器 README 的当前大小不一致（`RECOMPUTED_MISMATCH`）。`scripts_count` 和 `integration_points` 是清点子集，不是全仓普查。
<!-- unverifiable-legacy:end -->

## GitHub About

线上描述仍是："MiniMax M3 wired into the TMLR submission pipeline plus a hallucination detector; Phases 1–2 documented, later phases not included"。

替换成：

<!-- about:start -->
Offline scores for six hallucination-detector heuristics on synthetic fixtures. Not a live MiniMax M3 run and not a real-paper false-positive rate.
<!-- about:end -->

## CI

`.github/workflows/pr-checks.yml` 和 `.github/workflows/test_k_conflict_decision_tree.yml` 都在 pull request 上跑同一个 `make check`。每周定时任务此前已经去掉。

## 未合并的 pull request

四个未关闭条目都是 Dependabot，没有别的 open issue：#3 pyyaml、#4 pdfplumber、#5 pytest、#6 `actions/upload-artifact` 从 4.6.2 到 7.0.2。`make check` 不安装这些包。#6 只影响 `packaging.yml`，且是主版本升级。这里只读过，没有合并。

## 许可证

MIT。见 [LICENSE](LICENSE)。
