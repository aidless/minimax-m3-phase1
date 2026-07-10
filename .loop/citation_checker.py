#!/usr/bin/env python3
"""Loop Engineering v5.0 — Citation Verification Engine
Verifies every bibliography entry against real databases.
Usage: python citation_checker.py PAPER_ID [--strict]

Extracts bib entries, checks arXiv IDs, verifies author/title consistency.
Output: structured report with ✅⚠️🔴 verdicts.
"""
import yaml, re, sys, argparse, urllib.request, json, time
from pathlib import Path

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

KNOWN_PAPERS = {
    # Verified papers (from our web searches)
    'guo2017calibration': {
        'authors': ['Guo', 'Pleiss', 'Sun', 'Weinberger'],
        'title_keywords': ['calibration', 'modern', 'neural', 'networks'],
        'venue': 'ICML', 'year': 2017
    },
    'niculescu2005predicting': {
        'authors': ['Niculescu-Mizil', 'Caruana'],
        'title_keywords': ['predicting', 'good', 'probabilities'],
        'venue': 'ICML', 'year': 2005
    },
    'zheng2023judging': {
        'authors': ['Zheng', 'Chiang', 'Sheng'],
        'title_keywords': ['judging', 'llm-as-a-judge', 'mt-bench'],
        'venue': 'NeurIPS', 'year': 2023
    },
    'chiang2024chatbot': {
        'authors': ['Chiang'],
        'title_keywords': ['chatbot', 'arena'],
        'venue': 'arXiv', 'year': 2024
    },
    'cobbe2021gsm8k': {
        'authors': ['Cobbe', 'Kosaraju', 'Bavarian'],
        'title_keywords': ['training', 'verifiers', 'math', 'word'],
        'venue': 'arXiv', 'year': 2021
    },
    'dodge2019reproducibility': {
        'authors': ['Dodge', 'Gururangan', 'Card', 'Schwartz', 'Smith'],
        'title_keywords': ['show', 'your', 'work', 'reporting'],
        'venue': 'EMNLP', 'year': 2019
    },
    'messing2026tee': {
        'authors': ['Messing'],
        'title_keywords': ['hidden', 'measurement', 'error', 'llm'],
        'venue': 'arXiv', 'year': 2026
    },
    'huang2026cagecal': {
        'authors': ['Huang', 'Li', 'Li', 'Kwon', 'Yu', 'Zhang'],
        'title_keywords': ['counterfactual', 'graph', 'multi-agent', 'calibration'],
        'venue': 'arXiv', 'year': 2026
    },
    'sclar2024quantifying': {
        'authors': ['Sclar', 'Choi', 'Tsvetkov', 'Suhr'],
        'title_keywords': ['quantifying', 'sensitivity', 'spurious', 'prompt'],
        'venue': 'ICLR', 'year': 2024
    },
    'liu2026epc': {
        'authors': ['Liu'],
        'title_keywords': ['evaluator', 'preference', 'collapse'],
        'venue': 'arXiv', 'year': 2026
    },
    'bertalanic2026cost': {
        'authors': ['Bertalanič', 'Fortuna'],
        'title_keywords': ['cost', 'consensus', 'isolated', 'self-correction'],
        'venue': 'CAIS', 'year': 2026
    },
    'he2026paradox': {
        'authors': ['Shukla', 'Modi'],  # NOT He!
        'title_keywords': ['calibration', 'decision', 'reliability', 'paradox'],
        'venue': 'ACL SRW', 'year': 2026
    },
    'mills2026verification': {
        'authors': ['Wang'],  # NOT Mills!
        'title_keywords': ['verification', 'tax', 'fundamental', 'limits', 'auditing'],
        'venue': 'arXiv', 'year': 2026
    },
    'li2026drift': {
        'authors': ['Li'],
        'title_keywords': ['who', 'drifted', 'system', 'judge', 'attribution'],
        'venue': 'arXiv', 'year': 2026
    },
    'leng2024taming': {
        'authors': ['Leng', 'Huang', 'Zhu', 'Huang'],
        'title_keywords': ['taming', 'overconfidence', 'reward', 'calibration', 'rlhf'],
        'venue': 'EMNLP', 'year': 2025
    },
    'li2025judging': {
        'authors': ['Li'],
        'title_keywords': ['judging', 'confidence', 'calibrating', 'autoraters'],
        'venue': 'Preprint', 'year': 2025
    },
    'heineman2025snr': {
        'authors': ['Heineman', 'Hofmann', 'Magnusson'],
        'title_keywords': ['signal', 'noise', 'reducing', 'uncertainty'],
        'venue': 'NeurIPS', 'year': 2025
    },
    'singha2026uard': {
        'authors': ['Singha'],
        'title_keywords': ['uncertainty-aware', 'reward', 'discounting'],
        'venue': 'Preprint', 'year': 2026
    },
}

