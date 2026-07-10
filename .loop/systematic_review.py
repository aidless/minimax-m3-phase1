#!/usr/bin/env python3
"""Loop Engineering v5.3 — Systematic Review + Auto-Fix
One-pass comprehensive review that outputs a complete modification checklist.

Usage:
  python systematic_review.py PAPER_ID              # Review + auto-fix
  python systematic_review.py PAPER_ID --check-only # Review without fixing
  python systematic_review.py PAPER_ID --checklist  # Output modification checklist
  python systematic_review.py PAPER_ID --json       # JSON output
"""
import re, sys, json, argparse, shutil, yaml
from pathlib import Path
from datetime import datetime
from collections import Counter

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

# ============================================================
# Checklist: 7 dimensions, one pass
# ============================================================

def review_format(text, lines):
    """Dimension 1: Format & compliance."""
    issues = []

    # Title
    title_m = re.search(r'\\title\{(.+?)\}', text, re.DOTALL)
    if title_m:
        title = title_m.group(1)
        if len(re.sub(r'\\[a-z]+\{[^}]*\}', '', title)) > 150:
            issues.append(('FORMAT_TITLE_LONG', 'minor', f'Title > 150 chars'))

    # Author
    if not re.search(r'\\author\{Anonymous', text):
        issues.append(('FORMAT_AUTHOR', 'critical', 'Author not anonymous'))

    # Broader Impact
    if 'Broader Impact' not in text:
        issues.append(('FORMAT_NO_IMPACT', 'critical', 'Missing Broader Impact Statement'))

    # Reproducibility
    if 'Reproducibility' not in text:
        issues.append(('FORMAT_NO_REPRO', 'critical', 'Missing Reproducibility Statement'))

    # Email exposure
    for m in re.finditer(r'\\texttt\{([^}]+)\}', text):
        if '@' in m.group(1) or 'mail' in m.group(1).lower():
            issues.append(('FORMAT_EMAIL', 'critical', f'Email exposed: {m.group(1)[:40]}'))

    # hyperref color (TMLR requires black links)
    if 'colorlinks=true' in text:
        issues.append(('FORMAT_LINKS', 'minor', 'hyperref colorlinks=true — TMLR may require black links'))

    return issues


def review_formulas(text, lines):
    """Dimension 2: Every formula, theorem, proof."""
    issues = []

    # Unmatched $
    for i, line in enumerate(lines):
        dc = line.count('$') - line.count('\\$')
        if dc % 2 != 0:
            issues.append(('FORMULA_DOLLAR', 'critical', f'Line {i+1}: Unmatched $'))

    # Theorem-proof pairs
    thms = list(re.finditer(r'\\begin\{theorem\}(?:\[([^\]]*)\])?', text))
    prfs = list(re.finditer(r'\\begin\{proof\}', text))
    for t in thms:
        label = t.group(1) or 'unnamed'
        has_prf = any(p.start() > t.end() for p in prfs)
        if not has_prf:
            issues.append(('FORMULA_NO_PROOF', 'important', f'Theorem "{label[:30]}" has no proof'))

    # Symbol consistency: check if C and c_min are both used for same concept
    has_C = bool(re.search(r'\\geq C > 0', text))
    has_cmin = bool(re.search(r'\\geq c_\{\\min\} > 0', text))
    if has_C and has_cmin:
        issues.append(('FORMULA_SYMBOL', 'important', 'Both C and c_min used for same constant — standardize'))

    # Proof sketch without citation
    for m in re.finditer(r'\\begin\{proof\}(?:\[Proof sketch\])?', text, re.IGNORECASE):
        context = text[m.end():m.end()+500]
        if 'Proof sketch' in m.group(0) and not re.search(r'\\cite', context):
            issues.append(('FORMULA_SKETCH', 'important', 'Proof sketch without citation for key steps'))

    # Undefined constants
    for m in re.finditer(r'where\s+\$c_(\d+)\s*>\s*0\$', text):
        c = m.group(1)
        if not re.search(rf'c_{c}\s*=\s*[\d.]', text):
            issues.append(('FORMULA_UNDEF_CONST', 'minor', f'Constant c_{c} declared but never quantified'))

    return issues


