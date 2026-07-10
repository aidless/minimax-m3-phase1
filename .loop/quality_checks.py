#!/usr/bin/env python3
"""Loop Engineering v5.3 — Paper Quality Checks
15 automated checks: 9 from paperreview.ai gap analysis + 6 academic principles.

Checks:
  Q1.  CI_COVERAGE        — Confidence interval coverage
  Q2.  EFFECT_SIZE_REPORT — Effect sizes reported
  Q3.  TABLE_FIG_CONSIST  — Numerical consistency
  Q4.  SMALL_N_SWEEP      — Small N in sensitivity analyses
  Q5.  NOTATION_CONSIST   — Symbol definition consistency
  Q6.  MULTIPLE_COMPAR    — Multiple comparison correction
  Q7.  SELECTIVE_REPORT   — Cherry-picking detection
  Q8.  POWER_ANALYSIS     — Statistical power
  Q9.  BIBENTRY_FORMAT    — Bibliography format
  Q10. HONESTY            — Overclaim & tautology detection (诚实性)
  Q11. RIGOR              — Theorem-proof consistency (严谨性)
  Q12. ORIGINALITY        — Research gap & novelty (原创性)
  Q13. REPRODUCIBILITY    — Method transparency (可复现性)
  Q14. CITE_INTEGRITY     — Citation quality (规范引注)
  Q15. HUMILITY           — Limitation honesty (批判精神)

Usage:
  python quality_checks.py PAPER_ID          # Run all 15 checks
  python quality_checks.py PAPER_ID --check ci,es,ho  # Run specific checks
  python quality_checks.py PAPER_ID --json   # JSON output
"""

import re
import sys
import json
import argparse
from pathlib import Path
from collections import Counter, defaultdict

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

# ============================================================
# Q1: CI_COVERAGE — Confidence Interval Coverage
# ============================================================
# Pattern: Count statistical claims (p-values, means, differences) and
# check how many have accompanying CIs. Flag when coverage < 50%.

CI_PATTERNS = [
    r'\$\s*[\d.]+\s*\\pm\s*[\d.]+',           # $0.42 \pm 0.03$
    r'\\pm\s*[\d.]+',                           # \pm 0.03
    r'\[\s*[\d.]+\s*,\s*[\d.]+\s*\]',          # [0.38, 0.46]
    r'95\s*%\s*CI|95\%\s*confidence\s*interval', # 95% CI
    r'bootstrap.*?(?:CI|interval)',              # bootstrap CI
    r'confidence\s*interval',                    # confidence interval
    r'CI\s*=\s*\[',                             # CI = [
    r'\\(?:text|math)\{(?:95|99)\s*\\%\s*CI\}', # {95% CI}
    r'\(\s*CI[:\s]',                             # (CI:
    r'lower\s*CI|upper\s*CI',                   # lower CI / upper CI
]

# Statistical claims that SHOULD have CIs
STAT_CLAIM_PATTERNS = [
    # p-values with effect magnitude
    r'(?:p\s*[<>=]\s*[\d.]+)',
    # Means/averages with specific numbers
    r'(?:mean|average|M|μ)\s*=?\s*[\d.]+',
    # Differences/changes
    r'(?:Δ|delta|difference|change|increase|decrease)\s*=?\s*[+-]?[\d.]+',
    # Effect sizes (these already have CIs if reported properly)
    r"(?:Cohen|Cliff|Hedge).*?[=\s]+[+-]?[\d.]+",
    # Regression coefficients
    r'(?:β|beta|coefficient|slope)\s*=?\s*[+-]?[\d.]+',
    # Correlations
    r'(?:r|ρ|correlation)\s*=?\s*[+-]?[\d.]+',
]

def check_ci_coverage(text):
    """Check what fraction of statistical claims have accompanying CIs."""
    issues = []

    # Count CI instances
    ci_count = 0
    ci_locations = []
    for pat in CI_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            ci_count += 1
            ci_locations.append(m.group(0)[:50])

    # Count statistical claims
    stat_count = 0
    stat_locations = []
    for pat in STAT_CLAIM_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            stat_count += 1
            stat_locations.append(m.group(0)[:50])

    # Check abstract specifically
    abs_match = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', text, re.DOTALL)
    abs_ci = 0
    abs_stat = 0
    if abs_match:
        abstract = abs_match.group(1)
        for pat in CI_PATTERNS:
            abs_ci += len(re.findall(pat, abstract, re.IGNORECASE))
        for pat in STAT_CLAIM_PATTERNS:
            abs_stat += len(re.findall(pat, abstract, re.IGNORECASE))

    # Report
    if stat_count > 0:
        coverage = ci_count / stat_count
        if coverage < 0.3:
            issues.append(('CI_COVERAGE', 'important',
                f'Low CI coverage: {ci_count} CIs for {stat_count} statistical claims '
                f'({coverage:.0%}). Add bootstrap CIs or ±SEM to key results.'))
        elif coverage < 0.5:
            issues.append(('CI_COVERAGE', 'minor',
                f'Moderate CI coverage: {ci_count} CIs for {stat_count} claims '
                f'({coverage:.0%}). Consider adding CIs to more results.'))
        else:
            issues.append(('CI_COVERAGE', 'pass',
                f'CI coverage: {ci_count}/{stat_count} ({coverage:.0%})'))

    # Abstract-specific check (reviewers look here first)
    if abs_stat > 0 and abs_ci == 0:
        issues.append(('CI_ABSTRACT', 'important',
            f'Abstract has {abs_stat} statistical claims but 0 CIs. '
            f'Add CI/±SEM to at least the headline result.'))

    # Check if tables have CIs (as columns or ± notation)
    table_sections = re.findall(r'\\begin\{(?:tabular|table)\}(.*?)\\end\{(?:tabular|table)\}', text, re.DOTALL)
    tables_with_ci = sum(1 for t in table_sections if re.search(r'\\pm|\[.*?,.*?\]|CI', t, re.IGNORECASE))
    if len(table_sections) > 0 and tables_with_ci == 0:
        issues.append(('CI_TABLES', 'minor',
            f'{len(table_sections)} table(s) found but none contain CI/± columns. '
            f'Consider adding error bars or CI columns.'))

    return issues


# ============================================================
# Q2: EFFECT_SIZE_REPORT — Effect Size Reporting
# ============================================================
# Pattern: Check that main comparisons (those with p-values) also
# report effect sizes (Cohen's d, Cliff's δ, η², etc.)

