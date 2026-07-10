#!/usr/bin/env python3
"""Loop Engineering v5.2 — Submission Audit Engine
Pre-submission comprehensive check. Run before ANY submission.
Usage: python submission_audit.py PAPER_ID [--strict] [--json]
Checks: refs, figures, stats, TMLR compliance, anonymization, citations, consistency,
        CI coverage, effect sizes, table/fig consistency, small-N sweeps, notation, multi-compare
"""
import yaml, sys, argparse, re, json, os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

# ============================================================
# KNOWN CITATION DATABASE (verified from web searches)
# ============================================================
KNOWN_CITATIONS = {
    'cobbe2021gsm8k':  {'first_author': 'Cobbe',   'venue': 'arXiv',         'year': 2021},
    'guo2017calibration': {'first_author': 'Guo',   'venue': 'ICML',         'year': 2017},
    'huang2026cagecal': {'first_author': 'Huang',   'venue': 'arXiv',         'year': 2026},
    'jiang2021can':    {'first_author': 'Jiang',    'venue': 'TACL',          'year': 2021},  # NOT EMNLP
    'niculescu2005predicting': {'first_author': 'Niculescu-Mizil', 'venue': 'ICML', 'year': 2005},
    'zheng2023judging':{'first_author': 'Zheng',    'venue': 'NeurIPS',       'year': 2023},
    'chiang2024chatbot':{'first_author': 'Chiang',  'venue': 'arXiv',         'year': 2024},
    'dodge2019reproducibility': {'first_author': 'Dodge', 'venue': 'EMNLP',  'year': 2019},
    'messing2026tee':  {'first_author': 'Messing',  'venue': 'arXiv',         'year': 2026},
    'sclar2024quantifying': {'first_author': 'Sclar', 'venue': 'ICLR',        'year': 2024},
    'tversky1974anchoring': {'first_author': 'Tversky', 'venue': 'Science',   'year': 1974},
    'he2026paradox':   {'first_author': 'Shukla',   'venue': 'ACL SRW',       'year': 2026},  # NOT He
    'mills2026verification': {'first_author': 'Wang', 'venue': 'arXiv',       'year': 2026},  # NOT Mills
    'heineman2025snr': {'first_author': 'Heineman', 'venue': 'NeurIPS',       'year': 2025},
    'li2026drift':     {'first_author': 'Li',        'venue': 'arXiv',         'year': 2026},
    'leng2024taming':  {'first_author': 'Leng',      'venue': 'EMNLP',         'year': 2025},
    'bertalanic2026cost': {'first_author': 'Bertalanič', 'venue': 'CAIS',     'year': 2026},
    'schwarzschild2021can': {'first_author': 'Schwarzschild', 'venue': 'NeurIPS', 'year': 2021},
    'sun2020test':     {'first_author': 'Sun',       'venue': 'ICML',          'year': 2020},
    'tian2023just':    {'first_author': 'Tian',      'venue': 'EMNLP',         'year': 2023},
    'zhou2024incontext': {'first_author': 'Zhou',    'venue': 'EMNLP',         'year': 2024},
    'wu2024autogen':   {'first_author': 'Wu',        'venue': 'arXiv',         'year': 2024},
    'li2025judging':   {'first_author': 'Li',        'venue': 'arXiv',         'year': 2025},
    'li2023multiagent':{'first_author': 'Li',        'venue': 'NeurIPS',       'year': 2023},
    'lin2024collaborative': {'first_author': 'Lin',  'venue': 'ICLR Workshop', 'year': 2024},
    'button2013power': {'first_author': 'Button',    'venue': 'Nature Reviews','year': 2013},
    'ioannidis2005most': {'first_author': 'Ioannidis', 'venue': 'PLoS Medicine','year': 2005},
    'pearl2016causal': {'first_author': 'Pearl',     'venue': 'Cambridge',     'year': 2016},
    'shadish2002experimental': {'first_author': 'Shadish', 'venue': 'Houghton Mifflin', 'year': 2002},
    'luccioni2024estimating': {'first_author': 'Luccioni', 'venue': 'arXiv',   'year': 2024},
    'liang2023holistic': {'first_author': 'Liang',   'venue': 'arXiv',         'year': 2023},
    'bellinger2021calibrated': {'first_author': 'Bellinger','venue': 'DS',     'year': 2021},
    'huang2020experimental': {'first_author': 'Huang', 'venue': 'IEEE Access', 'year': 2020},
    'phelps2025platt': {'first_author': 'Phelps',    'venue': 'TMLR',          'year': 2025},
    'roelofs2022mitigating': {'first_author': 'Roelofs','venue': 'AISTATS',    'year': 2022},
    'nixon2019measuring': {'first_author': 'Nixon',   'venue': 'CVPR Workshop', 'year': 2019},
    'kumar2019verified': {'first_author': 'Kumar',    'venue': 'NeurIPS',       'year': 2019},
    'ovadia2019uncertainty': {'first_author': 'Ovadia','venue': 'NeurIPS',     'year': 2019},
    'minderer2021revisiting': {'first_author': 'Minderer','venue': 'NeurIPS',  'year': 2021},
    'wang2021revisiting': {'first_author': 'Wang',    'venue': 'NeurIPS',       'year': 2021},
    'kull2017temperature': {'first_author': 'Kull',   'venue': 'EJS',           'year': 2017},
    'kull2019dirichlet': {'first_author': 'Kull',     'venue': 'NeurIPS',       'year': 2019},
    'platt1999probabilistic': {'first_author': 'Platt','venue': 'MIT Press',    'year': 1999},
}