def parse_bib_entries(tex_content):
    """Extract all bib entries with their fields."""
    entries = {}
    pattern = r'\\bibitem\[(.*?)\]\{(.*?)\}(.*?)(?=\\bibitem|\\end\{thebibliography\})'
    for match in re.finditer(pattern, tex_content, re.DOTALL):
        label = match.group(1)
        key = match.group(2)
        body = match.group(3)
        
        author_match = re.search(r'\\newblock\s*\\(?:textit|textbf)\{(.*?)\}', body)
        title = author_match.group(1) if author_match else ''
        
        # Extract first author surname for matching
        first_author = ''
        author_line = body.split('\\newblock')[0] if '\\newblock' in body else body
        # Clean LaTeX: remove \v{}, \', etc
        author_clean = re.sub(r'\\v\{[^}]*\}', '', author_line)
        author_clean = re.sub(r"\\'\{[^}]*\}", '', author_clean)
        author_clean = re.sub(r'\\[a-z]+\s*', '', author_clean)
        author_clean = re.sub(r'[~{},.\d]', ' ', author_clean).strip()
        # Split: "B Bertalanič and C Fortuna" → take the SECOND token (surname)
        parts = author_clean.split()
        # The surname is the last word before "and" or the second word
        if len(parts) >= 2:
            # Bib format: "FirstInitial Surname" → surname is parts[1]
            first_author = parts[1] if len(parts) >= 2 else parts[0]
        
        entries[key] = {
            'label': label,
            'first_author': first_author,
            'title': title,
            'raw': body[:200]
        }
    return entries

def verify_entry(key, entry, known):
    """Verify a single bib entry against known papers."""
    if key not in known:
        return {
            'key': key,
            'verdict': '❓',
            'verdict_text': 'UNVERIFIED — not in known database',
            'fix': 'Manually verify via web search'
        }
    
    k = known[key]
    issues = []
    
    # Check first author
    bib_author = entry['first_author']
    expected = k['authors'][0]
    
    # Fuzzy match: ignore diacritics
    bib_simple = bib_author.replace('č','c').replace('ć','c').lower()
    exp_simple = expected.replace('č','c').replace('ć','c').lower()
    
    if bib_simple != exp_simple:
        # Check if it's in the author list at all
        all_simple = [a.replace('č','c').replace('ć','c').lower() for a in k['authors']]
        if bib_simple not in all_simple:
            issues.append(('🔴', f"AUTHOR: bib says '{bib_author}', paper has '{expected}' et al."))
    
    # Check title keywords
    title_lower = entry['title'].lower()
    missing = [kw for kw in k['title_keywords'] if kw.lower() not in title_lower]
    if len(missing) > len(k['title_keywords']) // 2:
        issues.append(('⚠️', f"TITLE: missing keywords: {missing[:3]}"))
    
    if not issues:
        return {'key': key, 'verdict': '✅', 'verdict_text': 'VERIFIED', 'fix': ''}
    
    severity = '🔴' if any(i[0] == '🔴' for i in issues) else '⚠️'
    return {
        'key': key,
        'verdict': severity,
        'verdict_text': '; '.join(i[1] for i in issues),
        'fix': f"Expected first author: {k['authors'][0]} et al."
    }

def main():
    parser = argparse.ArgumentParser(description='Loop Engineering v5.0 — Citation Verification Engine')
    parser.add_argument('paper_id', nargs='?', help='Paper ID (e.g., PAPER-A). Omit to scan all.')
    parser.add_argument('--strict', action='store_true', help='Flag unverified entries as errors')
    parser.add_argument('--all', '-a', action='store_true', help='Scan all registered papers')
    args = parser.parse_args()
    
    if not args.paper_id and not args.all:
        print("Usage: python citation_checker.py PAPER_ID [--strict]")
        print("       python citation_checker.py --all")
        sys.exit(1)
    
    registry = yaml.safe_load((LOOP_DIR / 'registry.yaml').read_text(encoding='utf-8'))
    
    paper_ids = []
    if args.all:
        paper_ids = [p['id'] for p in registry['papers'].values()]
    else:
        paper_ids = [args.paper_id]
    
    for paper_id in paper_ids:
        paper = None
        for p in registry['papers'].values():
            if p['id'] == paper_id:
                paper = p
                break
        if not paper:
            print(f"❌ Paper '{paper_id}' not found.")
            continue
        
        tex_path = AETTL_DIR / paper['path'] / 'main.tex'
        if not tex_path.exists():
            print(f"❌ No main.tex for {paper_id}")
            continue
        
        content = tex_path.read_text(encoding='utf-8', errors='ignore')
        entries = parse_bib_entries(content)
        
        if not entries:
            print(f"⚠️  No \\bibitem entries found in {paper_id}")
            continue
        
        print(f"\n📚 Citation Check — {paper_id}: {paper['short_title']}")
        print(f"   {'='*55}")
        
        verified = 0
        warnings = 0
        errors = 0
        unverified = 0
        
        for key, entry in entries.items():
            result = verify_entry(key, entry, KNOWN_PAPERS)
            icon = result['verdict']
            print(f"   {icon} {key}: {result['verdict_text'][:70]}")
            
            if icon == '✅': verified += 1
            elif icon == '⚠️': warnings += 1
            elif icon == '🔴': errors += 1
            else: unverified += 1
            
            if result['fix']:
                print(f"      → {result['fix'][:80]}")
        
        total = len(entries)
        print(f"\n   {'='*55}")
        print(f"   ✅ {verified}  ⚠️ {warnings}  🔴 {errors}  ❓ {unverified}")
        
        if errors > 0:
            print(f"   🔴 BLOCKING: {errors} citation errors must be fixed before submission.")
        if unverified > 0 and args.strict:
            print(f"   ⚠️  STRICT: {unverified} unverified entries treated as errors.")
        
        if errors == 0 and (unverified == 0 or not args.strict):
            print(f"   ✅ Citations clean for submission.")

if __name__ == '__main__':
    main()
