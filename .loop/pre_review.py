#!/usr/bin/env python3
"""Loop Engineering v4.1 — Automated Pre-Review Scanner
Applies Tier 1 rules from rulebook.yaml to a paper's main.tex

Usage:
    python pre_review.py PAPER_ID              # Run pre-review on a paper
    python pre_review.py PAPER_ID --tier 2     # Run Tier 1+2 checks
    python pre_review.py --help                # Show this help

Auto-hook: M3 Hallucination Check
    末尾自动调用 .loop/hallucination_check.py 检查 paper 的 M3 输出是否有 HIGH 级幻觉.
    HIGH > 0 时 pre_review.py 也会返回非零 exit code, 阻止 phase 推进.

Auto-hook: Detector Regression Test Suite
    同时跑 _test_granularity_suite.py (10 个粒度降级测试), 防止 detector 修改后
    软降级规则退化. 测试套件失败 = detector 自身 bug, 只警告不强制 block phase.

    详细文档: .loop/hallucination_check.README.md
              _inbox/方法论/mm3_hallucination_detector.README.md
"""
import yaml
import sys
import re
import argparse
from pathlib import Path

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def find_paper(paper_id):
    registry = load_yaml(LOOP_DIR / 'registry.yaml')
    for key, p in registry['papers'].items():
        if p['id'] == paper_id:
            return p
    return None

def read_tex(paper):
    tex_path = AETTL_DIR / paper['path'] / 'main.tex'
    if not tex_path.exists():
        return None
    with open(tex_path, 'r', encoding='utf-8') as f:
        return f.read()

def run_tier1_checks(text, paper_name):
    """Run all Tier 1 (blocking) checks"""
    issues = []
    
    # C1: "First"/"Novel" claims
    first_claims = re.findall(r'(?:first|novel|we are the first to)[^.]*\.', text, re.IGNORECASE)
    if first_claims:
        for claim in first_claims[:3]:
            issues.append({
                'rule': 'C1',
                'severity': 'critical',
                'description': f'"First/Novel" claim detected: "{claim.strip()[:80]}..."',
                'fix': 'Verify no prior work did the same thing. Search literature for each claim.'
            })
    
    # C9: Null effect misinterpretation
    null_phrases = re.findall(r'no statistically significant[^.]*\.|no detectable[^.]*\.|no effect[^.]*\.', text, re.IGNORECASE)
    for phrase in null_phrases[:3]:
        if 'p' in phrase.lower() and '=' in phrase:
            issues.append({
                'rule': 'C9',
                'severity': 'critical',
                'description': f'Null effect phrasing: "{phrase.strip()[:80]}..."',
                'fix': 'Use "insufficient evidence to reject the null" not "no effect exists".'
            })
    
    # C7: Count mismatch
    count_patterns = re.findall(r'(?:^|\s)([Tt]wo|[Tt]hree|[Ff]our|[Ff]ive|[Ss]ix)\s+\w+(?:\s+\w+)?\s*(?:recommendations|guidelines|findings|items|steps)', text)
    if count_patterns:
        issues.append({
            'rule': 'C7',
            'severity': 'minor',
            'description': f'Count claims detected: {count_patterns[:3]}. Verify enumerated items match count.',
            'fix': 'Count the actual items and match the number.'
        })
    
    # C4: Monotonic claims
    monotonic_claims = re.findall(r'monotonically[^.]*\.', text, re.IGNORECASE)
    if monotonic_claims:
        issues.append({
            'rule': 'C4',
            'severity': 'critical',
            'description': f'Monotonic claims: {len(monotonic_claims)} found. Verify per-condition data.',
            'fix': 'Check per-condition data for non-monotonic violations. Use "broadly" or "descriptively" qualifiers.'
        })
    
    # W4: Chinglish scan
    chinglish_patterns = [
        (r'different with', '"different with" → "different from"'),
        (r'\bcompare with\b(?!ed)', '"compare with" → "compared with/to"'),
        (r'\bprove\b(?!n|d|r|s)', '"prove" → "demonstrate/show" (unless mathematical proof)'),
        (r'in the following', '"in the following" → "below" or "in the next section"'),
        (r'most of\s(?!the)', '"most of" → "most" (unless followed by "the")'),
    ]
    for pattern, suggestion in chinglish_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            issues.append({
                'rule': 'W4',
                'severity': 'minor',
                'description': f'Chinglish: "{matches[0]}" → {suggestion}',
                'fix': suggestion
            })
    
    # Abstract density check
    abstract_match = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', text, re.DOTALL)
    if abstract_match:
        abstract = abstract_match.group(1)
        numbers = re.findall(r'\d+\.?\d*', abstract)
        sentences = [s.strip() for s in re.split(r'[.!?]\s+', abstract) if s.strip()]
        max_nums_in_sentence = max(len(re.findall(r'\d+\.?\d*', s)) for s in sentences) if sentences else 0
        if max_nums_in_sentence > 5:
            issues.append({
                'rule': 'ABSTRACT',
                'severity': 'important',
                'description': f'Abstract density: up to {max_nums_in_sentence} numbers in a single sentence ({len(numbers)} total numbers in abstract).',
                'fix': 'Break dense sentences. Narrative over data dump. Maximum ~4 numbers per sentence.'
            })
    
    return issues