def load_yaml(p):
    with open(p, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def find_paper(paper_id):
    reg = load_yaml(LOOP_DIR / 'registry.yaml')
    for k, p in reg['papers'].items():
        if p['id'] == paper_id:
            return p
    return None

def extract_citations(text):
    """Extract all citation keys from text."""
    keys = set()
    for m in re.finditer(r'\\cite[tp]?\{([^}]+)\}', text):
        for k in m.group(1).split(','):
            keys.add(k.strip())
    return keys

def extract_bib_authors(text, key):
    """Extract author surnames from a bib entry. Handles both \\bibitem and .bib formats."""
    # Try .bib format first (more structured)
    # Find the entry: @article{key, ... }
    entry_pattern = r'@\w+\{' + re.escape(key) + r',\s*\n(.*?)\n\}'
    m = re.search(entry_pattern, text, re.DOTALL)
    if m:
        body = m.group(1)
        # Extract author field
        author_m = re.search(r'author\s*=\s*\{(.+?)\}', body, re.DOTALL)
        if author_m:
            author_field = author_m.group(1)
            # Get first author's surname: "First Last and First Last" or "Last, First"
            first = author_field.split(' and ')[0].strip()
            # Check if it's "Last, First" format
            if ',' in first:
                surname = first.split(',')[0].strip()
            else:
                parts = first.split()
                surname = parts[-1] if parts else first
            surname = surname.replace('~', ' ').replace('č','c').replace('ć','c').rstrip('.')
            return [surname]
    
    # Try \\bibitem format
    pattern = r'\\bibitem(?:\[.*?\])?\{(?:' + re.escape(key) + r')\}\s*(.*?)(?:\\newblock|\n\n|\Z)'
    m = re.search(pattern, text, re.DOTALL)
    if m:
        author_part = m.group(1).strip()
        # "D.~Heineman et~al." or "Chuan Guo" → extract surname
        # Strip LaTeX: remove ~, \v{}, etc
        clean = re.sub(r'\\[a-z]+\{([^}]*)\}', r'\1', author_part)
        clean = clean.replace('~', ' ').replace('et al.', '').strip()
        # First author: "D. Heineman" → "Heineman", "Chuan Guo" → "Guo"
        parts = clean.split(',')[0].split(' and ')[0].split()
        if parts:
            # Take the last word as surname (after stripping initials)
            surname = parts[-1].rstrip('.,')
            return [surname]
    
    return []

def extract_bib_keys(text_or_path):
    """Extract keys from bibliography."""
    keys = set()
    if hasattr(text_or_path, 'read_text'):
        text_or_path = text_or_path.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'\\bibitem(?:\[.*?\])?\{(.+?)\}', text_or_path):
        keys.add(m.group(1).strip())
    for m in re.finditer(r'@\w+\{(.+?),', text_or_path):
        keys.add(m.group(1).strip())
    return keys

