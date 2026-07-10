# GitHub Push 指南 - F:\Research

**状态**: 本地 git 仓库已就绪, 2 个 commit 等待 push

## 当前 commit 状态

```
d7f55c1 (HEAD -> main) chore: add full F:\Research research workspace (200+ projects)
88e7bcc feat(phase1+2): M3 LLM PDF summarization + hallucination detector v5.3
```

**总计 33,900 个文件, 1,125 万行代码**

## 网络状态

- ❌ **github.com 当前不可达** (Test-NetConnection: False)
- ❌ 跟 Phase 2 batch 卡住是同一问题 (Windows DNS resolver 系统级 hang)
- ✅ 等 DNS 恢复后可 push

## 推送步骤

### 1. 在 GitHub 网页上创建 repo

1. 打开 https://github.com/new
2. Repository name: `minimax-m3-phase1` (或改名)
3. Description: "Phase 1+2 M3 LLM 集成 + 幻觉检测器 v5.3"
4. 选择 **Public** 或 **Private**
5. **不要**勾选 "Add a README file" / "Add .gitignore" / "Choose a license"
6. 点击 **Create repository**

### 2. 等 DNS 恢复后 push

```bash
cd F:\Research

# 添加远程仓库
git remote add origin https://github.com/aidless/minimax-m3-phase1.git

# 验证远程
git remote -v

# 推送 (首次推送要 -u 设置 upstream)
git push -u origin main
```

### 3. 验证

- https://github.com/aidless/minimax-m3-phase1 显示 2 个 commit
- `.github/workflows/test_k_conflict_decision_tree.yml` 在仓库根
- README 等文档可见

## 备选推送方式 (DNS 仍不通时)

### 用 gh CLI (需先安装)

```bash
winget install --id GitHub.cli
gh auth login
gh repo create minimax-m3-phase1 --public --source=. --remote=origin --push
```

### 用 SSH (推荐)

```bash
# 生成 SSH key
ssh-keygen -t ed25519 -C "101927025+aidless@users.noreply.github.com"

# 复制公钥
cat ~/.ssh/id_ed25519.pub

# 在 GitHub: Settings -> SSH and GPG keys -> New SSH key
# 粘贴公钥

# 改 remote URL
cd F:\Research
git remote set-url origin git@github.com:aidless/minimax-m3-phase1.git
git push -u origin main
```

### 离线 bundle 推送 (极端情况)

```bash
# 在联网机器上恢复
git clone F:/Research/.git minimax-m3-phase1
cd minimax-m3-phase1
git remote add origin https://github.com/aidless/minimax-m3-phase1.git
git push -u origin main
```

## 注意事项

### 仓库大小

| 项目 | 估计 |
|---|---|
| 总文件数 | 33,900 |
| 总大小 | ~1-3 GB (含 .zcode/, _submission_package/, arxiv_*.pdf 等) |
| commit 1 (Phase 1+2) | ~1 MB (89 个代码/文档文件) |
| commit 2 (全量) | ~1-2 GB (含 PDF + zip) |

**GitHub 限制**: 单仓 ≤ 100 GB, 单文件 ≤ 100 MB.

如果 `arxiv_*.pdf` 或 `*.zip` 太大, 可能需要先 `git rm` 排除:
```bash
# 不入仓大型产物
echo "*.pdf" >> .gitignore
echo "*.zip" >> .gitignore
git rm --cached -r arxiv*/*.pdf
git commit -m "chore: remove large PDF/zip files"
```

### 建议: 拆分多个 repo

`minimax-m3-phase1` 仓名不准确, F:\Research 实际是**研究工作区**。建议:

| 未来拆分 | 路径 | 目的 |
|---|---|---|
| `m3-llm-integration` | `_inbox/方法论/`, `.loop/`, `.github/`, `_k_conflict_decision_tree.py`, `_test_granularity_suite.py` | M3 LLM 集成 + 检测器 |
| `mm-epc` | `mm_epc_*.py`, `phoenix_v*.py`, `mm-epc-ablation/` | MM-EPC 研究代码 |
| `tmlr-papers` | `tmlr_p6/`, `tmlr_p9/`, ..., `tmlr_p21_*/` | 多个 TMLR 论文项目 |
| `arxiv-collection` | `arxiv/`, `arxiv_1m/`, `arxiv_p13/`, `arxiv_p14/`, `arxiv_test/` | arXiv 论文 |
| `aidless-profile` | `README.md`, `AGENTS.md`, `CLAUDE.md`, `LICENSE` | 个人主页材料 |

## 当前状态

```bash
$ cd F:\Research
$ git log --oneline
d7f55c1 (HEAD -> main) chore: add full F:\Research research workspace (200+ projects)
88e7bcc feat(phase1+2): M3 LLM PDF summarization + hallucination detector v5.3
```

**准备好 push (等网络恢复)**.

---

**生成日期**: 2026-07-10
**关联文件**:
- `.git/` - 本地 git 仓库
- `.gitignore` - 排除规则 (含 nul/aux/con/prn Windows 保留名)
- `.github/workflows/test_k_conflict_decision_tree.yml` - CI 流水线 (push 后会跑)