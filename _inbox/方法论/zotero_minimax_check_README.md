# Zotero + MiniMax 配置检查工具

**脚本**: [zotero_minimax_check.py](file:///F:/Research/_inbox/方法论/zotero_minimax_check.py)
**日期**: 2026-07-10
**作者**: 自动生成（基于 MiniMax Token Plan 接入笔记）

---

## 用途

三合一工具，验证你 TMLR 写作流水线里 Zotero + MiniMax M3 这条链路是否正常工作。

| 子命令 | 检查内容 |
|---|---|
| `api` | MiniMax API Key + Base URL 是否能连通，4 个端到端测试 |
| `zotero` | Zotero Preferences 里 MiniMax 配置是什么 |
| `all`（默认）| API + Zotero + 交叉验证 + 自动修正建议 |

---

## 用法

### 最常用：完整检查

```powershell
cd F:\Research\_inbox\方法论
python zotero_minimax_check.py
```

输出三段：
1. **API 连通性测试** - 国内 cn + 海外 global 两个 endpoint 各跑 4 个 case
2. **Zotero 配置检查** - 从 prefs.js + extension-settings 读填入的 base URL / API key / model
3. **交叉验证** - 用 Zotero 填的 key 测 Zotero 填的 URL，看是否一致
4. **修正建议** - 如果不匹配，自动给出正确的 URL

### 只测 API（无需 Zotero）

```powershell
python zotero_minimax_check.py api
```

适用场景：
- Zotero 还没装
- 想快速验证 token 是否过期
- 想确认 key 是国内 cn 还是海外 global

### 只查 Zotero 配置

```powershell
python zotero_minimax_check.py zotero
```

适用场景：
- Zotero 配完不知道是否生效
- 多人共用一台机器时核对谁配了什么

### 指定 key（不读 .env）

```powershell
python zotero_minimax_check.py api --key sk-cp-GfCveDNp...ARVNLg
```

### 只测一个 region

```powershell
python zotero_minimax_check.py api --cn-only
python zotero_minimax_check.py api --global-only
```

---

## 测试用例说明

脚本会跑 4 个测试，每个失败都能定位问题：

| 测试 | 消耗 | 用途 | 失败时诊断 |
|---|---|---|---|
| `list_models` | 0 token | 验证 key 有效性 | 401 → key 失效/region 不匹配 |
| `chat_minimal` (max_tokens=8) | ~5 tokens | 端到端连通性 | 网络问题/DNS 污染 |
| `chat_chinese` (max_tokens=32) | ~30 tokens | 中文理解 | 编码问题 |
| `chat_thinking` (max_tokens=1024) | ~50 tokens | reasoning model 识别 | max_tokens 不够 thinking |

`list_models` 调的是 `GET /v1/models` 端点——不消耗 token，**专用于检查 key 是否有效**，适合频繁调用。

---

## 输出样例

```
======================================================================
  Zotero + MiniMax M3 配置检查工具
  时间: 2026-07-10 00:59:05
======================================================================

  Key 来源: C:\Users\Administrator\AppData\Local\hermes\.env
  Key 字段: MINIMAX_API_KEY
  Key 预览: sk-cp-GfCv...ARVNLg

======================================================================
  API 连通性测试 (Key: sk-cp-GfCv...ARVNLg)
======================================================================

  ▸ cn (https://api.minimaxi.com/v1)
    [✓] list_models            0.2s  HTTP 200 | 8 models listed
    [✓] chat_minimal           1.2s
    [✓] chat_chinese           1.9s
    [✓] chat_thinking          1.6s
    ✅ ALL PASS (4/4)

  ▸ global (https://api.minimax.io/v1)
    [✗] list_models            2.2s  HTTP 401
    [✗] chat_minimal           2.0s  HTTP 401
    [✗] chat_thinking          2.0s  HTTP 401
    ❌ ALL FAIL (0/4)
```

---

## 常见问题

### Q: 跑出来 cn ✓ global ✗ 说明什么？

A: 你的 key 是国内 cn 专属。在 Zotero Preferences 里 **Base URL 必须填 `https://api.minimaxi.com/v1`**（注意是 `minimaxi.com`，**两段 ni**，不是 `minimax.io`）。

### Q: 跑出来全 401？

A: 三种可能：
1. key 已过期或被吊销 → 去 platform.minimaxi.com 控制台检查
2. Token Plan 订阅未付款/到期
3. key 跟 endpoint region 错配

### Q: 跑出来 cn ✓ global ✓ 呢？

A: 你的 key 是双 region 通用。Zotero 里任选一个 endpoint 都能用。

### Q: 脚本说"找不到 Zotero 里的 MiniMax 配置"，但我明明填了？

A: llm-for-zotero v3.8.25 把 provider 配置存在 plugin 内部的 SQLite (addon-storage)，**不是明文 prefs.js**。脚本只能验证它能读到的明文部分。

替代验证方式：
- 在 Zotero GUI 里点 Test Connection → 看到 ✓
- 用本脚本的 `api` 模式独立验证 token

### Q: 想批量给团队成员验证？

```powershell
# 把每个人的 key 列出来
foreach ($key in @('sk-cp-AAA...', 'sk-cp-BBB...', 'sk-cp-CCC...')) {
    Write-Host "=== Testing $key ==="
    python zotero_minimax_check.py api --key $key
}
```

---

## 与其他工具的关系

| 工具 | 角色 |
|---|---|
| `mm_epc_minimax_replication.py` | 实际跑 MiniMax M3 做 evaluator 的复现脚本 |
| `zotero_minimax_check.py`（本工具） | **只是验证**：检查 key + URL 是否工作 |
| `MiniMax_M3_接入笔记.md` | 接入技术文档（含踩坑记录） |
| `Zotero_阶段1_部署手册.md` | Zotero 部署步骤手册 |

---

## 依赖

- Python 3.8+
- 标库 only（`urllib`, `json`, `argparse`, `pathlib`, `re`, `time`）
- 无需 `pip install`

---

## 已知局限

1. **不能读 v3.8.25 加密存储** - plugin 内部 addon-storage 用 SQLite，key 在加密表中。本脚本只能扫明文位置。
2. **不能自动测 Test Connection** - 那个按钮在 Zotero GUI 里，脚本无法触发。
3. **不修改 Zotero 配置** - 只读不写。要改配置请用 Zotero GUI。

---

## 更新日志

### v1.0 (2026-07-10)
- 初始版本
- API 测试：4 个 case × 2 endpoints
- Zotero 配置：扫描 prefs.js + extension-settings
- 交叉验证 + 自动修正建议
- 支持命令行参数 `--key`, `--cn-only`, `--global-only`, `--fix`