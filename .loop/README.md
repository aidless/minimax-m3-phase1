# Loop Engineering v4.0

> 从单论文循环到跨论文智能审阅系统

## 设计理念

**问题**: 每篇论文从零开始审阅，发现的模式无法跨论文复用。

**方案**: 一个全局中枢 + 单论文实例的双层架构。中枢存储可复用规则、TMLR 基线、跨论文关联；每个论文有自己的 `.loop/` 实例追踪本地状态。

## 快速开始

```bash
# 查看全部论文状态
python .loop/status.py --all

# 初始化新论文
python .loop/init_paper.py my_paper "My Paper Title" --venue TMLR

# 对新论文运行自动预审阅
python .loop/pre_review.py my_paper

# 推进论文阶段（带前置条件校验）
python .loop/advance_phase.py my_paper

# 交互式回复审稿意见
python .loop/respond.py PAPER-A
```

## 目录结构

```
aettl-research/
├── .loop/                          ← 全局中枢
│   ├── registry.yaml               ← 论文注册表
│   ├── rulebook.yaml               ← 25条可自动化审阅规则
│   ├── tmlr_baselines.yaml         ← TMLR已发表论文基线
│   ├── cross_ref.yaml              ← 跨论文模式关联
│   ├── status.py                   ← 全局仪表盘
│   ├── pre_review.py               ← 自动预审阅扫描器
│   ├── init_paper.py               ← 论文初始化器
│   ├── respond.py                  ← 审稿回复工具
│   ├── advance_phase.py            ← 阶段推进工具
│   ├── templates/                  ← 可克隆模板
│   └── README.md                   ← 本文件
│
├── PAPER_A/                        ← 单论文实例
│   ├── main.tex
│   ├── src/
│   ├── experiments/
│   ├── figures/
│   ├── notes/
│   └── .loop/                      ← 本地状态
│       ├── state.yaml
│       ├── config.yaml
│       ├── issue_tracker.yaml
│       └── reviewer_response.yaml
│
└── PAPER_B/ ...
```

## 五个核心工具

| 工具 | 命令 | 功能 |
|------|------|------|
| `status.py` | `python .loop/status.py --all` | 全局仪表盘 + TMLR 基线对比 |
| `init_paper.py` | `python .loop/init_paper.py ID "Title"` | 一键生成论文骨架 |
| `pre_review.py` | `python .loop/pre_review.py ID` | 自动扫描 Tier 1 规则（7类阻断问题） |
| `respond.py` | `python .loop/respond.py ID` | 交互式审稿回复，逐条标记 resolved |
| `advance_phase.py` | `python .loop/advance_phase.py ID` | 校验前置条件后推进阶段 |

## 六阶段流水线

```
Phase 0 (基线评估) → Phase 1 (格式转换) → Phase 2 (内容审阅★)
  → Phase 3 (润色) → Phase 4 (匿名化) → Phase 5 (提交就绪)
```

每个 Phase 有前置条件、退出标准、最大轮次限制。

## 审阅规则库

从 3 篇论文的 11 轮审阅中提取，分三个 Tier：

- **Tier 1 (阻断)**: 7 条 — C1首次声称、L1遗漏文献、C6内部矛盾、M1混淆变量...
- **Tier 2 (高优)**: 10 条 — L2孤儿引用、S3效应量缺失、S4多重比较...
- **Tier 3 (润色)**: 8 条 — 术语一致性、图表完整性、写作质量...

完整 82 条规则见 `.loop/rulebook_full.yaml`（待补充）。

## TMLR 基线对标

5 篇已发表 TMLR 论文的关键特征已收录。自动对比你的论文在统计 rigor、数据集规模、CI/效应量报告等方面与 TMLR 中位数的差距。

## 添加新论文

```bash
# 1. 初始化
python .loop/init_paper.py my_paper "Title" --venue TMLR

# 2. 写论文 (编辑 main.tex)

# 3. 运行预审阅
python .loop/pre_review.py my_paper

# 4. 修复问题后推进阶段
python .loop/advance_phase.py my_paper
```

## 添加新规则

编辑 `.loop/rulebook.yaml`，在对应 Tier 下添加新条目：

```yaml
  NEW_rule_id:
    id: NEW
    category: claim_evidence
    description: "What to check"
    auto_check: "grep for 'pattern'"
    severity: critical
```

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v4.0 | 2026-07-02 | 全局中枢 + 自动预审阅 + TMLR对标 + 审稿回复追踪 |
| v3.1 | 2026-07-01 | 第三方审阅 + 回归测试 + Git自动提交 |
| v2.0 | 2026-06-28 | 多轮递进式审阅 (快速→深度→对抗→冷重启→终审) |
| v1.0 | 2026-06-27 | 单论文6阶段循环 |
