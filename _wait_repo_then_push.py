"""轮询检测 repo 创建 + 自动 push

用法:
  python _wait_repo_then_push.py
  python _wait_repo_then_push.py --repo user/other-repo

检测:
  - 每 5 秒检查 https://api.github.com/repos/aidless/minimax-m3-phase1
  - 当 status_code=200 (repo exists) 时, 自动 git push
  - 默认 timeout 5 分钟, 之后用户可继续等

退出码:
  0 = push 成功
  1 = timeout
  2 = 用户中断
"""
import sys
import time
import urllib.request
import urllib.error
import subprocess
import argparse
from datetime import datetime


def check_repo_exists(owner, repo, timeout=8):
    """检查 repo 是否存在. 返回 (exists: bool, status: int)"""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'wait-repo-then-push/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, r.status
    except urllib.error.HTTPError as e:
        return False, e.code
    except Exception as e:
        return False, -1


def push_to_remote(local_cwd, branch='main'):
    """git push 到已配的 origin. 返回 (ok, stdout, stderr, returncode)"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🚀 git push -u origin {branch}")
    print(f"  CWD: {local_cwd}")
    try:
        result = subprocess.run(
            ['git', 'push', '-u', 'origin', branch],
            capture_output=True, encoding='utf-8',
            cwd=local_cwd,
            env={'PATH': r'C:\Windows\System32;C:\Program Files\Git\cmd',
                 'HOME': r'C:\Users\Administrator',
                 'GIT_TERMINAL_PROMPT': '0'},
            timeout=600,  # 10 min
        )
        ok = result.returncode == 0
        return ok, result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return False, '', 'git push timeout (10 min)', -1
    except Exception as e:
        return False, '', str(e), -1


def main():
    parser = argparse.ArgumentParser(description='轮询检测 GitHub repo 创建 + 自动 push')
    parser.add_argument('--repo', default='aidless/minimax-m3-phase1',
                        help='GitHub repo (默认: aidless/minimax-m3-phase1)')
    parser.add_argument('--branch', default='main', help='分支 (默认: main)')
    parser.add_argument('--cwd', default=r'F:\Research', help='本地 git 仓根目录')
    parser.add_argument('--interval', type=int, default=5, help='检测间隔秒 (默认: 5)')
    parser.add_argument('--timeout-min', type=int, default=5, help='timeout 分钟 (默认: 5)')
    args = parser.parse_args()

    if '/' not in args.repo:
        print(f"❌ --repo 格式错误: {args.repo} (应是 owner/repo 形式)")
        return 3

    owner, repo_name = args.repo.split('/', 1)

    print("=" * 70)
    print("轮询检测 GitHub repo 创建 + 自动 push")
    print("=" * 70)
    print(f"  目标: https://github.com/{args.repo}")
    print(f"  检测间隔: {args.interval}s")
    print(f"  Timeout: {args.timeout_min} min")
    print(f"  本地: {args.cwd}")
    print("=" * 70)

    # 检查 origin
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 检查 origin 配置...")
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True, encoding='utf-8', cwd=args.cwd, timeout=10,
        )
        origin = result.stdout.strip()
        print(f"  origin: {origin}")
        if not origin:
            print(f"  ⚠ origin 未配置, 设置为 SSH")
            subprocess.run(
                ['git', 'remote', 'add', 'origin', f'git@github.com:{args.repo}.git'],
                cwd=args.cwd, timeout=10,
            )
    except Exception as e:
        print(f"  ⚠ 检查 origin 失败: {e}")
        return 1

    # 轮询
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔄 轮询 https://api.github.com/repos/{args.repo} ...")
    timeout_sec = args.timeout_min * 60
    start = time.time()
    attempt = 0
    try:
        while True:
            attempt += 1
            elapsed = time.time() - start
            if elapsed > timeout_sec:
                print(f"\n⏰ Timeout ({args.timeout_min} min), 退出")
                return 1

            exists, status = check_repo_exists(owner, repo_name)
            if exists:
                print(f"\n✅ Repo 创建成功! (status={status}, 第 {attempt} 次检测, {elapsed:.0f}s)")
                break
            else:
                print(f"  [{attempt:3d}] {datetime.now().strftime('%H:%M:%S')} "
                      f"status={status} (elapsed: {elapsed:.0f}s) - repo 还没创建, 等待 {args.interval}s ...")
                time.sleep(args.interval)

        # push
        ok, stdout, stderr, rc = push_to_remote(args.cwd, args.branch)
        print()
        print("=" * 70)
        if ok:
            print("🎉 git push 成功!")
        else:
            print(f"❌ git push 失败 (rc={rc})")
        print(f"  stdout: {stdout[:500]}")
        print(f"  stderr: {stderr[:500]}")
        print("=" * 70)
        return 0 if ok else 1

    except KeyboardInterrupt:
        print("\n[Ctrl+C] 用户中断")
        return 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[Ctrl+C] 用户中断")
        sys.exit(2)