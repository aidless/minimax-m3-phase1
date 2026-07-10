#!/usr/bin/env python3
"""Loop Engineering v5.3 — Agent Review Integration
Manages agent-based semantic review within the audit pipeline.

Usage:
  python agent_review.py PAPER_ID --generate   # Generate review prompt
  python agent_review.py PAPER_ID --parse response.md  # Parse agent response
  python agent_review.py PAPER_ID --report     # Show cached review
"""
import re, sys, json, argparse, yaml
from pathlib import Path
from datetime import datetime

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent
REVIEWS_DIR = LOOP_DIR / 'reviews'

# ============================================================
# Review Prompt Template
# ============================================================
REVIEW_PROMPT = """You are an expert academic paper reviewer for TMLR/arXiv submissions.
Review the following paper with extreme rigor. Focus ONLY on issues that require semantic understanding — do NOT flag formatting, grammar, or citation format issues (automated tools handle those).

## Paper
{paper_text}

## Review Dimensions

### 1. Experiment Design Validity
- Confounds (changing multiple variables simultaneously)?
- Fair comparisons (same N, same conditions, same metrics)?
- Control conditions truly controls?
- Hidden assumptions that could invalidate results?

### 2. Claim-Evidence Alignment
- Does abstract overstate results?
- Are "first"/"novel" claims supported?
- Do conclusions follow from data?
- Unsupported extrapolations?

### 3. Logical Consistency
- Contradictions between sections?
- Sound argument structure?
- Honest limitations?
- Findings contradict each other?

### 4. Methodological Gaps
- Missing baselines/comparisons?
- Incomplete ablation studies?
- Statistical issues (sample size, power, multiple comparisons)?
- Reproducibility concerns?

### 5. Literature Positioning
- Key prior works cited?
- Defensible novelty claim?
- Alternative approaches discussed?

## Output Format (JSON)
Return a JSON object:
```json
{{
  "overall_assessment": "one paragraph summary",
  "score": 1-10,
  "issues": [
    {{
      "dimension": "experiment_design|claim_evidence|logic|methodology|literature",
      "severity": "critical|important|minor",
      "location": "section/subsection",
      "issue": "concise description",
      "evidence": "specific quote or data from paper",
      "fix": "concrete suggestion"
    }}
  ],
  "strengths": ["list"],
  "verdict": "ready|revision_needed|not_ready"
}}
```

Be strict. Be specific. Every issue must cite evidence from the paper. Output ONLY the JSON."""

# ============================================================
# Core Functions
# ============================================================

def load_paper(paper_id):
    """Load paper from registry."""
    registry = yaml.safe_load((LOOP_DIR / 'registry.yaml').read_text(encoding='utf-8'))
    for k, p in registry['papers'].items():
        if p['id'] == paper_id:
            paper_dir = AETTL_DIR / p['path']
            tex_files = (list(paper_dir.glob('main_merged.tex')) or
                        list(paper_dir.glob('main_tmlr.tex')) or
                        list(paper_dir.glob('main.tex')))
            if tex_files:
                return {
                    'id': paper_id,
                    'title': p.get('short_title', paper_id),
                    'text': tex_files[0].read_text(encoding='utf-8', errors='ignore'),
                    'path': str(tex_files[0]),
                    'dir': str(paper_dir),
                }
    return None

def generate_prompt(paper_id):
    """Generate agent review prompt and save to file."""
    paper = load_paper(paper_id)
    if not paper:
        return None, f"Paper '{paper_id}' not found"

    # Truncate bibliography
    text = paper['text']
    bib_start = text.find('\\begin{thebibliography}')
    if bib_start > 0:
        text = text[:bib_start] + '\n\n[Bibliography omitted]\n'

    prompt = REVIEW_PROMPT.format(paper_text=text)

    # Save prompt
    REVIEWS_DIR.mkdir(exist_ok=True)
    prompt_file = REVIEWS_DIR / f"{paper_id}_prompt.md"
    prompt_file.write_text(prompt, encoding='utf-8')

    return prompt, str(prompt_file)

def parse_response(response_text, paper_id=None):
    """Parse agent JSON response into structured review."""
    # Try to extract JSON
    json_match = re.search(r'\{[\s\S]*"issues"[\s\S]*\}', response_text)
    if json_match:
        try:
            result = json.loads(json_match.group(0))
            # Save parsed result
            if paper_id:
                REVIEWS_DIR.mkdir(exist_ok=True)
                result_file = REVIEWS_DIR / f"{paper_id}_review.json"
                result['paper_id'] = paper_id
                result['timestamp'] = datetime.now().isoformat()
                result_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
            return result
        except json.JSONDecodeError:
            pass

    return {
        'overall_assessment': response_text[:500],
        'score': 0,
        'issues': [],
        'strengths': [],
        'verdict': 'parse_error',
    }

