#!/usr/bin/env python3
"""Loop Engineering v5.3 — Agent-Based Semantic Review
Uses ZCode Agent for semantic-level paper review that regex cannot do.

Usage:
  python review_agent.py PAPER_ID          # Generate agent review prompt
  python review_agent.py PAPER_ID --output prompt.md  # Save prompt to file

The actual agent review is run via ZCode's Agent tool:
  /review PAPER_ID  (triggers agent automatically)
"""

import sys, json, argparse, re
from pathlib import Path

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

# ============================================================
# Review Prompt Template
# ============================================================
REVIEW_PROMPT = """You are an expert academic paper reviewer for TMLR/arXiv submissions. 
Review the following paper with extreme rigor. Focus ONLY on issues that require 
semantic understanding — do NOT flag formatting, grammar, or citation format issues 
(automated tools handle those).

## Paper
{paper_text}

## Review Dimensions

### 1. Experiment Design Validity
- Are there confounds? (e.g., changing multiple variables simultaneously)
- Are comparisons fair? (same N, same conditions, same metrics)
- Is the control condition truly a control?
- Are there hidden assumptions that could invalidate results?

### 2. Claim-Evidence Alignment
- Does the abstract overstate the results?
- Are "first" / "novel" claims supported by the evidence?
- Do the conclusions follow from the data?
- Are there unsupported extrapolations?

### 3. Logical Consistency
- Are there contradictions between sections?
- Is the argument structure sound?
- Are limitations honestly stated?
- Do findings contradict each other?

### 4. Methodological Gaps
- Missing baselines or comparisons?
- Incomplete ablation studies?
- Statistical issues (sample size, power, multiple comparisons)?
- Reproducibility concerns?

### 5. Literature Positioning
- Are key prior works cited?
- Is the novelty claim defensible?
- Are alternative approaches discussed?

## Output Format (JSON)
Return a JSON object with this structure:
```json
{{
  "overall_assessment": "one paragraph summary",
  "score": 1-10,
  "issues": [
    {{
      "dimension": "experiment_design|claim_evidence|logic|methodology|literature",
      "severity": "critical|important|minor",
      "location": "section/subsection where the issue appears",
      "issue": "concise description of the problem",
      "evidence": "specific quote or data point from the paper",
      "fix": "concrete suggestion for fixing"
    }}
  ],
  "strengths": ["list of paper strengths"],
  "verdict": "ready|revision_needed|not_ready"
}}
```

Be strict. Be specific. Every issue must cite evidence from the paper.
"""

def load_paper(paper_id):
    """Load paper text from registry."""
    import yaml
    registry = yaml.safe_load((LOOP_DIR / 'registry.yaml').read_text(encoding='utf-8'))

    for k, p in registry['papers'].items():
        if p['id'] == paper_id:
            paper_dir = AETTL_DIR / p['path']
            tex_files = (list(paper_dir.glob('main_merged.tex')) or
                        list(paper_dir.glob('main_tmlr.tex')) or
                        list(paper_dir.glob('main.tex')))
            if tex_files:
                text = tex_files[0].read_text(encoding='utf-8', errors='ignore')
                return {
                    'paper_id': paper_id,
                    'title': p.get('short_title', paper_id),
                    'text': text,
                    'path': str(tex_files[0]),
                }
    return None

def generate_prompt(paper_id):
    """Generate the review agent prompt for a paper."""
    paper = load_paper(paper_id)
    if not paper:
        return None

    # Truncate if too long (agent context limits)
    text = paper['text']
    if len(text) > 50000:
        # Keep abstract, methods, results, discussion; trim bibliography
        bib_start = text.find('\\begin{thebibliography}')
        if bib_start > 0:
            text = text[:bib_start] + '\n\n[Bibliography omitted for brevity]\n'

    prompt = REVIEW_PROMPT.format(paper_text=text)
    return prompt

def parse_agent_response(response_text):
    """Parse agent's JSON response into structured issues."""
    # Try to extract JSON from response
    json_match = re.search(r'\{[\s\S]*"issues"[\s\S]*\}', response_text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback: parse as text
    return {
        'overall_assessment': response_text[:500],
        'score': 0,
        'issues': [],
        'strengths': [],
        'verdict': 'unknown',
    }

def print_report(result):
    """Pretty-print agent review results."""
    if not result:
        print("❌ No review results")
        return

    print(f"\n{'='*65}")
    print(f"🤖 Agent Review")
    print(f"{'='*65}")

    if result.get('overall_assessment'):
        print(f"\n  📝 {result['overall_assessment'][:200]}...")

    if result.get('score'):
        score = result['score']
        emoji = '✅' if score >= 8 else '⚠️' if score >= 6 else '🔴'
        print(f"\n  {emoji} Score: {score}/10")

    if result.get('issues'):
        print(f"\n  Issues ({len(result['issues'])}):")
        for issue in result['issues']:
            sev = issue.get('severity', 'unknown')
            icon = {'critical': '🔴', 'important': '🟡', 'minor': '🟢'}.get(sev, '•')
            dim = issue.get('dimension', '?')[:15]
            print(f"    {icon} [{dim}] {issue.get('issue', '')[:80]}")
            if issue.get('evidence'):
                print(f"       Evidence: {issue['evidence'][:60]}")
            if issue.get('fix'):
                print(f"       Fix: {issue['fix'][:60]}")

    if result.get('strengths'):
        print(f"\n  Strengths:")
        for s in result['strengths'][:3]:
            print(f"    ✅ {s}")

    if result.get('verdict'):
        verdict_emoji = {'ready': '✅', 'revision_needed': '⚠️', 'not_ready': '🔴'}.get(result['verdict'], '❓')
        print(f"\n  {verdict_emoji} Verdict: {result['verdict']}")

    print(f"\n{'='*65}")

def main():
    parser = argparse.ArgumentParser(description='Loop Engineering v5.3 — Agent Review')
    parser.add_argument('paper_id', help='Paper ID')
    parser.add_argument('--output', '-o', help='Save prompt to file')
    parser.add_argument('--json', '-j', action='store_true', help='JSON output')
    args = parser.parse_args()

    prompt = generate_prompt(args.paper_id)
    if not prompt:
        print(f"❌ Paper '{args.paper_id}' not found")
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(prompt, encoding='utf-8')
        print(f"✅ Prompt saved to {args.output}")
    else:
        print(f"Prompt length: {len(prompt)} chars")
        print(f"To run agent review, use: /review {args.paper_id}")

if __name__ == '__main__':
    main()