EFFECT_SIZE_TERMS = [
    r"Cohen'?s?\s*d",
    r"Cliff'?s?\s*(?:\\delta|δ|delta)",
    r"Hedges'?\s*g",
    r"Glass'?s?\s*(?:\\delta|Δ|delta)",
    r"(?:rank[- ])?biserial",
    r"η²|\\eta\^2|eta[- ]squared",
    r"ω²|\\omega\^2|omega[- ]squared",
    r"ε²|\\epsilon\^2|epsilon[- ]squared",
    r"\\delta\s*=\s*[+-]?[\d.]+",
    r"effect\s*size",
    r"Cram[eé]r'?s?\s*V",
    r"(?:Pearson|Spearman|point[- ]biserial)\s*r",
    r"log[- ]odds?\s*ratio",
    r"AUC|AUROC|area\s+under",
    r"r\s*=\s*[+-]?[\d.]+",
    r"d\s*=\s*[+-]?[\d.]+",
    r"g\s*=\s*[+-]?[\d.]+",
    r"V\s*=\s*[\d.]+",
]

PVALUE_PATTERNS = [
    r'p\s*[<>=]\s*[\d.]+',
    r'p\s*-\s*value',
    r'statistically\s+significant',
    r'nonsignificant|non-significant|n\.s\.',
    r't\s*\(\s*\d+\s*\)\s*=\s*[\d.]+',
    r'F\s*\(\s*\d+\s*,\s*\d+\s*\)\s*=\s*[\d.]+',
    r'χ²|\\chi\^2|chi[- ]square',
    r'z\s*=\s*[+-]?[\d.]+',
    r'U\s*=\s*[\d.]+',
    r'Mann[- ]Whitney|Wilcoxon|Kruskal[- ]Wallis',
    r'Fisher\s*(?:exact)?',
]

def check_effect_size(text):
    """Check if effect sizes accompany p-values."""
    issues = []

    # Count p-value instances
    p_locations = []
    for pat in PVALUE_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            p_locations.append((m.start(), m.group(0)[:50]))

    # Count effect size instances
    es_count = 0
    es_types = set()
    for pat in EFFECT_SIZE_TERMS:
        matches = re.findall(pat, text, re.IGNORECASE)
        es_count += len(matches)
        if matches:
            es_types.add(pat.split('(')[0].split('?')[0].strip('\\').strip("'"))

    # Check tables for effect size columns
    table_sections = re.findall(r'\\begin\{(?:tabular|table)\}(.*?)\\end\{(?:tabular|table)\}', text, re.DOTALL)
    tables_with_es = 0
    for t in table_sections:
        if re.search(r"d\s*=\s*[\d.]+|Cliff|effect|δ|η²", t, re.IGNORECASE):
            tables_with_es += 1

    if len(p_locations) > 3 and es_count == 0:
        issues.append(('EFFECT_SIZE', 'important',
            f'{len(p_locations)} p-value/statistical test results found but 0 effect sizes. '
            f'Report Cohen\'s d, Cliff\'s δ, or equivalent for main comparisons.'))
    elif len(p_locations) > 3 and es_count < len(p_locations) * 0.3:
        issues.append(('EFFECT_SIZE', 'minor',
            f'{es_count} effect sizes for {len(p_locations)} statistical tests ({es_count/len(p_locations):.0%}). '
            f'Consider adding effect sizes to more comparisons.'))
    elif es_count > 0:
        types_str = ', '.join(sorted(es_types)[:3])
        issues.append(('EFFECT_SIZE', 'pass',
            f'{es_count} effect sizes found ({types_str})'))

    # Check if abstract mentions effect sizes
    abs_match = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', text, re.DOTALL)
    if abs_match:
        abstract = abs_match.group(1)
        abs_p = sum(len(re.findall(p, abstract, re.I)) for p in PVALUE_PATTERNS)
        abs_es = sum(len(re.findall(e, abstract, re.I)) for e in EFFECT_SIZE_TERMS)
        if abs_p > 0 and abs_es == 0:
            issues.append(('ES_ABSTRACT', 'minor',
                'Abstract reports statistical significance without effect size. '
                'Consider adding d/r to strengthen the claim.'))

    return issues


# ============================================================
# Q3: TABLE_FIGURE_CONSISTENCY — Cross-validation
# ============================================================
# Pattern: Extract numbers from tables, figures (captions), and body text.
# Flag when the same metric appears with different values in different places.

def check_table_fig_consistency(text):
    """Cross-validate numbers between tables, figures, and body."""
    issues = []

    # Extract numbers from table environments
    table_nums = {}  # metric -> [(value, location)]
    table_sections = re.finditer(
        r'\\begin\{(?:tabular|table)\*?\}(.*?)\\end\{(?:tabular|table)\*?\}',
        text, re.DOTALL)
    for i, m in enumerate(table_sections):
        table_text = m.group(1)
        # Find labeled metrics with values: e.g., "ECE & 0.042" or "ECE: 0.042"
        for line in table_text.split('\\\\'):
            # Extract metric-value pairs from table cells
            cells = [c.strip() for c in line.split('&')]
            for j, cell in enumerate(cells):
                # Check if cell has a number (must have at least one digit)
                num_match = re.search(r'(\d+\.?\d*)', cell)
                if num_match:
                    val = float(num_match.group(1))
                    # Look for metric label in same row
                    row_text = line[:line.find(cell)] if cell in line else ''
                    # Store with context
                    key = f'table{i}_row{hash(line) % 1000}_col{j}'
                    table_nums[key] = val

    # Extract numbers from figure captions with metric names
    fig_nums = {}
    for m in re.finditer(r'\\caption\{([^}]+)\}', text):
        caption = m.group(1)
        # "ECE of 0.042" or "accuracy = 92.3%" — require metric and number close together
        for nm in re.finditer(
            r'(ECE|accuracy|precision|recall|F1|AUC|AUROC|Brier|NLL|γ|entropy|coupling)'
            r'\s*(?:of|=|:|is|was|≈|~)\s*(\d+\.?\d*)',
            caption, re.IGNORECASE):
            metric = nm.group(1).lower()
            val = float(nm.group(2))
            fig_nums[metric] = (val, caption[:60])

    # Extract numbers from body text with metric names
    body_nums = {}
    # Remove table and figure environments first
    body_text = re.sub(r'\\begin\{(?:tabular|table|figure)\*?\}.*?\\end\{(?:tabular|table|figure)\*?\}',
                       '', text, flags=re.DOTALL)
    for nm in re.finditer(
        r'(ECE|accuracy|precision|recall|F1|AUC|AUROC|Brier|NLL|γ|entropy|coupling)'
        r'[^0-9]*?(?:of|=|:)\s*(\d+\.?\d*)',
        body_text, re.IGNORECASE):
        metric = nm.group(1).lower()
        val = float(nm.group(2))
        if metric not in body_nums:
            body_nums[metric] = []
        body_nums[metric].append((val, nm.group(0)[:60]))

    # Cross-validate body vs figure for same metric
    for metric in set(fig_nums.keys()) & set(body_nums.keys()):
        fig_val = fig_nums[metric][0]
        for body_val, ctx in body_nums[metric]:
            if fig_val != body_val:
                # Allow rounding tolerance
                if abs(fig_val - body_val) > max(0.005, fig_val * 0.05):
                    issues.append(('NUM_INCONSISTENCY', 'important',
                        f'"{metric}" inconsistency: figure says {fig_val}, '
                        f'body says {body_val} ("{ctx}"). Verify which is correct.'))

    # Check for duplicate tables with same caption but different numbers
    captions = re.findall(r'\\caption\{([^}]+)\}', text)
    caption_counts = Counter(captions)
    for cap, count in caption_counts.items():
        if count > 1:
            issues.append(('DUP_CAPTION', 'minor',
                f'Duplicate caption: "{cap[:50]}..." appears {count} times. '
                f'Ensure each has unique content or update labels.'))

    if not issues:
        issues.append(('TABLE_FIG', 'pass', 'No obvious table/figure inconsistencies detected'))

    return issues


