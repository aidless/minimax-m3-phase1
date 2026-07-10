#!/usr/bin/env python3
"""Loop Engineering v5.2 — Batch AI Review Engine
Runs all tiers of rules across all registered papers.
Usage: python review_engine.py --all [--tier 1,2,3] [--output reviews/]
"""
import yaml, sys, argparse, re, json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

# ============================================================
# Tier 1: Regex-level checks (fast, deterministic)
# ============================================================
TIER1_CHECKS = {
    'C1_first_claim': {
        'desc': 'First/Novel claims that may be undermined by prior work',
        'check': lambda t: [(m.group(0)[:80], 'Verify with literature search') 
                           for m in re.finditer(r'(?:first|novel|we are the first to)[^.]*\.', t, re.I)],
        'severity': 'critical'
    },
    'C4_monotonic': {
        'desc': 'Monotonic/linear claims needing per-condition verification',
        'check': lambda t: [(m.group(0)[:80], 'Check per-condition data') 
                           for m in re.finditer(r'monotonically[^.]*\.', t, re.I)],
        'severity': 'critical'
    },
    'C9_null_effect': {
        'desc': 'Null effect phrasing ("no detectable") when "insufficient evidence" is correct',
        'check': lambda t: [(m.group(0)[:80], 'Use "insufficient evidence to reject null"') 
                           for m in re.finditer(r'no statistically significant[^.]*\.|no detectable[^.]*\.', t, re.I)
                           if 'p' in m.group(0).lower() and '=' in m.group(0)],
        'severity': 'critical'
    },
    'C7_count_mismatch': {
        'desc': 'Text says N items but may list N+1',
        'check': lambda t: [('Count claim: ' + m.group(0)[:60], 'Verify enumerated items match') 
                           for m in re.finditer(r'(?:^|\s)([Tt]wo|[Tt]hree|[Ff]our|[Ff]ive|[Ss]ix)\s+\w+(?:\s+\w+)?\s*(?:recommendations|guidelines|findings|items|steps)', t)],
        'severity': 'minor'
    },
    'W4_chinglish': {
        'desc': 'Chinglish patterns',
        'check': lambda t: [
            (f'"{pat}" → {fix}', fix) 
            for pat, fix in [
                (r'different with', '"different with" → "different from"'),
                (r'\bcompare with\b(?!ed)', '"compare with" → "compared with/to"'),
                (r'\bprove\b(?!n|d|r|s)', '"prove" → "demonstrate/show"'),
                (r'in the following', '"in the following" → "below"'),
            ] if re.search(pat, t, re.I)
        ],
        'severity': 'minor'
    },
    'ABSTRACT_density': {
        'desc': 'Abstract has too many numbers in a single sentence',
        'check': lambda t: _check_abstract(t),
        'severity': 'important'
    },
    'GHOST_citation': {
        'desc': 'Bibliography entries never cited in text',
        'check': lambda t: _check_ghosts(t),
        'severity': 'critical'
    },
}

def _check_abstract(text):
    m = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', text, re.DOTALL)
    if not m: return []
    abstract = m.group(1)
    sentences = [s.strip() for s in re.split(r'[.!?]\s+', abstract) if s.strip()]
    issues = []
    for s in sentences:
        nums = len(re.findall(r'\d+\.?\d*', s))
        if nums > 5:
            issues.append((f'{nums} numbers in sentence: "{s[:60]}..."', 'Split into multiple sentences'))
    return issues

def _check_ghosts(text):
    bib_keys = set(re.findall(r'\\bibitem\[.*?\]\{([^}]+)\}', text))
    cited = set()
    for m in re.finditer(r'\\cite\{([^}]+)\}', text):
        for k in m.group(1).split(','):
            cited.add(k.strip())
    ghost = bib_keys - cited
    return [(k, 'Add citation in text or remove from bibliography') for k in ghost]

