#!/usr/bin/env python3
"""Loop Engineering v5.3 — Skill Bridge
Integrates light-citation, light-typesetting, light-result-analysis skills
into the Loop Engineering audit pipeline.

Usage:
  python skill_bridge.py PAPER_ID          # Run all skill checks
  python skill_bridge.py PAPER_ID --cite   # Citation verification only
  python skill_bridge.py PAPER_ID --tex    # LaTeX compilation check only
  python skill_bridge.py PAPER_ID --stat   # Statistical analysis only
"""
import sys, json, argparse, subprocess, os, re
from pathlib import Path

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

# Skill script locations
SKILLS = {
    'cite': Path(os.path.expanduser('~/.zcode/skills/light-citation/scripts')),
    'tex': Path(os.path.expanduser('~/.zcode/skills/light-typesetting/scripts')),
    'stat': Path(os.path.expanduser('~/.zcode/skills/light-result-analysis/scripts')),
}

# ============================================================
# Citation Verification (light-citation)
# ============================================================
def run_citation_check(paper_dir, text):
    """Run citation verification using light-citation's verify_refs.py."""
    issues = []

    # Extract DOIs from text
    dois = set(re.findall(r'10\.\d{4,}/[^\s,;}\]]+', text))
    if not dois:
        issues.append(('NO_DOI', 'minor', 'No DOIs found in text. Add DOIs to bibliography entries.'))
        return issues

    # Write DOIs to temp file
    doi_file = paper_dir / '.loop_dois.txt'
    doi_file.write_text('\n'.join(sorted(dois)), encoding='utf-8')

    # Run verify_refs.py
    verify_script = SKILLS['cite'] / 'verify_refs.py'
    if verify_script.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(verify_script),
                 '--file', str(doi_file),
                 '--out', str(paper_dir / '.loop_cite_report.json')],
                capture_output=True, text=True, timeout=60, cwd=str(paper_dir))
            if result.returncode == 0:
                report_path = paper_dir / '.loop_cite_report.json'
                if report_path.exists():
                    report = json.loads(report_path.read_text(encoding='utf-8'))
                    summary = report.get('summary', {})
                    if summary.get('high_severity_errors', 0) > 0:
                        issues.append(('CITE_ERROR', 'critical',
                            f'{summary["high_severity_errors"]} citation(s) failed verification. '
                            f'Check .loop_cite_report.json for details.'))
                    if summary.get('retracted_count', 0) > 0:
                        issues.append(('CITE_RETRACTED', 'critical',
                            f'{summary["retracted_count"]} retracted citation(s) found. Remove or replace.'))
                    if summary.get('unverified_offline_count', 0) > 0:
                        issues.append(('CITE_OFFLINE', 'minor',
                            f'{summary["unverified_offline_count"]} citations could not be verified (offline). '
                            f'Re-run with internet for full verification.'))
                    if summary.get('high_severity_errors', 0) == 0 and summary.get('retracted_count', 0) == 0:
                        issues.append(('CITE_VERIFY', 'pass',
                            f'{len(dois)} DOIs verified via Crossref+OpenAlex.'))
            else:
                issues.append(('CITE_SCRIPT', 'minor',
                    f'verify_refs.py returned error: {result.stderr[:100]}'))
        except subprocess.TimeoutExpired:
            issues.append(('CITE_TIMEOUT', 'minor',
                'Citation verification timed out (60s). Check network.'))
        except Exception as e:
            issues.append(('CITE_ERROR', 'minor', f'Citation check error: {e}'))
    else:
        issues.append(('CITE_NOSCRIPT', 'minor',
            f'verify_refs.py not found at {verify_script}'))

    # Cleanup
    if doi_file.exists():
        doi_file.unlink()

    return issues