def review_references(text, lines):
    """Dimension 3: Every citation and reference."""
    issues = []

    # Extract all cite keys
    cited = set()
    for m in re.finditer(r'\\cite[tp]?\{([^}]+)\}', text):
        for k in m.group(1).split(','):
            k = k.strip()
            if not k:
                issues.append(('REF_EMPTY_KEY', 'critical', 'Empty citation key'))
            elif ' ' in k:
                issues.append(('REF_SPACE_KEY', 'critical', f'Space in citation key: "{k}"'))
            else:
                cited.add(k)

    # Self-citation rate
    self_cites = {k for k in cited if 'liu202' in k.lower()}
    if cited:
        rate = len(self_cites) / len(cited)
        if rate > 0.5:
            issues.append(('REF_SELF_HIGH', 'important', f'Self-citation {rate:.0%} ({len(self_cites)}/{len(cited)}) — too high'))
        elif rate > 0.3:
            issues.append(('REF_SELF_MODERATE', 'minor', f'Self-citation {rate:.0%} ({len(self_cites)}/{len(cited)}) — consider adding external refs'))

    # Manuscript references
    ms = re.findall(r'Manuscript', text, re.IGNORECASE)
    if ms:
        issues.append(('REF_MANUSCRIPT', 'minor', f'{len(ms)} reference(s) marked "Manuscript" — provide arXiv links'))

    # Unused labels
    labels = set(re.findall(r'\\label\{([^}]+)\}', text))
    refs = set(re.findall(r'\\ref\{([^}]+)\}', text))
    eqrefs = set(re.findall(r'\\eqref\{([^}]+)\}', text))
    for label in labels:
        if label not in refs and label not in eqrefs:
            issues.append(('REF_UNUSED_LABEL', 'minor', f'Unused label: {label}'))

    # Duplicate captions
    caps = re.findall(r'\\caption\{([^}]+)\}', text)
    for cap, cnt in Counter(caps).items():
        if cnt > 1:
            issues.append(('REF_DUP_CAPTION', 'minor', f'Duplicate caption ({cnt}x): "{cap[:40]}..."'))

    # Bibitem format
    bibs = list(re.finditer(r'\\bibitem\[([^\]]*)\]\{([^}]+)\}', text))
    bib_starts = [m.start() for m in bibs]
    for i, (b, start) in enumerate(zip(bibs, bib_starts)):
        key = b.group(2)
        end = bib_starts[i+1] if i+1 < len(bib_starts) else len(text)
        body = text[start:end]
        titles = re.findall(r'\\textit\{([^}]+)\}', body)
        if len(titles) > 1:
            issues.append(('REF_MERGED_BIB', 'critical', f'Bibitem "{key}" merged ({len(titles)} titles)'))

    return issues


def review_tables_figures(text, lines):
    """Dimension 4: Every table and figure."""
    issues = []

    # Check tables for empty cells
    tables = list(re.finditer(
        r'\\begin\{(?:tabular|table)\*?\}(.*?)\\end\{(?:tabular|table)\*?\}',
        text, re.DOTALL))
    for i, table in enumerate(tables):
        table_text = table.group(1)
        if '&  &' in table_text or '& & ' in table_text:
            issues.append(('TABLE_EMPTY_CELL', 'minor', f'Table {i+1}: Empty cell'))

    # Check figures for missing captions
    figs = list(re.finditer(r'\\begin\{figure\}', text))
    for i, fig in enumerate(figs):
        fig_end = text.find('\\end{figure}', fig.start())
        fig_body = text[fig.start():fig_end] if fig_end > 0 else ''
        if '\\caption' not in fig_body:
            issues.append(('FIG_NO_CAPTION', 'important', f'Figure {i+1}: Missing caption'))

    return issues


def review_statistics(text, lines):
    """Dimension 5: Statistical claims."""
    issues = []

    # CI coverage
    ci_patterns = [
        r'\\pm\s*\d', r'\{\\pm\}\s*\d', r'\[\d+.*?,\s*\d+.*?\]',
        r'95\s*%\s*CI', r'bootstrap.*?CI', r'confidence\s*interval',
    ]
    ci_count = sum(len(re.findall(p, text, re.I)) for p in ci_patterns)
    stat_patterns = [r'p\s*[<>=]\s*[\d.]+', r'statistically\s+significant']
    stat_count = sum(len(re.findall(p, text, re.I)) for p in stat_patterns)
    if stat_count > 3 and ci_count / max(stat_count, 1) < 0.3:
        issues.append(('STAT_LOW_CI', 'important', f'CI coverage {ci_count}/{stat_count} ({100*ci_count/max(stat_count,1):.0f}%) — add CIs'))

    # Abstract CI
    abstract = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', text, re.DOTALL)
    if abstract:
        abs_text = abstract.group(1)
        abs_stats = len(re.findall(r'p\s*[<>=]\s*[\d.]+', abs_text))
        abs_ci = len(re.findall(r'95.*?CI|\\\\\[', abs_text))
        if abs_stats > 0 and abs_ci == 0:
            issues.append(('STAT_ABSTRACT_CI', 'important', f'Abstract has {abs_stats} stats but 0 CIs'))

    # Sample size
    n_matches = re.findall(r'N\s*[{=:]\s*(\d+)', text)
    n_values = [int(n) for n in n_matches if 1 < int(n) < 10000]
    if n_values:
        min_n = min(n_values)
        if min_n < 10:
            issues.append(('STAT_LOW_N', 'important', f'Smallest N={min_n} — may be underpowered'))

    return issues


