#!/usr/bin/env python3
"""Loop Engineering v5.3 — LaTeX Compilation Check
Verifies .aux, .log, refs, labels, bibentries, and figures.

Usage:
  python latex_check.py PAPER_ID
  python latex_check.py PAPER_ID --json
"""
import re, sys, json, argparse
from pathlib import Path
from collections import Counter

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

# ============================================================
# Check 1: bibitem format (merged entries, missing fields)
# ============================================================
def check_bibitem_format(text):
    """Check bibitem entries for formatting issues."""
    issues = []

    # Find all bibitem entries
    entries = list(re.finditer(
        r'\\bibitem\[([^\]]*)\]\{([^}]+)\}\s*(.*?)(?=\\bibitem|\Z)',
        text, re.DOTALL))

    for m in entries:
        label = m.group(1).strip()
        key = m.group(2).strip()
        body = m.group(3).strip()

        # Check for merged entries (multiple \newblock in one bibitem)
        newblock_count = body.count('\\newblock')
        if newblock_count > 1:
            # Check if there are two distinct titles (sign of merged entries)
            titles = re.findall(r'\\textit\{([^}]+)\}', body)
            if len(titles) > 1:
                issues.append(('MERGED_BIBENTRY', 'critical',
                    f"Bibitem '{key}' has {len(titles)} titles — likely merged entries: "
                    f"{'; '.join(t[:40] for t in titles)}. Split into separate \\bibitem."))

        # Check for missing essential fields
        has_title = bool(re.search(r'\\textit\{', body))
        has_year = bool(re.search(r'\d{4}', body))
        has_author = bool(label and len(label) > 3)

        if not has_title:
            issues.append(('BIB_NO_TITLE', 'important',
                f"Bibitem '{key}' has no \\textit{{}} title."))
        if not has_year:
            issues.append(('BIB_NO_YEAR', 'important',
                f"Bibitem '{key}' has no year."))
        if not has_author:
            issues.append(('BIB_NO_AUTHOR', 'important',
                f"Bibitem '{key}' has no author in label."))

    return issues

# ============================================================
# Check 2: cite/bibitem key matching
# ============================================================
def check_cite_bib_match(text):
    """Check that all \cite keys have matching \bibitem entries and vice versa."""
    issues = []

    cite_keys = set()
    for m in re.finditer(r'\\cite[tp]?\{([^}]+)\}', text):
        for k in m.group(1).split(','):
            cite_keys.add(k.strip())

    bib_keys = set()
    for m in re.finditer(r'\\bibitem\[.*?\]\{([^}]+)\}', text):
        bib_keys.add(m.group(1).strip())

    # Missing from bib
    missing = cite_keys - bib_keys
    for k in sorted(missing):
        issues.append(('CITE_NO_BIB', 'critical',
            f"Citation '\\cite{{{k}}}' has no matching \\bibitem entry."))

    # Ghost refs (in bib but not cited)
    ghost = bib_keys - cite_keys
    for k in sorted(ghost):
        issues.append(('GHOST_REF', 'critical',
            f"Bibitem '{k}' is never cited. Remove or add \\cite."))

    if not issues:
        issues.append(('CITE_BIB', 'pass',
            f"All {len(cite_keys)} citations match {len(bib_keys)} bibitems."))

    return issues

# ============================================================
# Check 3: ref/label matching
# ============================================================
def check_ref_label(text):
    """Check that all \ref{} have matching \label{} and vice versa."""
    issues = []

    labels = set(re.findall(r'\\label\{([^}]+)\}', text))
    refs = set(re.findall(r'\\ref\{([^}]+)\}', text))
    eqrefs = set(re.findall(r'\\eqref\{([^}]+)\}', text))
    all_refs = refs | eqrefs

    # Undefined refs
    undefined = all_refs - labels
    for r in sorted(undefined):
        issues.append(('UNDEF_REF', 'important',
            f"Reference '\\ref{{{r}}}' has no matching \\label."))

    # Unused labels (not counting internal ones)
    unused = labels - all_refs
    for l in sorted(unused):
        if not l.startswith('sec:') and not l.startswith('app:'):
            issues.append(('UNUSED_LABEL', 'minor',
                f"Label '\\label{{{l}}}' is never referenced."))

    if not issues:
        issues.append(('REF_LABEL', 'pass',
            f"All {len(all_refs)} references match {len(labels)} labels."))

    return issues

# ============================================================
# Check 4: .aux file analysis
# ============================================================
def check_aux_files(paper_dir):
    """Check .aux files for undefined references and warnings."""
    issues = []
    aux_files = list(paper_dir.glob('*.aux'))

    if not aux_files:
        issues.append(('NO_AUX', 'minor',
            "No .aux files found. Compile LaTeX first for full verification."))
        return issues

    for aux in aux_files:
        content = aux.read_text(encoding='utf-8', errors='ignore')

        # Undefined references
        for m in re.finditer(r"Warning: Reference `([^']+)' .*undefined", content):
            issues.append(('AUX_UNDEF_REF', 'critical',
                f"Undefined reference in {aux.name}: '{m.group(1)}'"))

        # Undefined citations
        for m in re.finditer(r"Warning: Citation `([^']+)' .*undefined", content):
            issues.append(('AUX_UNDEF_CITE', 'critical',
                f"Undefined citation in {aux.name}: '{m.group(1)}'"))

        # Multiply defined labels
        for m in re.finditer(r"Warning: Label `([^']+)' multiply defined", content):
            issues.append(('MULTI_LABEL', 'important',
                f"Multiply defined label in {aux.name}: '{m.group(1)}'"))

    if not issues:
        issues.append(('AUX', 'pass', f"{len(aux_files)} .aux files clean."))

    return issues