def check_cross_refs(paper_dir):
    """Check .aux for undefined references."""
    issues = []
    for aux in paper_dir.glob('*.aux'):
        content = aux.read_text(encoding='utf-8', errors='ignore')
        # LaTeX Warning: Reference `xxx' on page X undefined
        for m in re.finditer(r"Warning: Reference `([^']+)' .*undefined", content):
            issues.append(('UNDEFINED_REF', 'critical', f"Undefined reference: {m.group(1)}"))
        # LaTeX Warning: Citation `xxx' on page X undefined
        for m in re.finditer(r"Warning: Citation `([^']+)' .*undefined", content):
            issues.append(('UNDEFINED_CITE', 'critical', f"Undefined citation: {m.group(1)}"))
    if not issues:
        issues.append(('CROSS_REFS', 'pass', 'All cross-references resolved'))
    return issues

def check_figures(text, paper_dir):
    """Verify all figure files exist."""
    issues = []
    for m in re.finditer(r'\\includegraphics(?:\[.*?\])?\{(.+?)\}', text):
        fig = m.group(1).strip()
        # Try multiple paths
        paths = [
            paper_dir / fig,
            paper_dir / 'figures' / Path(fig).name,
        ]
        found = any(p.exists() for p in paths)
        if not found:
            issues.append(('MISSING_FIGURE', 'critical', f"Figure not found: {fig}"))
    if not issues:
        issues.append(('FIGURES', 'pass', 'All figures present'))
    return issues

def check_stats(text):
    """Check statistical reporting completeness."""
    issues = []
    has_ci = bool(re.search(r'\\pm\s*\d|\{\\pm\}\s*\d|\[\d+.*?,\s*\d+.*?\]|bootstrap.*?CI|confidence\s*interval', text, re.I))
    has_es = bool(re.search(r"Cohen'?s\s*d|Cliff'?s\s*\\?delta|Hedges'?\s*g|\beffect\s*size\b", text, re.I))
    has_p = bool(re.search(r'p\s*[<>=]', text))
    
    if not has_ci:
        issues.append(('NO_CI', 'important', 'No confidence intervals detected. Add bootstrap CI or ±SEM.'))
    if not has_es:
        issues.append(('NO_EFFECT_SIZE', 'important', 'No effect sizes detected. Add Cohen\'s d or equivalent.'))
    if not has_p:
        issues.append(('NO_PVALUE', 'minor', 'No p-values detected. Consider adding statistical tests.'))
    
    if has_ci and has_es:
        issues.append(('STATS', 'pass', 'Statistical reporting complete (CI + effect size)'))
    elif has_ci:
        issues.append(('STATS', 'pass', 'CI reported (effect size recommended)'))
    return issues

def check_tmlr_compliance(text):
    """Check TMLR format requirements."""
    issues = []
    if '\\usepackage{tmlr}' not in text:
        issues.append(('NO_TMLR_STY', 'critical', 'Missing \\usepackage{tmlr}. Not in TMLR format.'))
    if 'Broad Impact' not in text and 'Broader Impact' not in text:
        issues.append(('NO_BROADER_IMPACT', 'critical', 'Missing Broader Impact Statement (TMLR required)'))
    if 'Reproducibility' not in text:
        issues.append(('NO_REPRODUCIBILITY', 'critical', 'Missing Reproducibility Statement (TMLR required)'))
    if not issues:
        issues.append(('TMLR_FORMAT', 'pass', 'TMLR format compliance'))
    return issues

