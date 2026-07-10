#!/usr/bin/env python3
"""Loop Engineering v5.3 — Unified Audit Engine
One command for complete paper audit.

Usage:
  python audit.py PAPER_ID              # Quick audit (regex + quality)
  python audit.py PAPER_ID --full       # Full audit (+ skill bridge + agent)
  python audit.py PAPER_ID --fix        # Auto-fix what's fixable
  python audit.py PAPER_ID --progress   # Show progress over time
  python audit.py PAPER_ID --rebuttal   # Generate rebuttal draft
  python audit.py PAPER_ID --agent      # Re-run agent review
  python audit.py --all                 # Portfolio audit
"""
import re, sys, json, argparse, hashlib, yaml
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent
SNAPSHOTS_DIR = LOOP_DIR / 'snapshots'
REVIEWS_DIR = LOOP_DIR / 'reviews'

# ============================================================
# Priority Classification
# ============================================================
PRIORITY_RULES = {
    # P0: Would cause desk reject
    'P0': [
        'MERGED_BIB', 'CITE_NO_BIB', 'GHOST_REF', 'AUTHOR_EXPOSED',
        'NO_TMLR_STY', 'NO_BROADER_IMPACT', 'NO_REPRODUCIBILITY',
        'LATEX_FATAL', 'UNDEF_REF', 'UNDEF_CITE', 'CITE_RETRACTED',
        'AGENT_METHODOL',  # Agent critical methodology issues
    ],
    # P1: Reviewer will ask about
    'P1': [
        'FIRST_CLAIM', 'CI_COVERAGE', 'CI_ABSTRACT', 'POWER_LOW_N',
        'EFFECT_SIZE', 'MULT_COMPAR', 'PAIRED_TEST', 'NO_STD',
        'AGENT_CLAIM_EV', 'AGENT_EXPERIME', 'AGENT_LOGIC',
        'NO_NONSIG', 'SELECTIVE_REPORTING',
        'TMLR_SAMPLE_SIZ', 'TMLR_SELF_CIT', 'TMLR_REFERENC',
    ],
    # P2: Nice to fix
    'P2': [
        'ABSTRACT_DENSE', 'UNUSED_LABEL', 'NO_DOI', 'NO_SLICE',
        'AGENT_LITERATU', 'BIB_KEY_FORMAT', 'NOTATION',
        'AGENT_SUMMARY', 'NO_SUPPLEMENTARY', 'NO_PREREG',
    ],
}

def classify_priority(issue_code):
    """Classify an issue into P0/P1/P2."""
    for p, codes in PRIORITY_RULES.items():
        if any(c in issue_code for c in codes):
            return p
    return 'P2'

# ============================================================
# Issue Normalization
# ============================================================
def normalize_issues(raw_issues):
    """Normalize issues from different sources into unified format."""
    issues = []
    for item in raw_issues:
        if len(item) == 3:
            code, severity, msg = item
        else:
            continue
        if severity == 'pass':
            continue
        priority = classify_priority(code)
        issues.append({
            'code': code,
            'severity': severity,
            'priority': priority,
            'message': msg,
            'source': detect_source(code),
        })
    return issues

def detect_source(code):
    """Detect which module produced this issue."""
    if code.startswith('AGENT_'):
        return 'agent'
    elif code.startswith('TMLR_'):
        return 'tmlr_compare'
    elif code in ('PAIRED_TEST', 'NO_STD', 'NO_DOI', 'NO_SLICE', 'NO_FDR'):
        return 'skill_bridge'
    elif code in ('LATEX_LOG', 'SUBMISSION', 'CITE_VERIFY', 'CITE_OFFLINE'):
        return 'skill_bridge'
    elif code in ('MERGED_BIB', 'CITE_NO_BIB', 'GHOST_REF', 'LATEX_FATAL',
                  'UNDEF_REF', 'UNDEF_CITE', 'UNUSED_LABEL', 'MULTI_LABEL'):
        return 'latex_check'
    elif code in ('BIBENTRY', 'POWER_LOW_N', 'POWER_LOW', 'SELECTIVE_REPORTING',
                  'NO_NONSIG', 'UNEQUAL_N', 'NO_SUPPLEMENTARY', 'NO_PREREG'):
        return 'quality_checks'
    elif code in ('CI_COVERAGE', 'CI_ABSTRACT', 'EFFECT_SIZE', 'TABLE_FIG',
                  'SMALL_N', 'NOTATION', 'MULT_COMPAR', 'BIB_KEY_FORMAT'):
        return 'quality_checks'
    else:
        return 'submission_audit'