# ============================================================
# Check 5: .log file analysis
# ============================================================
def check_log_files(paper_dir):
    """Check .log files for LaTeX warnings and errors."""
    issues = []
    log_files = list(paper_dir.glob('*.log'))

    if not log_files:
        return issues

    for log_f in log_files:
        content = log_f.read_text(encoding='utf-8', errors='ignore')

        # Errors
        errors = re.findall(r'^! (.+)$', content, re.MULTILINE)
        for e in errors[:5]:
            issues.append(('LATEX_ERROR', 'critical',
                f"LaTeX error in {log_f.name}: {e[:80]}"))

        # Overfull/underfull boxes
        overfull = len(re.findall(r'Overfull \\hbox', content))
        underfull = len(re.findall(r'Underfull \\hbox', content))
        if overfull > 5:
            issues.append(('OVERFULL', 'minor',
                f"{overfull} overfull hbox warnings. Check line breaks."))

        # Font warnings
        font_warn = len(re.findall(r'Font warning', content, re.IGNORECASE))
        if font_warn > 0:
            issues.append(('FONT_WARN', 'minor',
                f"{font_warn} font warnings in {log_f.name}."))

    return issues

# ============================================================
# Check 6: Figure files
# ============================================================
def check_figures(text, paper_dir):
    """Verify all \includegraphics files exist."""
    issues = []
    for m in re.finditer(r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}', text):
        fig = m.group(1).strip()
        paths = [
            paper_dir / fig,
            paper_dir / 'figures' / Path(fig).name,
            paper_dir / fig.replace('.pdf', '.png'),
            paper_dir / 'figures' / Path(fig).stem,
        ]
        found = any(p.exists() for p in paths)
        if not found:
            issues.append(('MISSING_FIG', 'critical',
                f"Figure file not found: {fig}"))

    if not issues:
        issues.append(('FIGURES', 'pass', 'All figure files present.'))

    return issues

# ============================================================
# Run all
# ============================================================
def run_all_checks(paper_id):
    """Run all LaTeX checks on a paper."""
    import yaml
    registry = yaml.safe_load((LOOP_DIR / 'registry.yaml').read_text(encoding='utf-8'))

    paper = None
    for k, p in registry['papers'].items():
        if p['id'] == paper_id:
            paper = p
            break

    if not paper:
        return {'error': f"Paper '{paper_id}' not found"}

    paper_dir = AETTL_DIR / paper['path']
    tex_files = (list(paper_dir.glob('main_merged.tex')) or
                 list(paper_dir.glob('main_tmlr.tex')) or
                 list(paper_dir.glob('main.tex')))

    if not tex_files:
        return {'error': 'No .tex file found'}

    text = tex_files[0].read_text(encoding='utf-8', errors='ignore')

    all_issues = []
    all_issues.extend(check_bibitem_format(text))
    all_issues.extend(check_cite_bib_match(text))
    all_issues.extend(check_ref_label(text))
    all_issues.extend(check_aux_files(paper_dir))
    all_issues.extend(check_log_files(paper_dir))
    all_issues.extend(check_figures(text, paper_dir))

    return {
        'paper_id': paper_id,
        'tex_file': str(tex_files[0].name),
        'issues': all_issues,
        'critical': sum(1 for i in all_issues if i[1] == 'critical'),
        'important': sum(1 for i in all_issues if i[1] == 'important'),
        'minor': sum(1 for i in all_issues if i[1] == 'minor'),
        'passed': sum(1 for i in all_issues if i[1] == 'pass'),
    }

def print_report(result):
    """Pretty-print report."""
    if 'error' in result:
        print(f"❌ {result['error']}")
        return

    print(f"\n{'='*65}")
    print(f"🔧 LaTeX Check — {result['paper_id']} ({result['tex_file']})")
    print(f"{'='*65}")

    for sev, icon, label in [('critical','🔴','CRITICAL'), ('important','🟡','IMPORTANT'), ('minor','🟢','MINOR')]:
        items = [i for i in result['issues'] if i[1] == sev]
        if items:
            print(f"\n  {icon} {label} ({len(items)}):")
            for code, s, msg in items:
                print(f"    [{code}] {msg}")

    passed = [i for i in result['issues'] if i[1] == 'pass']
    if passed:
        print(f"\n  ✅ PASSED ({len(passed)}):")
        for code, s, msg in passed:
            print(f"    [{code}] {msg}")

    print(f"\n{'='*65}")
    total = result['critical'] + result['important'] + result['minor']
    print(f"  {result['critical']}C / {result['important']}I / {result['minor']}M — {result['passed']} passed")
    print(f"{'='*65}")

def main():
    parser = argparse.ArgumentParser(description='Loop Engineering v5.3 — LaTeX Check')
    parser.add_argument('paper_id', help='Paper ID')
    parser.add_argument('--json', '-j', action='store_true', help='JSON output')
    args = parser.parse_args()

    result = run_all_checks(args.paper_id)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_report(result)

if __name__ == '__main__':
    main()
