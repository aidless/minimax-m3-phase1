#!/usr/bin/env python3
"""Loop Engineering v5.3 — Semantic Scholar Citation Verification
Verifies bibliography entries against Semantic Scholar API.
Searches for prior work on "first" claims.

Usage:
  python scholar_verify.py PAPER_ID          # Verify all bib entries
  python scholar_verify.py PAPER_ID --novelty # Also search for prior work on claims
  python scholar_verify.py PAPER_ID --json   # JSON output
"""
import re, sys, json, argparse, time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import quote
from urllib.error import URLError, HTTPError

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent
CACHE_PATH = LOOP_DIR / 'scholar_cache.json'

# ============================================================
# Cache
# ============================================================
def load_cache():
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding='utf-8'))
    return {}

def save_cache(cache):
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding='utf-8')

# ============================================================
# Semantic Scholar API
# ============================================================
S2_BASE = 'https://api.semanticscholar.org/graph/v1'
S2_FIELDS = 'title,authors,year,venue,externalIds,citationCount'

def s2_search(query, limit=5, retries=2):
    """Search Semantic Scholar for papers matching query."""
    url = f"{S2_BASE}/paper/search?query={quote(query)}&limit={limit}&fields={S2_FIELDS}"
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={'User-Agent': 'LoopEngineering/5.3'})
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                return data.get('data', [])
        except HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(3 * (attempt + 1))  # Back off
                continue
            return []
        except (URLError, json.JSONDecodeError):
            return []
    return []

def s2_get_paper(paper_id):
    """Get paper details by S2 paper ID or external ID."""
    url = f"{S2_BASE}/paper/{paper_id}?fields={S2_FIELDS}"
    try:
        req = Request(url, headers={'User-Agent': 'LoopEngineering/5.3'})
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except (URLError, HTTPError, json.JSONDecodeError):
        return None

# ============================================================
# Bibentry parsing
# ============================================================
def extract_bibentries(text):
    """Extract all bibitem entries with their metadata."""
    entries = []
    for m in re.finditer(
        r'\\bibitem\[([^\]]*)\]\{([^}]+)\}\s*(.*?)(?=\\bibitem|\Z)',
        text, re.DOTALL):
        label = m.group(1).strip()
        key = m.group(2).strip()
        body = m.group(3).strip()

        # Extract title (in \textit{} or after \newblock)
        title = ''
        title_m = re.search(r'\\textit\{([^}]+)\}', body)
        if title_m:
            title = title_m.group(1).strip()

        # Extract author from label: "Author(et~al.(Year)" → "Author"
        author = ''
        author_m = re.match(r'([A-Z\u00C0-\u024F][a-z\u00C0-\u024F]+(?:\s+et~?al)?)', label)
        if author_m:
            author = author_m.group(1).replace('~', ' ').strip()

        # Extract year
        year = ''
        year_m = re.search(r'(\d{4})', label)
        if year_m:
            year = year_m.group(1)

        entries.append({
            'key': key,
            'label': label,
            'title': title,
            'author': author,
            'year': year,
            'body': body[:200]
        })
    return entries

def extract_cite_keys(text):
    """Extract all citation keys from text."""
    keys = set()
    for m in re.finditer(r'\\cite[tp]?\{([^}]+)\}', text):
        for k in m.group(1).split(','):
            keys.add(k.strip())
    return keys

# ============================================================
# Verification
# ============================================================
def verify_entry(entry, cache):
    """Verify a single bibentry against Semantic Scholar."""
    key = entry['key']
    issues = []

    # Check cache first
    if key in cache:
        return cache[key]

    # Search by title
    if entry['title'] and len(entry['title']) > 10:
        results = s2_search(entry['title'])
        time.sleep(1)  # Rate limit

        if results:
            best = results[0]
            s2_title = best.get('title', '').lower()
            s2_authors = [a.get('name', '') for a in best.get('authors', [])]
            s2_year = best.get('year', '')
            s2_venue = best.get('venue', '')

            # Check title similarity
            title_match = entry['title'].lower()[:30] in s2_title or s2_title[:30] in entry['title'].lower()

            # Check author
            author_match = True
            if entry['author'] and s2_authors:
                first_author = s2_authors[0].split()[-1] if s2_authors[0] else ''
                author_match = (entry['author'].lower() in first_author.lower() or
                               first_author.lower() in entry['author'].lower())

            # Check year
            year_match = True
            if entry['year'] and s2_year:
                year_match = (entry['year'] == str(s2_year))

            result = {
                'found': True,
                's2_title': best.get('title', ''),
                's2_authors': s2_authors[:3],
                's2_year': s2_year,
                's2_venue': s2_venue,
                's2_citations': best.get('citationCount', 0),
                'title_match': title_match,
                'author_match': author_match,
                'year_match': year_match,
            }

            if not title_match:
                result['issue'] = f"Title mismatch: bib='{entry['title'][:40]}' vs S2='{s2_title[:40]}'"
            elif not author_match:
                result['issue'] = f"Author mismatch: bib='{entry['author']}' vs S2='{s2_authors[0] if s2_authors else 'N/A'}'"
            elif not year_match:
                result['issue'] = f"Year mismatch: bib='{entry['year']}' vs S2='{s2_year}'"

            cache[key] = result
            return result
        else:
            result = {'found': False, 'issue': f"Not found on Semantic Scholar: '{entry['title'][:50]}'"}
            cache[key] = result
            return result

    return {'found': False, 'issue': 'No title to search'}

