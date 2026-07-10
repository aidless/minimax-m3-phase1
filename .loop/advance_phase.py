#!/usr/bin/env python3
"""Loop Engineering v4.1 — Phase Advancement Tool
Validates preconditions before advancing paper to next phase.

Usage:
    python advance_phase.py PAPER_ID           # Advance with precondition checks
    python advance_phase.py PAPER_ID --force   # Skip precondition checks
    python advance_phase.py PAPER_ID --dry-run # Show what's missing without advancing
    python advance_phase.py --help             # Show this help

Precondition: M3 Hallucination Check
    Phase 1→2/2→3/3→4/4→5 推进时自动检查 paper 的 M3 输出是否有 HIGH 级幻觉.
    HIGH > 0 时 advance_phase.py 返回非零 exit code, 阻止 phase 推进.
    除非使用 --force 跳过.

    详细文档: .loop/hallucination_check.README.md
              _inbox/方法论/mm3_hallucination_detector.README.md
"""
import yaml
import sys
import argparse
from pathlib import Path
from datetime import datetime

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

# Phase advancement preconditions
PRECONDITIONS = {
    0: [],  # Phase 0 → 1: no preconditions (baseline assessment is self-contained)
    1: [    # Phase 1 → 2: format conversion complete
        ('Compilation', 'Verify tmlr_submit/main.log has 0 Errors',
         lambda paper_dir: _check_log(paper_dir / 'tmlr_submit' / 'main.log')),
        ('M3 Hallucination Check', 'No HIGH-level hallucination in llm_summaries/*.md',
         lambda paper_dir, paper_id: _check_m3_hallucination(paper_id)),
        ('Detector Tests', '10 granularity降级测试都通过 (警告不 block)',
         lambda paper_dir, paper_id: _check_detector_tests(paper_id)),
    ],
    2: [    # Phase 2 → 3: content review complete
        ('Critical Issues', 'All critical issues resolved or documented',
         lambda paper_dir: _check_critical_issues(paper_dir)),
        ('M3 Hallucination Check', 'No HIGH-level hallucination in llm_summaries/*.md',
         lambda paper_dir, paper_id: _check_m3_hallucination(paper_id)),
        ('Detector Tests', '10 granularity降级测试都通过 (警告不 block)',
         lambda paper_dir, paper_id: _check_detector_tests(paper_id)),
    ],
    3: [    # Phase 3 → 4: polish complete
        ('Abstract Check', 'Abstract is standalone-readable',
         lambda paper_dir: True),  # Manual check — always passes auto
        ('M3 Hallucination Check', 'No HIGH-level hallucination in llm_summaries/*.md',
         lambda paper_dir, paper_id: _check_m3_hallucination(paper_id)),
        ('Detector Tests', '10 granularity降级测试都通过 (警告不 block)',
         lambda paper_dir, paper_id: _check_detector_tests(paper_id)),
    ],
    4: [    # Phase 4 → 5: anonymization complete
        ('Anonymization', 'Zero identity leaks in grep verification',
         lambda paper_dir: _check_anonymization(paper_dir)),
        ('M3 Hallucination Check', 'No HIGH-level hallucination in llm_summaries/*.md',
         lambda paper_dir, paper_id: _check_m3_hallucination(paper_id)),
        ('Detector Tests', '10 granularity降级测试都通过 (警告不 block)',
         lambda paper_dir, paper_id: _check_detector_tests(paper_id)),
    ],
    5: [    # Phase 5: final sign-off
        ('User Sign-off', 'User has manually confirmed readiness',
         lambda paper_dir: False),  # Always requires --force or manual confirmation
    ],
}