# ============================================================
# Snapshot Management (Progress Tracking)
# ============================================================
def save_snapshot(paper_id, issues, score):
    """Save audit snapshot for progress tracking."""
    SNAPSHOTS_DIR.mkdir(exist_ok=True)
    snapshot = {
        'paper_id': paper_id,
        'timestamp': datetime.now().isoformat(),
        'score': score,
        'total': len(issues),
        'by_priority': {
            'P0': sum(1 for i in issues if i.get('priority') == 'P0'),
            'P1': sum(1 for i in issues if i.get('priority') == 'P1'),
            'P2': sum(1 for i in issues if i.get('priority') == 'P2'),
        },
        'by_source': dict(defaultdict(int, {
            i.get('source', 'unknown'): 1 for i in issues
        })),
        'issues': [{'code': i['code'], 'priority': i['priority'],
                    'message': i['message'][:80]} for i in issues],
    }

    # Hash-based filename
    content_hash = hashlib.md5(
        json.dumps(snapshot['issues'], sort_keys=True).encode()
    ).hexdigest()[:8]

    filename = f"{paper_id}_{datetime.now().strftime('%Y%m%d')}_{content_hash}.json"
    filepath = SNAPSHOTS_DIR / filename
    filepath.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding='utf-8')

    return filepath

def load_snapshots(paper_id):
    """Load all snapshots for a paper."""
    if not SNAPSHOTS_DIR.exists():
        return []
    snapshots = []
    for f in sorted(SNAPSHOTS_DIR.glob(f"{paper_id}_*.json")):
        snapshots.append(json.loads(f.read_text(encoding='utf-8')))
    return snapshots

def show_progress(paper_id):
    """Show progress over time."""
    snapshots = load_snapshots(paper_id)
    if not snapshots:
        print(f"No snapshots found for {paper_id}")
        return

    print(f"\n{'='*65}")
    print(f"📈 Progress — {paper_id}")
    print(f"{'='*65}")

    for i, snap in enumerate(snapshots):
        ts = snap.get('timestamp', '?')[:10]
        score = snap.get('score', '?')
        p0 = snap['by_priority'].get('P0', 0)
        p1 = snap['by_priority'].get('P1', 0)
        p2 = snap['by_priority'].get('P2', 0)

        trend = ''
        if i > 0:
            prev_score = snapshots[i-1].get('score', 0)
            if isinstance(score, (int, float)) and isinstance(prev_score, (int, float)):
                diff = score - prev_score
                trend = f" {'📈' if diff > 0 else '📉' if diff < 0 else '➡️'} {diff:+.1f}"

        print(f"  {ts}  Score: {score}/10  P0:{p0} P1:{p1} P2:{p2}{trend}")

    # Show resolved issues
    if len(snapshots) >= 2:
        prev_codes = {i['code'] for i in snapshots[-2].get('issues', [])}
        curr_codes = {i['code'] for i in snapshots[-1].get('issues', [])}
        resolved = prev_codes - curr_codes
        new = curr_codes - prev_codes
        if resolved:
            print(f"\n  ✅ Resolved: {', '.join(sorted(resolved))}")
        if new:
            print(f"  🆕 New: {', '.join(sorted(new))}")

    print(f"\n{'='*65}")