def review_logic(text, lines):
    """Dimension 6: Logic and claims."""
    issues = []

    # First/novel claims
    first_claims = re.findall(r'(?:first|novel|we are the first to|no prior)[^.]*\.', text, re.I)
    if first_claims:
        issues.append(('LOGIC_FIRST', 'important', f'{len(first_claims)} "first"/"novel" claims — verify against literature'))

    # Universal claims from limited data
    universal = re.findall(r'(?:all|every|always|never|universally|fundamental)[^.]*\.', text, re.I)
    n_conds = len(re.findall(r'condition|dataset|experiment', text, re.I))
    if len(universal) > 3 and n_conds < 20:
        issues.append(('LOGIC_UNIVERSAL', 'minor', f'{len(universal)} universal claims with ~{n_conds} conditions'))

    # Limitations section
    lim_match = re.search(r'\\(?:sub)?section\{Limitations?\}(.*?)\\(?:sub)?section\{', text, re.DOTALL | re.I)
    if lim_match:
        lim_items = re.findall(r'\\item\s+', lim_match.group(1))
        if len(lim_items) < 2:
            issues.append(('LOGIC_FEW_LIM', 'minor', f'Only {len(lim_items)} limitation(s) — consider adding more'))
    else:
        issues.append(('LOGIC_NO_LIM', 'important', 'No Limitations section found'))

    # Alternative explanations
    disc = re.search(r'Discussion(.*?)\\(?:sub)?section\{', text, re.DOTALL | re.I)
    if disc:
        if not re.search(r'alternative|confound|could also be|another explanation', disc.group(1), re.I):
            issues.append(('LOGIC_NO_ALT', 'minor', 'Discussion does not consider alternative explanations'))

    return issues


def review_reproducibility(text, lines):
    """Dimension 7: Reproducibility."""
    issues = []

    has_seed = bool(re.search(r'(?:random\s+seed|seed\s*=\s*\d|seeded)', text, re.I))
    has_version = bool(re.search(r'(?:version[- ]lock|API.*?version|model.*?version)', text, re.I))
    has_params = bool(re.search(r'(?:learning\s+rate|temperature|α\s*=\s*[\d.]+)', text, re.I))
    has_code = bool(re.search(r'(?:code.*?available|reproducib.*?statement)', text, re.I))

    missing = []
    if not has_seed: missing.append('seeds')
    if not has_version: missing.append('API versions')
    if not has_params: missing.append('hyperparameters')
    if not has_code: missing.append('code availability')

    if len(missing) >= 3:
        issues.append(('REPRO_MISSING', 'important', f'Missing: {", ".join(missing)}'))

    if re.search(r'will\s+be.*?available\s+upon\s+acceptance', text, re.I):
        issues.append(('REPRO_UPON_ACCEPT', 'minor', 'Code "upon acceptance" — reviewers cannot verify'))

    return issues


# ============================================================
# Auto-fix
# ============================================================

def fix_missing_r(text):
    """Fix missing 'r' before '= -0.XXX'."""
    fixes = []
    pattern = r',\s*= (-?0\.\d+)\$'
    for m in re.finditer(pattern, text):
        context = text[max(0, m.start()-50):m.end()+30]
        if 'r =' in context or 'r=' in context:
            old = m.group(0)
            new = f', $r = {m.group(1)}$'
            text = text.replace(old, new, 1)
            fixes.append(f'Added missing "r" before "= {m.group(1)}"')
    return text, fixes


def fix_symbol_inconsistency(text):
    """Standardize C vs c_min."""
    fixes = []
    if re.search(r'\\geq C > 0', text) and re.search(r'\\geq c_\\{\\min\\} > 0', text):
        text = re.sub(r'(\\geq )C( > 0)', r'\1c_{\min}\2', text)
        fixes.append('Standardized C → c_min')
    return text, fixes


def fix_duplicate_paragraph(text):
    """Merge duplicate paragraphs."""
    fixes = []
    pattern = r'(\w+\s+(?:is|are)):\s*\n\s*(\1)'
    if re.search(pattern, text):
        text = re.sub(pattern, r'\2', text, count=1)
        fixes.append('Merged duplicate paragraph')
    return text, fixes


def fix_caption_periods(text):
    """Add periods to captions."""
    fixes = []
    def add_period(m):
        cap = m.group(1)
        if cap and not cap.rstrip().endswith(('.', '!', '?', ')}')):
            fixes.append(f'Added period to caption')
            return '\\caption{' + cap.rstrip() + '.}'
        return m.group(0)
    text = re.sub(r'\\caption\{([^}]+)\}', add_period, text)
    return text, fixes


