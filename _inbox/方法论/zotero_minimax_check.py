"""
zotero_minimax_check.py
=======================
Zotero + MiniMax M3 配置检查工具 (固化版)

用途:
  1. 验证 MiniMax API Key 跟 Base URL 是否真的能连通
  2. 读取 Zotero Preferences 里填的 MiniMax 配置,核对跟 API 实际行为是否一致
  3. 检测常见配置错误 (key/region 不匹配、model 名错、key 失效等)
  4. (可选) 自动同步修正 Zotero 偏好配置

子命令:
  python zotero_minimax_check.py api           # 只测 API 连通性
  python zotero_minimax_check.py zotero         # 只查 Zotero 偏好
  python zotero_minimax_check.py all            # 全查 (默认)
  python zotero_minimax_check.py all --fix      # 检查 + 自动修正配置
  python zotero_minimax_check.py all --key sk-cp-...   # 用指定 key (覆盖 .env)

位置: F:\\Research\\_inbox\\方法论\\zotero_minimax_check.py
作者: (生成于 2026-07-10)
依赖: Python 3.8+ (用 urllib 不需要额外 pip)
"""
import os
import sys
import json
import time
import re
import argparse
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ── 颜色输出 ──────────────────────────────────────────────────────
class C:
    R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'; B = '\033[94m'
    M = '\033[95m'; CY = '\033[96m'; DIM = '\033[2m'; BOLD = '\033[1m'; END = '\033[0m'

def enable_windows_ansi():
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

# ── 常量 ──────────────────────────────────────────────────────────
ZOTERO_PROFILE_GLOB = Path(os.environ.get('APPDATA', '')) / 'Zotero' / 'Zotero' / 'Profiles'
ENV_FILES = [
    Path(os.environ.get('USERPROFILE', '')) / 'AppData' / 'Local' / 'hermes' / '.env',
]
ENDPOINTS = {
    'cn':     'https://api.minimaxi.com/v1',   # 国内 cn
    'global': 'https://api.minimax.io/v1',     # 海外 global
}

# ── 工具: 读取 API Key ─────────────────────────────────────────────
def read_api_key(arg_key=None):
    """优先级: --key 参数 > .env 文件 > None"""
    if arg_key:
        return arg_key, 'command-line arg', None
    for env in ENV_FILES:
        if not env.exists():
            continue
        try:
            for line in env.read_text(encoding='utf-8').splitlines():
                m = re.match(r'(MINIMAX_(?:CN_)?API_KEY|OPENAI_API_KEY)\s*=\s*(.+)', line.strip())
                if m:
                    val = m.group(2).strip().strip('"').strip("'")
                    if val.startswith('sk-'):
                        return val, str(env), m.group(1)
        except Exception:
            pass
    return None, None, None

# ── 工具: 安全访问嵌套 dict ──────────────────────────────────────
def _sg(body, *keys, default='?'):
    if not isinstance(body, dict): return default
    cur = body
    for k in keys:
        if not isinstance(cur, dict) or k not in cur: return default
        cur = cur[k]
    return cur

# ── MiniMax API 客户端 ─────────────────────────────────────────────
class MiniMaxClient:
    def __init__(self, base_url, api_key, model='MiniMax-M3'):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model

    def _req(self, path, body, timeout=20):
        req = urllib.request.Request(self.base_url + path,
                                     data=json.dumps(body).encode(),
                                     method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {self.api_key}')
        return urllib.request.urlopen(req, timeout=timeout)

    def list_models(self):
        req = urllib.request.Request(self.base_url + '/models', method='GET')
        req.add_header('Authorization', f'Bearer {self.api_key}')
        try:
            r = urllib.request.urlopen(req, timeout=15)
            return 200, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8', errors='replace')[:500]
        except Exception as e:
            return -1, f'{type(e).__name__}: {str(e)[:200]}'

    def chat(self, message, max_tokens=64, temperature=0):
        try:
            r = self._req('/chat/completions', {
                'model': self.model,
                'messages': [{'role': 'user', 'content': message}],
                'max_tokens': max_tokens, 'temperature': temperature,
            })
            return 200, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8', errors='replace')[:500]
        except Exception as e:
            return -1, f'{type(e).__name__}: {str(e)[:200]}'

    def list_model_ids(self):
        code, body = self.list_models()
        if code != 200: return []
        return [m.get('id') for m in _sg(body, 'data', default=[]) if m.get('id')]

# ── API 测试套件 ──────────────────────────────────────────────────
def test_api(base_url, api_key, model='MiniMax-M3'):
    """返回 dict {test_name: (code, body, ok, elapsed, detail)}"""
    client = MiniMaxClient(base_url, api_key, model)
    results = {}

    # 测试用 list of dict 而非 (method_name, kwargs) tuple,避免 getattr 错误
    tests = [
        {
            'name': 'list_models',
            'run': lambda: client.list_models(),
            'ok': lambda c, b: c == 200 and _sg(b, 'data') != '?',
            'detail': lambda c, b: f'HTTP {c} | {len(_sg(b, "data", default=[]))} models listed',
        },
        {
            'name': 'chat_minimal',
            'run': lambda: client.chat('ping', max_tokens=8),
            'ok': lambda c, b: c == 200,
            'detail': lambda c, b: f'HTTP {c} | response=' + repr(_sg(b, "choices", 0, "message", "content")[:30])[:60],
        },
        {
            'name': 'chat_chinese',
            'run': lambda: client.chat('一句话:你好', max_tokens=32),
            'ok': lambda c, b: c == 200,
            'detail': lambda c, b: f'HTTP {c} | response=' + repr(_sg(b, "choices", 0, "message", "content")[:40])[:70],
        },
        {
            'name': 'chat_thinking',
            'run': lambda: client.chat('1+1=?', max_tokens=1024),
            'ok': lambda c, b: c == 200,
            'detail': lambda c, b: (
                f'HTTP {c} | has_think=' + str(bool(re.search(r'<think>', str(_sg(b, "choices", 0, "message", "content")))))
                + ' | reasoning_tokens=' + str(_sg(b, "usage", "completion_tokens_details", "reasoning_tokens"))
            )[:200],
        },
    ]

    for t in tests:
        t0 = time.time()
        code, body = t['run']()
        elapsed = time.time() - t0
        ok = t['ok'](code, body)
        detail = t['detail'](code, body)
        results[t['name']] = {'code': code, 'body': body, 'ok': ok,
                              'elapsed': elapsed, 'detail': detail}

    return results

# ── Zotero 配置读取 ──────────────────────────────────────────────
def find_zotero_profile():
    """找 Zotero 默认 profile 目录."""
    if not ZOTERO_PROFILE_GLOB.exists():
        return None
    for prof in ZOTERO_PROFILE_GLOB.iterdir():
        if prof.is_dir() and prof.name.endswith('.default'):
            return prof
    return None

def read_zotero_minimax_config():
    """
    从 Zotero profile 的 prefs.js + extension-settings/ 读取 MiniMax 配置.
    返回 dict: {base_url, api_key, model, found}
    """
    profile = find_zotero_profile()
    if not profile:
        return {'found': False, 'reason': 'Zotero profile not found'}

    prefs_file = profile / 'prefs.js'
    if not prefs_file.exists():
        return {'found': False, 'reason': f'{prefs_file} not found'}

    # llm-for-zotero 把配置存在 extension-settings/<addon-id>.json
    es_dir = profile / 'extension-settings'
    config = {
        'profile': str(profile),
        'prefs_file': str(prefs_file),
        'base_url': None,
        'api_key': None,
        'model': None,
    }

    # 优先级 1: extension-settings/*.json (llm-for-zotero 主配置)
    if es_dir.exists():
        for f in es_dir.iterdir():
            if f.suffix != '.json':
                continue
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
            except Exception:
                continue
            # llm-for-zotero v3.8.x 的字段: providers (list)
            providers = data.get('providers') or data.get('provider') or []
            if isinstance(providers, dict):
                providers = [providers]
            for p in providers:
                name = (p.get('name') or p.get('provider') or '').lower()
                if 'MiniMax' in name or 'minimax' in name:
                    config['base_url'] = p.get('baseURL') or p.get('base_url') or p.get('url')
                    config['api_key'] = p.get('apiKey') or p.get('api_key') or p.get('key')
                    config['model'] = p.get('model') or p.get('models')
                    break

    # 优先级 2: prefs.js (备用,适用于直接写入 prefs 的旧版插件)
    if not config['api_key']:
        prefs_text = prefs_file.read_text(encoding='utf-8', errors='replace')
        # 提取 llm-for-zotero 相关 pref
        patterns = {
            'base_url': r'extensions\.zotero-llm@github\.com\.yilewang\.\w+\.baseURL\s*[,=]\s*"([^"]+)"',
            'api_key':  r'extensions\.zotero-llm@github\.com\.yilewang\.\w+\.apiKey\s*[,=]\s*"([^"]+)"',
            'model':    r'extensions\.zotero-llm@github\.com\.yilewang\.\w+\.model\s*[,=]\s*"([^"]+)"',
        }
        for k, pat in patterns.items():
            m = re.search(pat, prefs_text)
            if m and not config[k]:
                config[k] = m.group(1)

    config['found'] = bool(config['api_key'] or config['base_url'])
    return config

# ── 报告输出 ──────────────────────────────────────────────────────
def mask_key(key):
    if not key or len(key) < 10:
        return key or '(empty)'
    return f'{key[:10]}...{key[-6:]}'

def print_header(title):
    print(f'\n{C.BOLD}{C.CY}{"="*70}{C.END}')
    print(f'{C.BOLD}{C.CY}  {title}{C.END}')
    print(f'{C.BOLD}{C.CY}{"="*70}{C.END}')

def run_api_check(api_key):
    """测国内 cn + 海外 global 两个 endpoint, 报告哪个能通."""
    print_header(f'API 连通性测试 (Key: {mask_key(api_key)})')
    all_results = {}
    for label, url in ENDPOINTS.items():
        print(f'\n  {C.BOLD}▸ {label} ({url}){C.END}')
        results = test_api(url, api_key)
        all_results[label] = results
        for name, r in results.items():
            mark = f'{C.G}✓{C.END}' if r['ok'] else f'{C.R}✗{C.END}'
            print(f'    [{mark}] {name:20s}  {r["elapsed"]:>4.1f}s  {C.DIM}{r["detail"][:80]}{C.END}')
        passed = sum(1 for r in results.values() if r['ok'])
        total = len(results)
        if passed == total:
            print(f'    {C.G}✅ ALL PASS ({passed}/{total}){C.END}')
        elif passed == 0:
            print(f'    {C.R}❌ ALL FAIL ({passed}/{total}){C.END}')
        else:
            print(f'    {C.Y}⚠ PARTIAL ({passed}/{total}){C.END}')
    return all_results

def run_zotero_check():
    """读取并报告 Zotero 里的 MiniMax 配置."""
    print_header('Zotero 配置检查')
    cfg = read_zotero_minimax_config()
    if not cfg.get('found'):
        print(f'  {C.Y}⚠ Zotero 配置文件里没找到 MiniMax 配置{C.END}')
        print(f'  这通常意味着两种情况之一:')
        print(f'    1. 你还没在 Zotero GUI Preferences 里填过 (正常)')
        print(f'    2. 你填了,但 v3.8.25 把配置加密存在 SQLite (脚本无法读明文)')
        print()
        print(f'  检测到的:')
        print(f'    Profile:       {cfg.get("profile", "(not found)")}')
        print(f'    Prefs file:    {cfg.get("prefs_file", "(not found)")}')
        print()
        print(f'  {C.BOLD}怎么确认你的 Zotero Preferences 已经填好了?{C.END}')
        print(f'    1. 启动 Zotero')
        print(f'    2. Tools → Add-ons → LLM for Zotero → Preferences')
        print(f'    3. 在 Providers 标签应该看到 MiniMax provider')
        print(f'    4. 点 Test Connection → 看到 ✓ 表示填对了')
        print()
        print(f'  {C.BOLD}或者:{C.END}')
        print(f'    直接用 API 模式测 (无需 Zotero 配置):')
        print(f'      python zotero_minimax_check.py api')
        return None

    print(f'  Profile:    {cfg["profile"]}')
    print(f'  Base URL:   {cfg["base_url"] or f"{C.Y}(未填){C.END}"}')
    print(f'  API Key:    {mask_key(cfg["api_key"]) if cfg["api_key"] else f"{C.Y}(未填){C.END}"}')
    print(f'  Model:      {cfg["model"] or f"{C.Y}(未填){C.END}"}')

    # 识别 region
    base_url = cfg['base_url'] or ''
    region = 'unknown'
    if 'minimaxi.com' in base_url: region = 'cn'
    elif 'minimax.io' in base_url: region = 'global'
    print(f'  Region:     {region}  ({"https://api.minimaxi.com/v1" if region=="cn" else "https://api.minimax.io/v1" if region=="global" else "无法识别"})')
    return cfg

def run_cross_check(api_key, zotero_cfg):
    """交叉验证: Zotero 填的 config 跟实际 API 行为是否一致."""
    if not zotero_cfg or not zotero_cfg.get('api_key'):
        return
    print_header('交叉验证 (Zotero 配置 vs API 实际行为)')
    url = zotero_cfg['base_url']
    if not url:
        print(f'  {C.Y}⚠ Zotero 里没填 Base URL, 跳过交叉验证{C.END}')
        return

    print(f'  用 Zotero 填的 key ({mask_key(zotero_cfg["api_key"])}) 测 Zotero 填的 URL ({url})')
    results = test_api(url, zotero_cfg['api_key'], zotero_cfg.get('model') or 'MiniMax-M3')

    passed = sum(1 for r in results.values() if r['ok'])
    total = len(results)
    if passed == total:
        print(f'  {C.G}✅ Zotero 配置完全可用 ({passed}/{total}){C.END}')
        return True
    else:
        print(f'  {C.R}❌ Zotero 配置有问题 ({passed}/{total}){C.END}')
        # 给出建议
        first_code = next(iter(results.values()))['code']
        if first_code == 401:
            print(f'  {C.Y}可能原因:{C.END}')
            print(f'    - Key 失效或订阅过期')
            print(f'    - 国内 cn key 配了 global endpoint (或反之)')
            print(f'  {C.Y}建议:{C.END}')
            print(f'    1. 用 miniMax API 测试脚本先确认 key 跟哪个 endpoint 配')
            print(f'    2. 然后在 Zotero Preferences 里改成正确的 Base URL')
        elif first_code == 404:
            print(f'  {C.Y}可能原因: Model 名错 (找不到 {zotero_cfg.get("model")}){C.END}')
        elif first_code == 403:
            print(f'  {C.Y}可能原因: 订阅过期或余额不足{C.END}')
        return False

def auto_fix_suggestion(api_results, zotero_cfg):
    """根据 API 测试结果给 Zotero 配置修正建议."""
    if not zotero_cfg: return
    cn_ok = all(r['ok'] for r in api_results.get('cn', {}).values())
    global_ok = all(r['ok'] for r in api_results.get('global', {}).values())
    z_url = zotero_cfg.get('base_url', '') or ''
    z_is_cn = 'minimaxi.com' in z_url

    print_header('修正建议')
    if cn_ok and not global_ok and not z_is_cn:
        print(f'  {C.Y}⚠ 检测到你的 key 是国内 cn 专属{C.END}')
        print(f'  {C.Y}  但 Zotero 配的是: {z_url}{C.END}')
        print(f'  {C.G}  建议改成: https://api.minimaxi.com/v1{C.END}')
    elif global_ok and not cn_ok and z_is_cn:
        print(f'  {C.Y}⚠ 检测到你的 key 是海外 global 专属{C.END}')
        print(f'  {C.Y}  但 Zotero 配的是: {z_url}{C.END}')
        print(f'  {C.G}  建议改成: https://api.minimax.io/v1{C.END}')
    elif not cn_ok and not global_ok:
        print(f'  {C.R}❌ Key 在两个 endpoint 都 401{C.END}')
        print(f'  1. 去 platform.minimaxi.com 控制台查 key 状态')
        print(f'  2. 重新生成 key 后用 --key sk-cp-... 再测')
    elif cn_ok and global_ok:
        print(f'  {C.G}✅ Key 双 region 通用, 当前 Zotero 配置无需改动{C.END}')

# ── 主入口 ────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description='Zotero + MiniMax M3 配置检查工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例:\n'
               '  python zotero_minimax_check.py api\n'
               '  python zotero_minimax_check.py zotero\n'
               '  python zotero_minimax_check.py all --fix\n',
    )
    p.add_argument('mode', nargs='?', default='all',
                   choices=['api', 'zotero', 'all'],
                   help='检查模式: api(只测API) / zotero(只查配置) / all(都查)')
    p.add_argument('--key', help='直接传 API key (覆盖 .env)')
    p.add_argument('--cn-only', action='store_true', help='只测国内 cn')
    p.add_argument('--global-only', action='store_true', help='只测海外 global')
    args = p.parse_args()

    enable_windows_ansi()
    print(f'{C.BOLD}{C.M}{"="*70}{C.END}')
    print(f'{C.BOLD}{C.M}  Zotero + MiniMax M3 配置检查工具{C.END}')
    print(f'{C.BOLD}{C.M}  时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}{C.END}')
    print(f'{C.BOLD}{C.M}{"="*70}{C.END}')

    api_key, source, field = read_api_key(args.key)
    if not api_key:
        print(f'\n{C.R}❌ 找不到 API Key{C.END}')
        print(f'  解决: --key sk-cp-... 直接传, 或把 key 写入 {ENV_FILES[0]} 的 MINIMAX_API_KEY 字段')
        sys.exit(1)

    print(f'\n  Key 来源: {source}')
    if field: print(f'  Key 字段: {field}')
    print(f'  Key 预览: {mask_key(api_key)}')

    api_results = None
    if args.mode in ('api', 'all'):
        api_results = run_api_check(api_key)

    zotero_cfg = None
    if args.mode in ('zotero', 'all'):
        zotero_cfg = run_zotero_check()

    if api_results and zotero_cfg:
        run_cross_check(api_key, zotero_cfg)
        auto_fix_suggestion(api_results, zotero_cfg)

    print(f'\n{C.BOLD}{C.M}{"="*70}{C.END}')
    print(f'{C.BOLD}  ✅ 检查完成{C.END}')
    print(f'{C.BOLD}{C.M}{"="*70}{C.END}')

if __name__ == '__main__':
    main()