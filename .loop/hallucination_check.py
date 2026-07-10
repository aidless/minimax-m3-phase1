#!/usr/bin/env python3
"""Loop Engineering v5.1 — M3 Hallucination Hook
================================================
对每篇 paper 在 Phase 2/3 阶段的 M3 输出做 hallucination 检测.
跟 pre_review.py 同风格, 复用 registry + LOOP_DIR 常量.

检测源 (按优先级):
  1. paper/_m3_summaries/*.md    (M3 直接输出, 4 个 task)
  2. paper/llm_summaries/*.md    (兼容老路径)

检测类型 (复用 _inbox/方法论/mm3_hallucination_detector.py):
  - arXiv 未来年 / 超窗口 / 安全窗口内
  - GitHub URL 格式
  - 论文内部矛盾 (ECE bins, Bootstrap B, etc.)
  - DOI 数字精度 未定义术语

Usage:
    python .loop/hallucination_check.py PAPER-A            # 检测单篇
    python .loop/hallucination_check.py PAPER-A --json     # JSON 输出
    python .loop/hallucination_check.py --all              # 扫所有 paper
    python .loop/hallucination_check.py PAPER-A --pdf      # 同时检查未定义术语 (需要原 PDF)

Hook 集成:
    在 pre_review.py 末尾自动调用, 失败 (HIGH > 0) 返回非零退出码
"""
import sys
import json
import argparse
import re
import importlib.util
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