def search_novelty_claims(text):
    """Search for prior work on 'first'/'novel' claims in the paper."""
    claims = []
    # Find "first" claims
    for m in re.finditer(
        r'(?:first|novel|we are the first to|no prior)[^.]*\.',
        text, re.IGNORECASE):
        claim = m.group(0).strip()
        if len(claim) > 20:
            claims.append(claim[:100])

    results = []
    for claim in claims[:3]:  # Limit to 3 to avoid rate limiting
        # Extract key terms for search
        terms = re.findall(r'\b[A-Za-z]{4,}\b', claim)
        query = ' '.join(terms[:6])
        if len(query) > 10:
            papers = s2_search(query, limit=3)
            time.sleep(1)
            if papers:
                results.append({
                    'claim': claim,
                    'query': query,
                    'prior_work': [{
                        'title': p.get('title', ''),
                        'year': p.get('year', ''),
                        'venue': p.get('venue', ''),
                        'citations': p.get('citationCount', 0),
                    } for p in papers]
                })
    return results

# ============================================================
# Main
# ============================================================
def run_verification(paper_id, do_novelty=False):
    """Run full verification on a paper."""
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
    cache = load_cache()

    # Extract entries
    bibentries = extract_bibentries(text)
    cite_keys = extract_cite_keys(text)

    # Verify each entry
    verifications = []
    for entry in bibentries:
        result = verify_entry(entry, cache)
        result['key'] = entry['key']
        result['cited'] = entry['key'] in cite_keys
        verifications.append(result)

    save_cache(cache)

    # Novelty search
    novelty_results = []
    if do_novelty:
        novelty_results = search_novelty_claims(text)

    return {
        'paper_id': paper_id,
        'total_entries': len(bibentries),
        'verified': sum(1 for v in verifications if v.get('found')),
        'issues': [v for v in verifications if v.get('issue')],
        'novelty_claims': novelty_results,
    }

def print_report(result):
    """Pretty-print verification report."""
    if 'error' in result:
        print(f"❌ {result['error']}")
        return

    print(f"\n{'='*65}")
    print(f"📚 Semantic Scholar Verification — {result['paper_id']}")
    print(f"{'='*65}")

    print(f"\n  Total entries: {result['total_entries']}")
    print(f"  Found on S2:  {result['verified']}")
    print(f"  Issues:       {len(result['issues'])}")

    if result['issues']:
        print(f"\n  ⚠️  Issues:")
        for issue in result['issues']:
            status = '✅' if issue.get('found') else '❌'
            print(f"    {status} [{issue['key']}] {issue.get('issue', 'unknown')}")

    if result.get('novelty_claims'):
        print(f"\n  🔍 Novelty Claims ({len(result['novelty_claims'])}):")
        for nc in result['novelty_claims']:
            print(f"\n    Claim: \"{nc['claim'][:70]}...\"")
            print(f"    Search: \"{nc['query']}\"")
            for pw in nc['prior_work']:
                print(f"      → {pw['title'][:60]} ({pw['year']}, {pw['venue']}, {pw['citations']} cites)")

    print(f"\n{'='*65}")

def main():
    parser = argparse.ArgumentParser(description='Loop Engineering v5.3 — Semantic Scholar Verification')
    parser.add_argument('paper_id', help='Paper ID')
    parser.add_argument('--novelty', '-n', action='store_true', help='Also search for prior work on claims')
    parser.add_argument('--json', '-j', action='store_true', help='JSON output')
    args = parser.parse_args()

    result = run_verification(args.paper_id, args.novelty)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_report(result)

if __name__ == '__main__':
    main()