# ============================================================
# Q4: SMALL_N_SWEEP — Sensitivity/Ablation with Small N
# ============================================================
# Pattern: Find "N=X" or "X seeds/runs" in context of sweeps/ablations.
# Flag when N < 5 for sensitivity analyses.

def check_small_n_sweep(text):
    """Flag sensitivity/ablation analyses with small sample sizes."""
    issues = []

    # Patterns for sensitivity/ablation contexts
    sweep_context = re.compile(
        r'(?:sensitivity|ablation|sweep|varying|parameter\s+search|grid\s+search|'
        r'hyperparameter|robustness|cooldown|learning.rate\s+sweep)',
        re.IGNORECASE)

    # Find N specifications (avoid matching "N=1,000" or LaTeX "N=2{,}000" as N=1/N=2)
    n_patterns = [
        # "N=3 seeds" or "N = 3 runs"
        (r'[Nn]\s*=\s*(\d+)\s*(?:seeds?|runs?|replications?|trials?|experiments?)', 'explicit'),
        # "3 seeds" or "5 runs"
        (r'(\d+)\s+(?:seeds?|runs?|replications?|trials?)', 'count'),
        # "with 3 repetitions"
        (r'with\s+(\d+)\s+(?:repetitions?|replicates?|copies?)', 'count'),
        # Table headers: "N=3" in column headers (avoid N=1,000 and LaTeX N=2{,}000)
        (r'[Nn]\s*[=:]\s*(\d+)(?!\d|,\d|\{,\})', 'table_n'),
    ]

    # Split text into paragraphs for context
    paragraphs = re.split(r'\n\s*\n', text)

    small_n_sweeps = []
    for para in paragraphs:
        is_sweep = bool(sweep_context.search(para))
        if not is_sweep:
            continue

        for pat, ptype in n_patterns:
            for m in re.finditer(pat, para):
                n_val = int(m.group(1))
                if n_val < 5:
                    ctx = para[max(0, m.start()-30):m.end()+30].replace('\n', ' ')
                    small_n_sweeps.append((n_val, ctx.strip()))

    # Deduplicate
    seen = set()
    for n_val, ctx in small_n_sweeps:
        key = f'{n_val}_{ctx[:40]}'
        if key in seen:
            continue
        seen.add(key)
        if n_val <= 2:
            issues.append(('SMALL_N', 'important',
                f'Sensitivity/ablation with N={n_val}: "{ctx[:70]}..." '
                f'Increase to N≥10 for reliable inference.'))
        elif n_val < 5:
            issues.append(('SMALL_N', 'minor',
                f'Sensitivity/ablation with N={n_val}: "{ctx[:70]}..." '
                f'Consider N≥5 for stable estimates.'))

    # Also check for any "N=X" with X<3 anywhere (likely too small)
    # Avoid LaTeX "N=2{,}000" false positives
    all_ns = re.finditer(r'(?:^|\s)(?:N\s*=\s*|n\s*=\s*)([12])(?!\d|,\d|\{,\})(?:\s|,|\)|$)', text)
    for m in all_ns:
        n_val = int(m.group(1))
        ctx_start = max(0, m.start() - 40)
        ctx = text[ctx_start:m.end()+20].replace('\n', ' ').strip()
        if 'floor' not in ctx.lower() and 'threshold' not in ctx.lower():
            issues.append(('TINY_N', 'minor',
                f'Very small sample: N={n_val} in "{ctx[:60]}..."'))

    if not issues:
        # Count total N values mentioned for context
        all_n_vals = [int(m.group(1)) for m in re.finditer(r'[Nn]\s*=\s*(\d+)', text)]
        if all_n_vals:
            issues.append(('SAMPLE_SIZES', 'pass',
                f'Sample sizes found: N ∈ {{{", ".join(str(n) for n in sorted(set(all_n_vals)))}}}. '
                f'Min={min(all_n_vals)}, no small-N sweeps detected.'))

    return issues


# ============================================================
# Q5: NOTATION_CONSISTENCY — Symbol Definitions
# ============================================================
# Pattern: Track mathematical symbol definitions. Flag when the same
# symbol is defined differently in different locations.

