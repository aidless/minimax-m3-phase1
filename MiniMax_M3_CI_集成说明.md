# K 冲突测试 CI 集成说明

**目的**: 自动跑 K 冲突决策树测试, 防止 detector 改动导致 K 冲突误报回归

---

## 📦 交付物

| 文件 | 平台 | 作用 |
|---|---|---|
| `.github/workflows/test_k_conflict_decision_tree.yml` | GitHub Actions | 推代码/PR/定时自动跑测试 |
| `run_k_conflict_tests.sh` | Linux/macOS/Git Bash | 本地运行 K 冲突测试 |
| `run_k_conflict_tests.cmd` | Windows | 本地运行 K 冲突测试 |
| `.pre-commit-config.yaml` | pre-commit | git commit 前自动跑测试 |

---

## 🚀 用法

### A. 本地手动跑

**Windows**:
```cmd
cd F:\Research
run_k_conflict_tests.cmd
```

**Linux/macOS**:
```bash
cd F:/Research
bash run_k_conflict_tests.sh
```

**跑 K 冲突 + 主测试套件**:
```bash
bash run_k_conflict_tests.sh --all
```

### B. GitHub Actions 自动跑

| 触发 | 说明 |
|---|---|
| push 到 main/master 改动 detector | 跑测试 |
| PR 改动 detector | 跑测试 |
| 每周一 0:00 UTC | 防回归 |
| 手动触发 (workflow_dispatch) | workflow_dispatch 入口 |

### C. Pre-commit Hook (git commit 前)

**安装**:
```bash
pip install pre-commit
pre-commit install
```

**效果**: 改 `_k_conflict_decision_tree.py` 或 `mm3_hallucination_detector.py` 后 `git commit`, 自动跑测试, fail 则阻止 commit。

---

## 🧪 测试内容

### K 冲突决策树 (5/5)

| Test | 场景 | 期望 |
|---|---|---|
| T1 | 因子设计 (PAPER-D 修复后) | INFO |
| T2 | 真矛盾 (同 context K=3 / K=5) | HIGH |
| T3 | cell 显式 + 因子设计 | HIGH |
| T4 | K 模式不匹配 B 模式 | NONE |
| T5 | strict 模式强制 HIGH | HIGH |

### 主测试套件 (15/15)

15 个粒度降级 case (C1-C15), 见 `_test_granularity_suite.py`。

### Smoke Test

- `mm3_hallucination_detector.py` 编译通过

---

## 📂 CI 流水线架构

```
┌────────────────────────────────────────────┐
│           触发条件                          │
├────────────────────────────────────────────┤
│  push to main/master (detector 改动)       │
│  pull_request (detector 改动)               │
│  schedule (每周一 0:00 UTC)                 │
│  workflow_dispatch (手动)                   │
└─────────────────┬──────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────┐
│  test-k-conflict (ubuntu-latest)            │
├────────────────────────────────────────────┤
│  1. Checkout                                │
│  2. Set up Python 3.9                       │
│  3. Run _k_conflict_decision_tree.py        │
│  4. Run _test_granularity_suite.py          │
│  5. Smoke test: detector py_compile         │
│  6. Validate mm3 files (best-effort)        │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│  test-on-windows (windows-latest)           │
├────────────────────────────────────────────┤
│  1. Checkout                                │
│  2. Set up Python 3.9                       │
│  3. Run _k_conflict_decision_tree.py        │
│  4. Run _test_granularity_suite.py          │
└────────────────────────────────────────────┘
```

---

## 🛠️ 集成步骤

### 当前状态: F:\Research 不是 git 项目

F:\Research 目录下没有 `.git` 也没有 `.github` 目录。
**CI 配置文件已经创建**, 但**不会自动跑**（因为没 git）。

### 启用 CI 的 3 种方式

| # | 方式 | 工作量 | 推荐度 |
|---|---|---|---|
| 1 | `git init` + 推到 GitHub | 5 min | ⭐⭐⭐ |
| 2 | 把 .github 移到 F:\TMLR 推 GitHub | 10 min | ⭐⭐ |
| 3 | 保留配置作为参考, 等项目正式 git 化 | 0 | ⭐ |

### 方式 1: git init + GitHub (推荐)

```bash
cd F:\Research
git init
git add .github/ run_k_conflict_tests.sh run_k_conflict_tests.cmd .pre-commit-config.yaml _k_conflict_decision_tree.py
git commit -m "ci: K conflict decision tree tests"
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```

### 方式 2: 复制到现有 git 项目

```bash
cp .github/workflows/test_k_conflict_decision_tree.yml <existing-project>/.github/workflows/
cp run_k_conflict_tests.sh run_k_conflict_tests.cmd .pre-commit-config.yaml <existing-project>/
```

---

## 📋 退出码约定

| 退出码 | 含义 | CI 行为 |
|---|---|---|
| 0 | 全部测试通过 | ✅ 绿勾 |
| 1 | 部分测试失败 | ❌ 红叉, block merge |
| 124 | timeout (5 min) | ❌ 红叉, 需优化 |

---

## 🎯 后续优化

| # | 优化 | 工作量 |
|---|---|---|
| 1 | 加 `coverage` 报告 (`pytest --cov`) | 1h |
| 2 | 加 `mutmut` mutation testing | 2h |
| 3 | 集成到 advance_phase.py gate | 0.5h |
| 4 | 加 Slack/Discord 通知 | 0.5h |
| 5 | 用 matrix strategy 跑 3.8/3.9/3.10/3.11 | 0.5h |

---

## 📚 相关文件

| 文件 | 用途 |
|---|---|
| `_k_conflict_decision_tree.py` | K 冲突决策树实现 + 5 测试 |
| `_test_granularity_suite.py` | 15 case 主测试套件 |
| `_inbox/方法论/mm3_hallucination_detector.py` | 主 detector |
| `MiniMax_M3_K冲突修复_技术文档.md` | K 冲突修复技术文档 |

---

**文档版本**: v1.0
**生成日期**: 2026-07-10
**关联文档**:
- [MiniMax_M3_K冲突修复_技术文档.md](MiniMax_M3_K冲突修复_技术文档.md)
- [MiniMax_M3_Phase_2_汇报.md](MiniMax_M3_Phase_2_汇报.md)