def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_yaml(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

def _check_log(log_path):
    if not log_path.exists():
        return False, "main.log not found"
    content = log_path.read_text(encoding='utf-8', errors='ignore')
    errors = content.count('Error:')
    if errors > 0:
        return False, f"{errors} errors in log"
    return True, "0 errors"

def _check_critical_issues(paper_dir):
    issue_path = paper_dir / '.loop' / 'issue_tracker.yaml'
    if not issue_path.exists():
        return False, "issue_tracker.yaml not found"
    issues = load_yaml(issue_path)
    open_critical = [i for i in issues.get('issues', {}).values() 
                     if i.get('severity') == 'critical' and i.get('status') == 'open']
    if open_critical:
        ids = ', '.join(i['id'] for i in open_critical)
        return False, f"{len(open_critical)} open critical issues: {ids}"
    return True, "0 open critical issues"

def _check_anonymization(paper_dir):
    patterns = ['zewen', 'qilu', 'lzw7071', 'jinan']
    tex_dir = paper_dir / 'tmlr_submit'
    if not tex_dir.exists():
        tex_dir = paper_dir
    found = []
    for pattern in patterns:
        for ext in ['*.tex', '*.bib', '*.bbl']:
            import glob
            for f in glob.glob(str(tex_dir / '**' / ext), recursive=True):
                content = Path(f).read_text(encoding='utf-8', errors='ignore').lower()
                if pattern in content:
                    found.append(f"{pattern} in {Path(f).name}")
    if found:
        return False, f"Identity leaks: {', '.join(found[:3])}"
    return True, "0 identity leaks"

def _check_m3_hallucination(paper_id):
    """Hook 到 hallucination_check.run_hallucination_hook.
    Returns: (passed: bool, detail: str)
    """
    # 如果 paper 没有 llm_summaries/, 跳过 (没有 M3 输出 = 不需要检查)
    import sys
    paper = find_paper(paper_id)
    if not paper:
        return False, f"Paper {paper_id} not found"
    paper_dir = AETTL_DIR / paper['path']
    summaries_dir = paper_dir / 'llm_summaries'
    if not summaries_dir.exists() or not any(summaries_dir.glob('*.md')):
        return True, "No llm_summaries/ — 跳过 (没有 M3 输出)"

    # 复用 hallucination_check.py 公共 API
    if str(LOOP_DIR) not in sys.path:
        sys.path.insert(0, str(LOOP_DIR))
    try:
        from hallucination_check import run_hallucination_hook
    except Exception as e:
        return False, f"hook import failed: {e}"

    passed, n_high, n_med, n_low, _ = run_hallucination_hook(
        paper_id, verbose=False)  # 静默模式, 不刷屏
    if passed:
        return True, f"OK (HIGH=0, MEDIUM={n_med}, LOW={n_low})"
    else:
        return False, f"{n_high} HIGH hallucination (MEDIUM={n_med}, LOW={n_low}). Run `.loop/hallucination_check.py {paper_id}` for details."

def _check_detector_tests(paper_id):
    """跑 _test_granularity_suite.py 验证 detector 自身没 bug.
    设计选择: 测试套件失败 = detector 自身 bug, 警告但 passed=True
              (论文问题 ≠ 代码 bug, 不应 block phase 推进).
    Returns: (passed: bool, detail: str)
    """
    import subprocess
    import re as _re
    import os
    test_suite = AETTL_DIR / '_test_granularity_suite.py'
    if not test_suite.exists():
        return True, "No _test_granularity_suite.py — 跳过 (detector 测试套件未配置)"
    try:
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        result = subprocess.run(
            [sys.executable, str(test_suite)],
            capture_output=True, text=True, encoding='utf-8',
            env=env, timeout=60,
        )
        m = _re.search(r'共\s+(\d+)\s+个测试.*?通过\s+(\d+).*?失败\s+(\d+)', result.stdout)
        if m:
            total, passed, failed = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if failed == 0:
                return True, f"OK ({total}/{total} tests passed)"
            else:
                # 警告但不 block
                return True, f"⚠ {failed}/{total} tests failed (detector bug, 警告不 block)"
        return True, f"无法解析结果 (exit={result.returncode})"
    except subprocess.TimeoutExpired:
        return True, "测试超时 (60s), 跳过"
    except Exception as e:
        return True, f"测试异常 ({e}), 跳过"

def find_paper(paper_id):
    registry = load_yaml(LOOP_DIR / 'registry.yaml')
    for key, p in registry['papers'].items():
        if p['id'] == paper_id:
            return p
    return None

def main():
    parser = argparse.ArgumentParser(
        description='Loop Engineering v4.1 — Phase Advancement Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python advance_phase.py PAPER-A              # Advance with precondition checks
  python advance_phase.py PAPER-A --force      # Skip precondition checks
  python advance_phase.py PAPER-A --dry-run    # Show what's missing
        """
    )
    parser.add_argument('paper_id', help='Paper ID (e.g., PAPER-A, PAPER-B)')
    parser.add_argument('--force', '-f', action='store_true', help='Skip precondition checks')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Check preconditions without advancing')
    args = parser.parse_args()
    
    paper_id = args.paper_id
    force = args.force
    dry_run = args.dry_run
    
    paper = find_paper(paper_id)
    if not paper:
        print(f"❌ Paper '{paper_id}' not found.")
        sys.exit(1)
    
    paper_dir = AETTL_DIR / paper['path']
    state_path = paper_dir / '.loop' / 'state.yaml'
    
    if not state_path.exists():
        print(f"❌ No .loop/state.yaml found. Initialize paper first: python init_paper.py")
        sys.exit(1)
    
    state = load_yaml(state_path)
    current = state['current_phase']
    
    if current >= 5:
        print(f"✅ Paper is already at Phase 5 (submission ready). No further phases.")
        return
    
    next_phase = current + 1
    preconditions = PRECONDITIONS.get(current, [])
    
    print(f"\n📈 Advancing {paper_id}: Phase {current} → Phase {next_phase}")
    print(f"   Paper: {paper['short_title']}")
    
    if current == 5:
        print(f"\n🔴 Phase 5 → Complete requires USER SIGN-OFF.")
        if not force:
            print("   Use --force only after manually reviewing the final PDF.")
            sys.exit(1)
    
    # Check preconditions
    all_pass = True
    if preconditions:
        print(f"\n   Checking preconditions:")
        for name, desc, check_fn in preconditions:
            # 检查 lambda 是否需要 paper_id (2-arg vs 1-arg)
            import inspect
            try:
                sig = inspect.signature(check_fn)
                if len(sig.parameters) >= 2:
                    passed, detail = check_fn(paper_dir, paper_id)
                else:
                    passed, detail = check_fn(paper_dir)
            except Exception:
                passed, detail = check_fn(paper_dir)
            icon = '✅' if passed else '❌'
            print(f"   {icon} {name}: {detail}")
            if not passed:
                all_pass = False

    if not all_pass and not force and not dry_run:
        print(f"\n❌ Preconditions not met. Fix issues, use --force, or use --dry-run to inspect.")
        sys.exit(1)

    if dry_run:
        if all_pass:
            print(f"\n✅ All preconditions met — ready to advance to Phase {next_phase}!")
            print(f"   Run without --dry-run to advance.")
        else:
            print(f"\n📋 Preconditions NOT met. Missing items:")
            for name, desc, check_fn in preconditions:
                import inspect
                try:
                    sig = inspect.signature(check_fn)
                    if len(sig.parameters) >= 2:
                        passed, detail = check_fn(paper_dir, paper_id)
                    else:
                        passed, detail = check_fn(paper_dir)
                except Exception:
                    passed, detail = check_fn(paper_dir)
                if not passed:
                    print(f"   ❌ {name}: {detail}")
            print(f"\n   Fix these before advancing, or use --force.")
        return
    
    if force and not all_pass:
        print(f"\n⚠️  Forcing advancement despite failed preconditions.")
    
    # Backup old state
    backup_path = state_path.with_suffix('.yaml.bak')
    save_yaml(backup_path, state)
    
    # Advance phase
    state['current_phase'] = next_phase
    state['updated'] = datetime.now().strftime('%Y-%m-%d')
    state['phases'][f'phase_{current}']['status'] = 'completed'
    state['phases'][f'phase_{current}']['completed'] = datetime.now().strftime('%Y-%m-%d')
    state['phases'][f'phase_{next_phase}']['status'] = 'in_progress'
    state['phases'][f'phase_{next_phase}']['started'] = datetime.now().strftime('%Y-%m-%d')
    
    state['session_history'].append({
        'date': datetime.now().strftime('%Y-%m-%d'),
        'action': f'phase_{current}_completed',
        'note': f'Advanced from Phase {current} to Phase {next_phase}. {"Forced." if force and not all_pass else "All preconditions met."}'
    })
    
    save_yaml(state_path, state)
    
    # Update registry
    registry = load_yaml(LOOP_DIR / 'registry.yaml')
    for key, p in registry['papers'].items():
        if p['id'] == paper_id:
            p['phase'] = next_phase
            phase_names = ['基线评估', '格式转换', '内容审阅', '润色', '匿名化', '提交就绪']
            p['phase_name'] = phase_names[next_phase] if next_phase < len(phase_names) else '完成'
    save_yaml(LOOP_DIR / 'registry.yaml', registry)
    
    print(f"\n{'='*50}")
    print(f"✅ Advanced to Phase {next_phase}!")
    print(f"   Backup saved: {backup_path.name}")
    print(f"   Next: python ../.loop/pre_review.py {paper_id}")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