# ============================================================
# Tier 2: Statistical checks (heuristic, needs human verification)
# ============================================================
TIER2_CHECKS = {
    'S3_effect_size': {
        'desc': 'Effect sizes reported alongside p-values',
        'check': lambda t: [] if re.search(r"Cohen'?s\s*d|Cliff'?s\s*\\?delta|Hedges'?\s*g|\beffect size\b", t, re.I) 
                   else [('No effect size found', 'Report Cohen\'s d, Cliff\'s delta, or Hedges\' g')],
        'severity': 'important'
    },
    'S5_ci': {
        'desc': 'Confidence intervals on key numbers',
        'check': lambda t: [] if re.search(r'\\pm\s*\d|confidence\s*interval|\[\d+.*?,\s*\d+.*?\]', t, re.I)
                   else [('No CI/SD/SEM found', 'Add CIs to key numerical claims')],
        'severity': 'important'
    },
    'R5_anonymization': {
        'desc': 'Author identity fully anonymized',
        'check': lambda t: _check_anonymization(t),
        'severity': 'critical'
    },
    'ST1_structure': {
        'desc': 'Two disconnected studies in one paper',
        'check': lambda t: _check_structure(t),
        'severity': 'important'
    },
}

def _check_anonymization(text):
    issues = []
    # Check for common identity leaks
    patterns = [r'\\author\{[^}]*[A-Z][a-z]+', r'\\texttt\{', r'\\href\{']
    for p in patterns:
        if re.search(p, text):
            issues.append(('Identity leak detected', 'Remove author info, email, URLs'))
            break
    # Check for acknowledgments
    if re.search(r'\\section\*?\{Acknowledgment', text):
        issues.append(('Acknowledgments section present', 'Remove for anonymous submission'))
    return issues

def _check_structure(text):
    sections = re.findall(r'\\section\{([^}]+)\}', text)
    if len(sections) > 10:
        return [('Many sections', 'Consider consolidating or moving to appendix')]
    return []

# ============================================================
# Tier 3: Writing polish
# ============================================================
TIER3_CHECKS = {
    'T1_terminology': {
        'desc': 'Consistent terminology throughout',
        'check': lambda t: _check_terms(t),
        'severity': 'minor'
    },
    'F2_caption': {
        'desc': 'Figure captions self-contained',
        'check': lambda t: [(f'Caption may lack detail: "{c[:50]}..."', 'Add sample size, model, error bar info') 
                           for c in re.findall(r'\\caption\{([^}]{10,200})\}', t)
                           if not re.search(r'\\pm|seed|N\s*=|error|SEM', c)],
        'severity': 'minor'
    },
}

def _check_terms(text):
    issues = []
    variants = [
        (r'post-hoc\s+calibration|post-hoc\s+recalibration', 'post-hoc calibration vs post-hoc recalibration'),
        (r'degradation|damage|cost|penalty', 'calibration degradation/damage/cost/penalty variants'),
    ]
    for pattern, desc in variants:
        found = set(re.findall(pattern, text, re.I))
        if len(found) > 2:
            issues.append((f'{len(found)} variants of "{desc.split(" vs ")[0]}"', f'Unify to one term'))
    return issues

def _run_quality_checks(text):
    """Run v5.2 quality gates from quality_checks.py."""
    try:
        from quality_checks import run_all_checks
        results = run_all_checks(text)
        issues = []
        for check_name, items in results.items():
            for code, severity, msg in items:
                if severity != 'pass':
                    issues.append({
                        'rule': code, 'tier': 2, 'severity': severity,
                        'finding': msg[:100], 'fix': 'See quality_checks.py details'
                    })
        return issues
    except ImportError:
        return []
    except Exception:
        return []