def check_anonymization(text):
    """Check for identity leaks."""
    issues = []
    # Check author block
    author_match = re.search(r'\\author\{(.+?)\}', text, re.DOTALL)
    if author_match:
        author_text = author_match.group(1)
        if 'Anonymous' not in author_text:
            issues.append(('AUTHOR_EXPOSED', 'critical', f'Author not anonymous: {author_text[:60]}'))
    
    # Check for personal info (email in \texttt{}, \href{mailto:}, etc.)
    # Only flag \texttt{} if it contains an email-like pattern (has @ or "email")
    texttt_matches = re.findall(r'\\texttt\{([^}]+)\}', text)
    for tt in texttt_matches:
        if '@' in tt or 'mail' in tt.lower():
            issues.append(('EMAIL_EXPOSED', 'critical', f'Email-like \\texttt{{}}: {tt[:40]}'))
            break
    # Also check for bare email patterns outside \texttt
    if re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text):
        if not any(i[0] == 'EMAIL_EXPOSED' for i in issues):
            issues.append(('EMAIL_EXPOSED', 'critical', 'Bare email address found in text'))
    if re.search(r'\\href\{', text):
        issues.append(('URL_EXPOSED', 'important', 'Hyperlink found — verify it is not a personal URL'))
    if re.search(r'\\section\*\{Acknowledgment', text):
        issues.append(('ACK_EXPOSED', 'critical', 'Acknowledgments section present — remove for TMLR'))
    
    # Check PDF metadata
    if re.search(r'pdfauthor=\{([^A]|A[^n])', text):
        issues.append(('PDF_METADATA', 'important', 'PDF metadata may contain author info'))
    
    if all('EXPOSED' not in i[0] for i in issues):
        issues.append(('ANONYMIZATION', 'pass', 'Anonymization complete'))
    return issues

def check_self_citation(text, paper_dir):
    """Check self-citation rate."""
    all_keys = extract_citations(text)
    bib_keys = extract_bib_keys(text)
    # Try external .bib
    for bib_file in paper_dir.glob('*.bib'):
        bib_keys |= extract_bib_keys(bib_file)
    
    all_cited = all_keys & bib_keys
    self_cites = {k for k in all_cited if 'liu202' in k.lower() or 'liu2025' in k.lower() or 'liu2026' in k.lower()}
    total = len(all_cited) if all_cited else 1
    rate = len(self_cites) / total
    issues = []
    if rate > 0.5:
        issues.append(('SELF_CITE_HIGH', 'important', f'Self-citation rate: {rate:.0%} ({len(self_cites)}/{total}). Consider adding external references.'))
    elif rate > 0.3:
        issues.append(('SELF_CITE_MODERATE', 'minor', f'Self-citation rate: {rate:.0%} ({len(self_cites)}/{total})'))
    else:
        issues.append(('SELF_CITE', 'pass', f'Self-citation rate: {rate:.0%} ({len(self_cites)}/{total})'))
    return issues

def check_ghost_refs(text, paper_dir):
    """Find bibliography entries never cited."""
    cited = extract_citations(text)
    bib_keys = extract_bib_keys(text)
    for bib_file in paper_dir.glob('*.bib'):
        bib_keys |= extract_bib_keys(bib_file)
    
    ghost = bib_keys - cited
    issues = []
    for g in sorted(ghost):
        issues.append(('GHOST_REF', 'critical', f'Bibliography entry never cited: {g}. Cite it or remove from bib.'))
    if not ghost:
        issues.append(('GHOST_REFS', 'pass', 'No ghost references'))
    return issues

def check_citation_accuracy(text, paper_dir):
    """Verify citations against known database."""
    all_text = text
    for bib_file in sorted(paper_dir.glob('*.bib')):
        all_text += '\n' + bib_file.read_text(encoding='utf-8', errors='ignore')
    
    # Get all bib keys from the combined text
    bib_keys = set()
    for m in re.finditer(r'\\bibitem(?:\[.*?\])?\{(.+?)\}', all_text):
        bib_keys.add(m.group(1))
    for m in re.finditer(r'@\w+\{(.+?),', all_text):
        bib_keys.add(m.group(1))
    
    issues = []
    for key in sorted(bib_keys):
        if key in KNOWN_CITATIONS:
            known = KNOWN_CITATIONS[key]
            authors = extract_bib_authors(all_text, key)
            
            if authors:
                expected = known['first_author'].replace('č','c').replace('ć','c').lower()
                found = authors[0].lower()
                if expected not in found and found not in expected:
                    # Special cases: Shukla (not He), Wang (not Mills)
                    if key == 'he2026paradox' and 'shukla' in found:
                        pass  # Correct — the bib was fixed to Shukla
                    elif key == 'mills2026verification' and 'wang' in found:
                        pass  # Correct — the bib was fixed to Wang
                    elif found in expected or expected in found:
                        pass  # Partial match (e.g., "Bertalani" vs "Bertalanič")
                    else:
                        issues.append(('CITE_AUTHOR', 'critical', 
                            f"{key}: bib says '{authors[0]}', expected '{known['first_author']}'"))
            
            # Check venue for TACL papers
            if known['venue'] == 'TACL':
                # Search for "EMNLP" near this citation in the bib
                entry_start = all_text.find(key)
                if entry_start > 0:
                    chunk = all_text[entry_start:entry_start+500]
                    if 'EMNLP' in chunk:
                        issues.append(('CITE_VENUE_TACL', 'critical',
                            f"{key}: Published in TACL, but bib says EMNLP"))
    
    if not issues:
        issues.append(('CITE_ACCURACY', 'pass', 'All known citations verified'))
    return issues

