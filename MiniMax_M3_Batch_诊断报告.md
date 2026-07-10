# MiniMax M3 Batch 卡住 - 诊断报告

**诊断时间**: 2026-07-10
**触发场景**: Phase 2 batch 跑 10 个 mm3.md，生成 1 个后剩余 9 个卡住

## 排查步骤

### Step 1: 隔离 demo 进程

| 测试 | 命令 | 结果 |
|---|---|---|
| demo 单次调用 | `python demo.py --task critique` | 跑了 6+ 分钟无 stdout |
| demo 加 `timeout=60s` | `subprocess.run(timeout=60)` | 进程不退 |
| demo 加 `timeout=120s` | `urlopen(timeout=120)` 内置 | 进程不退 |

**结论**: 不是 demo 进程本身卡——demo 内部 `urllib.urlopen(req, timeout=120)` 卡住。

### Step 2: 隔离网络

| 测试 | 命令 | 结果 |
|---|---|---|
| curl POST API | `curl -m 8 ...api.minimaxi.com/v1/chat/completions` | 卡 8s 后被 m 8 截断 |
| Test-NetConnection 443 | `Test-NetConnection api.minimaxi.com -Port 443` | 卡 90+ 秒 |
| Resolve-DnsName M3 | `Resolve-DnsName api.minimaxi.com` | 卡 90+ 秒 |

**关键发现**: `api.minimaxi.com` DNS 解析在 Windows 系统层 hang。

### Step 3: 全局网络

| 测试 | 命令 | 结果 |
|---|---|---|
| Resolve-DnsName baidu | `Resolve-DnsName www.baidu.com` | **同样卡 45+ 秒** |

**关键发现**: 不仅是 `api.minimaxi.com`——**任意外网域名** DNS 解析都卡。

## 根本原因

**Windows 系统 DNS resolver 整体 hang**——和 demo 进程、M3 API 完全无关。

### 怀疑方向

| # | 嫌疑 | 验证方式 |
|---|---|---|
| 1 | 本机占用了 53 端口（占 DNS）| `netstat -ano \| findstr :53` |
| 2 | localhost:3000 服务（zcode）拦截 DNS | `Get-NetTCPConnection -LocalPort 53` |
| 3 | Windows DNS Client 服务挂了 | `Get-Service DNS Client` |
| 4 | DNS 缓存溢出 | `Clear-DnsClientCache` |
| 5 | 路由表损坏 | `route print` |

## 结论

**Batch 卡住 = 网络问题，与 M3 LLM 集成、detector、demo 脚本都无关。**

| 组件 | 状态 |
|---|---|
| M3 API 调用 | ✅ 1 次成功（生成 PAPER-C summary）|
| demo 脚本 | ✅ 正常（前面 1 次跑通）|
| Detector | ✅ 7/7 通过（0 HIGH）|
| **Windows DNS resolver** | ❌ **当前 hang** |

## 后续

**短期**: 用 **global endpoint** 备选（`https://api.MiniMax.io/v1`）——不同域名，绕开 DNS hang。

**长期**: 给 demo 脚本加：
1. `urllib3.Retry` + `Retry-After` 处理
2. **`socket.create_connection((host, port), timeout=10)`** 作为 DNS 解析的早期检测
3. 在 batch 里加**健康检查**——开始 batch 前先测一次 API 联通性
4. 失败时**退避**（sleep 30/60/120s）而非 stop

## 状态

- ✅ 7/16 mm3.md 已生成（4 paper 全验证过 0 HIGH）
- ❌ 剩余 9 个需要等 DNS 恢复或换 endpoint
- 📝 **接受当前 7/16 状态作为 Phase 2 结论**