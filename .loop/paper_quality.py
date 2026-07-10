#!/usr/bin/env python3
"""Loop Engineering v5.1 — Paper Quality Evaluator
Four-dimensional quality assessment based on supervisor review criteria.
Usage: python paper_quality.py PAPER_ID
Dimensions: Novelty, Method, Story, Presentation
"""
import yaml, sys, argparse, re
from pathlib import Path

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

# ============================================================
# Quality dimensions from Supervisor-Skills framework
# ============================================================

QUALITY_DIMENSIONS = {
    'novelty': {
        'name': 'Novel Problem / Contribution',
        'weight': 0.30,
        'description': 'Does the paper define a useful new problem or provide a novel solution?',
        'checks': [
            ('PROBLEM_STATED', 'Is the problem clearly stated in the first paragraph?',
             lambda t: bool(re.search(r'(?:problem|challenge|gap|limitation).{0,50}(?:is|remains|persists)', t[:5000], re.I))),
            ('CLAIM_SPECIFIC', 'Are contribution claims specific (not vague "we study X")?',
             lambda t: len(re.findall(r'\\item\s*\\textbf\{Finding|\\item\s*\\textbf\{Contribution', t)) >= 2),
            ('DELTA_EXPLICIT', 'Is the delta over prior work explicit?',
             lambda t: bool(re.search(r'(?:unlike|differs? from|in contrast|whereas|extends|improves upon|first to)', t[:8000], re.I))),
            ('FIRST_CLAIM_BALANCED', 'Are "first"/"novel" claims qualified with evidence scope?',
             lambda t: not (len(re.findall(r'(?:first|novel|we are the first to)', t[:3000], re.I)) > 2 and 
                          'limitation' not in t[:3000].lower())),
        ]
    },
    'method': {
        'name': 'Method Effectiveness',
        'weight': 0.25,
        'description': 'Is the method effective and well-validated?',
        'checks': [
            ('EXPERIMENT_SCALE', 'Are experiments at adequate scale?',
             lambda t: bool(re.search(r'(?:N\s*=\s*\d+.*?(?:seed|rep|independent|condition))|(?:total.*?(?:API|calls?|runs?))', t, re.I))),
            ('STATS_RIGOR', 'Are statistical tests, effect sizes, and CIs reported?',
             lambda t: bool(re.search(r"Cohen'?s\s*d|Cliff'?s\s*\\?delta|bootstrap.*?CI|\\pm\s*\d", t, re.I))),
            ('ABLATION_PRESENT', 'Are there ablations or controlled experiments?',
             lambda t: bool(re.search(r'(?:ablation|controlled|factorial|deconfound|isolation baseline)', t[:10000], re.I))),
            ('STRONG_BASELINES', 'Are baselines strong and relevant?',
             lambda t: len(re.findall(r'\\cite\{', t[:5000])) >= 5),
        ]
    },
    'story': {
        'name': 'Nice Story',
        'weight': 0.25,
        'description': 'Does the paper tell a compelling, logical story?',
        'checks': [
            ('INTRO_FUNNEL', 'Introduction: broad context → specific gap → our approach?',
             lambda t: bool(re.search(r'(?:pervasive|widely|increasingly|recent|growing).{0,200}(?:However|But|Yet|despite)', t[:3000], re.I))),
            ('CONTRIBUTION_LIST', 'Are contributions numbered and each mapped to a section?',
             lambda t: bool(re.search(r'\\item.*\\textbf\{.*\}.*§|\\item.*\\textbf\{.*\}.*Section', t[:5000]))),
            ('TAKEAWAY_CLEAR', 'Does each section end with a clear takeaway?',
             lambda t: len(re.findall(r'(?:implication|takeaway|suggest|practical|guideline|recommend)', t, re.I)) >= 3),
            ('CONCLUSION_MATCH', 'Do abstract findings match conclusion findings?',
             lambda t: _check_conclusion_match(t)),
        ]
    },
    'presentation': {
        'name': 'Nice Presentation',
        'weight': 0.20,
        'description': 'Is the paper well-formatted and visually clear?',
        'checks': [
            ('FIGURES_EXIST', 'Are there figures referenced in the text?',
             lambda t: len(re.findall(r'\\includegraphics', t)) >= 2),
            ('CAPTIONS_SELFCONTAINED', 'Are figure captions self-contained?',
             lambda t: len(re.findall(r'\\caption\{[^}]{50,}', t)) >= len(re.findall(r'\\includegraphics', t)) // 2),
            ('WRITING_CLEAN', 'No Chinglish patterns?',
             lambda t: not any(re.search(p, t, re.I) for p in [r'different with', r'\bcompare with\b(?!ed)', r'\bprove\b(?!n|d|r|s)', r'in the following'])),
            ('FORMAT_CONSISTENT', 'Consistent use of \\textbf, \\emph, citation style?',
             lambda t: len(re.findall(r'\\textbf\{', t)) > 0),  # Basic check
        ]
    }
}

def _check_conclusion_match(text):
    """Check if abstract and conclusion findings match."""
    abs_m = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', text, re.DOTALL)
    conc_m = re.search(r'\\section\{Conclusion\}(.*?)(?=\\section|\n\\end)', text, re.DOTALL)
    if not abs_m or not conc_m:
        return False
    abstract = abs_m.group(1)
    conclusion = conc_m.group(1)
    # Extract key numbers from both
    abs_nums = set(re.findall(r'\d+\.?\d*', abstract))
    conc_nums = set(re.findall(r'\d+\.?\d*', conclusion))
    overlap = len(abs_nums & conc_nums)
    return overlap >= 2  # At least 2 key numbers shared

def load_yaml(p):
    with open(p, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def evaluate_paper(paper_id, paper):
    """Run full quality evaluation."""
    paper_dir = AETTL_DIR / paper['path']
    tex_files = list(paper_dir.glob('main_tmlr.tex')) or list(paper_dir.glob('main.tex')) or list(paper_dir.glob('main_merged.tex'))
    
    if not tex_files:
        return {'error': 'No tex file found'}
    
    text = tex_files[0].read_text(encoding='utf-8', errors='ignore')
    
    results = {}
    total_score = 0
    all_issues = []
    
    for dim_key, dim in QUALITY_DIMENSIONS.items():
        dim_passed = 0
        dim_issues = []
        
        for check_id, check_desc, check_fn in dim['checks']:
            passed = check_fn(text)
            if passed:
                dim_passed += 1
            else:
                dim_issues.append((check_id, check_desc))
        
        dim_score = dim_passed / len(dim['checks']) if dim['checks'] else 0
        weighted = dim_score * dim['weight']
        total_score += weighted
        
        results[dim_key] = {
            'name': dim['name'],
            'weight': dim['weight'],
            'score': dim_score,
            'weighted': weighted,
            'passed': dim_passed,
            'total': len(dim['checks']),
            'issues': dim_issues,
            'grade': '⭐' if dim_score >= 0.75 else '✅' if dim_score >= 0.5 else '⚠️' if dim_score >= 0.25 else '❌'
        }
    
    return {
        'paper_id': paper_id,
        'title': paper.get('short_title', paper_id),
        'dimensions': results,
        'total_score': total_score * 10,  # Scale to 10
        'grade': '⭐ Outstanding' if total_score >= 0.8 else '✅ Strong' if total_score >= 0.6 else '⚠️ Needs Work' if total_score >= 0.4 else '❌ Weak',
    }

def print_report(eval_result):
    if 'error' in eval_result:
        print(f"❌ {eval_result['error']}")
        return
    
    print(f"\n{'='*65}")
    print(f"📊 Paper Quality — {eval_result['paper_id']}: {eval_result['title']}")
    print(f"{'='*65}")
    
    dims = eval_result['dimensions']
    
    for dim_key in ['novelty', 'method', 'story', 'presentation']:
        d = dims[dim_key]
        bar = '█' * int(d['score'] * 20) + '░' * (20 - int(d['score'] * 20))
        print(f"\n   {d['grade']} {d['name']} [{bar}] {d['passed']}/{d['total']}")
        print(f"      Score: {d['score']:.0%} (weight: {d['weight']:.0%}, weighted: {d['weighted']:.2f})")
        if d['issues']:
            for check_id, desc in d['issues']:
                print(f"      ❌ {check_id}: {desc}")
    
    print(f"\n{'='*65}")
    print(f"   Overall: {eval_result['total_score']:.1f}/10 — {eval_result['grade']}")
    
    # Recommendations
    print(f"\n   💡 Recommendations:")
    worst_dim = min(dims.items(), key=lambda x: x[1]['score'])
    print(f"      Priority: Improve '{worst_dim[1]['name']}' ({worst_dim[1]['score']:.0%})")
    print(f"      {worst_dim[1]['issues'][0][1] if worst_dim[1]['issues'] else 'All checks passed'}")
    
    all_issues = sum(len(d['issues']) for d in dims.values())
    if all_issues == 0:
        print(f"      ✅ All quality checks passed!")
    
    print(f"{'='*65}")

def main():
    parser = argparse.ArgumentParser(description='Loop Engineering v5.1 — Paper Quality Evaluator')
    parser.add_argument('paper_id', help='Paper ID')
    parser.add_argument('--json', '-j', action='store_true', help='JSON output')
    args = parser.parse_args()
    
    registry = load_yaml(LOOP_DIR / 'registry.yaml')
    paper = None
    for p in registry['papers'].values():
        if p['id'] == args.paper_id:
            paper = p
            break
    
    if not paper:
        print(f"❌ Paper '{args.paper_id}' not found")
        sys.exit(1)
    
    result = evaluate_paper(args.paper_id, paper)
    
    if args.json:
        import json
        print(json.dumps(result, indent=2, default=str))
    else:
        print_report(result)

if __name__ == '__main__':
    main()