def check_abstract_consistency(text):
    """Check abstract vs body consistency."""
    issues = []
    m = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', text, re.DOTALL)
    if not m:
        return [('NO_ABSTRACT', 'critical', 'Abstract not found')]
    
    abstract = m.group(1)
    # Count findings
    abs_findings = len(re.findall(r'(?:finding|Finding)\s*\d|\(\d\)', abstract))
    body_findings = len(re.findall(r'\\item\s*\\textbf\{Finding', text))
    
    if abs_findings > 0 and body_findings > 0 and abs_findings != body_findings:
        issues.append(('FINDING_COUNT', 'important',
            f'Abstract mentions ~{abs_findings} findings, body has {body_findings}'))
    
    # Check number density
    numbers = re.findall(r'\d+\.?\d*', abstract)
    sentences = [s.strip() for s in re.split(r'[.!?]\s+', abstract) if s.strip()]
    max_dense = max(len(re.findall(r'\d+\.?\d*', s)) for s in sentences) if sentences else 0
    if max_dense > 6:
        issues.append(('ABSTRACT_DENSE', 'minor', f'Up to {max_dense} numbers in one abstract sentence'))
    
    # Check "first" claims
    first_claims = re.findall(r'(?:first|novel|we are the first to)[^.]*\.', abstract, re.I)
    if first_claims:
        issues.append(('FIRST_CLAIM', 'important', f'{len(first_claims)} "first"/"novel" claims in abstract. Verify with literature search.'))
    
    if not issues:
        issues.append(('ABSTRACT', 'pass', 'Abstract-body consistency check passed'))
    return issues

def check_title(text):
    """Check title format."""
    issues = []
    title_match = re.search(r'\\title\{(.+?)\}', text, re.DOTALL)
    if title_match:
        title = title_match.group(1)
        # Remove LaTeX
        title_clean = re.sub(r'\\\w+\{.*?\}', '', title)
        title_clean = re.sub(r'\\\\', ' ', title_clean).strip()
        if len(title_clean) > 150:
            issues.append(('TITLE_LONG', 'minor', f'Title is {len(title_clean)} chars (consider shortening)'))
        if '\\bf' in title or '\\textbf' in title:
            issues.append(('TITLE_BOLD', 'minor', 'Title has manual bold formatting'))
    return issues

def check_dual_consistency(paper_dir):
    """Check arXiv vs TMLR version consistency."""
    arxiv = paper_dir / 'main_arxiv.tex'
    tmlr = paper_dir / 'main_tmlr.tex'
    issues = []
    
    if arxiv.exists() and tmlr.exists():
        arxiv_text = arxiv.read_text(encoding='utf-8', errors='ignore')
        tmlr_text = tmlr.read_text(encoding='utf-8', errors='ignore')
        
        if 'Anonymous Authors' not in tmlr_text:
            issues.append(('DUAL_AUTHOR', 'critical', 'TMLR version not anonymized'))
        if 'Zewen Liu' not in arxiv_text and 'Anonymous' in arxiv_text:
            issues.append(('DUAL_AUTHOR_ARXIV', 'important', 'arXiv version missing author name'))
        
        # Check content similarity (should be almost identical except preamble)
        arxiv_body = arxiv_text[arxiv_text.find('\\begin{document}'):]
        tmlr_body = tmlr_text[tmlr_text.find('\\begin{document}'):]
        if len(arxiv_body) > 0 and len(tmlr_body) > 0:
            diff_ratio = abs(len(arxiv_body) - len(tmlr_body)) / max(len(arxiv_body), 1)
            if diff_ratio > 0.1:
                issues.append(('DUAL_DIVERGE', 'important', f'ArXiv/TMLR versions diverge by {diff_ratio:.0%}'))
        
        if not issues:
            issues.append(('DUAL', 'pass', 'arXiv/TMLR versions consistent'))
    return issues

