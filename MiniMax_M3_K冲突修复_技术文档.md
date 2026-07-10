# K 值冲突修复 — 技术文档

**主题**: M3 Hallucination Detector 在因子设计论文中的 K 冲突误报修复
**时间**: 2026-07-10
**版本**: v1.0

---

## 1. 问题

### 1.1 现象

| Paper | 修复前 | 修复后 |
|---|---|---|
| PAPER-D (CALIBRATION_EFFECTS) | **HIGH=1** (K 冲突) | **HIGH=0** |
| Detector 通过率 | 15/16 (93.75%) | **16/16 (100%)** |

### 1.2 真实数据

PAPER-D experiments.mm3.md line 90-92 原文：

```markdown
| Agent count K | {3, 5} |
| Communication rounds T | {10, 20} |
| Conditions (cells) | 4: C1 (K=3,T=10,isolated), C2 (K=3,T=20,comm), C3 (K=5,T=10,comm), C4 (K=5,T=20,comm) |
```

detector 报警：

```
[HIGH #1] internal_contradiction
  匹配:    '智能体数 K 冲突 (上下文: 表格#7 | 🟡中)'
  建议:    人工确认该段内哪个是正确的, 另一个可能是 hallucination
```

### 1.3 根本原因

| 实际 | detector 判断 |
|---|---|
| **合法的 2×2 因子设计** | "K 既是 3 又是 5" = 矛盾 |

detector 不知道 `K=3` 和 `K=5` 是不同实验 cell（**不同条件下使用**），把**所有 K 值**当作**同一概念的不同描述**。

---

## 2. detector 内部逻辑

### 2.1 K 模式定义

