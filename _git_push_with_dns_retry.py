"""DNS 状态检测 + GitHub push 自动重试脚本

目的:
  1. 检测当前 DNS / 网络状态
  2. 如果 GitHub 不可达, 退避重试
  3. 一旦可达, 自动 push 到 GitHub

用法:
  # 默认 push 到 https://github.com/aidless/minimax-m3-phase1
  python _git_push_with_dns_retry.py

  # 自定义 repo
  python _git_push_with_dns_retry.py --repo https://github.com/user/repo

  # 永远重试 (不限制次数)
  python _git_push_with_dns_retry.py --forever

  # 只检测 DNS 状态不 push
  python _git_push_with_dns_retry.py --check-only

退出码:
  0 = 推送成功
  1 = 推送失败 (最终)
  2 = 用户中断 (Ctrl+C)
  3 = 参数错误

关联文档: GitHub_Push_指南.md
"""
import os
import sys
import time
import socket
import argparse
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ── 常量 ────────────────────────────────────────────────────────
GITHUB_HOST = 'github.com'
GITHUB_PORT = 443
GITHUB_API = 'https://api.github.com'

# 退避策略
INITIAL_BACKOFF = 30       # 初始退避秒
MAX_BACKOFF = 300          # 最大退避秒 (5 min)
BACKOFF_FACTOR = 1.5       # 每次失败 * 1.5
MAX_ATTEMPTS = 20          # 默认最大尝试 20 次
DNS_TIMEOUT = 10           # DNS 检测超时
TCP_TIMEOUT = 15           # TCP 握手超时
HTTP_TIMEOUT = 10          # HTTP 检测超时


# ── DNS / 网络检测函数 ─────────────────────────────────────────
def check_dns(host: str = GITHUB_HOST, timeout: int = DNS_TIMEOUT) -> dict:
    """检测 DNS 解析. 返回 {ok, ip, error, elapsed}"""
    t0 = time.time()
    try:
        ip = socket.gethostbyname(host)
        elapsed = time.time() - t0
        return {'ok': True, 'ip': ip, 'error': None, 'elapsed': elapsed}
    except socket.gaierror as e:
        elapsed = time.time() - t0
        return {'ok': False, 'ip': None, 'error': f'DNS: {e}', 'elapsed': elapsed}
    except Exception as e:
        elapsed = time.time() - t0
        return {'ok': False, 'ip': None, 'error': f'{type(e).__name__}: {e}', 'elapsed': elapsed}


def check_tcp(host: str = GITHUB_HOST, port: int = GITHUB_PORT, timeout: int = TCP_TIMEOUT) -> dict:
    """检测 TCP 握手. 返回 {ok, error, elapsed}"""
    t0 = time.time()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        elapsed = time.time() - t0
        return {'ok': True, 'error': None, 'elapsed': elapsed}
    except (socket.timeout, OSError) as e:
        elapsed = time.time() - t0
        return {'ok': False, 'error': f'TCP: {e}', 'elapsed': elapsed}
    except Exception as e:
        elapsed = time.time() - t0
        return {'ok': False, 'error': f'{type(e).__name__}: {e}', 'elapsed': elapsed}


def check_http(url: str = GITHUB_API, timeout: int = HTTP_TIMEOUT) -> dict:
    """检测 HTTP 访问. 返回 {ok, status, error, elapsed}"""
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'dns-retry-script/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = r.status
            elapsed = time.time() - t0
            return {'ok': True, 'status': status, 'error': None, 'elapsed': elapsed}
    except urllib.error.HTTPError as e:
        elapsed = time.time() - t0
        # HTTP 4xx/5xx 仍算 ok (说明服务可达)
        return {'ok': True, 'status': e.code, 'error': None, 'elapsed': elapsed}
    except (socket.timeout, urllib.error.URLError, OSError) as e:
        elapsed = time.time() - t0
        return {'ok': False, 'status': None, 'error': f'HTTP: {e}', 'elapsed': elapsed}
    except Exception as e:
        elapsed = time.time() - t0
        return {'ok': False, 'status': None, 'error': f'{type(e).__name__}: {e}', 'elapsed': elapsed}