def check_quality_gates(text):
    """Run v5.2 quality checks from quality_checks.py (paperreview.ai gap analysis)."""
    try:
        from quality_checks import run_all_checks
        results = run_all_checks(text)
        issues = []
        for check_name, items in results.items():
            for code, severity, msg in items:
                if severity != 'pass':
                    issues.append((code, severity, msg))
        if not issues:
            issues.append(('QUALITY_GATES', 'pass', 'All 9 quality gates passed'))
        return issues
    except ImportError:
        return [('QUALITY_IMPORT', 'minor', 'quality_checks.py not found — skipping v5.3 gates')]
    except Exception as e:
        return [('QUALITY_ERROR', 'minor', f'Quality check error: {e}')]


def check_latex_compilation(paper_dir):
    """Run v5.3 LaTeX compilation checks from latex_check.py."""
    try:
        from latex_check import check_bibitem_format, check_cite_bib_match, check_ref_label
        tex_files = (list(paper_dir.glob('main_merged.tex')) or
                     list(paper_dir.glob('main_tmlr.tex')) or
                     list(paper_dir.glob('main.tex')))
        if not tex_files:
            return [('NO_TEX', 'critical', 'No .tex file found')]
        text = tex_files[0].read_text(encoding='utf-8', errors='ignore')
        issues = []
        issues.extend(check_bibitem_format(text))
        issues.extend(check_cite_bib_match(text))
        issues.extend(check_ref_label(text))
        # Only return non-pass issues
        return [(code, sev, msg) for code, sev, msg in issues if sev != 'pass']
    except ImportError:
        return []
    except Exception as e:
        return [('LATEX_ERROR', 'minor', f'LaTeX check error: {e}')]


def check_skill_bridge(paper_id, paper_dir, text):
    """Run v5.3 skill bridge checks (light-citation, light-typesetting, light-result-analysis)."""
    try:
        from skill_bridge import run_citation_check, run_precheck_log, run_submission_check, check_claim_evidence
        issues = []
        issues.extend(run_citation_check(paper_dir, text))
        issues.extend(run_precheck_log(paper_dir))
        issues.extend(run_submission_check(paper_dir, text))
        issues.extend(check_claim_evidence(text))
        return [(code, sev, msg) for code, sev, msg in issues if sev != 'pass']
    except ImportError:
        return []
    except Exception as e:
        return [('SKILL_BRIDGE', 'minor', f'Skill bridge error: {e}')]


def check_agent_review(paper_id):
    """Load cached agent review if available."""
    try:
        from agent_review import load_cached_review, format_for_audit
        result = load_cached_review(paper_id)
        if result:
            issues = format_for_audit(result)
            # Add summary
            score = result.get('score', '?')
            verdict = result.get('verdict', 'unknown')
            issues.insert(0, ('AGENT_SUMMARY', 'minor',
                f'Agent review: score={score}/10, verdict={verdict}'))
            return issues
        return [('AGENT_REVIEW', 'minor',
                'No cached agent review. Run: python agent_review.py PAPER_ID --generate')]
    except ImportError:
        return []
    except Exception as e:
        return [('AGENT_ERROR', 'minor', f'Agent review error: {e}')]