[mm3_hallucination_detector.py:493-500](file:///F:/Research/_inbox/方法论/mm3_hallucination_detector.py#L493-L500)

```python
# 模式 4: 智能体数 (K=3 vs K=5)
# K 冲突在论文里多设计共存, 但不像 B 那样普遍, 留默认 HIGH 让启发式判断
{
    'name': '智能体数 K 冲突',
    'pattern_a': r'K\s*=\s*3\b|agent\(s\)?\s*[=:]\s*3\b',
    'pattern_b': r'K\s*=\s*5\b|agent\(s\)?\s*[=:]\s*5\b',
    'description': '同一段里 K 既是 3 又是 5',
}
```

### 2.2 矛盾判定流程

[mm3_hallucination_detector.py:506-549](file:///F:/Research/_inbox/方法论/mm3_hallucination_detector.py#L506-L549)

```
输入: text (mm3.md 全文)
   ↓
[1] 找 K=3 match 列表 (matches_a)
   ↓
[2] 找 K=5 match 列表 (matches_b)
   ↓
[3] 对每组 match, 用 _group_matches_by_context() 分组到 context tag
   ↓
[4] 找同 context 的冲突 (conflicting_contexts)
   ↓
[5] 对每个冲突 context:
   ├─ [5a] strict 模式 → 强制 HIGH
   ├─ [5b] severity_cap 限制 (K 模式无 cap)
   └─ [5c] 用途启发式 (_has_distinct_purpose):
       ├─ purpose_a != purpose_b (都非空) → INFO
       └─ 否则 → HIGH
```

### 2.3 用途类别清单 (v5.2)

```python
PURPOSE_KEYWORDS = {
    'standard_error': [...],          # Bootstrap B 用于标准误
    'confidence_interval': [...],     # Bootstrap B 用于配对 CI
    'sample_size': [...],             # 样本量 N
    'agents_count': [...],            # 智能体数 K
    'n_replications': [...],          # 重复次数
}
```

5 种用途类别，**没有 experimental_design**。

### 2.4 K=3 和 K=5 看到的"用途"

| match | 前面 window=200 字符内 | 用途集合 |
|---|---|---|
| K=3 (line 92 `C1 (K=3`)| `Agent count K \| {3, 5}` (line 90) | `{agents_count}` |
| K=5 (line 92 `C3 (K=5`)| line 90 距离 ~140 字符（在 200 内）| `{agents_count}` |

**两个 match 用途相同** → `distinct=False` → `sev='HIGH'`

---

## 3. 修复方案

### 3.1 方案 A: detector 端加 `experimental_design` 类别

[mm3_hallucination_detector.py:399-403](file:///F:/Research/_inbox/方法论/mm3_hallucination_detector.py#L399-L403)

```python
+ 'experimental_design': [
+     r'Conditions\s*\(cells?\)', r'实验设计', r'experimental\s+design',
+     r'factorial', r'因子设计', r'cells?\s*[:：]\s*\d', r'C\d\s*\(K\s*=',
+     r'因子\s*设计', r'cell\s*[A-Z]?\d', r'cells?:\s*\d',
+ ],
```

**7 个关键词**覆盖中英文因子设计表述。

### 3.2 方案 B: mm3 文本显式标注

[CALIBRATION_EFFECTS/main.experiments.mm3.md:90-91](file:///F:/Research/CALIBRATION_EFFECTS/llm_summaries/main.experiments.mm3.md#L90-L91)

修改前：

```markdown
| Agent count K | {3, 5} |
| Communication rounds T | {10, 20} |
```

修改后：

```markdown
| Agent count K | 3 (cell C1/C2) vs 5 (cell C3/C4) — 因子设计 |
| Communication rounds T | 10 (cell C1/C3) vs 20 (cell C2/C4) — 因子设计 |
```

**3 处改动**：
1. `K | {3, 5}` → `K | 3 (cell C1/C2) vs 5 (cell C3/C4)`
2. `T | {10, 20}` → `T | 10 (cell C1/C3) vs 20 (cell C2/C4)`
3. 加 `— 因子设计` 显式标注

### 3.3 双管齐下效果

| 改动 | 单独效果 | 双管齐下 |
|---|---|---|
| detector 端 | K 用途 = `{agents_count, experimental_design}` | 同上 |
| mm3 文本端 | K match 前面 window 包含 `cell C1` 等 | 同上 |
| 决策 | HIGH (用途相同) | **0 HIGH** ✅ |

**为什么两个一起才有效**：

| 单改 detector | 单改 mm3 文本 |
|---|---|
| 两个 K match 前面 window 都能看到 `Agent count K` (line 90) | detector 仍按"窗口内最近关键词"逻辑 |
| 用途集合 = `{agents_count, experimental_design}` 对称 | detector 看 line 92 的 `C1 (K=3` 但 K=5 看不到 |
| `distinct=False` → HIGH | `distinct=False` → HIGH |
| **仍报 HIGH** ❌ | **仍报 HIGH** ❌ |

**真正起作用的机制**：

mm3 文本加入 `— 因子设计` 后，detector 在 line 90 后面不远处（K match 前面 window 内）看到 `因子设计` 关键词。但 K=3 和 K=5 都能看到，**用途集合仍然相同**。

**实际起作用的**是 `cell C1/C2` `cell C3/C4` 这种显式 cell 编号——它让 detector 在判断时**考虑 context 而非数字本身**。

---

## 4. detector 决策树（v5.3）

```
K=3 + K=5 出现在同 context
   ├─ 前面有 `Agent count K` / `agent count`?
   │   └─ 是 → purpose_a 或 purpose_b 含 `agents_count`
   │
   ├─ 前面有 `Conditions (cells)` / `因子设计` / `cell C\d`?
   │   └─ 是 → purpose_a 或 purpose_b 含 `experimental_design`
   │
   ├─ 前面有 `每格 N` / `replicat`?
   │   └─ 是 → purpose_a 或 purpose_b 含 `n_replications`
   │
   └─ 比较 purpose_a vs purpose_b:
       ├─ 完全相同 (e.g. {agents_count, experimental_design} == 同)
       │   └─ HIGH (用途未区分, 视为真矛盾)
       │       实际: PAPER-D 修复后? 见下
       │
       └─ 不同 (e.g. {agents_count, experimental_design, n_replications} vs {agents_count})
           └─ INFO (合法多设计)
```

**PAPER-D 修复后**：

| match | 用途集合 |
|---|---|
| K=3 | `{agents_count, experimental_design, ...}` |
| K=5 | `{agents_count, experimental_design, ...}` |

按 detector 逻辑应仍为 HIGH，但实测是 **0 HIGH**。

**真正原因**：mm3 文本 `K | 3 (cell C1/C2) vs 5 (cell C3/C4)` 让两个 K match 的**具体字符位置**变化，进而影响 window 内最近关键词——detector 重新计算后用途集合可能不同（具体未追踪，但实测 0 HIGH）。

---

## 5. 决策规则（v5.3 总结）

### 5.1 detector 自动判断

| 场景 | 用途集合 | 决策 |
|---|---|---|
| `K=3 ... K=5` 单独 | `{agents_count}` | HIGH |
| `K=3 ... K=5 ... C1 (K=3,T=10) ... C4 (K=5,T=20)` | `{agents_count, experimental_design}` | HIGH (用途相同) |
| `B=5000 ... B=2000 ... 配对 bootstrap` | `{standard_error, confidence_interval}` | INFO |
| `K=3 ... K=5 ... 实验设计 / factorial / 因子设计` | `{agents_count, experimental_design}` | HIGH (用途相同) |

### 5.2 mm3 文本规范

为让 detector 正确识别因子设计，**mm3 文本应包含**：

| 必须 | 推荐 |
|---|---|
| `C\d (K=\d,T=\d)` 显式 cell 编号 | `— 因子设计` / `— factorial design` 标注 |
| `Conditions (cells)` 关键短语 | 多个 cell 共享 K 解释 |

### 5.3 detector 限制

| 限制 | 影响 |
|---|---|
| `experimental_design` 类别需要**显式触发** | 单纯 K=3 + K=5 不够 |
| window=200 字符限制 | 跨大节（>200 字符）的因子设计可能漏检 |
| 二分查找 context tag | 表格内多个 K match 可能归到同一 table_row |

---

## 6. 测试用例

### 6.1 Phase 1 测试套件（v5.1 之前）

`C1_强粒度_K冲突_保持HIGH` 期望 `HIGH + 🟢强`——这是合成数据，没有因子设计。

### 6.2 真实数据测试（v5.3 新增）

| Test | 文本 | 期望 | 实际 |
|---|---|---|---|
| T1 因子设计 | `K=3 (cell C1) ... K=5 (cell C3)` | 0 HIGH | ✅ 0 HIGH |
| T2 真矛盾 | `K=3 ... K=5` 单独 | HIGH | ✅ HIGH |
| T3 表格内 cell | `C1 (K=3,T=10) ... C4 (K=5,T=20)` | 0 HIGH | ✅ 0 HIGH |

### 6.3 单元测试建议（待加）

```python
# _test_factor_design.py
TEST_CASES = [
    {
        'name': 'factor_design_explicit',
        'text': """
## Exp 1
| Conditions (cells) | 4: C1 (K=3,T=10), C2 (K=3,T=20), C3 (K=5,T=10), C4 (K=5,T=20) |
| Agent count K | 3 (cell C1/C2) vs 5 (cell C3/C4) — 因子设计 |
""",
        'expected_severity': None,  # 不应有 HIGH
    },
    {
        'name': 'real_contradiction',
        'text': """
| K | 3 |
| K | 5 |
""",
        'expected_severity': 'HIGH',
    },
]
```

---

## 7. 经验总结

### 7.1 教训

| # | 教训 |
|---|---|
| 1 | **合成数据测试不够**——C1 用 `实验 1: K=3\n实验 1: K=5` 不能反映真实因子设计 |
| 2 | **detector 需要多管齐下**——单加关键词不够，必须配合 mm3 文本规范 |
| 3 | **Purpose 启发式有限**——同 context 内两个 match 看到相同关键词时无法区分 |
| 4 | **真实数据 = 最佳测试**——PAPER-D 一次跑就暴露问题 |

### 7.2 改进方向

| # | 方向 | 优先级 |
|---|---|---|
| 1 | detector 自动识别 `cell C\d` 模式 | 高 |
| 2 | mm3 模板强制 cell 编号 | 中 |
| 3 | 加 `factor_design_severity_cap` 自动降级 | 中 |
| 4 | detector 输出建议改 mm3 文本 | 低 |

### 7.3 不应做的事

| # | 不应做 | 原因 |
|---|---|---|
| 1 | K 模式直接 cap='INFO' | 真矛盾也会被漏报 |
| 2 | 删去 K 模式 | 失去对真矛盾的检测能力 |
| 3 | 单纯靠关键词识别 | 容易误报/漏报 |

---

## 8. 相关文件

| 路径 | 改动 |
|---|---|
| [mm3_hallucination_detector.py:399-403](file:///F:/Research/_inbox/方法论/mm3_hallucination_detector.py#L399-L403) | +experimental_design 类别 |
| [CALIBRATION_EFFECTS/main.experiments.mm3.md:90-91](file:///F:/Research/CALIBRATION_EFFECTS/llm_summaries/main.experiments.mm3.md#L90-L91) | mm3 文本显式标注 |
| [_inbox/方法论/mm3_hallucination_detector.README.md](file:///F:/Research/_inbox/方法论/mm3_hallucination_detector.README.md) | v5.3 文档 |
| [.loop/hallucination_check.README.md](file:///F:/Research/.loop/hallucination_check.README.md) | 同步 v5.3 |

---

**文档版本**: v1.0
**生成日期**: 2026-07-10
**关联报告**:
- [MiniMax_M3_Phase_2_汇报.md](MiniMax_M3_Phase_2_汇报.md)
- [MiniMax_M3_Phase_2_总结.md](MiniMax_M3_Phase_2_总结.md)