def check_notation_consistency(text):
    """Check for inconsistent symbol/notation definitions."""
    issues = []

    # Track symbol definitions: symbol -> [(definition_context, location)]
    symbol_defs = defaultdict(list)

    # Pattern 1: "X denotes/is defined as/represents Y"
    define_patterns = [
        r'(\$[^$]*?\b([A-Za-z])\b[^$]*?\$)\s*(?:denotes?|is\s+defined\s+as|represents?|stands?\s+for|measures?)\s*([^.,;]+)',
        r'let\s+\$?([A-Za-z])\$?\s*(?:be|denote)\s*([^.,;]+)',
        r'\\(?:text|mathrm)\{([^}]+)\}\s*(?:denotes?|represents?)\s*([^.,;]+)',
        # Greek letters with definitions
        r'\$\\(gamma|alpha|beta|delta|epsilon|theta|mu|sigma|pi)\$\s*(?:denotes?|represents?|measures?|is)\s*([^.,;]+)',
    ]

    for pat in define_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            symbol = m.group(1) if len(m.groups()) >= 2 else ''
            definition = m.group(2) if len(m.groups()) >= 2 else m.group(1)
            symbol = symbol.strip().lower()
            if len(symbol) <= 3:  # Short symbols (single letter or Greek)
                symbol_defs[symbol].append((definition.strip()[:60], m.start()))

    # Check for symbol redefinitions
    for symbol, defs in symbol_defs.items():
        if len(defs) > 1:
            unique_defs = set(d[0].lower() for d in defs)
            if len(unique_defs) > 1:
                locs = [f"pos {d[1]}" for d in defs[:3]]
                issues.append(('NOTATION_REDEF', 'minor',
                    f'Symbol "{symbol}" defined differently:\n'
                    + '\n'.join(f'  - "{d[0]}" at pos {d[1]}' for d in defs[:3])
                    + '\n  Unify definitions or clarify context.'))

    # Check for common notation conflicts
    # γ (gamma) — very common in this portfolio
    gamma_defs = re.findall(
        r'(?:γ|\\gamma)\s*(?:\{[^}]*\})?\s*(?:denotes?|represents?|measures?|is|as)\s*([^.,;]{5,60})',
        text, re.IGNORECASE)
    if len(set(d.strip().lower() for d in gamma_defs)) > 1:
        issues.append(('GAMMA_CONFLICT', 'minor',
            f'γ defined in multiple ways: {"; ".join(d.strip()[:40] for d in gamma_defs[:3])}. '
            f'Clarify if these are different γ\'s or a redefinition.'))

    # Check for undefined key symbols used in equations
    # Find symbols in math mode that are never defined
    math_symbols = set()
    for m in re.finditer(r'\$([^$]+)\$', text):
        eq = m.group(1)
        # Extract single-letter variables (not operators, not numbers)
        for sym in re.findall(r'(?<![a-zA-Z])([A-Z])(?![a-zA-Z])', eq):
            if sym not in ('E', 'N', 'P', 'R', 'T', 'H', 'L', 'I'):  # Common standalone
                math_symbols.add(sym)

    # Check if these are defined somewhere
    for sym in sorted(math_symbols):
        # Check for definition near first use
        first_use = text.find(f'${sym}')
        if first_use < 0:
            first_use = text.find(f'$ {sym}')
        if first_use > 0:
            context = text[max(0, first_use-100):first_use+100]
            if not re.search(rf'{sym}\s*(?:denotes?|is|represents?|where|:=)', context, re.IGNORECASE):
                pass  # Could flag but too noisy — symbols often defined in surrounding text

    if not issues:
        issues.append(('NOTATION', 'pass', 'No obvious notation inconsistencies detected'))

    return issues


# ============================================================
# Q6: MULTIPLE_COMPARISON — Multiple Testing Correction
# ============================================================
# Pattern: Count distinct hypothesis tests (p-values, significance tests).
# Flag when >3 tests appear without mention of correction.

CORRECTION_TERMS = [
    r'bonferroni',
    r'holm',
    r'benjamini',
    r'fdr',
    r'false\s+discovery\s+rate',
    r'family[- ]wise',
    r'multiple\s+(?:comparison|test|testing)',
    r'correction\s+for\s+multiple',
    r'adjusted?\s+p',
    r'q\s*-\s*value',
    r'sidak',
    r'Hochberg',
    r'Hommel',
    r'FWER',
    r'multitest',
]

def check_multiple_comparison(text):
    """Check if multiple hypothesis tests are corrected."""
    issues = []

    # Count distinct p-value mentions
    p_mentions = []
    for m in re.finditer(r'p\s*[<>=]\s*[\d.]+', text, re.IGNORECASE):
        p_mentions.append(m.group(0))

    # Also count test statistics
    test_stats = []
    for pat in [r't\s*\(\s*\d+\s*\)\s*=', r'F\s*\(\s*\d+\s*,\s*\d+\s*\)\s*=',
                r'z\s*=\s*[+-]?[\d.]+', r'χ²\s*=', r'U\s*=\s*[\d.]+']:
        test_stats.extend(re.findall(pat, text))

    total_tests = len(p_mentions) + len(test_stats)

    # Check for correction mentions
    has_correction = False
    correction_found = []
    for pat in CORRECTION_TERMS:
        matches = re.findall(pat, text, re.IGNORECASE)
        if matches:
            has_correction = True
            correction_found.append(pat)

    # Check tables for multiple tests
    table_tests = 0
    table_sections = re.findall(r'\\begin\{(?:tabular|table)\}(.*?)\\end\{(?:tabular|table)\}', text, re.DOTALL)
    for t in table_sections:
        table_tests += len(re.findall(r'[pP]\s*[<>=]\s*[\d.]+', t))
        table_tests += len(re.findall(r'\*', t))  # Stars for significance

    # Report
    if total_tests > 5 and not has_correction:
        issues.append(('MULT_COMPAR', 'important',
            f'{total_tests} hypothesis tests found but no multiple comparison correction '
            f'(Bonferroni, Holm, FDR, etc.). Add correction or justify why not needed.'))
    elif total_tests > 10 and has_correction:
        issues.append(('MULT_COMPAR', 'pass',
            f'{total_tests} tests with correction ({", ".join(correction_found[:2])})'))
    elif total_tests > 3:
        if has_correction:
            issues.append(('MULT_COMPAR', 'pass',
                f'{total_tests} tests, correction applied ({", ".join(correction_found[:2])})'))
        else:
            issues.append(('MULT_COMPAR', 'minor',
                f'{total_tests} statistical tests found. Consider whether correction is needed.'))

    # Check for "all p < 0.05" claims without correction
    all_sig = re.findall(r'all\s+(?:p|P)\s*<\s*[\d.]+', text, re.IGNORECASE)
    if all_sig and not has_correction:
        issues.append(('ALL_SIGNIFICANT', 'minor',
            f'"{all_sig[0]}" claim without multiple comparison correction. '
            f'Individual p-values should be reported with correction.'))

    if not issues:
        issues.append(('MULT_COMPAR', 'pass', f'{total_tests} tests found, no issues'))

    return issues


# ============================================================
# Q7: SELECTIVE_REPORTING — Cherry-picking Detection
# ============================================================
# Pattern: Detect signs of selective reporting:
# - "all significant" claims without individual p-values
# - Only significant results reported (no non-significant mentions)
# - Unequal N across conditions (some conditions much smaller)
# - Missing supplementary material reference