def load_cached_review(paper_id):
    """Load cached agent review if available."""
    result_file = REVIEWS_DIR / f"{paper_id}_review.json"
    if result_file.exists():
        return json.loads(result_file.read_text(encoding='utf-8'))
    return None

def format_for_audit(result):
    """Convert agent review to audit issue format (code, severity, msg)."""
    if not result or not result.get('issues'):
        return []

    issues = []
    for item in result['issues']:
        sev = item.get('severity', 'minor')
        dim = item.get('dimension', 'unknown')[:10]
        loc = item.get('location', '')
        issue_text = item.get('issue', '')
        fix = item.get('fix', '')

        # Map to audit severity
        if sev == 'critical':
            audit_sev = 'important'  # Downgrade to important (agent reviews are heuristic)
        elif sev == 'important':
            audit_sev = 'important'
        else:
            audit_sev = 'minor'

        msg = f"[{dim}] {issue_text}"
        if fix:
            msg += f" → {fix[:60]}"

        issues.append((f'AGENT_{dim.upper()[:8]}', audit_sev, msg[:150]))

    return issues

# ============================================================
# CLI
# ============================================================

def print_report(result):
    """Pretty-print agent review."""
    if not result:
        print("❌ No cached review found. Run: python agent_review.py PAPER_ID --generate")
        return

    print(f"\n{'='*65}")
    print(f"🤖 Agent Review — {result.get('paper_id', '?')}")
    if result.get('timestamp'):
        print(f"   {result['timestamp']}")
    print(f"{'='*65}")

    if result.get('overall_assessment'):
        print(f"\n  📝 {result['overall_assessment'][:300]}...")

    if result.get('score'):
        score = result['score']
        emoji = '✅' if score >= 8 else '⚠️' if score >= 6 else '🔴'
        print(f"\n  {emoji} Score: {score}/10")

    if result.get('issues'):
        crit = [i for i in result['issues'] if i.get('severity') == 'critical']
        imp = [i for i in result['issues'] if i.get('severity') == 'important']
        minor = [i for i in result['issues'] if i.get('severity') == 'minor']

        if crit:
            print(f"\n  🔴 Critical ({len(crit)}):")
            for i in crit:
                print(f"    [{i.get('dimension','?')[:8]}] {i.get('issue','')[:80]}")
        if imp:
            print(f"\n  🟡 Important ({len(imp)}):")
            for i in imp:
                print(f"    [{i.get('dimension','?')[:8]}] {i.get('issue','')[:80]}")
        if minor:
            print(f"\n  🟢 Minor ({len(minor)}):")
            for i in minor:
                print(f"    [{i.get('dimension','?')[:8]}] {i.get('issue','')[:80]}")

    if result.get('strengths'):
        print(f"\n  ✅ Strengths ({len(result['strengths'])}):")
        for s in result['strengths'][:3]:
            print(f"    • {s[:80]}")

    if result.get('verdict'):
        v = {'ready': '✅ Ready', 'revision_needed': '⚠️ Revision Needed', 'not_ready': '🔴 Not Ready'}
        print(f"\n  Verdict: {v.get(result['verdict'], result['verdict'])}")

    print(f"\n{'='*65}")

def main():
    parser = argparse.ArgumentParser(description='Loop Engineering v5.3 — Agent Review')
    parser.add_argument('paper_id', help='Paper ID')
    parser.add_argument('--generate', '-g', action='store_true', help='Generate review prompt')
    parser.add_argument('--parse', '-p', help='Parse agent response from file')
    parser.add_argument('--report', '-r', action='store_true', help='Show cached review')
    parser.add_argument('--json', '-j', action='store_true', help='JSON output')
    args = parser.parse_args()

    if args.generate:
        prompt, path = generate_prompt(args.paper_id)
        if prompt:
            print(f"✅ Prompt generated: {path}")
            print(f"   Length: {len(prompt)} chars")
            print(f"   To review: send prompt to agent, save response, then:")
            print(f"   python agent_review.py {args.paper_id} --parse response.md")
        else:
            print(f"❌ {path}")

    elif args.parse:
        response = Path(args.parse).read_text(encoding='utf-8')
        result = parse_response(response, args.paper_id)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print_report(result)

    elif args.report:
        result = load_cached_review(args.paper_id)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print_report(result)

    else:
        parser.print_help()

if __name__ == '__main__':
    main()
