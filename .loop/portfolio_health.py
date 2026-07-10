#!/usr/bin/env python3
"""Loop Engineering v5.0 — Portfolio Health Dashboard
One-command overview of all papers: scores, issues, readiness.
Usage: python portfolio_health.py [--detail]
"""
import yaml, sys, argparse
from pathlib import Path
from datetime import datetime

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

def load_yaml(p):
    with open(p, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def status_bar(value, max_val=5):
    filled = int(20 * value / max_val)
    return '█' * filled + '░' * (20 - filled)

def main():
    parser = argparse.ArgumentParser(description='Loop Engineering v5.0 — Portfolio Health Dashboard')
    parser.add_argument('--detail', '-d', action='store_true', help='Show per-paper detail')
    args = parser.parse_args()
    
    registry = load_yaml(LOOP_DIR / 'registry.yaml')
    baselines = load_yaml(LOOP_DIR / 'tmlr_baselines.yaml')
    
    papers = registry['papers']
    
    print(f"\n🏥 Portfolio Health — {len(papers)} papers")
    print(f"   {'='*65}")
    
    # Sort by priority: Phase 5 > has issues > Phase 0
    def priority(p):
        phase = p.get('phase', 0)
        score = p.get('score_self') or 0
        return (5 - phase) * 10 - score
    
    sorted_papers = sorted(papers.values(), key=priority)
    
    for p in sorted_papers:
        pid = p['id']
        title = p.get('short_title', pid)[:30]
        phase = p.get('phase', 0)
        score = p.get('score_self')
        calibrated = p.get('score_tmlr_calibrated')
        has_loop = p.get('has_loop', False)
        
        # Determine health indicators
        indicators = []
        if phase >= 5:
            indicators.append('🚀 Ready')
        elif phase >= 3:
            indicators.append('📝 Polish')
        elif phase >= 1:
            indicators.append('🔧 In Progress')
        else:
            indicators.append('🌱 Seed')
        
        if not has_loop:
            indicators.append('⚠️ No Loop')
        
        if calibrated and score:
            if calibrated < score - 0.5:
                indicators.append('📉 Over-scored')
        
        bar = status_bar(phase)
        score_str = f"{score}/10" if score else "—"
        cal_str = f"→{calibrated}" if calibrated else ""
        
        print(f"\n   {p['id']:<10} [{bar}] P{phase}")
        print(f"   {'':10} {title}")
        print(f"   {'':10} Score: {score_str} {cal_str} | {' '.join(indicators)}")
        
        if args.detail and p.get('notes'):
            print(f"   {'':10} 📝 {p['notes'][:80]}")
    
    # Portfolio summary
    ready = sum(1 for p in papers.values() if p.get('phase', 0) >= 5)
    in_progress = sum(1 for p in papers.values() if 1 <= p.get('phase', 0) < 5)
    seeds = sum(1 for p in papers.values() if p.get('phase', 0) == 0)
    with_loop = sum(1 for p in papers.values() if p.get('has_loop'))
    
    agg = baselines['aggregate']
    print(f"\n   {'='*65}")
    print(f"   📊 Summary")
    print(f"   🚀 Ready to submit:  {ready}")
    print(f"   🔧 In progress:      {in_progress}")
    print(f"   🌱 Seeds:            {seeds}")
    print(f"   🔁 With Loop infra:  {with_loop}/{len(papers)}")
    print(f"   📐 TMLR baseline:    median score {agg['median_estimated_score']}/10")
    print(f"   📐 TMLR typical:     {agg['typical_profile']['datasets']} datasets, {agg['typical_profile']['models']} models")
    print(f"                       CI: {agg['typical_profile']['ci']}, ES: {agg['typical_profile']['effect_sizes']}")
    
    # Recommended next action
    if seeds > 0:
        print(f"\n   💡 Next: Initialize loops for {seeds} seed papers: python init_paper.py PAPER_ID")
    if ready > 0:
        print(f"   🚀 {ready} paper(s) ready — submit when citations are clean!")

if __name__ == '__main__':
    main()