# ============================================================
# Auto-Fix
# ============================================================
def auto_fix(paper_id, issues):
    """Attempt to auto-fix fixable issues."""
    import yaml
    registry = yaml.safe_load((LOOP_DIR / 'registry.yaml').read_text(encoding='utf-8'))

    paper = None
    for k, p in registry['papers'].items():
        if p['id'] == paper_id:
            paper = p
            break
    if not paper:
        return []

    paper_dir = AETTL_DIR / paper['path']
    tex_files = (list(paper_dir.glob('main_merged.tex')) or
                 list(paper_dir.glob('main_tmlr.tex')) or
                 list(paper_dir.glob('main.tex')))
    if not tex_files:
        return []

    tex_path = tex_files[0]
    text = tex_path.read_text(encoding='utf-8', errors='ignore')
    fixes = []

    for issue in issues:
        code = issue['code']

        # Fix: UNUSED_LABEL — remove \label{} that are never \ref'd
        if code == 'UNUSED_LABEL':
            label = re.search(r"'\\label\{([^}]+)\}'", issue['message'])
            if label:
                label_name = label.group(1)
                # Only remove if truly unused
                refs = re.findall(r'\\ref\{' + re.escape(label_name) + r'\}', text)
                if not refs:
                    text = text.replace(f'\\label{{{label_name}}}', '')
                    fixes.append(f"Removed unused label: {label_name}")

        # Fix: ABSTRACT_DENSE — add line breaks
        # (Not auto-fixable — needs human judgment)

        # Fix: BIB_KEY_FORMAT — not auto-fixable without changing \cite{} too

    if fixes:
        # Save fixed version
        tex_path.write_text(text, encoding='utf-8')
        print(f"\n  🔧 Auto-fixed {len(fixes)} issue(s):")
        for f in fixes:
            print(f"    ✅ {f}")
    else:
        print("\n  ℹ️  No auto-fixable issues found.")

    return fixes