def check_selective_reporting(text):
    """Detect signs of selective reporting / cherry-picking."""
    issues = []

    # Check for "all significant" without individual p-values
    all_sig = re.findall(r'all\s+(?:p|P)\s*<\s*[\d.]+', text, re.IGNORECASE)
    if all_sig:
        issues.append(('ALL_SIGNIFICANT', 'important',
            f'"{all_sig[0]}" claim — list individual p-values for transparency.'))

    # Check for "significant" vs "non-significant" balance
    sig_count = len(re.findall(r'statistically\s+significant|p\s*[<]\s*0\.0[0-5]', text, re.I))
    nonsig_count = len(re.findall(r'nonsignificant|non-significant|n\.s\.|p\s*[>≥]\s*0\.[05]', text, re.I))
    if sig_count > 5 and nonsig_count == 0:
        issues.append(('NO_NONSIG', 'minor',
            f'{sig_count} significant results reported but 0 non-significant. '
            f'Consider reporting null results for transparency.'))

    # Check for unequal N across conditions
    n_values = re.findall(r'N\s*[={}:]\s*(\d+)', text)
    if n_values:
        n_ints = [int(n) for n in n_values if int(n) > 0]
        if n_ints:
            min_n = min(n_ints)
            max_n = max(n_ints)
            if max_n / max(min_n, 1) > 3 and min_n < 10:
                issues.append(('UNEQUAL_N', 'minor',
                    f'Unequal sample sizes: N ranges from {min_n} to {max_n}. '
                    f'Smaller conditions may be underpowered.'))

    # Check for supplementary material reference
    has_supplementary = bool(re.search(
        r'supplementary|supplement|appendix|\\input\{.*?(?:supp|append)',
        text, re.IGNORECASE))
    if not has_supplementary:
        issues.append(('NO_SUPPLEMENTARY', 'minor',
            'No reference to supplementary material. '
            'Consider including detailed results, robustness checks, and code.'))

    # Check for pre-registration mention
    has_prereg = bool(re.search(
        r'pre-?regist|preregist|OSF|AsPredicted|PROSPERO',
        text, re.IGNORECASE))
    if not has_prereg and sig_count > 10:
        issues.append(('NO_PREREG', 'minor',
            f'Large study ({sig_count} significant tests) without pre-registration mention. '
            f'Consider noting exploratory vs confirmatory analyses.'))

    if not issues:
        issues.append(('SELECTIVE_REPORTING', 'pass', 'No signs of selective reporting.'))

    return issues


# ============================================================
# Q8: POWER_ANALYSIS — Statistical Power Check
# ============================================================
# Pattern: For reported N values and effect sizes, estimate whether
# the study has adequate power (≥0.8) for the claimed effects.

def check_power_analysis(text):
    """Check statistical power for reported sample sizes and effect sizes."""
    import math
    issues = []

    # Extract N values from conditions (handle LaTeX formats: N{=}30, $N{=}30$, N=30)
    n_matches = re.findall(r'N\s*\{?=\}?(\d+)', text)
    n_values = sorted(set(int(n) for n in n_matches if 1 < int(n) < 10000))

    # Extract effect sizes (Cohen's d)
    d_matches = re.findall(r'(?:Cohen.?s?\s*d|d)\s*=\s*([+-]?[\d.]+)', text, re.I)
    d_values = [float(d) for d in d_matches if 0 < float(d) < 10]

    if not n_values:
        return [('POWER_NO_N', 'pass', 'No sample sizes detected for power analysis.')]

    # For each N, compute MDE at 80% power
    # MDE = (z_α/2 + z_β) × √(2/N) for two-sample t-test
    # z_0.025 = 1.96, z_0.80 = 0.84
    z_alpha = 1.96
    z_beta = 0.84

    min_n = min(n_values)
    mde = (z_alpha + z_beta) * math.sqrt(2 / min_n)

    if min_n < 10:
        issues.append(('POWER_LOW_N', 'important',
            f'Smallest N={min_n}. MDE at 80% power: d={mde:.2f}. '
            f'Only effects larger than d={mde:.2f} can be detected. '
            f'Consider N≥20 for medium effects (d≥0.5).'))
    elif min_n < 30:
        issues.append(('POWER_MODERATE_N', 'minor',
            f'Smallest N={min_n}. MDE at 80% power: d={mde:.2f}. '
            f'Suitable for large effects but may miss small effects.'))

    # Check if reported effect sizes are detectable at given N
    if d_values:
        underpowered = []
        for d in d_values:
            # Post-hoc power: power = Φ(d×√(N/2) - z_α/2)
            # where Φ is standard normal CDF
            try:
                n_for_d = max(n_values)  # Use largest N as reference
                noncentrality = d * math.sqrt(n_for_d / 2)
                # Approximate power using normal distribution
                power = 1 - 0.5 * (1 + math.erf((z_alpha - noncentrality) / math.sqrt(2)))
                if power < 0.8:
                    underpowered.append((d, n_for_d, power))
            except (ValueError, ZeroDivisionError):
                pass

        if underpowered:
            d_small, n_ref, pw = min(underpowered, key=lambda x: x[2])
            issues.append(('POWER_LOW', 'minor',
                f'Some reported effect sizes (d={d_small:.2f}) may be underpowered '
                f'at N={n_ref} (est. power={pw:.2f}). Interpret with caution.'))

    if not issues:
        issues.append(('POWER', 'pass',
            f'Sample sizes {n_values} provide adequate power for '
            f'MDE≤{mde:.2f} at 80% power.'))

    return issues


# ============================================================
# Q9: BIBENTRY_FORMAT — Bibliography Format Consistency
# ============================================================
# Pattern: Check bibitem entries for:
# - Merged entries (multiple \newblock in one bibitem)
# - Missing fields (title, year, author)
# - Key format consistency

def check_bibentry_format(text):
    """Check bibliography format consistency."""
    issues = []

    # Find all bibitem keys and extract bodies between them
    keys = [m.group(1).strip() for m in re.finditer(r'\\bibitem\[[^\]]*\]\{([^}]+)\}', text)]

    if not keys:
        return [('NO_BIB', 'pass', 'No \\bibitem entries (external .bib may be used).')]

    # Extract body for each entry (text between consecutive bibitems)
    bib_starts = [m.start() for m in re.finditer(r'\\bibitem\[', text)]
    for i, (key, start) in enumerate(zip(keys, bib_starts)):
        end = bib_starts[i + 1] if i + 1 < len(bib_starts) else len(text)
        body = text[start:end]

        # Check for merged entries (multiple \textit{} = multiple titles)
        titles = re.findall(r'\\textit\{([^}]+)\}', body)
        if len(titles) > 1:
            issues.append(('MERGED_BIB', 'critical',
                f"Bibitem '{key}' has {len(titles)} titles — likely merged: "
                f"{'; '.join(t[:35] for t in titles)}. Split into separate entries."))

        # Check for missing fields
        if not re.search(r'\\textit\{', body):
            issues.append(('BIB_NO_TITLE', 'important',
                f"Bibitem '{key}' missing \\textit{{}} title."))
        if not re.search(r'\d{4}', body):
            issues.append(('BIB_NO_YEAR', 'important',
                f"Bibitem '{key}' missing year."))

    # Check key format consistency
    year_pattern = re.compile(r'^[a-z]+\d{4}[a-z]?$')
    non_standard = [k for k in keys if not year_pattern.match(k)]
    if non_standard and len(non_standard) < len(keys):
        issues.append(('BIB_KEY_FORMAT', 'minor',
            f'{len(non_standard)} keys don\'t follow author+year format: '
            f'{", ".join(non_standard[:3])}'))

    if not issues:
        issues.append(('BIBENTRY', 'pass',
            f'{len(keys)} bibitem entries, format consistent.'))

    return issues