# ── 颜色 (Windows ANSI) ───────────────────────────────────────────
class C:
    R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'; B = '\033[94m'
    M = '\033[95m'; CY = '\033[96m'; DIM = '\033[2m'; BOLD = '\033[1m'; END = '\033[0m'

def _enable_ansi():
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass
    # 同时强制 stdout/stderr 用 UTF-8 (Windows GBK 会把 emoji/中文标点截断)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── 加载 detector 模块 ───────────────────────────────────────────
def load_detector():
    """从 _inbox/方法论/ 动态加载 mm3_hallucination_detector.py."""
    detector_path = AETTL_DIR / '_inbox' / '方法论' / 'mm3_hallucination_detector.py'
    if not detector_path.exists():
        return None
    spec = importlib.util.spec_from_file_location('hallucination_detector', detector_path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print(f'{C.R}无法加载 detector: {e}{C.END}')
        return None

# ── paper 注册表 (复用 .loop/registry.yaml) ──────────────────────
def load_registry():
    import yaml
    registry_file = LOOP_DIR / 'registry.yaml'
    if not registry_file.exists():
        return None
    with open(registry_file, encoding='utf-8') as f:
        return yaml.safe_load(f)

def find_paper(paper_id, registry):
    if not registry or 'papers' not in registry:
        return None
    for key, p in registry['papers'].items():
        if p['id'] == paper_id or key == paper_id:
            return p
    return None

def find_m3_outputs(paper):
    """找到 paper 的所有 M3 输出文件."""
    if not paper:
        return []
    paper_path = AETTL_DIR / paper['path']
    candidates = []
    # 优先级 1: 论文自带的 llm_summaries (zotero_pdf_summary_demo.py 输出)
    for d in ['llm_summaries', '_m3_summaries', 'summaries']:
        p = paper_path / d
        if p.exists():
            candidates.extend(p.glob('*.md'))
    return sorted(set(candidates))

def find_paper_pdf(paper):
    """找到 paper 的 main.pdf (用于术语回查)."""
    if not paper:
        return None
    paper_path = AETTL_DIR / paper['path']
    for name in ['main.pdf', 'paper.pdf', 'manuscript.pdf']:
        p = paper_path / name
        if p.exists():
            return str(p)
    return None

# ── 主分析 ────────────────────────────────────────────────────────
def analyze_paper(paper, detector, use_pdf=False, strict=False):
    files = find_m3_outputs(paper)
    pdf_text = None
    pdf_path = None
    if use_pdf:
        pdf_path = find_paper_pdf(paper)
        if pdf_path:
            try:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    pdf_text = '\n'.join((p.extract_text() or '') for p in pdf.pages[:15])
            except Exception as e:
                print(f'{C.Y}PDF 读取失败: {e}{C.END}')

    all_results = []
    for f in files:
        body, issues = detector.analyze_file(
            f, pdf_text=pdf_text, current_year=date.today().year, strict=strict)
        if body is None:
            continue
        all_results.append({
            'file': str(f.relative_to(AETTL_DIR)),
            'chars': len(body),
            'issues': issues,
        })
    return all_results

# ── 报告 ──────────────────────────────────────────────────────────
def print_text_report(paper, results):
    print(f'\n{C.BOLD}{C.CY}{"="*70}{C.END}')
    print(f'{C.BOLD}{C.CY}  M3 Hallucination Hook: {paper["id"]}{C.END}')
    print(f'{C.BOLD}{C.CY}  Title: {paper["title"][:60]}{C.END}')
    print(f'{C.BOLD}{C.CY}  Phase: {paper.get("phase", "?")} | Venue: {paper.get("venue", "?")}{C.END}')
    print(f'{C.BOLD}{C.CY}  时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}{C.END}')
    print(f'{C.BOLD}{C.CY}{"="*70}{C.END}')

    if not results:
        print(f'\n  {C.G}✅ 没找到 M3 输出文件 (.loop/ 期待的路径:{C.END}')
        print(f'    {paper["path"]}/llm_summaries/*.md')
        print(f'    {paper["path"]}/_m3_summaries/*.md')
        print(f'\n  这通常意味着 paper 还没跑过 zotero_pdf_summary_demo.py')
        print(f'  或者跑过但输出在别处. 用 --all 扫所有 paper 看看.')
        return 0  # 不是失败, 是没数据

    total_high = total_medium = total_low = 0
    for r in results:
        n_high = sum(1 for i in r['issues'] if i['severity'] == 'HIGH')
        n_med = sum(1 for i in r['issues'] if i['severity'] == 'MEDIUM')
        n_low = sum(1 for i in r['issues'] if i['severity'] == 'LOW')
        total_high += n_high
        total_medium += n_med
        total_low += n_low
        status = f'{C.G}✅{C.END}' if n_high == 0 else f'{C.R}❌{C.END}'
        print(f'\n  {status} {r["file"]}  ({r["chars"]:,} chars)')
        print(f'    HIGH={C.R}{n_high}{C.END}  MEDIUM={C.Y}{n_med}{C.END}  LOW={C.DIM}{n_low}{C.END}')

        # 列出 HIGH 问题
        if n_high > 0:
            for i, iss in enumerate(r['issues']):
                if iss['severity'] != 'HIGH':
                    continue
                print(f'\n    {C.R}[HIGH #{i}]{C.END} {iss["type"]}')
                print(f'      匹配:    {iss["match"]!r}')
                if 'parsed' in iss:
                    print(f'      解析:    {iss["parsed"]}')
                print(f'      建议:    {iss["suggestion"]}')

    print(f'\n{C.BOLD}{C.M}{"="*70}{C.END}')
    print(f'{C.BOLD}  总结{C.END}')
    print(f'{C.BOLD}{C.M}{"="*70}{C.END}')
    print(f'  扫描文件: {len(results)}')
    print(f'  HIGH: {total_high}  MEDIUM: {total_medium}  LOW: {total_low}')
    if total_high == 0:
        print(f'  {C.G}✅ 没 HIGH 级 hallucination, 可以推进 Phase{C.END}')
        return 0
    print(f'  {C.R}❌ {total_high} 个 HIGH 级问题, 必须修复后才能推进 Phase{C.END}')
    return 1  # exit code 1 = block

# ── 公共 API: 供其他 .loop/ 模块 (pre_review.py, advance_phase.py) 调用 ──
def run_hallucination_hook(paper_id, verbose=True, use_pdf=False, strict=False):
    """对单 paper 跑 M3 hallucination 检测.
    Returns: (passed: bool, n_high: int, n_medium: int, n_low: int, results: list)

    passed = (n_high == 0)  →  True 表示可以推进 Phase

    strict=True: 忽略 detector 内部 severity_cap, 把所有冲突都报 HIGH.
    用于: 查看"如果不做上下文区分"会报什么, 跟正常模式对比, 区分真矛盾 vs 多设计共存.

    用法 (from other .loop/ scripts):
        from hallucination_check import run_hallucination_hook
        passed, n_high, n_med, n_low, _ = run_hallucination_hook('PAPER-A')
        if not passed:
            sys.exit(1)  # block phase advancement
    """
    _enable_ansi()
    detector = load_detector()
    if detector is None:
        if verbose:
            print(f'{C.R}找不到 detector 模块 (期望路径: _inbox/方法论/mm3_hallucination_detector.py){C.END}')
        return False, -1, -1, -1, []

    registry = load_registry()
    if registry is None:
        if verbose:
            print(f'{C.R}registry.yaml 加载失败{C.END}')
        return False, -1, -1, -1, []

    paper = find_paper(paper_id, registry)
    if not paper:
        if verbose:
            print(f'{C.R}Paper "{paper_id}" 不在 registry.yaml 里{C.END}')
        return False, -1, -1, -1, []

    results = analyze_paper(paper, detector, use_pdf=use_pdf, strict=strict)
    if verbose:
        print_text_report(paper, results)

    n_high = sum(sum(1 for i in r['issues'] if i['severity'] == 'HIGH') for r in results)
    n_medium = sum(sum(1 for i in r['issues'] if i['severity'] == 'MEDIUM') for r in results)
    n_low = sum(sum(1 for i in r['issues'] if i['severity'] == 'LOW') for r in results)
    passed = (n_high == 0)
    return passed, n_high, n_medium, n_low, results

# ── 入口 ──────────────────────────────────────────────────────────
def main():
    _enable_ansi()
    parser = argparse.ArgumentParser(
        description='Loop Engineering v5.1 — M3 Hallucination Hook',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python .loop/hallucination_check.py PAPER-A            # 单 paper
  python .loop/hallucination_check.py PAPER-A --pdf      # 同时回查未定义术语
  python .loop/hallucination_check.py PAPER-A --json     # JSON 输出
  python .loop/hallucination_check.py --all              # 扫所有 paper
        """,
    )
    parser.add_argument('paper_id', nargs='?', help='Paper ID (PAPER-A, PAPER-B, ...)。--all 时忽略')
    parser.add_argument('--all', action='store_true', help='扫所有 paper')
    parser.add_argument('--pdf', action='store_true', help='同时加载原 PDF 做术语回查')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    parser.add_argument('--strict', action='store_true',
                        help='严格模式: 忽略 severity_cap, 把所有冲突都报 HIGH. '
                             '用于跟正常模式对比, 区分真矛盾 vs 多设计共存.')
    args = parser.parse_args()

    detector = load_detector()
    if detector is None:
        print(f'{C.R}找不到 detector 模块 (期望路径: _inbox/方法论/mm3_hallucination_detector.py){C.END}')
        sys.exit(1)

    registry = load_registry()
    if registry is None:
        print(f'{C.R}registry.yaml 加载失败{C.END}')
        sys.exit(1)

    # 决定处理哪些 paper
    if args.all:
        papers = list(registry.get('papers', {}).values())
    elif args.paper_id:
        paper = find_paper(args.paper_id, registry)
        if not paper:
            print(f'{C.R}Paper "{args.paper_id}" 不在 registry.yaml 里{C.END}')
            sys.exit(1)
        papers = [paper]
    else:
        parser.print_help()
        sys.exit(0)

    # 跑所有 paper
    exit_code = 0
    all_json = {}
    if args.strict and not args.json:
        print(f'{C.R}🔴 --strict 模式: 把所有冲突都报 HIGH{C.END}')
    for paper in papers:
        results = analyze_paper(paper, detector, use_pdf=args.pdf, strict=args.strict)
        if args.json:
            all_json[paper['id']] = [
                {
                    'file': r['file'],
                    'chars': r['chars'],
                    'issues': [
                        {'severity': i['severity'], 'type': i['type'], 'match': i['match'],
                         'reason': i.get('reason', ''), 'suggestion': i.get('suggestion', '')}
                        for i in r['issues']
                    ],
                } for r in results
            ]
        else:
            code = print_text_report(paper, results)
            exit_code = max(exit_code, code)

    if args.json:
        print(json.dumps(all_json, indent=2, ensure_ascii=False))
    sys.exit(exit_code)

if __name__ == '__main__':
    main()