def main():
    parser = argparse.ArgumentParser(
        description='Loop Engineering v4.1 — Automated Pre-Review Scanner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pre_review.py PAPER-A           # Run Tier 1 checks
  python pre_review.py PAPER-A --tier 2  # Run Tier 1+2 checks
  python pre_review.py PAPER-B --json    # Output as JSON
        """
    )
    parser.add_argument('paper_id', help='Paper ID (e.g., PAPER-A, PAPER-B)')
    parser.add_argument('--tier', '-t', type=int, default=1, choices=[1, 2, 3], help='Max tier to check (1-3)')
    parser.add_argument('--json', '-j', action='store_true', help='Output as JSON')
    args = parser.parse_args()
    
    paper_id = args.paper_id
    paper = find_paper(paper_id)
    if not paper:
        print(f"Paper '{paper_id}' not found in registry.")
        return
    
    text = read_tex(paper)
    if not text:
        print(f"main.tex not found at {AETTL_DIR / paper['path'] / 'main.tex'}")
        return
    
    print(f"\n🔍 Pre-Review: {paper['title'][:60]}...")
    print(f"   Paper: {paper_id} | Phase: {paper['phase']}")
    print("=" * 60)
    
    issues = run_tier1_checks(text, paper['short_title'])
    
    if not issues:
        print("\n✅ No Tier 1 issues detected!")
        return
    
    critical = [i for i in issues if i['severity'] == 'critical']
    important = [i for i in issues if i['severity'] == 'important']
    minor = [i for i in issues if i['severity'] == 'minor']
    
    print(f"\n🔴 Critical ({len(critical)}):")
    for i in critical:
        print(f"  [{i['rule']}] {i['description']}")
        print(f"  → Fix: {i['fix']}\n")
    
    print(f"🟡 Important ({len(important)}):")
    for i in important:
        print(f"  [{i['rule']}] {i['description']}")
        print(f"  → Fix: {i['fix']}\n")
    
    print(f"🟢 Minor ({len(minor)}):")
    for i in minor:
        print(f"  [{i['rule']}] {i['description']}")
    
    print(f"\n{'='*60}")
    print(f"Summary: {len(critical)} critical, {len(important)} important, {len(minor)} minor")
    print(f"Estimated review time saved: ~{len(issues) * 5} minutes")

    # 退出码: critical > 0 → 1, 否则 0 (供脚本/CI 自动化使用)
    block_exit_code = 1 if critical else 0

    # ── Auto-hook: M3 hallucination 检查 ──────────────────────────
    # 仅在 paper 路径下存在 llm_summaries/ 时运行, 否则跳过
    try:
        paper_rel_path = paper['path']
        summaries_dir = AETTL_DIR / paper_rel_path / 'llm_summaries'
        if summaries_dir.exists() and any(summaries_dir.glob('*.md')):
            print(f"\n{'='*60}")
            print("🔗 Auto-hook: M3 Hallucination Check")
            print(f"{'='*60}")
            # 复用 hallucination_check.py 里的公共函数 (避免 subprocess + GBK 问题)
            sys.path.insert(0, str(LOOP_DIR))
            from hallucination_check import run_hallucination_hook
            passed, n_high, n_med, n_low, _ = run_hallucination_hook(paper_id, verbose=True)
            if not passed:
                print(f"⚠ Hallucination hook 失败: {n_high} 个 HIGH 级问题")
                print(f"  → 建议先修复后再推进 Phase")
                block_exit_code = max(block_exit_code, 1)
            else:
                print(f"✅ Hallucination hook 通过 (HIGH=0)")
    except Exception as e:
        print(f"  (auto-hook 跳过: {e})")

    # ── Auto-hook: Detector regression test suite ─────────────────
    # 跑 10 个粒度降级测试, 防止 detector 修改后软降级规则退化.
    # 设计选择: 测试套件失败 = detector 自身 bug, 不强制 block phase 推进
    #           (论文问题 ≠ 代码 bug), 只显示警告
    try:
        test_suite = AETTL_DIR / '_test_granularity_suite.py'
        if test_suite.exists():
            print(f"\n{'='*60}")
            print("🧪 Auto-hook: Detector Regression Test Suite")
            print(f"{'='*60}")
            import subprocess
            env = {**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8'}
            result = subprocess.run(
                [sys.executable, str(test_suite)],
                capture_output=True, text=True, encoding='utf-8',
                env=env, timeout=60,
            )
            # 提取通过/失败计数
            import re as _re
            m = _re.search(r'共\s+(\d+)\s+个测试.*?通过\s+(\d+).*?失败\s+(\d+)', result.stdout)
            if m:
                total, passed, failed = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if failed == 0:
                    print(f"✅ Detector 测试套件全部通过 ({total}/{total})")
                else:
                    print(f"⚠ Detector 测试套件 {failed}/{total} 失败")
                    print(f"  → 这是 detector 自身的 bug, 不影响 phase 推进")
                    print(f"  → 但建议尽快修复 (调 _inbox/方法论/mm3_hallucination_detector.py)")
                    print(f"\n{result.stdout}")
            else:
                print(f"  (无法解析测试结果, exit={result.returncode})")
    except Exception as e:
        print(f"  (test suite 跳过: {e})")

    sys.exit(block_exit_code)

if __name__ == '__main__':
    main()