# ============================================================
# Q10: HONESTY — Overclaim & Tautology Detection
# ============================================================
# Principle: 诚实性（真理至上）
# Detect when conclusions overstate evidence or when results are
# true by construction presented as empirical discoveries.

def check_honesty(text):
    """Detect overclaims and tautological results."""
    issues = []

    # Check for universal claims from limited data
    universal_claims = re.findall(
        r'(?:all|every|always|never|universally|fundamental(?:ly)?|'
        r'any\s+(?:evaluator|model|system))[^.]*\.',
        text, re.IGNORECASE)

    # Count how many conditions/datasets the paper uses
    n_conditions = len(re.findall(r'condition|dataset|experiment', text, re.IGNORECASE))
    n_models = len(re.findall(r'(?:DeepSeek|GPT|Claude|Qwen|GLM|Llama|Gemini)', text, re.IGNORECASE))

    if universal_claims and n_conditions < 20:
        issues.append(('OVERCLAIM', 'important',
            f'{len(universal_claims)} universal claims with only ~{n_conditions} conditions. '
            f'Soften language: "in the settings tested" or "preliminary evidence suggests".'))

    # Check for "empirical result" claims that might be by-construction
    empirical_claims = re.findall(
        r'empirical\s+(?:result|finding|evidence)[^.]*\.',
        text, re.IGNORECASE)
    construction_indicators = re.findall(
        r'(?:by\s+construction|identical|same\s+(?:model|evaluator|seed)|'
        r'matched\s+seed|re-queried)',
        text, re.IGNORECASE)

    if empirical_claims and construction_indicators:
        issues.append(('TAUTOLOGY_RISK', 'minor',
            f'Paper claims "empirical result" but also mentions construction-like conditions '
            f'({construction_indicators[0][:30]}). Verify the result is not by-construction.'))

    # Check for "first" claims
    first_claims = re.findall(
        r'(?:first|novel|we are the first to|no prior)[^.]*\.',
        text, re.IGNORECASE)
    if first_claims:
        issues.append(('FIRST_CLAIM_CHECK', 'important',
            f'{len(first_claims)} "first"/"novel" claims. '
            f'Verify each against Semantic Scholar before submission.'))

    if not issues:
        issues.append(('HONESTY', 'pass', 'No overclaim or tautology risks detected.'))

    return issues


# ============================================================
# Q11: RIGOR — Proof & Definition Consistency
# ============================================================
# Principle: 严谨性（逻辑闭环）
# Check that theorem statements match their proofs,
# and that definitions are consistent throughout.

def check_rigor(text):
    """Check theorem-proof consistency and definition rigor."""
    issues = []

    # Find all theorem-proof pairs
    theorems = list(re.finditer(
        r'\\begin\{theorem\}(?:\[([^\]]*)\])?\s*(.*?)\\end\{theorem\}',
        text, re.DOTALL))
    proofs = list(re.finditer(
        r'\\begin\{proof\}(?:\[([^\]]*)\])?\s*(.*?)\\end\{proof\}',
        text, re.DOTALL))

    for thm in theorems:
        thm_label = thm.group(1) or ''
        thm_body = thm.group(2)

        # Extract key variables from theorem statement
        thm_vars = set(re.findall(r'\\(?:gamma|alpha|beta|sigma|epsilon|delta|mu|theta|'
                                   r'mathrm\{CV\}|mathrm\{ECE\}|mathbf\{w\})', thm_body))

        # Find matching proof (nearest proof after theorem)
        thm_end = thm.end()
        matching_proof = None
        for pr in proofs:
            if pr.start() > thm_end:
                matching_proof = pr
                break

        if matching_proof:
            proof_body = matching_proof.group(2)
            proof_vars = set(re.findall(r'\\(?:gamma|alpha|beta|sigma|epsilon|delta|mu|theta|'
                                         r'mathrm\{CV\}|mathrm\{ECE\}|mathbf\{w\})', proof_body))

            # Check if theorem variables appear in proof
            missing_in_proof = thm_vars - proof_vars
            if missing_in_proof and len(missing_in_proof) > 1:
                issues.append(('THEOREM_PROOF', 'important',
                    f'Theorem "{thm_label[:30]}" uses variables {missing_in_proof} '
                    f'that don\'t appear in its proof. Verify alignment.'))

    # Check for "proof sketch" without references
    proof_sketches = re.findall(r'\\begin\{proof\}\[Proof sketch\]', text, re.IGNORECASE)
    if proof_sketches:
        # Check if nearby text has citations
        for m in re.finditer(r'\\begin\{proof\}\[Proof sketch\]', text, re.IGNORECASE):
            context = text[m.end():m.end()+500]
            has_cite = bool(re.search(r'\\cite', context))
            if not has_cite:
                issues.append(('PROOF_SKETCH', 'important',
                    'Proof sketch without citation for non-trivial steps. '
                    'Add references or complete the proof.'))

    # Check for undefined constants
    undefined_consts = re.findall(
        r'where\s+\$c_(\d+)\s*>\s*0\$', text)
    if undefined_consts:
        for c in undefined_consts:
            # Check if c_N is given a value anywhere
            if not re.search(rf'c_{c}\s*=\s*[\d.]', text):
                issues.append(('UNDEFINED_CONST', 'minor',
                    f'Constant c_{c} is declared positive but never quantified. '
                    f'Consider giving its value or range.'))

    if not issues:
        issues.append(('RIGOR', 'pass', 'Theorem-proof consistency verified.'))

    return issues


# ============================================================
# Q12: ORIGINALITY — Novelty Verification
# ============================================================
# Principle: 原创性与问题意识
# Check that research gap is clearly identified and
# novelty claims are properly positioned.