def full_connectivity_check(verbose: bool = True) -> dict:
    """完整连通性检查: DNS + TCP + HTTP. 返回综合结果

    短路逻辑: 任一步失败立即返回, 不测后续步骤.
    """
    if verbose:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Checking connectivity to {GITHUB_HOST}...")

    dns = check_dns()
    if verbose:
        if dns['ok']:
            print(f"  ✅ DNS  {GITHUB_HOST} → {dns['ip']} ({dns['elapsed']:.1f}s)")
        else:
            print(f"  ❌ DNS  {dns['error']} ({dns['elapsed']:.1f}s)")
    # 短路: DNS 失败立即返回
    if not dns['ok']:
        return {'ok': False, 'dns': dns}

    tcp = check_tcp()
    if verbose:
        if tcp['ok']:
            print(f"  ✅ TCP  {GITHUB_HOST}:{GITHUB_PORT} OK ({tcp['elapsed']:.1f}s)")
        else:
            print(f"  ❌ TCP  {tcp['error']} ({tcp['elapsed']:.1f}s)")
    # 短路: TCP 失败立即返回
    if not tcp['ok']:
        return {'ok': False, 'dns': dns, 'tcp': tcp}

    http = check_http()
    if verbose:
        if http['ok']:
            print(f"  ✅ HTTP {GITHUB_API} status={http['status']} ({http['elapsed']:.1f}s)")
        else:
            print(f"  ❌ HTTP {http['error']} ({http['elapsed']:.1f}s)")
    # 短路: HTTP 失败立即返回
    if not http['ok']:
        return {'ok': False, 'dns': dns, 'tcp': tcp, 'http': http}

    return {'ok': True, 'dns': dns, 'tcp': tcp, 'http': http}


# ── Git push 函数 ──────────────────────────────────────────────
def git_push(repo_url: str, branch: str = 'main', cwd: str = None, verbose: bool = True) -> dict:
    """执行 git push. 返回 {ok, stdout, stderr, returncode, elapsed}"""
    t0 = time.time()
    if verbose:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🚀 git push to {repo_url} ({branch})")

    # 先看 remote 是否已配置
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True, encoding='utf-8', cwd=cwd,
            timeout=10,
        )
        existing_url = result.stdout.strip()
        if existing_url == repo_url:
            if verbose:
                print(f"  ✅ remote origin 已配置: {existing_url}")
        elif existing_url:
            if verbose:
                print(f"  ⚠ remote origin 已存在 ({existing_url}), 改为 {repo_url}")
            subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url],
                           capture_output=True, encoding='utf-8', cwd=cwd, timeout=10)
        else:
            if verbose:
                print(f"  ➕ 添加 remote origin: {repo_url}")
            subprocess.run(['git', 'remote', 'add', 'origin', repo_url],
                           capture_output=True, encoding='utf-8', cwd=cwd, timeout=10)
    except Exception as e:
        return {'ok': False, 'stdout': '', 'stderr': f'remote config failed: {e}',
                'returncode': 1, 'elapsed': time.time() - t0}

    # push
    cmd = ['git', 'push', '-u', 'origin', branch]
    try:
        result = subprocess.run(
            cmd, capture_output=True, encoding='utf-8',
            cwd=cwd or os.getcwd(),
            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'},  # 不弹认证框
            timeout=300,  # 5 min
        )
        elapsed = time.time() - t0
        ok = result.returncode == 0
        if verbose:
            status = '✅' if ok else '❌'
            print(f"  {status} push returncode={result.returncode} ({elapsed:.1f}s)")
            if result.stdout:
                print(f"  stdout: {result.stdout[:200]}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:200]}")
        return {
            'ok': ok,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
            'elapsed': elapsed,
        }
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        return {'ok': False, 'stdout': '', 'stderr': 'git push timeout (5 min)',
                'returncode': -1, 'elapsed': elapsed}
    except Exception as e:
        elapsed = time.time() - t0
        return {'ok': False, 'stdout': '', 'stderr': str(e),
                'returncode': -1, 'elapsed': elapsed}


