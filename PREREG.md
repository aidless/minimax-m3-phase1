# 预注册规格 — minimax-m3-phase1 幻觉检测器

> 这份文档把本仓**真实**的研究假设、评测方案、成功标准与边界写下来，**先于**（或
> 独立于）任何"能力声明"。所有引用数字均来自仓内可复算的测试套件与源码，不虚构。

## 1. 研究对象

本仓把 MiniMax M3 接入 TMLR 投稿管线，并带一个**幻觉检测器**
（`_inbox/方法论/mm3_hallucination_detector.py`），在生成稿进入修订循环前跑一遍。
检测器不是通用幻觉检测，它检测**同一文档内对同一概念的不同描述**（内部矛盾/
多设计共存），分四类模式：`confidence 描述冲突`、`ECE 分箱数冲突`、
`Bootstrap B 数量冲突`、`智能体数 K 冲突`（`detect_internal_contradictions`，
行 456 起）。检测不是基于"全文出现"，而是**基于同 context 内出现**——实验、
标题、表格行、列表项、段落五个粒度（`GRANULARITY`）。

## 2. 假设（H1–H5）

- **H1（context-aware 判定）**：同一概念的不同描述在**同 context** 内出现应被判为
  疑似矛盾；在不同 context 出现（如 E1 用 5-category confidence、E3 用 continuous
  confidence）应判为**多设计共存**而非矛盾。
- **H2（用途启发式）**：同一 context 内两个数字若各带**不同用途**关键词（如
  "标准误 SE=5000" vs "配对 CI=2000"），应降为 `INFO`（合法多设计）；若无用途区分，
  保持 `HIGH`（真矛盾）。
- **H3（粒度软降级）**：`🔴弱`（段落）context 里的 `HIGH` 应**自动降为 `MEDIUM`**
  （段落是弱 context、可能跨节、误报率高，不应直接 block）；`🟢强`（实验）与
  `🟡中`（标题/表格/列表）不降。
- **H4（strict 覆盖）**：`strict=True` 应**强制 `HIGH`**（用户主动选最严格模式），
  覆盖软降级与用途启发式。
- **H5（可执行性）**：决策树逻辑可被独立复现为可执行代码，且该参考实现通过
  K 冲突 5 用例 + 粒度 15 用例。

## 3. 评测方案

### 3.1 K 冲突决策树（`_k_conflict_decision_tree.py`，5 用例）

把 README §4 的决策树转成可执行参考实现，逐用例验证分类。真实执行：
`python3 _k_conflict_decision_tree.py` → **5 PASS, 0 FAIL**。

| 用例 | 场景 | 期望 |
|---|---|---|
| K-explicit strong/no-strict | 实验级 K 冲突，非严格 | HIGH |
| B-title purpose-distinct | 标题级 B 冲突，用途区分 | INFO |
| K-table factorial | 表格级 K 冲突（因子设计） | HIGH |
| K-mode-mismatch | 模式不匹配 | HIGH |
| strict-force-HIGH | strict 强制 | HIGH |

### 3.2 粒度软降级套件（`_test_granularity_suite.py`，15 用例）

5 粒度 × 4 模式 × strict/normal 的覆盖。真实执行：
`python3 _test_granularity_suite.py` → **15 PASS, 0 FAIL**。关键断言：
C5/C8（段落 soft 降级 MEDIUM+weak）、C9/C15（strict 强制 HIGH）、
C11（3+1 因子设计 HIGH+strong）、C13（跨 H3 INFO+mid）。

### 3.3 判定标准（成功 = 满足）

| 标准 | 目标 | 当前实测 |
|---|---|---|
| K 冲突决策树 | 5/5 PASS | 5/5（本树） |
| 粒度软降级 | 15/15 PASS | 15/15（本树） |
| 软降级方向 | 段落 HIGH→MEDIUM | 生效（C5/C8） |
| strict 覆盖 | strict→HIGH 不降级 | 生效（C9/C15） |

## 4. 明确边界（不证明什么）

1. **不证明检测器在真实论文上抓到了幻觉**：`MiniMax_M3_Phase_1_完成报告.md` 的
   "0 HIGH 误报" 依赖 4 份真实 PDF 摘要（M3 API 生成），**未提交**，本仓不可复现。
2. **不证明检出率/误报率**：15 用例是**合成**单元套件（手工构建片段），不是真实管线
   基准，不含统计功效或置信区间。
3. **不证明 Phase 3+ 能力**：Phase 3（LLM-as-judge fallback）与 Phase 4（本地小模型）
   不在本仓。
4. **词法启发式，非语义理解**：检测器基于正则+上下文标签，`HIGH` 只表示"同一
   context 内数字不一致且无用途区分"，**不**等于该数字一定是幻觉。
5. **小样本**：所有结论基于 5+15=20 个构造用例，不构成泛化声明。

## 5. 预注册承诺

任何后续**能力**声明（"检出率 X%""误报率 Y%"）必须先在本仓补真实评测数据
（提交真实 PDF 摘要或真实管线基准）再写；本仓当前只声明"5 用例决策树 + 15 用例
粒度套件通过"，且明确该声明**不**外推到真实论文或能力上限。