def check_originality(text):
    """Check research gap identification and novelty positioning."""
    issues = []

    # Check if introduction identifies a clear gap
    intro_match = re.search(
        r'\\section\{Introduction\}(.*?)\\section\{',
        text, re.DOTALL)
    if intro_match:
        intro = intro_match.group(1)
        gap_indicators = re.findall(
            r'(?:gap|missing|unknown|unresolved|open\s+question|'
            r'prior\s+work\s+(?:has\s+)?not|no\s+prior|'
            r'remains\s+unclear|not\s+(?:yet\s+)?(?:been|understood))',
            intro, re.IGNORECASE)
        if not gap_indicators:
            issues.append(('NO_GAP', 'minor',
                'Introduction does not explicitly identify a research gap. '
                'Add: "Prior work has not addressed..." or similar.'))

    # Check contribution list
    contrib_match = re.search(
        r'\\(?:textbf\{Contributions?:?\}|begin\{enumerate\})(.*?)\\end\{enumerate\}',
        text, re.DOTALL)
    if contrib_match:
        contrib = contrib_match.group(1)
        items = re.findall(r'\\item\s+(.*?)(?=\\item|\\end)', contrib, re.DOTALL)
        for item in items:
            item_clean = re.sub(r'\\[a-z]+\{[^}]*\}', '', item).strip()[:80]
            # Check if contribution is just a method description
            if re.search(r'we\s+(?:provide|derive|prove|show|demonstrate)', item, re.I):
                pass  # Good — finding/method claim
            elif re.search(r'we\s+(?:use|apply|combine|extend)', item, re.I):
                issues.append(('CONTRIB_METHOD', 'minor',
                    f'Contribution "{item_clean[:60]}..." may be a method description, '
                    f'not a finding. Reframe as "We show that..."'))

    if not issues:
        issues.append(('ORIGINALITY', 'pass', 'Research gap and novelty properly positioned.'))

    return issues


# ============================================================
# Q13: REPRODUCIBILITY — Method Transparency
# ============================================================
# Principle: 可复现性与方法透明
# Check that key methodological details are provided.

def check_reproducibility(text):
    """Check method transparency and reproducibility."""
    issues = []

    # Check for key reproducibility elements
    has_seed = bool(re.search(r'(?:random\s+seed|seed\s*=\s*\d|seeded|reproducib)', text, re.I))
    has_model_version = bool(re.search(r'(?:version[- ]lock|API.*?version|model.*?version|'
                                        r'gpt-4o-\d|deepseek.*?v\d|claude.*?v\d)', text, re.I))
    has_hyperparams = bool(re.search(r'(?:learning\s+rate|temperature|batch\s+size|'
                                      r'α\s*=\s*[\d.]+|temp\s*=\s*[\d.]+)', text, re.I))
    has_data_split = bool(re.search(r'(?:train.*?test|train.*?val|fold|split)', text, re.I))
    has_code = bool(re.search(r'(?:code.*?(?:available|github|supplementary)|'
                               r'reproducib.*?statement)', text, re.I))

    missing = []
    if not has_seed:
        missing.append('random seeds')
    if not has_model_version:
        missing.append('model/API versions')
    if not has_hyperparams:
        missing.append('hyperparameters')
    if not has_code:
        missing.append('code availability')

    if len(missing) >= 3:
        issues.append(('REPRODUCIBILITY', 'important',
            f'Missing reproducibility elements: {", ".join(missing)}. '
            f'Add details to Methods or Reproducibility Statement.'))
    elif missing:
        issues.append(('REPRODUCIBILITY', 'minor',
            f'Consider adding: {", ".join(missing)}.'))

    # Check for "will be available upon acceptance"
    upon_acceptance = re.findall(
        r'will\s+be\s+(?:made\s+)?available\s+upon\s+acceptance',
        text, re.I)
    if upon_acceptance:
        issues.append(('CODE_UPON_ACCEPT', 'minor',
            'Code "available upon acceptance" — reviewers cannot verify. '
            'Consider providing anonymous link now.'))

    if not issues:
        issues.append(('REPRODUCIBILITY', 'pass', 'Key reproducibility elements present.'))

    return issues


# ============================================================
# Q14: CITATION_INTEGRITY — Citation Quality
# ============================================================
# Principle: 规范引注与知识产权
# Check citation quality beyond format.

def check_citation_integrity(text):
    """Check citation quality and integrity."""
    issues = []

    # Extract all cite keys
    cited = set()
    for m in re.finditer(r'\\cite[tp]?\{([^}]+)\}', text):
        for k in m.group(1).split(','):
            cited.add(k.strip())

    # Self-citation detection
    self_cites = {k for k in cited if 'liu202' in k.lower()}
    total = len(cited)
    if total > 0:
        self_rate = len(self_cites) / total
        if self_rate > 0.5:
            issues.append(('SELF_CITE_HIGH', 'important',
                f'Self-citation rate: {self_rate:.0%} ({len(self_cites)}/{total}). '
                f'High self-citation undermines credibility. Add external references.'))
        elif self_rate > 0.3:
            issues.append(('SELF_CITE_MODERATE', 'minor',
                f'Self-citation rate: {self_rate:.0%} ({len(self_cites)}/{total}). '
                f'Consider adding more external references.'))

    # Check for "et al." without enough authors
    et_al = re.findall(r'\\citet?\{([^}]+)\}', text)
    single_author_refs = 0
    for ref_block in et_al:
        keys = ref_block.split(',')
        for k in keys:
            k = k.strip()
            # If key looks like single-author (e.g., "liu2026impossible")
            if re.match(r'^[a-z]+\d{4}[a-z]?$', k):
                single_author_refs += 1

    # Check for "Manuscript" or "unpublished" references
    bibtext = text
    manuscript_refs = re.findall(
        r'\\bibitem.*?Manuscript.*?\\newblock',
        bibtext, re.DOTALL | re.IGNORECASE)
    if manuscript_refs:
        issues.append(('MANUSCRIPT_REFS', 'minor',
            f'{len(manuscript_refs)} reference(s) marked as "Manuscript". '
            f'Provide arXiv links or publication status.'))

    if not issues:
        issues.append(('CITE_INTEGRITY', 'pass',
            f'Citation integrity OK. {total} refs, {len(self_cites)} self-cites.'))

    return issues


# ============================================================
# Q15: HUMILITY — Limitation & Alternative Explanations
# ============================================================
# Principle: 批判精神与谦逊开放
# Check that limitations are honest and alternatives considered.