# ── 主循环 ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='DNS 状态检测 + GitHub push 自动重试',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 默认 push 到 https://github.com/aidless/minimax-m3-phase1
  python _git_push_with_dns_retry.py

  # 自定义 repo
  python _git_push_with_dns_retry.py --repo https://github.com/user/repo

  # 无限重试
  python _git_push_with_dns_retry.py --forever

  # 只检测 DNS 不 push
  python _git_push_with_dns_retry.py --check-only
        """,
    )
    parser.add_argument('--repo', default='https://github.com/aidless/minimax-m3-phase1.git',
                        help='GitHub repo URL (默认: https://github.com/aidless/minimax-m3-phase1.git)')
    parser.add_argument('--branch', default='main', help='分支名 (默认: main)')
    parser.add_argument('--cwd', default=None, help='git 仓库根目录 (默认: 当前目录)')
    parser.add_argument('--max-attempts', type=int, default=MAX_ATTEMPTS,
                        help=f'最大尝试次数 (默认: {MAX_ATTEMPTS})')
    parser.add_argument('--initial-backoff', type=int, default=INITIAL_BACKOFF,
                        help=f'初始退避秒 (默认: {INITIAL_BACKOFF})')
    parser.add_argument('--max-backoff', type=int, default=MAX_BACKOFF,
                        help=f'最大退避秒 (默认: {MAX_BACKOFF})')
    parser.add_argument('--backoff-factor', type=float, default=BACKOFF_FACTOR,
                        help=f'退避因子 (默认: {BACKOFF_FACTOR})')
    parser.add_argument('--forever', action='store_true', help='无限重试 (忽略 --max-attempts)')
    parser.add_argument('--check-only', action='store_true', help='只检测 DNS 状态, 不 push')
    parser.add_argument('--quiet', action='store_true', help='安静模式, 只输出关键事件')
    args = parser.parse_args()

    verbose = not args.quiet

    print("=" * 70)
    print("DNS 检测 + GitHub Push 重试脚本")
    print("=" * 70)
    print(f"  时间: {datetime.now().isoformat()}")
    print(f"  Repo: {args.repo}")
    print(f"  分支: {args.branch}")
    print(f"  CWD:  {args.cwd or os.getcwd()}")
    print(f"  模式: {'check-only' if args.check_only else 'forever' if args.forever else f'max {args.max_attempts} attempts'}")
    print(f"  退避: {args.initial_backoff}s → {args.max_backoff}s (×{args.backoff_factor})")
    print("=" * 70)

    # ── Step 1: 一次性 DNS 检查 (--check-only)
    if args.check_only:
        result = full_connectivity_check(verbose=verbose)
        return 0 if result['ok'] else 1

    # ── Step 2: 主循环: 检测 + push
    backoff = args.initial_backoff
    attempt = 0

    try:
        while True:
            attempt += 1
            if not args.forever and attempt > args.max_attempts:
                print(f"\n❌ 已达最大尝试次数 {args.max_attempts}, 退出")
                return 1

            # 连通性检查
            check = full_connectivity_check(verbose=verbose)
            if not check['ok']:
                # 不可达, 退避重试
                if not args.forever and attempt >= args.max_attempts:
                    print(f"\n❌ 已达最大尝试次数 {args.max_attempts}, 退出")
                    return 1
                next_backoff = min(backoff, args.max_backoff)
                print(f"\n⏳ 等待 {next_backoff}s 后重试 (第 {attempt+1}/{args.max_attempts if not args.forever else '∞'} 次)...")
                try:
                    time.sleep(next_backoff)
                except KeyboardInterrupt:
                    print("\n[Ctrl+C] 用户中断")
                    return 2
                backoff = int(backoff * args.backoff_factor)
                continue

            # 可达, 尝试 push
            backoff = args.initial_backoff  # reset
            push = git_push(args.repo, args.branch, cwd=args.cwd, verbose=verbose)
            if push['ok']:
                print(f"\n🎉 推送成功! ({push['elapsed']:.1f}s)")
                return 0

            # push 失败, 退避
            if not args.forever and attempt >= args.max_attempts:
                print(f"\n❌ 已达最大尝试次数 {args.max_attempts}, 退出")
                return 1
            next_backoff = min(backoff, args.max_backoff)
            print(f"\n⏳ push 失败, 等待 {next_backoff}s 后重试 (第 {attempt+1}/{args.max_attempts if not args.forever else '∞'} 次)...")
            try:
                time.sleep(next_backoff)
            except KeyboardInterrupt:
                print("\n[Ctrl+C] 用户中断")
                return 2
            backoff = int(backoff * args.backoff_factor)

    except KeyboardInterrupt:
        print("\n[Ctrl+C] 用户中断")
        return 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[Ctrl+C] 用户中断")
        sys.exit(2)