def fix_whitespace(text):
    """Fix double spaces and trailing whitespace."""
    fixes = []
    original = text
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r' +\n', '\n', text)
    if text != original:
        fixes.append('Fixed whitespace')
    return text, fixes


# ============================================================
# Main pipeline
# ============================================================

def run_review(text, auto_fix=True):
    """One-pass comprehensive review."""
    lines = text.split('\n')
    all_issues = []
    all_fixes = []

    # 7 dimensions in one pass
    all_issues.extend(review_format(text, lines))
    all_issues.extend(review_formulas(text, lines))
    all_issues.extend(review_references(text, lines))
    all_issues.extend(review_tables_figures(text, lines))
    all_issues.extend(review_statistics(text, lines))
    all_issues.extend(review_logic(text, lines))
    all_issues.extend(review_reproducibility(text, lines))

    # Auto-fix
    if auto_fix:
        text, fixes = fix_missing_r(text)
        all_fixes.extend(fixes)
        text, fixes = fix_symbol_inconsistency(text)
        all_fixes.extend(fixes)
        text, fixes = fix_duplicate_paragraph(text)
        all_fixes.extend(fixes)
        text, fixes = fix_caption_periods(text)
        all_fixes.extend(fixes)
        text, fixes = fix_whitespace(text)
        all_fixes.extend(fixes)

    return {
        'issues': all_issues,
        'fixes': all_fixes,
        'text': text,
        'changed': text != text,
    }


def print_checklist(paper_id, issues, fixes):
    """Print modification checklist."""
    # Group by priority
    crit = [i for i in issues if i[1] == 'critical']
    imp = [i for i in issues if i[1] == 'important']
    minor = [i for i in issues if i[1] == 'minor']

    print(f"\n{'='*65}")
    print(f"📋 Modification Checklist — {paper_id}")
    print(f"{'='*65}")

    if crit:
        print(f"\n  🔴 P0 — MUST FIX ({len(crit)}):")
        for code, sev, msg in crit:
            print(f"    □ [{code}] {msg}")

    if imp:
        print(f"\n  🟡 P1 — SHOULD FIX ({len(imp)}):")
        for code, sev, msg in imp:
            print(f"    □ [{code}] {msg}")

    if minor:
        print(f"\n  🟢 P2 — NICE TO FIX ({len(minor)}):")
        for code, sev, msg in minor:
            print(f"    □ [{code}] {msg}")

    if fixes:
        print(f"\n  🔧 Auto-fixes applied ({len(fixes)}):")
        for fix in fixes:
            print(f"    ✅ {fix}")

    print(f"\n{'='*65}")
    print(f"  Total: {len(crit)} P0 + {len(imp)} P1 + {len(minor)} P2 = {len(issues)} issues")
    print(f"{'='*65}")


def main():
    parser = argparse.ArgumentParser(description='Systematic Review + Auto-Fix')
    parser.add_argument('paper_id', help='Paper ID or path to .tex')
    parser.add_argument('--check-only', action='store_true', help='Review without fixing')
    parser.add_argument('--json', '-j', action='store_true', help='JSON output')
    args = parser.parse_args()

    # Find paper
    text = None
    tex_path = None
    paper_id = args.paper_id

    registry_path = LOOP_DIR / 'registry.yaml'
    if registry_path.exists():
        reg = yaml.safe_load(registry_path.read_text(encoding='utf-8'))
        for k, p in reg.get('papers', {}).items():
            if p['id'] == paper_id:
                paper_dir = AETTL_DIR / p['path']
                for name in ['main_merged.tex', 'main_tmlr.tex', 'main.tex']:
                    candidate = paper_dir / name
                    if candidate.exists():
                        tex_path = candidate
                        text = candidate.read_text(encoding='utf-8', errors='ignore')
                        break
                break

    if text is None:
        candidate = Path(paper_id)
        if candidate.exists():
            tex_path = candidate
            text = candidate.read_text(encoding='utf-8', errors='ignore')

    if text is None:
        print(f"❌ Paper '{paper_id}' not found")
        sys.exit(1)

    # Run review
    result = run_review(text, auto_fix=not args.check_only)

    # Save fixed version
    if result['changed'] and not args.check_only and tex_path:
        backup = tex_path.with_suffix('.tex.bak')
        if not backup.exists():
            import shutil
            shutil.copy2(tex_path, backup)
        tex_path.write_text(result['text'], encoding='utf-8')

    if args.json:
        print(json.dumps({
            'paper_id': paper_id,
            'issues': result['issues'],
            'fixes': result['fixes'],
        }, indent=2, ensure_ascii=False))
    else:
        print_checklist(paper_id, result['issues'], result['fixes'])


if __name__ == '__main__':
    main()