def check_humility(text):
    """Check limitation honesty and alternative explanations."""
    issues = []

    # Find limitations section
    lim_match = re.search(
        r'\\(?:sub)?section\{Limitations?\}(.*?)\\(?:sub)?section\{',
        text, re.DOTALL | re.IGNORECASE)
    if lim_match:
        limitations = lim_match.group(1)
        lim_items = re.findall(r'\\item\s+(.*?)(?=\\item|\\end)', limitations, re.DOTALL)

        if len(lim_items) < 2:
            issues.append(('FEW_LIMITATIONS', 'minor',
                f'Only {len(lim_items)} limitation(s) discussed. '
                f'Consider adding: dataset breadth, model diversity, statistical power.'))

        # Check if limitations discuss impact on conclusions
        impact_discussed = bool(re.search(
            r'(?:affects?|impacts?|limits?|weakens?|undermines?|caveat|'
            r'conclusions?\s+(?:are|may\s+be)\s+(?:limited|qualified))',
            limitations, re.I))
        if not impact_discussed:
            issues.append(('LIM_NO_IMPACT', 'minor',
                'Limitations section lists constraints but doesn\'t discuss '
                'how they affect main conclusions. Add: "This means our results may not generalize to..."'))
    else:
        issues.append(('NO_LIMITATIONS', 'important',
            'No Limitations section found. Add one — every paper has limitations.'))

    # Check for alternative explanations in discussion
    disc_match = re.search(
        r'\\(?:sub)?section\{Discussion\}(.*?)\\(?:sub)?section\{',
        text, re.DOTALL | re.IGNORECASE)
    if disc_match:
        discussion = disc_match.group(1)
        alternatives = re.findall(
            r'(?:alternative|confound|could\s+also\s+be|another\s+explanation|'
            r'it\s+is\s+possible\s+that|one\s+might\s+argue)',
            discussion, re.I)
        if not alternatives:
            issues.append(('NO_ALTERNATIVES', 'minor',
                'Discussion does not consider alternative explanations for results. '
                'Add: "An alternative explanation is..." or "One confound is..."'))

    if not issues:
        issues.append(('HUMILITY', 'pass', 'Limitations and alternatives properly discussed.'))

    return issues


# ============================================================
# Run all checks
# ============================================================

def run_all_checks(text, checks=None):
    """Run specified or all quality checks.

    Args:
        text: LaTeX source text
        checks: list of check names, or None for all

    Returns:
        dict mapping check name -> list of (id, severity, message) tuples
    """
    all_checks = {
        'ci': ('CI_COVERAGE', check_ci_coverage),
        'es': ('EFFECT_SIZE', check_effect_size),
        'tf': ('TABLE_FIG', check_table_fig_consistency),
        'sn': ('SMALL_N', check_small_n_sweep),
        'nc': ('NOTATION', check_notation_consistency),
        'mc': ('MULT_COMPAR', check_multiple_comparison),
        'sr': ('SELECTIVE_REPORTING', check_selective_reporting),
        'pa': ('POWER_ANALYSIS', check_power_analysis),
        'bf': ('BIBENTRY_FORMAT', check_bibentry_format),
        # Academic principles (v5.3)
        'ho': ('HONESTY', check_honesty),
        'rg': ('RIGOR', check_rigor),
        'og': ('ORIGINALITY', check_originality),
        'rp': ('REPRODUCIBILITY', check_reproducibility),
        'ci2': ('CITE_INTEGRITY', check_citation_integrity),
        'hm': ('HUMILITY', check_humility),
    }

    if checks is None:
        checks = list(all_checks.keys())
    else:
        checks = [c.strip() for c in checks.split(',')]

    results = {}
    for key in checks:
        if key in all_checks:
            name, func = all_checks[key]
            results[name] = func(text)

    return results


def print_report(paper_id, results):
    """Pretty-print quality check results."""
    print(f"\n{'='*65}")
    print(f"📊 Quality Checks — {paper_id}")
    print(f"{'='*65}")

    total_pass = total_issues = 0
    for check_name, items in results.items():
        print(f"\n  ▸ {check_name}")
        for item in items:
            code, severity, msg = item
            if severity == 'pass':
                print(f"    ✅ [{code}] {msg}")
                total_pass += 1
            elif severity == 'important':
                print(f"    🟡 [{code}] {msg}")
                total_issues += 1
            elif severity == 'minor':
                print(f"    🟢 [{code}] {msg}")
                total_issues += 1
            else:
                print(f"    • [{code}] {msg}")

    print(f"\n{'='*65}")
    print(f"  Summary: {total_pass} passed, {total_issues} issues found")
    print(f"{'='*65}")

    return total_issues


def main():
    parser = argparse.ArgumentParser(
        description='Loop Engineering v5.3 — Paper Quality Checks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Checks:
  ci  — CI_COVERAGE:        Confidence interval coverage
  es  — EFFECT_SIZE:         Effect size reporting
  tf  — TABLE_FIG_CONSIST:   Table/figure/body consistency
  sn  — SMALL_N_SWEEP:       Small N in sensitivity analyses
  nc  — NOTATION_CONSIST:    Symbol definition consistency
  mc  — MULTIPLE_COMPAR:     Multiple comparison correction
  sr  — SELECTIVE_REPORTING: Cherry-picking detection
  pa  — POWER_ANALYSIS:      Statistical power analysis
  bf  — BIBENTRY_FORMAT:     Bibliography format consistency

Examples:
  python quality_checks.py FLAGSHIP
  python quality_checks.py FLAGSHIP --check ci,mc,pa
  python quality_checks.py FLAGSHIP --json
        """)
    parser.add_argument('paper_id', help='Paper ID or path to .tex file')
    parser.add_argument('--check', '-c', default=None,
                       help='Comma-separated checks: ci,es,tf,sn,nc,mc (default: all)')
    parser.add_argument('--json', '-j', action='store_true', help='JSON output')

    args = parser.parse_args()

    # Try to find paper in registry
    tex_path = None
    paper_id = args.paper_id

    registry_path = LOOP_DIR / 'registry.yaml'
    if registry_path.exists():
        import yaml
        reg = yaml.safe_load(registry_path.read_text(encoding='utf-8'))
        for key, p in reg.get('papers', {}).items():
            if p['id'] == paper_id:
                paper_dir = AETTL_DIR / p['path']
                for name in ['main_merged.tex', 'main_tmlr.tex', 'main.tex']:
                    candidate = paper_dir / name
                    if candidate.exists():
                        tex_path = candidate
                        break
                break

    # Fallback: try direct path
    if tex_path is None:
        candidate = Path(paper_id)
        if candidate.exists():
            tex_path = candidate
        else:
            # Try common locations
            for loc in [AETTL_DIR / paper_id / 'main.tex',
                       AETTL_DIR / paper_id / 'main_merged.tex',
                       AETTL_DIR / paper_id / 'main_tmlr.tex']:
                if loc.exists():
                    tex_path = loc
                    break

    if tex_path is None:
        print(f"❌ Paper '{paper_id}' not found. Provide paper ID or path to .tex file.")
        sys.exit(1)

    text = tex_path.read_text(encoding='utf-8', errors='ignore')
    results = run_all_checks(text, args.check)

    if args.json:
        # Flatten for JSON
        flat = []
        for check_name, items in results.items():
            for code, severity, msg in items:
                flat.append({'check': check_name, 'code': code,
                           'severity': severity, 'message': msg})
        print(json.dumps({'paper_id': paper_id, 'file': str(tex_path),
                         'checks': flat}, indent=2))
    else:
        print_report(paper_id, results)


if __name__ == '__main__':
    main()