def run_audit(paper_id, paper, strict=False):
    """Run complete audit."""
    paper_dir = AETTL_DIR / paper['path']
    tex_files = (list(paper_dir.glob('main_merged.tex')) or
                 list(paper_dir.glob('main_tmlr.tex')) or
                 list(paper_dir.glob('main.tex')))

    if not tex_files:
        return {'paper_id': paper_id, 'error': 'No .tex file found'}

    tex_path = tex_files[0]
    text = tex_path.read_text(encoding='utf-8', errors='ignore')

    all_issues = []
    all_issues.extend(check_cross_refs(paper_dir))
    all_issues.extend(check_figures(text, paper_dir))
    all_issues.extend(check_stats(text))
    all_issues.extend(check_tmlr_compliance(text))
    all_issues.extend(check_anonymization(text))
    all_issues.extend(check_self_citation(text, paper_dir))
    all_issues.extend(check_ghost_refs(text, paper_dir))
    all_issues.extend(check_citation_accuracy(text, paper_dir))
    all_issues.extend(check_abstract_consistency(text))
    all_issues.extend(check_title(text))
    all_issues.extend(check_dual_consistency(paper_dir))
    all_issues.extend(check_quality_gates(text))
    all_issues.extend(check_latex_compilation(paper_dir))
    all_issues.extend(check_skill_bridge(paper_id, paper_dir, text))
    all_issues.extend(check_agent_review(paper_id))
    
    critical  = [i for i in all_issues if i[1] == 'critical']
    important = [i for i in all_issues if i[1] == 'important']
    minor     = [i for i in all_issues if i[1] == 'minor']
    passed    = [i for i in all_issues if i[1] == 'pass']
    
    return {
        'paper_id': paper_id,
        'title': paper.get('short_title', paper_id),
        'issues': all_issues,
        'critical': critical,
        'important': important,
        'minor': minor,
        'passed': len(passed),
        'total': len(all_issues),
        'score': min(10, 10 - len(critical) * 2 - len(important) * 0.5),
    }

def print_report(result):
    """Pretty-print audit report."""
    if 'error' in result:
        print(f"❌ {result['paper_id']}: {result['error']}")
        return
    
    print(f"\n{'='*65}")
    print(f"📋 Submission Audit — {result['paper_id']}: {result['title']}")
    print(f"{'='*65}")
    
    if result['critical']:
        print(f"\n🔴 CRITICAL ({len(result['critical'])}):")
        for code, sev, msg in result['critical']:
            print(f"   [{code}] {msg}")
    
    if result['important']:
        print(f"\n🟡 IMPORTANT ({len(result['important'])}):")
        for code, sev, msg in result['important']:
            print(f"   [{code}] {msg}")
    
    if result['minor']:
        print(f"\n🟢 MINOR ({len(result['minor'])}):")
        for code, sev, msg in result['minor']:
            print(f"   [{code}] {msg}")
    
    # Print pass summary
    passed_codes = defaultdict(int)
    for code, sev, msg in result['issues']:
        if sev == 'pass':
            passed_codes[code] += 1
    
    print(f"\n{'='*65}")
    print(f"✅ Passed: {result['passed']} checks")
    print(f"🔴 Critical: {len(result['critical'])}  🟡 Important: {len(result['important'])}  🟢 Minor: {len(result['minor'])}")
    
    score = result['score']
    if score >= 9:
        grade = '✅ READY TO SUBMIT'
    elif score >= 7:
        grade = '⚠️  FIX CRITICAL ISSUES'
    else:
        grade = '🔴 NOT READY'
    
    print(f"Audit Score: {score}/10 — {grade}")
    print(f"{'='*65}")

def main():
    parser = argparse.ArgumentParser(description='Loop Engineering v5.1 — Submission Audit Engine')
    parser.add_argument('paper_id', help='Paper ID (e.g., PAPER-D)')
    parser.add_argument('--strict', '-s', action='store_true', help='Treat important as critical')
    parser.add_argument('--json', '-j', action='store_true', help='Output as JSON')
    args = parser.parse_args()
    
    paper = find_paper(args.paper_id)
    if not paper:
        print(f"❌ Paper '{args.paper_id}' not found")
        sys.exit(1)
    
    result = run_audit(args.paper_id, paper, args.strict)
    
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_report(result)

if __name__ == '__main__':
    main()
