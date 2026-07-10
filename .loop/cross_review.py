#!/usr/bin/env python3
"""Loop Engineering v4.1 — Cross-Paper Pattern Scanner
Scans all registered papers for shared issues and generates meta-review reports.

Usage:
    python cross_review.py                  # Scan all papers
    python cross_review.py --pattern C1     # Check specific pattern across papers
    python cross_review.py --paper PAPER-A  # Check what this paper shares with others
    python cross_review.py --report         # Generate full meta-review markdown report
"""
import yaml
import sys
import re
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_yaml(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

def run_pre_review_for_paper(paper, paper_dir):
    """Run pre_review.py logic inline to get issues for a paper."""
    tex_path = paper_dir / 'main.tex'
    if not tex_path.exists():
        return []
    
    text = tex_path.read_text(encoding='utf-8', errors='ignore')
    issues = []
    
    # C1: First/Novel claims
    first_claims = re.findall(r'(?:first|novel|we are the first to)[^.]*\.', text, re.IGNORECASE)
    if first_claims:
        issues.append({'rule': 'C1', 'severity': 'critical', 'count': len(first_claims)})
    
    # C9: Null effect
    null_phrases = re.findall(r'no statistically significant[^.]*\.|no detectable[^.]*\.', text, re.IGNORECASE)
    for phrase in null_phrases:
        if 'p' in phrase.lower() and '=' in phrase:
            issues.append({'rule': 'C9', 'severity': 'critical', 'count': 1})
            break
    
    # C7: Count mismatch
    count_patterns = re.findall(r'(?:^|\s)([Tt]wo|[Tt]hree|[Ff]our|[Ff]ive|[Ss]ix)\s+\w+(?:\s+\w+)?\s*(?:recommendations|guidelines|findings|items|steps)', text)
    if count_patterns:
        issues.append({'rule': 'C7', 'severity': 'minor', 'count': len(count_patterns)})
    
    # C4: Monotonic claims
    monotonic = re.findall(r'monotonically[^.]*\.', text, re.IGNORECASE)
    if monotonic:
        issues.append({'rule': 'C4', 'severity': 'critical', 'count': len(monotonic)})
    
    # W4: Chinglish
    chinglish = [
        (r'different with', 'W4'),
        (r'\bcompare with\b(?!ed)', 'W4'),
        (r'\bprove\b(?!n|d|r|s)', 'W4'),
        (r'in the following', 'W4'),
    ]
    for pattern, rule in chinglish:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            issues.append({'rule': rule, 'severity': 'minor', 'count': len(matches), 'detail': matches[0]})
    
    # Abstract density
    abstract_match = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', text, re.DOTALL)
    if abstract_match:
        abstract = abstract_match.group(1)
        numbers = re.findall(r'\d+\.?\d*', abstract)
        sentences = [s.strip() for s in re.split(r'[.!?]\s+', abstract) if s.strip()]
        max_nums = max(len(re.findall(r'\d+\.?\d*', s)) for s in sentences) if sentences else 0
        if max_nums > 5:
            issues.append({'rule': 'ABSTRACT', 'severity': 'important', 'count': len(numbers)})
    
    # S5: Missing CI in abstract
    has_ci = bool(re.search(r'\[.*?\d+.*?,\s*\d+.*?\]', abstract_match.group(1) if abstract_match else ''))
    if not has_ci and abstract_match:
        numbers_in_abstract = len(re.findall(r'\d+\.\d+', abstract_match.group(1)))
        if numbers_in_abstract > 3:
            issues.append({'rule': 'S5', 'severity': 'important', 'count': numbers_in_abstract})
    
    return issues

def scan_all_papers(registry):
    """Scan all registered papers and collect issues."""
    results = {}
    for key, paper in registry['papers'].items():
        paper_dir = AETTL_DIR / paper['path']
        if not paper_dir.exists():
            continue
        issues = run_pre_review_for_paper(paper, paper_dir)
        if issues:
            results[paper['id']] = {
                'title': paper['short_title'],
                'issues': issues,
                'phase': paper['phase'],
                'score': paper.get('score_self'),
            }
    return results

def find_cross_patterns(results, cross_ref):
    """Find patterns that appear across multiple papers."""
    cross_patterns = []
    
    # Group issues by rule across papers
    rule_papers = defaultdict(list)
    for paper_id, data in results.items():
        for issue in data['issues']:
            rule_papers[issue['rule']].append({
                'paper': paper_id,
                'title': data['title'],
                'count': issue.get('count', 1),
                'severity': issue['severity']
            })
    
    # Find rules that appear in 2+ papers
    for rule, papers in rule_papers.items():
        if len(papers) >= 2:
            # Check if this rule has a cross_ref entry
            pattern_info = None
            for pattern in cross_ref.get('cross_references', []):
                if pattern['pattern_id'].upper().startswith(rule) or rule in str(pattern):
                    pattern_info = pattern
                    break
            
            cross_patterns.append({
                'rule': rule,
                'papers': [p['paper'] for p in papers],
                'paper_count': len(papers),
                'severity': papers[0]['severity'],
                'cross_ref': pattern_info['description'] if pattern_info else 'No cross-ref entry',
                'auto_fix': pattern_info['auto_check'] if pattern_info else 'Add to cross_ref.yaml',
            })
    
    return sorted(cross_patterns, key=lambda x: x['paper_count'], reverse=True)

def generate_report(results, cross_patterns, output_path=None):
    """Generate a markdown meta-review report."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    lines = [
        f"# Cross-Paper Meta-Review Report",
        f"**Generated**: {now}",
        f"**Papers scanned**: {len(results)}",
        f"**Cross-paper patterns found**: {len(cross_patterns)}",
        "",
        "---",
        "",
        "## 📊 Per-Paper Summary",
        "",
        "| Paper | Phase | Score | Issues Found |",
        "|-------|-------|-------|-------------|",
    ]
    
    for paper_id, data in sorted(results.items()):
        critical = sum(1 for i in data['issues'] if i['severity'] == 'critical')
        important = sum(1 for i in data['issues'] if i['severity'] == 'important')
        minor = sum(1 for i in data['issues'] if i['severity'] == 'minor')
        issue_str = f"{critical}C/{important}I/{minor}M"
        score = f"{data['score']}/10" if data['score'] else "—"
        lines.append(f"| {paper_id} | {data['title'][:30]} | P{data['phase']} | {score} | {issue_str} |")
    
    lines += [
        "",
        "---",
        "",
        "## 🔗 Cross-Paper Patterns",
        "",
    ]
    
    if not cross_patterns:
        lines.append("✅ No cross-paper patterns detected. All issues are paper-specific.")
    else:
        lines.append("| Rule | Papers | Severity | Pattern |")
        lines.append("|------|--------|----------|---------|")
        for cp in cross_patterns:
            papers_str = ', '.join(cp['papers'])
            lines.append(f"| {cp['rule']} | {papers_str} ({cp['paper_count']}) | {cp['severity']} | {cp['cross_ref'][:60]} |")
    
    lines += [
        "",
        "---",
        "",
        "## 💡 Systematic Recommendations",
        "",
    ]
    
    if cross_patterns:
        # Group by severity
        critical_patterns = [cp for cp in cross_patterns if cp['severity'] == 'critical']
        if critical_patterns:
            lines.append("### 🔴 Critical — Fix across all affected papers")
            for cp in critical_patterns:
                lines.append(f"- **{cp['rule']}**: Affects {', '.join(cp['papers'])}. {cp['cross_ref']}")
            lines.append("")
        
        # Suggest automation for high-frequency patterns
        high_freq = [cp for cp in cross_patterns if cp['paper_count'] >= 2]
        if high_freq:
            lines.append("### 🤖 Candidates for Automation")
            for cp in high_freq:
                lines.append(f"- **{cp['rule']}** ({cp['paper_count']} papers): Add stricter auto-check to `pre_review.py`")
            lines.append("")
    
    lines.append(f"*Report generated by Loop Engineering v4.1 cross_review.py*")
    
    report = '\n'.join(lines)
    
    if output_path:
        Path(output_path).write_text(report, encoding='utf-8')
        print(f"📄 Report saved to: {output_path}")
    
    return report

def main():
    parser = argparse.ArgumentParser(
        description='Loop Engineering v4.1 — Cross-Paper Pattern Scanner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cross_review.py                    # Scan all papers
  python cross_review.py --pattern C1       # Check specific pattern
  python cross_review.py --paper PAPER-A    # Single paper cross-ref
  python cross_review.py --report           # Generate meta-review .md
  python cross_review.py --report --output meta.md  # Save to file
        """
    )
    parser.add_argument('--pattern', '-p', help='Check specific rule pattern (e.g., C1, W4)')
    parser.add_argument('--paper', '-P', help='Show cross-ref for specific paper')
    parser.add_argument('--report', '-r', action='store_true', help='Generate full meta-review report')
    parser.add_argument('--output', '-o', help='Save report to file (requires --report)')
    args = parser.parse_args()
    
    registry_path = LOOP_DIR / 'registry.yaml'
    cross_ref_path = LOOP_DIR / 'cross_ref.yaml'
    
    if not registry_path.exists():
        print("❌ registry.yaml not found. Run from aettl-research/ directory.")
        sys.exit(1)
    
    registry = load_yaml(registry_path)
    cross_ref = load_yaml(cross_ref_path) if cross_ref_path.exists() else {'cross_references': []}
    
    results = scan_all_papers(registry)
    
    if not results:
        print("❌ No papers with main.tex found. Add papers first.")
        sys.exit(1)
    
    cross_patterns = find_cross_patterns(results, cross_ref)
    
    # Single paper mode
    if args.paper:
        if args.paper not in results:
            print(f"❌ Paper '{args.paper}' not found or has no issues.")
            print(f"   Available: {', '.join(results.keys())}")
            sys.exit(1)
        
        paper_data = results[args.paper]
        print(f"\n📄 {args.paper}: {paper_data['title']}")
        print(f"   Phase: {paper_data['phase']} | Issues: {len(paper_data['issues'])}")
        print()
        
        # Find which patterns this paper shares with others
        shared = [cp for cp in cross_patterns if args.paper in cp['papers']]
        if shared:
            print(f"   Shared patterns with other papers:")
            for cp in shared:
                others = [p for p in cp['papers'] if p != args.paper]
                print(f"   🔗 {cp['rule']}: also in {', '.join(others)} — {cp['cross_ref'][:60]}")
        else:
            print(f"   No shared patterns — issues are paper-specific.")
        
        # Find patterns this paper is MISSING that others have
        all_rules = set()
        for cp in cross_patterns:
            all_rules.update(cp['papers'])
        print()
        return
    
    # Pattern-specific mode
    if args.pattern:
        matching = [cp for cp in cross_patterns if cp['rule'].upper() == args.pattern.upper()]
        if matching:
            cp = matching[0]
            print(f"\n🔍 Pattern {cp['rule']} appears in {cp['paper_count']} papers:")
            for paper_id in cp['papers']:
                data = results[paper_id]
                print(f"   📄 {paper_id}: {data['title']} (Phase {data['phase']})")
            print(f"\n   Pattern: {cp['cross_ref']}")
            print(f"   Auto-fix: {cp['auto_fix']}")
        else:
            print(f"\n✅ Pattern '{args.pattern}' not found across papers (paper-specific or no hits).")
        return
    
    # Default: summary mode
    print(f"\n🔗 Cross-Paper Scan — {len(results)} papers, {len(cross_patterns)} shared patterns")
    print(f"{'='*60}")
    
    if cross_patterns:
        for cp in cross_patterns:
            icon = '🔴' if cp['severity'] == 'critical' else '🟡' if cp['severity'] == 'important' else '🟢'
            papers_str = ', '.join(cp['papers'])
            print(f"  {icon} {cp['rule']} ({cp['paper_count']} papers): {cp['cross_ref'][:70]}")
            print(f"     Papers: {papers_str}")
    else:
        print("  ✅ No cross-paper patterns detected.")
    
    # Report mode
    if args.report:
        output_path = args.output or (LOOP_DIR / 'reports' / f'meta_review_{datetime.now().strftime("%Y%m%d")}.md')
        if not args.output:
            output_path.parent.mkdir(exist_ok=True)
        report = generate_report(results, cross_patterns, output_path)
        print(f"\n{report[:500]}...")
    
    print(f"\n{'='*60}")
    print(f"Commands: cross_review.py --report | cross_review.py --paper PAPER-A | cross_review.py --pattern C1")

if __name__ == '__main__':
    main()