def run_citekey_audit(paper_dir, text):
    """Run citekey audit using light-citation's citekey_audit.py."""
    issues = []
    audit_script = SKILLS['cite'] / 'citekey_audit.py'

    if not audit_script.exists():
        return issues

    # Find .tex and .bib files
    tex_files = list(paper_dir.glob('main*.tex'))
    bib_files = list(paper_dir.glob('*.bib'))

    if not tex_files:
        return issues

    tex_file = tex_files[0]
    bib_file = bib_files[0] if bib_files else None

    try:
        cmd = [sys.executable, str(audit_script), '--tex', str(tex_file)]
        if bib_file:
            cmd.extend(['--bib', str(bib_file)])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(paper_dir))
        if result.returncode != 0 and result.stdout:
            # Parse output for issues
            if 'missing' in result.stdout.lower() or 'undefined' in result.stdout.lower():
                issues.append(('CITEKEY_MISMATCH', 'important',
                    f'Citekey mismatch detected. Run: python {audit_script} --tex {tex_file}'))
    except (subprocess.TimeoutExpired, Exception):
        pass

    return issues

# ============================================================
# LaTeX Compilation Check (light-typesetting)
# ============================================================
def run_precheck_log(paper_dir):
    """Run LaTeX log precheck using light-typesetting's precheck_log.py."""
    issues = []
    precheck_script = SKILLS['tex'] / 'precheck_log.py'

    if not precheck_script.exists():
        return issues

    # Find .log files
    log_files = list(paper_dir.glob('*.log'))
    if not log_files:
        return issues

    for log_file in log_files:
        try:
            result = subprocess.run(
                [sys.executable, str(precheck_script), str(log_file), '--json'],
                capture_output=True, text=True, timeout=15, cwd=str(paper_dir))

            if result.stdout:
                try:
                    report = json.loads(result.stdout)
                    if report.get('fatal', 0) > 0:
                        for item in report.get('issues', []):
                            if item.get('severity') == 'fatal':
                                issues.append(('LATEX_FATAL', 'critical',
                                    f'{log_file.name}: {item.get("message", "")[:80]}'))
                    if report.get('undefined_refs', 0) > 0:
                        issues.append(('UNDEF_REF', 'critical',
                            f'{log_file.name}: {report["undefined_refs"]} undefined reference(s)'))
                    if report.get('undefined_cites', 0) > 0:
                        issues.append(('UNDEF_CITE', 'critical',
                            f'{log_file.name}: {report["undefined_cites"]} undefined citation(s)'))
                except json.JSONDecodeError:
                    pass
        except (subprocess.TimeoutExpired, Exception):
            pass

    if not issues:
        issues.append(('LATEX_LOG', 'pass', 'LaTeX log clean (precheck_log.py)'))

    return issues

def run_submission_check(paper_dir, text):
    """Run submission compliance check using light-typesetting's submission_check.py."""
    issues = []
    check_script = SKILLS['tex'] / 'submission_check.py'

    if not check_script.exists():
        return issues

    tex_files = list(paper_dir.glob('main*.tex'))
    pdf_files = list(paper_dir.glob('main*.pdf'))

    if not tex_files:
        return issues

    try:
        cmd = [sys.executable, str(check_script), '--tex', str(tex_files[0])]
        if pdf_files:
            cmd.extend(['--pdf', str(pdf_files[0])])

        # Check if TMLR (double-blind)
        if '\\usepackage{tmlr}' in text or 'Anonymous' in text:
            cmd.append('--double-blind')

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, cwd=str(paper_dir))
        if result.returncode != 0 and result.stdout:
            for line in result.stdout.strip().split('\n'):
                if 'HIGH' in line or 'CRITICAL' in line:
                    issues.append(('SUBMISSION_HIGH', 'critical', line.strip()[:100]))
                elif 'WARN' in line:
                    issues.append(('SUBMISSION_WARN', 'important', line.strip()[:100]))
    except (subprocess.TimeoutExpired, Exception):
        pass

    if not issues:
        issues.append(('SUBMISSION', 'pass', 'Submission compliance check passed'))

    return issues