# ============================================================
# Rebuttal Generation
# ============================================================
def generate_rebuttal(paper_id):
    """Generate rebuttal draft from agent review findings."""
    review_file = REVIEWS_DIR / f"{paper_id}_review.json"
    if not review_file.exists():
        print(f"❌ No agent review found for {paper_id}. Run: python agent_review.py {paper_id} --generate")
        return None

    review = json.loads(review_file.read_text(encoding='utf-8'))
    issues = review.get('issues', [])

    if not issues:
        print("No issues to generate rebuttal for.")
        return None

    rebuttal_lines = []
    rebuttal_lines.append(f"# Rebuttal Draft — {paper_id}")
    rebuttal_lines.append(f"# Generated from agent review (score: {review.get('score', '?')}/10)")
    rebuttal_lines.append(f"# {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    rebuttal_lines.append("")

    # Group by severity
    crit = [i for i in issues if i.get('severity') == 'critical']
    imp = [i for i in issues if i.get('severity') == 'important']
    minor = [i for i in issues if i.get('severity') == 'minor']

    for group_name, group in [('CRITICAL', crit), ('IMPORTANT', imp), ('MINOR', minor)]:
        if not group:
            continue
        rebuttal_lines.append(f"## {group_name} ({len(group)})")
        rebuttal_lines.append("")

        for i, issue in enumerate(group, 1):
            q = issue.get('issue', '')
            evidence = issue.get('evidence', '')
            fix = issue.get('fix', '')

            rebuttal_lines.append(f"### Q{i}: {q[:80]}")
            rebuttal_lines.append("")
            rebuttal_lines.append(f"**Reviewer concern:** {q}")
            if evidence:
                rebuttal_lines.append(f"**Evidence cited:** {evidence[:120]}")
            rebuttal_lines.append("")
            rebuttal_lines.append(f"**Suggested fix:** {fix[:120] if fix else 'TODO'}")
            rebuttal_lines.append("")
            rebuttal_lines.append("**Response (draft):**")
            rebuttal_lines.append("TODO: Write response here")
            rebuttal_lines.append("")
            rebuttal_lines.append("**Changes made:**")
            rebuttal_lines.append("- TODO: List specific changes")
            rebuttal_lines.append("")
            rebuttal_lines.append("---")
            rebuttal_lines.append("")

    # Save rebuttal
    rebuttal_text = '\n'.join(rebuttal_lines)
    rebuttal_file = REVIEWS_DIR / f"{paper_id}_rebuttal.md"
    rebuttal_file.write_text(rebuttal_text, encoding='utf-8')

    print(f"✅ Rebuttal draft saved: {rebuttal_file}")
    print(f"   {len(crit)} critical, {len(imp)} important, {len(minor)} minor questions")
    return str(rebuttal_file)

# ============================================================
# Main Audit Orchestrator
# ============================================================
def run_systematic_review(paper_id, text=None, auto_fix=True):
    """Run systematic line-by-line review with auto-fix."""
    try:
        from systematic_review import run_systematic_review as sr_run
        import yaml
        if text is None:
            registry = yaml.safe_load((LOOP_DIR / 'registry.yaml').read_text(encoding='utf-8'))
            for k, p in registry.get('papers', {}).items():
                if p['id'] == paper_id:
                    paper_dir = AETTL_DIR / p['path']
                    for name in ['main_merged.tex', 'main_tmlr.tex', 'main.tex']:
                        candidate = paper_dir / name
                        if candidate.exists():
                            text = candidate.read_text(encoding='utf-8', errors='ignore')
                            break
                    break
        if text is None:
            return [], []
        result = sr_run(text, auto_fix=auto_fix)
        issues = []
        for code, sev, msg in result['issues']:
            issues.append((f'SR_{code}', sev, msg))
        return issues, result['fixes']
    except ImportError:
        return [], []
    except Exception as e:
        return [('SR_ERROR', 'minor', f'Systematic review error: {e}')], []


def run_tmlr_comparison(paper_id, text=None):
    """Run TMLR library comparison."""
    try:
        from tmlr_compare import load_library, extract_paper_features, compare_with_library
        library = load_library()
        if not library:
            return []

        if text is None:
            import yaml
            registry = yaml.safe_load((LOOP_DIR / 'registry.yaml').read_text(encoding='utf-8'))
            for k, p in registry.get('papers', {}).items():
                if p['id'] == paper_id:
                    paper_dir = AETTL_DIR / p['path']
                    for name in ['main_merged.tex', 'main_tmlr.tex', 'main.tex']:
                        candidate = paper_dir / name
                        if candidate.exists():
                            text = candidate.read_text(encoding='utf-8', errors='ignore')
                            break
                    break

            # Fallback: try direct path
            if text is None:
                candidate = Path(paper_id)
                if candidate.exists():
                    text = candidate.read_text(encoding='utf-8', errors='ignore')

        if text is None:
            return []

        features = extract_paper_features(text)
        results = compare_with_library(features, library)

        issues = []
        for dim, r in results.items():
            if r['status'] == 'fail':
                issues.append(('TMLR_' + dim.upper()[:10], 'important',
                    f'{dim}: {r["label"]} — {r["benchmark"]}'))
            elif r['status'] == 'warn':
                issues.append(('TMLR_' + dim.upper()[:10], 'minor',
                    f'{dim}: {r["label"]} — {r["benchmark"]}'))

        return issues
    except ImportError:
        return []
    except Exception as e:
        return [('TMLR_ERROR', 'minor', f'TMLR comparison error: {e}')]


def run_quick_audit(paper_id):
    """Quick audit: submission_audit + quality_checks + latex_check + tmlr_compare."""
    from submission_audit import find_paper, run_audit
    paper = find_paper(paper_id)
    if not paper:
        return None
    result = run_audit(paper_id, paper)

    # Add TMLR comparison (lightweight, always included)
    tmlr_issues = run_tmlr_comparison(paper_id)
    existing_msgs = {i[2][:60] for i in result['issues'] if len(i) == 3}
    for issue in tmlr_issues:
        if len(issue) == 3 and issue[2][:60] not in existing_msgs:
            result['issues'].append(issue)

    # Add systematic review (line-by-line + auto-fix)
    sr_issues, sr_fixes = run_systematic_review(paper_id)
    for issue in sr_issues:
        if len(issue) == 3 and issue[2][:60] not in existing_msgs:
            result['issues'].append(issue)
    result['auto_fixes'] = sr_fixes

    # Recalculate
    critical = sum(1 for i in result['issues'] if i[1] == 'critical')
    important = sum(1 for i in result['issues'] if i[1] == 'important')
    minor = sum(1 for i in result['issues'] if i[1] == 'minor')
    result['critical'] = critical
    result['important'] = important
    result['minor'] = minor
    result['score'] = round(min(10, 10 - critical * 2 - important * 0.3), 1)

    return result

def run_full_audit(paper_id):
    """Full audit: quick + skill_bridge + agent_review + tmlr_compare."""
    result = run_quick_audit(paper_id)
    if not result:
        return None

    # Agent review (from cache)
    try:
        from agent_review import load_cached_review, format_for_audit
        agent_result = load_cached_review(paper_id)
        if agent_result:
            agent_issues = format_for_audit(agent_result)
            # Deduplicate: only add issues not already in result
            existing_msgs = {i[2][:60] for i in result['issues'] if len(i) == 3}
            for issue in agent_issues:
                if len(issue) == 3 and issue[2][:60] not in existing_msgs:
                    result['issues'].append(issue)
                    existing_msgs.add(issue[2][:60])
    except ImportError:
        pass

    # TMLR comparison
    tmlr_issues = run_tmlr_comparison(paper_id)
    existing_msgs = {i[2][:60] for i in result['issues'] if len(i) == 3}
    for issue in tmlr_issues:
        if len(issue) == 3 and issue[2][:60] not in existing_msgs:
            result['issues'].append(issue)

    # Recalculate
    critical = sum(1 for i in result['issues'] if i[1] == 'critical')
    important = sum(1 for i in result['issues'] if i[1] == 'important')
    minor = sum(1 for i in result['issues'] if i[1] == 'minor')
    result['critical'] = critical
    result['important'] = important
    result['minor'] = minor
    result['score'] = round(min(10, 10 - critical * 2 - important * 0.3), 1)

    return result

def print_unified_report(result, paper_id):
    """Print unified audit report with priority classification."""
    if not result or 'error' in result:
        print(f"❌ {result.get('error', 'Unknown error')}")
        return

    # Normalize issues
    issues = normalize_issues(result.get('issues', []))

    print(f"\n{'='*65}")
    print(f"📋 Loop Engineering v5.3 — {paper_id}")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*65}")

    # Priority groups
    p0 = [i for i in issues if i['priority'] == 'P0']
    p1 = [i for i in issues if i['priority'] == 'P1']
    p2 = [i for i in issues if i['priority'] == 'P2']

    if p0:
        print(f"\n  🔴 P0 — DESK REJECT RISK ({len(p0)}):")
        for i in p0:
            src = {'agent': '🤖', 'skill_bridge': '🔗', 'latex_check': '🔧',
                   'quality_checks': '📊', 'submission_audit': '📋'}.get(i['source'], '•')
            print(f"    {src} [{i['code']}] {i['message'][:80]}")

    if p1:
        print(f"\n  🟡 P1 — REVIEWER WILL ASK ({len(p1)}):")
        for i in p1:
            src = {'agent': '🤖', 'skill_bridge': '🔗', 'latex_check': '🔧',
                   'quality_checks': '📊', 'submission_audit': '📋',
                   'tmlr_compare': '📈'}.get(i['source'], '•')
            print(f"    {src} [{i['code']}] {i['message'][:80]}")

    if p2:
        print(f"\n  🟢 P2 — POLISH ({len(p2)}):")
        for i in p2[:5]:  # Show first 5
            src = {'agent': '🤖', 'skill_bridge': '🔗', 'latex_check': '🔧',
                   'quality_checks': '📊', 'submission_audit': '📋'}.get(i['source'], '•')
            print(f"    {src} [{i['code']}] {i['message'][:80]}")
        if len(p2) > 5:
            print(f"    ... and {len(p2)-5} more")

    # TMLR comparison summary
    tmlr_issues = [i for i in issues if i['source'] == 'tmlr_compare']
    if tmlr_issues:
        print(f"\n  📊 TMLR Benchmark ({len(tmlr_issues)}):")
        for i in tmlr_issues:
            icon = {'important': '🟡', 'minor': '🟢'}.get(i['severity'], '•')
            print(f"    {icon} {i['message'][:80]}")

    # Auto-fix summary
    auto_fixes = result.get('auto_fixes', [])
    if auto_fixes:
        print(f"\n  🔧 Auto-fixes applied ({len(auto_fixes)}):")
        for fix in auto_fixes:
            print(f"    ✅ {fix}")

    # Score
    score = result.get('score', 0)
    emoji = '✅' if score >= 8 else '⚠️' if score >= 6 else '🔴'
    verdict = 'READY' if score >= 8 else 'REVISION NEEDED' if score >= 6 else 'NOT READY'

    print(f"\n{'='*65}")
    print(f"  {emoji} Score: {score}/10 — {verdict}")
    print(f"  P0: {len(p0)}  P1: {len(p1)}  P2: {len(p2)}")
    sources = Counter(i.get('source', 'unknown') for i in issues)
    source_str = ', '.join(f'{v} {k}' for k, v in sources.most_common() if v > 0)
    print(f"  Sources: {source_str}")
    print(f"{'='*65}")

    # Save snapshot
    save_snapshot(paper_id, issues, score)

    return issues

# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='Loop Engineering v5.3 — Unified Audit Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python audit.py PAPER-E              # Quick audit
  python audit.py PAPER-E --full       # Full audit (+ agent)
  python audit.py PAPER-E --fix        # Auto-fix
  python audit.py PAPER-E --progress   # Show progress
  python audit.py PAPER-E --rebuttal   # Generate rebuttal
  python audit.py PAPER-E --agent      # Re-run agent review
  python audit.py --all                # Portfolio audit
        """)
    parser.add_argument('paper_id', nargs='?', help='Paper ID')
    parser.add_argument('--all', '-a', action='store_true', help='Portfolio audit')
    parser.add_argument('--full', '-f', action='store_true', help='Full audit (includes agent)')
    parser.add_argument('--fix', action='store_true', help='Auto-fix fixable issues')
    parser.add_argument('--progress', '-p', action='store_true', help='Show progress')
    parser.add_argument('--rebuttal', '-r', action='store_true', help='Generate rebuttal')
    parser.add_argument('--agent', action='store_true', help='Generate agent review prompt')
    parser.add_argument('--json', '-j', action='store_true', help='JSON output')
    args = parser.parse_args()

    if not args.paper_id and not args.all:
        parser.print_help()
        sys.exit(1)

    if args.all:
        # Portfolio audit
        registry = yaml.safe_load((LOOP_DIR / 'registry.yaml').read_text(encoding='utf-8'))
        print(f"\n{'='*65}")
        print(f"📋 Portfolio Audit — {len(registry['papers'])} papers")
        print(f"{'='*65}")
        for key, p in registry['papers'].items():
            paper_id = p['id']
            print(f"\n  ▸ {paper_id}: {p.get('short_title', key)}")
            if args.full:
                result = run_full_audit(paper_id)
            else:
                result = run_quick_audit(paper_id)
            if result and 'error' not in result:
                issues = normalize_issues(result.get('issues', []))
                p0 = sum(1 for i in issues if i['priority'] == 'P0')
                p1 = sum(1 for i in issues if i['priority'] == 'P1')
                p2 = sum(1 for i in issues if i['priority'] == 'P2')
                score = result.get('score', 0)
                emoji = '✅' if score >= 8 else '⚠️' if score >= 6 else '🔴'
                print(f"    {emoji} Score: {score}/10  P0:{p0} P1:{p1} P2:{p2}")
            else:
                print(f"    ❌ Error")
        print(f"\n{'='*65}")
        return

    paper_id = args.paper_id

    if args.progress:
        show_progress(paper_id)
        return

    if args.rebuttal:
        generate_rebuttal(paper_id)
        return

    if args.agent:
        from agent_review import generate_prompt
        prompt, path = generate_prompt(paper_id)
        if prompt:
            print(f"✅ Agent review prompt: {path}")
            print(f"   Send to agent, save response, then parse.")
        else:
            print(f"❌ {path}")
        return

    if args.fix:
        # Run audit first to get issues
        if args.full:
            result = run_full_audit(paper_id)
        else:
            result = run_quick_audit(paper_id)
        if result and 'error' not in result:
            issues = normalize_issues(result.get('issues', []))
            auto_fix(paper_id, issues)
        return

    # Standard audit
    if args.full:
        result = run_full_audit(paper_id)
    else:
        result = run_quick_audit(paper_id)

    if not result:
        print(f"❌ Paper '{paper_id}' not found")
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_unified_report(result, paper_id)

if __name__ == '__main__':
    main()