def scan_paper(paper_id, paper, tex_path):
    """Run all tier checks on a single paper."""
    if not tex_path.exists():
        return None

    text = tex_path.read_text(encoding='utf-8', errors='ignore')
    all_issues = []

    for name, check in TIER1_CHECKS.items():
        for finding, fix in check['check'](text):
            all_issues.append({
                'rule': name, 'tier': 1, 'severity': check['severity'],
                'finding': finding[:100], 'fix': fix
            })

    for name, check in TIER2_CHECKS.items():
        for finding, fix in check['check'](text):
            all_issues.append({
                'rule': name, 'tier': 2, 'severity': check['severity'],
                'finding': finding[:100], 'fix': fix
            })

    for name, check in TIER3_CHECKS.items():
        for finding, fix in check['check'](text):
            all_issues.append({
                'rule': name, 'tier': 3, 'severity': check['severity'],
                'finding': finding[:100], 'fix': fix
            })

    # v5.2: Paperreview.ai gap analysis checks
    all_issues.extend(_run_quality_checks(text))

    return {
        'paper_id': paper_id,
        'title': paper.get('short_title', paper_id),
        'phase': paper.get('phase', 0),
        'issues': all_issues,
        'critical': sum(1 for i in all_issues if i['severity'] == 'critical'),
        'important': sum(1 for i in all_issues if i['severity'] == 'important'),
        'minor': sum(1 for i in all_issues if i['severity'] == 'minor'),
    }

def main():
    parser = argparse.ArgumentParser(description='Loop Engineering v5.0 — Batch AI Review Engine')
    parser.add_argument('paper_id', nargs='?', help='Paper ID or --all for all papers')
    parser.add_argument('--all', '-a', action='store_true', help='Scan all registered papers')
    parser.add_argument('--tier', '-t', type=str, default='1,2,3', help='Tiers to run (default: 1,2,3)')
    parser.add_argument('--output', '-o', help='Save results as JSON')
    parser.add_argument('--summary', '-s', action='store_true', help='Summary only (no per-issue detail)')
    args = parser.parse_args()
    
    registry = yaml.safe_load((LOOP_DIR / 'registry.yaml').read_text(encoding='utf-8'))
    
    paper_ids = []
    if args.all:
        paper_ids = [p['id'] for p in registry['papers'].values()]
    elif args.paper_id:
        paper_ids = [args.paper_id]
    else:
        parser.print_help()
        sys.exit(1)
    
    tiers = [int(t) for t in args.tier.split(',')]
    
    results = []
    for paper_id in paper_ids:
        paper = None
        for p in registry['papers'].values():
            if p['id'] == paper_id:
                paper = p
                break
        if not paper:
            continue
        
        tex_path = AETTL_DIR / paper['path'] / 'main.tex'
        result = scan_paper(paper_id, paper, tex_path)
        if result:
            results.append(result)
    
    # Print results
    print(f"\n🔍 Review Engine — {len(results)} papers scanned (Tiers: {tiers})")
    print(f"   {'='*60}")
    
    total_critical = total_important = total_minor = 0
    
    for r in results:
        tier_issues = [i for i in r['issues'] if i['tier'] in tiers]
        c = sum(1 for i in tier_issues if i['severity'] == 'critical')
        i_count = sum(1 for i in tier_issues if i['severity'] == 'important')
        m = sum(1 for i in tier_issues if i['severity'] == 'minor')
        total_critical += c; total_important += i_count; total_minor += m
        
        status = '🔴' if c > 0 else '🟡' if i_count > 0 else '✅'
        print(f"\n   {status} {r['paper_id']}: {r['title'][:45]}")
        print(f"      Phase {r['phase']} | {c}C / {i_count}I / {m}M")
        
        if not args.summary:
            for issue in tier_issues[:5]:
                icon = {'critical':'🔴','important':'🟡','minor':'🟢'}.get(issue['severity'],'•')
                print(f"      {icon} [{issue['rule']}] {issue['finding'][:70]}")
            if len(tier_issues) > 5:
                print(f"      ... and {len(tier_issues)-5} more issues")
    
    print(f"\n   {'='*60}")
    print(f"   Portfolio Total: {total_critical}C / {total_important}I / {total_minor}M")
    
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(exist_ok=True)
        with open(out_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"   📄 Saved to {out_path}")

if __name__ == '__main__':
    main()
