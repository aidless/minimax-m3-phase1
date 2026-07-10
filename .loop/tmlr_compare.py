#!/usr/bin/env python3
"""Loop Engineering v5.3 — TMLR Paper Comparison Tool
Compare a paper against 833 real TMLR papers (OpenReview data).

Usage:
  python tmlr_compare.py PAPER_ID              # Compare against TMLR library
  python tmlr_compare.py PAPER_ID --topic      # Compare within topic
  python tmlr_compare.py PAPER_ID --detail     # Detailed comparison
  python tmlr_compare.py --library             # Show library stats
"""
import yaml, sys, argparse, re
from pathlib import Path
from collections import Counter

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

def load_library():
    path = LOOP_DIR / 'tmlr_paper_library.yaml'
    if path.exists():
        return yaml.safe_load(path.read_text(encoding='utf-8'))
    return None

def extract_paper_features(text):
    """Extract measurable features from paper text."""
    features = {}

    # CI coverage
    ci_patterns = [
        r'\\pm\s*\d', r'\{\\pm\}\s*\d', r'\[\d+.*?,\s*\d+.*?\]',
        r'95\s*%\s*CI', r'bootstrap.*?CI', r'confidence\s*interval',
        r'CI\s*=\s*\[', r'lower\s*CI', r'upper\s*CI',
    ]
    ci_count = sum(len(re.findall(p, text, re.I)) for p in ci_patterns)

    stat_patterns = [
        r'p\s*[<>=]\s*[\d.]+', r'statistically\s+significant',
        r't\s*\(\s*\d+\s*\)\s*=', r'F\s*\(\s*\d+\s*,\s*\d+\s*\)\s*=',
    ]
    stat_count = sum(len(re.findall(p, text, re.I)) for p in stat_patterns)
    features['ci_coverage'] = ci_count / max(stat_count, 1)

    # Effect sizes
    es_patterns = [
        r"Cohen'?s?\s*d", r"Cliff'?s?\s*(?:\\delta|δ|delta)",
        r"Hedges'?\s*g", r"(?:rank[- ])?biserial",
        r"η²|\\eta\^2", r"ω²|\\omega\^2", r"effect\s*size",
        r"Cram[eé]r'?s?\s*V", r"(?:Pearson|Spearman)\s*r",
    ]
    features['has_effect_size'] = any(re.search(p, text, re.I) for p in es_patterns)

    # Theorems
    features['has_theorem'] = bool(re.search(r'\\begin\{theorem\}', text))

    # Seeds specified
    seed_match = re.findall(r'(?:N\s*[=:]\s*|n\s*[=:]\s*)(\d+)', text)
    features['min_n'] = min((int(n) for n in seed_match if 1 < int(n) < 10000), default=0)

    # Self-citation rate
    cited = set()
    for m in re.finditer(r'\\cite[tp]?\{([^}]+)\}', text):
        for k in m.group(1).split(','):
            cited.add(k.strip())
    self_cites = {k for k in cited if 'liu202' in k.lower()}
    features['self_cite_rate'] = len(self_cites) / max(len(cited), 1)

    # References count
    bib_keys = set(re.findall(r'\\bibitem\[.*?\]\{([^}]+)\}', text))
    features['ref_count'] = len(bib_keys) if bib_keys else len(cited)

    # Tables and figures
    features['table_count'] = len(re.findall(r'\\begin\{(?:tabular|table)', text))
    features['figure_count'] = len(re.findall(r'\\includegraphics', text))

    # Pages (approximate from line count)
    features['line_count'] = len(text.split('\n'))

    return features

def compare_with_library(features, library, topic=None):
    """Compare paper features against library."""
    papers = library['papers']

    # Filter by topic if specified
    if topic:
        topic_papers = [p for p in papers if p.get('topic') == topic]
        if not topic_papers:
            topic_papers = papers  # fallback
    else:
        topic_papers = papers

    results = {}

    # Self-citation rate comparison
    self_rate = features.get('self_cite_rate', 0)
    results['self_citation'] = {
        'value': self_rate,
        'label': f'{self_rate:.0%}',
        'benchmark': 'TMLR typical: <30%',
        'status': 'pass' if self_rate < 0.3 else 'warn' if self_rate < 0.5 else 'fail',
    }

    # Reference count
    ref_count = features.get('ref_count', 0)
    results['references'] = {
        'value': ref_count,
        'label': str(ref_count),
        'benchmark': 'TMLR median: ~30',
        'status': 'pass' if ref_count >= 20 else 'warn' if ref_count >= 10 else 'fail',
    }

    # Theorem
    has_thm = features.get('has_theorem', False)
    thm_pct = sum(1 for p in papers if 'theor' in p.get('topic', '')) / len(papers) * 100
    results['theorem'] = {
        'value': has_thm,
        'label': 'Yes' if has_thm else 'No',
        'benchmark': f'TMLR: ~{thm_pct:.0f}% have theorems',
        'status': 'pass' if has_thm else 'info',
    }

    # CI coverage
    ci_cov = features.get('ci_coverage', 0)
    results['ci_coverage'] = {
        'value': ci_cov,
        'label': f'{ci_cov:.0%}',
        'benchmark': 'TMLR: ~26% report CI',
        'status': 'pass' if ci_cov > 0.3 else 'warn' if ci_cov > 0.1 else 'fail',
    }

    # Effect size
    has_es = features.get('has_effect_size', False)
    results['effect_size'] = {
        'value': has_es,
        'label': 'Yes' if has_es else 'No',
        'benchmark': 'TMLR: ~6% report effect sizes',
        'status': 'pass' if has_es else 'warn',
    }

    # Sample size
    min_n = features.get('min_n', 0)
    results['sample_size'] = {
        'value': min_n,
        'label': f'N={min_n}' if min_n > 0 else 'Not specified',
        'benchmark': 'TMLR: ~34% specify seeds',
        'status': 'pass' if min_n >= 10 else 'warn' if min_n >= 3 else 'fail',
    }

    # Topic match
    if topic:
        topic_count = len(topic_papers)
        results['topic_match'] = {
            'value': topic_count,
            'label': f'{topic_count} papers in "{topic}"',
            'benchmark': f'Out of {len(papers)} total TMLR papers',
            'status': 'info',
        }

    return results

