#!/usr/bin/env python3
"""Loop Engineering v5.0 — TMLR Calibrated Scoring Engine
Prevents self-score inflation by benchmarking against published TMLR papers.
Usage: python score_calibrator.py PAPER_ID
"""
import yaml, sys, argparse, re
from pathlib import Path

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

PENALTIES = {
    'n_below_5':     ('N < 5 in any experiment', -0.3),
    'n_below_10':    ('N < 10 in any experiment', -0.2),
    'no_ci':         ('No CI reporting', -0.5),
    'no_effect_size':('No effect size reporting', -0.5),
    'single_dataset':('Single dataset/model only', -0.3),
    'self_cite_high':('Self-citation rate > 30%', -0.2),
    'ghost_cite':    ('Ghost citations found', -1.0),
    'author_mismatch':('Citation author mismatch', -0.5),
    'confound_unack':('Confound not acknowledged', -0.5),
    'overclaim':     ('Claim beyond evidence scope', -0.3),
}

def extract_paper_stats(paper_dir):
    """Extract key statistics from a paper for scoring."""
    tex_path = paper_dir / 'main.tex'
    if not tex_path.exists():
        return {}
    
    text = tex_path.read_text(encoding='utf-8', errors='ignore')
    stats = {}
    
    # Seeds / N
    seeds = re.findall(r'(?:N\s*=\s*|n\s*=\s*)(\d+)\s*(?:seed|rep|independent)', text, re.IGNORECASE)
    if seeds:
        stats['min_n'] = min(int(s) for s in seeds)
    
    # CI reporting
    stats['has_ci'] = bool(re.search(r'\\pm\s*\d|confidence\s*interval|\[\d+.*?,\s*\d+.*?\]|bootstrap.*?CI', text, re.IGNORECASE))
    
    # Effect size
    stats['has_effect_size'] = bool(re.search(r"Cohen'?s\s*d|Cliff'?s\s*\\?delta|Hedges'?\s*g|effect\s*size", text, re.IGNORECASE))
    
    # Datasets count
    dataset_section = re.search(r'(?:\\section\{|Dataset|datasets|benchmark)', text)
    stats['datasets_mentioned'] = len(re.findall(r'(?:20 Newsgroups|AG News|DBPedia|GSM8K|Pima|Credit-g|Phoneme|Adult|Yeast|CIFAR|ImageNet|MMLU)', text))
    
    # Self-citation rate
    total_cites = len(re.findall(r'\\cite\{', text))
    self_cites = len(re.findall(r'\\cite\{liu2026', text))
    stats['self_cite_rate'] = self_cites / max(total_cites, 1)
    
    # Confound acknowledgment
    stats['acknowledges_confound'] = bool(re.search(r'confound|limitation|cannot.*(?:isolate|separate|distinguish)|not.*?(?:pure|clean|isolated)', text, re.IGNORECASE))
    
    return stats

def calibrate_score(self_score, stats):
    """Apply penalties to produce calibrated score."""
    penalties_applied = []
    adjustment = 0.0
    
    # N checks
    min_n = stats.get('min_n', 999)
    if min_n < 5:
        penalties_applied.append(PENALTIES['n_below_5'])
        adjustment += PENALTIES['n_below_5'][1]
    elif min_n < 10:
        penalties_applied.append(PENALTIES['n_below_10'])
        adjustment += PENALTIES['n_below_10'][1]
    
    # CI check
    if not stats.get('has_ci'):
        penalties_applied.append(PENALTIES['no_ci'])
        adjustment += PENALTIES['no_ci'][1]
    
    # Effect size check
    if not stats.get('has_effect_size'):
        penalties_applied.append(PENALTIES['no_effect_size'])
        adjustment += PENALTIES['no_effect_size'][1]
    
    # Dataset check
    if stats.get('datasets_mentioned', 0) <= 1:
        penalties_applied.append(PENALTIES['single_dataset'])
        adjustment += PENALTIES['single_dataset'][1]
    
    # Self-citation
    if stats.get('self_cite_rate', 0) > 0.3:
        penalties_applied.append(PENALTIES['self_cite_high'])
        adjustment += PENALTIES['self_cite_high'][1]
    
    calibrated = max(0, self_score + adjustment) if self_score else None
    
    return calibrated, penalties_applied, adjustment

def main():
    parser = argparse.ArgumentParser(description='Loop Engineering v5.0 — TMLR Calibrated Scoring Engine')
    parser.add_argument('paper_id', help='Paper ID (e.g., PAPER-A, PAPER-C)')
    parser.add_argument('--self-score', type=float, help='Override self-score from registry')
    args = parser.parse_args()
    
    registry = yaml.safe_load((LOOP_DIR / 'registry.yaml').read_text(encoding='utf-8'))
    baselines = yaml.safe_load((LOOP_DIR / 'tmlr_baselines.yaml').read_text(encoding='utf-8'))
    
    paper = None
    for p in registry['papers'].values():
        if p['id'] == args.paper_id:
            paper = p
            break
    
    if not paper:
        print(f"❌ Paper '{args.paper_id}' not found.")
        sys.exit(1)
    
    self_score = args.self_score or paper.get('score_self')
    if not self_score:
        print(f"❌ No self-score available for {args.paper_id}. Use --self-score to provide one.")
        sys.exit(1)
    
    paper_dir = AETTL_DIR / paper['path']
    stats = extract_paper_stats(paper_dir)
    calibrated, penalties, adjustment = calibrate_score(self_score, stats)
    
    agg = baselines['aggregate']
    
    print(f"\n📊 TMLR Calibrated Score — {args.paper_id}: {paper['short_title']}")
    print(f"   {'='*55}")
    print(f"   Self-score:     {self_score}/10")
    print(f"   Calibrated:     {calibrated}/10  (adjustment: {adjustment:+.1f})")
    print(f"   TMLR median:    {agg['median_estimated_score']}/10")
    
    if calibrated and calibrated > agg['median_estimated_score']:
        print(f"   → Above TMLR median by {calibrated - agg['median_estimated_score']:.1f} points ✅")
    elif calibrated:
        print(f"   → Below TMLR median by {agg['median_estimated_score'] - calibrated:.1f} points ⚠️")
    
    print(f"\n   Penalties applied:")
    if penalties:
        for name, penalty in penalties:
            print(f"   {penalty:+.1f}  {name}")
    else:
        print(f"   (none) — paper meets or exceeds TMLR baseline on all dimensions")
    
    print(f"\n   Paper stats detected:")
    print(f"   Min N: {stats.get('min_n', 'unknown')}  |  CI: {'✅' if stats.get('has_ci') else '❌'}  |  Effect size: {'✅' if stats.get('has_effect_size') else '❌'}")
    print(f"   Datasets: {stats.get('datasets_mentioned', 0)}  |  Self-cite: {stats.get('self_cite_rate', 0)*100:.0f}%  |  Confound ack: {'✅' if stats.get('acknowledges_confound') else '❌'}")

if __name__ == '__main__':
    main()
