#!/usr/bin/env python3
"""Loop Engineering v4.1 — Global Status Dashboard

Usage:
    python status.py                  # Summary of all papers
    python status.py --all            # Same as default
    python status.py PAPER-A          # Detailed view of one paper
    python status.py --help
"""
import yaml
import sys
import argparse
from pathlib import Path
from datetime import datetime

LOOP_DIR = Path(__file__).resolve().parent

def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def phase_bar(phase, total=5):
    filled = int(30 * phase / total)
    return '█' * filled + '░' * (30 - filled)

def status_icon(status):
    icons = {'completed': '✅', 'in_progress': '🔄', 'pending': '⬜', 'blocked': '🚫'}
    return icons.get(status, '❓')

def main():
    parser = argparse.ArgumentParser(
        description='Loop Engineering v4.1 — Global Status Dashboard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python status.py              # Summary of all papers
  python status.py PAPER-A      # Detailed view of one paper
  python status.py --all        # Same as default (all papers)
        """
    )
    parser.add_argument('paper', nargs='?', help='Paper ID for detailed view (e.g., PAPER-A)')
    parser.add_argument('--all', '-a', action='store_true', help='Show all papers (default)')
    args = parser.parse_args()
    
    registry = load_yaml(LOOP_DIR / 'registry.yaml')
    baselines = load_yaml(LOOP_DIR / 'tmlr_baselines.yaml')
    
    paper_id = args.paper
    show_all = args.all or not paper_id
    
    papers = registry['papers']
    
    print("=" * 65)
    print(f"  🔁 Loop Engineering v4.0 — Global Dashboard")
    print(f"  🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  📊 {registry['summary']['total_papers']} papers tracked | {registry['summary']['papers_with_loop']} with Loop")
    print("=" * 65)
    
    if paper_id:
        # Single paper detail view
        p = papers.get(paper_id)
        if not p:
            print(f"  ❌ Paper '{paper_id}' not found. Use: PAPER-A, PAPER-B, etc.")
            return
        print(f"\n  📄 {p['title'][:55]}...")
        print(f"  📍 {p['path']}")
        print(f"  🏷️  {p['venue']} | Type: {p['type']}")
        print(f"  📈 Phase: {p['phase']}/5 — {p['phase_name']}")
        print(f"  {'✅' if p['has_loop'] else '⬜'} Loop {'v' + str(p['loop_version']) if p['loop_version'] else 'not initialized'}")
        if p['score_self']:
            print(f"  ⭐ Self-score: {p['score_self']}/10")
        if p['score_tmlr_calibrated']:
            print(f"  📐 TMLR-calibrated: {p['score_tmlr_calibrated']}/10")
        if p.get('notes'):
            print(f"  📝 {p['notes']}")
        return
    
    # All papers summary
    print(f"\n  {'ID':<12} {'Short Title':<25} {'Phase':<8} {'Score':<8} {'Loop':<6}")
    print("  " + "-" * 60)
    
    for key, p in papers.items():
        pid = p['id']
        title = p['short_title'][:23]
        phase_str = f"{status_icon(p.get('phase_name','pending').split()[0] if p['phase']==5 else 'completed' if p['phase']==5 else 'pending')} P{p['phase']}"
        score = f"{p.get('score_self','—')}/10" if p.get('score_self') else "—"
        loop = "v" + str(p['loop_version']) if p.get('loop_version') else "⬜"
        print(f"  {pid:<12} {title:<25} {phase_str:<8} {score:<8} {loop:<6}")
    
    # TMLR baseline reference
    print(f"\n  📐 TMLR Baseline (median of {len(baselines['baselines'])} papers):")
    agg = baselines['aggregate']
    print(f"     Datasets: {agg['median_datasets']} | Models: {agg['median_models']}")
    print(f"     CI reported: {agg['ci_reported_pct']}% | Effect sizes: {agg['effect_size_reported_pct']}%")
    print(f"     Median score: {agg['median_estimated_score']}/10")
    
    # Cross-paper insights
    cross = load_yaml(LOOP_DIR / 'cross_ref.yaml')
    pending = [p for p in cross['propagation_log'] if p['status'] == 'pending_review']
    if pending:
        print(f"\n  🔗 {len(pending)} cross-paper patterns pending propagation")
    
    print("\n" + "=" * 65)
    print("  Commands: status.py --all | status.py PAPER-A | status.py PAPER-B")
    print("=" * 65)

if __name__ == '__main__':
    main()