# ============================================================
# Statistical Analysis (light-result-analysis)
# ============================================================
def check_claim_evidence(text):
    """Check that statistical claims are properly supported."""
    issues = []

    # Check for claim-evidence patterns
    # Each claim with p-value should also have effect size + CI
    claims = re.finditer(
        r'(?:significant|p\s*[<>=]\s*[\d.]+|Δ\s*=?\s*[+-]?[\d.]+)',
        text, re.IGNORECASE)

    claim_count = sum(1 for _ in claims)

    # Check for paired design detection
    has_paired = bool(re.search(r'paired|matched|within[- ]subject|repeated[- ]measure', text, re.I))
    if has_paired and not re.search(r'Wilcoxon|paired[- ]t|sign[- ]rank|McNemar', text, re.I):
        issues.append(('PAIRED_TEST', 'important',
            'Paired design detected but no paired test mentioned. '
            'Use paired t / Wilcoxon signed-rank, not independent tests.'))

    # Check for slice analysis
    has_slice = bool(re.search(r'slice|subgroup|stratif|per[- ]class|per[- ]category', text, re.I))
    if not has_slice and claim_count > 5:
        issues.append(('NO_SLICE', 'minor',
            f'{claim_count} statistical claims but no slice/subgroup analysis mentioned. '
            f'Consider per-category breakdown to avoid aggregation blindness.'))

    # Check for FDR correction
    has_fdr = bool(re.search(r'FDR|Benjamini|false[- ]discovery|adjusted?\s+p|q\s*[<>=]', text, re.I))
    has_bonferroni = bool(re.search(r'bonferroni|holm|family[- ]wise', text, re.I))
    if claim_count > 5 and not has_fdr and not has_bonferroni:
        issues.append(('NO_FDR', 'minor',
            f'{claim_count} claims without FDR/Bonferroni correction. '
            f'Consider BH-FDR for multiple comparisons.'))

    # Check for mean ± std (not just mean)
    # Match both Unicode ± and LaTeX {\pm} or \pm
    means_without_std = len(re.findall(r'(?:mean|average|M)\s*=?\s*[\d.]+(?!\s*[±{\\])', text, re.I))
    means_with_std = len(re.findall(r'[\d.]+\s*(?:[±]|\\pm|\{\\pm\})\s*[\d.]+', text))
    if means_without_std > 3 and means_with_std == 0:
        issues.append(('NO_STD', 'important',
            f'{means_without_std} means reported but 0 with ±std. '
            f'Report mean ± std for reproducibility.'))

    if not issues:
        issues.append(('CLAIM_EVIDENCE', 'pass', 'Statistical claims properly supported.'))

    return issues

# ============================================================
# Run all skill checks
# ============================================================
def run_all_skill_checks(paper_id):
    """Run all skill-integrated checks."""
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

    # Citation verification
    all_issues.extend(run_citation_check(paper_dir, text))
    all_issues.extend(run_citekey_audit(paper_dir, text))

    # LaTeX compilation
    all_issues.extend(run_precheck_log(paper_dir))
    all_issues.extend(run_submission_check(paper_dir, text))

    # Statistical analysis
    all_issues.extend(check_claim_evidence(text))

    return {
        'paper_id': paper_id,
        'issues': all_issues,
        'critical': sum(1 for i in all_issues if i[1] == 'critical'),
        'important': sum(1 for i in all_issues if i[1] == 'important'),
        'minor': sum(1 for i in all_issues if i[1] == 'minor'),
        'passed': sum(1 for i in all_issues if i[1] == 'pass'),
    }

def print_report(result):
    """Pretty-print skill bridge report."""
    if 'error' in result:
        print(f"❌ {result['error']}")
        return

    print(f"\n{'='*65}")
    print(f"🔗 Skill Bridge — {result['paper_id']}")
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
    print(f"  {result['critical']}C / {result['important']}I / {result['minor']}M — {result['passed']} passed")
    print(f"{'='*65}")

def main():
    parser = argparse.ArgumentParser(description='Loop Engineering v5.3 — Skill Bridge')
    parser.add_argument('paper_id', help='Paper ID')
    parser.add_argument('--cite', action='store_true', help='Citation checks only')
    parser.add_argument('--tex', action='store_true', help='LaTeX checks only')
    parser.add_argument('--stat', action='store_true', help='Statistical checks only')
    parser.add_argument('--json', '-j', action='store_true', help='JSON output')
    args = parser.parse_args()

    result = run_all_skill_checks(args.paper_id)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_report(result)

if __name__ == '__main__':
    main()