def print_comparison(paper_id, results, topic=None):
    """Pretty-print comparison."""
    print(f"\n{'='*65}")
    print(f"📊 TMLR Comparison — {paper_id}")
    if topic:
        print(f"   Topic: {topic}")
    print(f"{'='*65}")

    for dim, r in results.items():
        status = r['status']
        icon = {'pass': '🟢', 'warn': '🟡', 'fail': '🔴', 'info': 'ℹ️'}.get(status, '•')
        print(f"  {icon} {dim:18s}  {r['label']:20s}  {r['benchmark']}")

    # Overall assessment
    passes = sum(1 for r in results.values() if r['status'] == 'pass')
    warns = sum(1 for r in results.values() if r['status'] == 'warn')
    fails = sum(1 for r in results.values() if r['status'] == 'fail')

    print(f"\n{'='*65}")
    if fails == 0 and passes >= 3:
        print(f"  ✅ Strong — {passes} pass, {warns} warn, {fails} fail")
    elif fails <= 1:
        print(f"  ⚠️  Acceptable — {passes} pass, {warns} warn, {fails} fail")
    else:
        print(f"  🔴 Needs work — {passes} pass, {warns} warn, {fails} fail")
    print(f"{'='*65}")

def print_library_stats(library):
    """Print library statistics."""
    papers = library['papers']
    print(f"\n{'='*65}")
    print(f"📚 TMLR Paper Library")
    print(f"{'='*65}")
    print(f"  Total papers: {len(papers)}")
    print(f"  Source: {library.get('metadata', {}).get('source', 'unknown')}")

    topics = Counter(p.get('topic', 'unknown') for p in papers)
    print(f"\n  Topics ({len(topics)}):")
    for topic, count in topics.most_common():
        bar = '#' * (count // 5)
        print(f"    {topic:15s} {count:3d} {bar}")

    years = Counter(p.get('year', '') for p in papers)
    print(f"\n  Years:")
    for year in sorted(years.keys()):
        if year:
            print(f"    {year}: {years[year]}")

    print(f"\n{'='*65}")

def main():
    parser = argparse.ArgumentParser(description='TMLR Comparison Tool')
    parser.add_argument('paper_id', nargs='?', help='Paper ID or path to .tex')
    parser.add_argument('--topic', '-t', help='Compare within specific topic')
    parser.add_argument('--detail', '-d', action='store_true', help='Detailed comparison')
    parser.add_argument('--library', '-l', action='store_true', help='Show library stats')
    parser.add_argument('--json', '-j', action='store_true', help='JSON output')
    args = parser.parse_args()

    library = load_library()
    if not library:
        print("❌ TMLR library not found")
        sys.exit(1)

    if args.library:
        print_library_stats(library)
        return

    if not args.paper_id:
        parser.print_help()
        sys.exit(1)

    # Find paper
    paper_id = args.paper_id
    text = None

    # Try registry
    registry_path = LOOP_DIR / 'registry.yaml'
    if registry_path.exists():
        reg = yaml.safe_load(registry_path.read_text(encoding='utf-8'))
        for k, p in reg.get('papers', {}).items():
            if p['id'] == paper_id:
                paper_dir = AETTL_DIR / p['path']
                for name in ['main_merged.tex', 'main_tmlr.tex', 'main.tex']:
                    candidate = paper_dir / name
                    if candidate.exists():
                        text = candidate.read_text(encoding='utf-8', errors='ignore')
                        break
                break

    # Try direct path
    if text is None:
        candidate = Path(paper_id)
        if candidate.exists():
            text = candidate.read_text(encoding='utf-8', errors='ignore')

    if text is None:
        print(f"❌ Paper '{paper_id}' not found")
        sys.exit(1)

    # Extract features and compare
    features = extract_paper_features(text)
    results = compare_with_library(features, library, args.topic)

    if args.json:
        import json
        print(json.dumps({'paper_id': paper_id, 'features': features, 'results': results},
                        indent=2, default=str))
    else:
        print_comparison(paper_id, results, args.topic)

if __name__ == '__main__':
    main()
