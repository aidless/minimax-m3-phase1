#!/usr/bin/env python3
"""Loop Engineering v4.1 — Interactive Reviewer Response Tool
Guides author through responding to reviewer questions.

Usage:
    python respond.py PAPER_ID                # Interactive: respond to all pending questions
    python respond.py PAPER_ID --question Q6  # Respond to specific question
    python respond.py PAPER_ID --list         # List all questions with status
    python respond.py --help
"""
import yaml
import sys
import argparse
from pathlib import Path
from datetime import datetime

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_yaml(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

def find_paper(paper_id):
    registry = load_yaml(LOOP_DIR / 'registry.yaml')
    for key, p in registry['papers'].items():
        if p['id'] == paper_id:
            return p
    return None

def main():
    parser = argparse.ArgumentParser(
        description='Loop Engineering v4.1 — Interactive Reviewer Response Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python respond.py PAPER-A                  # Respond to all pending questions
  python respond.py PAPER-A --question Q6    # Respond to specific question
  python respond.py PAPER-A --list           # List all questions
        """
    )
    parser.add_argument('paper_id', help='Paper ID (e.g., PAPER-A)')
    parser.add_argument('--question', '-q', help='Target specific question (e.g., Q6)')
    parser.add_argument('--list', '-l', action='store_true', help='List all questions with status')
    args = parser.parse_args()
    
    paper_id = args.paper_id
    paper = find_paper(paper_id)
    if not paper:
        print(f"❌ Paper '{paper_id}' not found.")
        sys.exit(1)
    
    response_path = AETTL_DIR / paper['path'] / '.loop' / 'reviewer_response.yaml'
    if not response_path.exists():
        print(f"❌ No reviewer_response.yaml found for {paper_id}.")
        print(f"   Create one first at: {response_path}")
        sys.exit(1)
    
    data = load_yaml(response_path)
    questions = data.get('questions', {})
    
    # --list mode
    if args.list:
        print(f"\n📋 Reviewer Questions — {paper['short_title']}")
        print(f"   {'='*50}")
        for qid, q in questions.items():
            icon = {'resolved': '✅', 'partial': '🟡', 'unresolved': '🔴'}.get(q['status'], '⬜')
            print(f"   {icon} {qid}: {q['text'][:70]}...")
            print(f"      Status: {q['status']} | Fix: {q.get('fix_type', 'unknown')}")
        resolved = sum(1 for q in questions.values() if q['status'] == 'resolved')
        print(f"\n   {resolved}/{len(questions)} resolved")
        return
    
    # Filter to specific question
    if args.question:
        if args.question not in questions:
            print(f"❌ Question '{args.question}' not found. Available: {', '.join(questions.keys())}")
            sys.exit(1)
        pending = {args.question: questions[args.question]}
    else:
        pending = {k: v for k, v in questions.items() if v['status'] != 'resolved'}
    
    if not pending:
        print(f"✅ All {len(questions)} questions resolved!")
        return
    
    print(f"\n📝 Reviewer Response — {paper['short_title']}")
    print(f"   {len(pending)}/{len(questions)} questions pending\n")
    
    for qid, q in pending.items():
        status_icon = {'partial': '🟡', 'unresolved': '🔴', 'pending': '⬜'}.get(q['status'], '❓')
        print(f"{status_icon} {qid}: {q['text'][:80]}...")
        print(f"   Status: {q['status']} | Fix type: {q.get('fix_type', 'unknown')}")
        if q.get('fix'):
            print(f"   Current fix: {q['fix'][:80]}...")
        if q.get('remaining'):
            print(f"   Remaining: {q['remaining']}")
        print()
        
        answer = input("   → Update? (enter=skip, 'r'=mark resolved, or type new fix): ").strip()
        
        if answer.lower() == 'r':
            q['status'] = 'resolved'
            q['resolved_date'] = datetime.now().strftime('%Y-%m-%d')
            print(f"   ✅ Marked as resolved.\n")
        elif answer:
            q['fix'] = answer
            q['status'] = 'partial'
            q['updated_date'] = datetime.now().strftime('%Y-%m-%d')
            print(f"   📝 Fix updated.\n")
    
    # Update summary
    resolved = sum(1 for q in questions.values() if q['status'] == 'resolved')
    data['summary'] = {
        'total_questions': len(questions),
        'resolved': resolved,
        'partial': sum(1 for q in questions.values() if q['status'] == 'partial'),
        'unresolved': sum(1 for q in questions.values() if q['status'] == 'unresolved')
    }
    
    save_yaml(response_path, data)
    
    print(f"{'='*50}")
    print(f"Summary: {resolved}/{len(questions)} resolved")
    print(f"Saved to: {response_path}")
    
    # Suggest next step
    if resolved == len(questions):
        print(f"\n🎉 All questions resolved! Run pre-review to verify:")
        print(f"   python ../.loop/pre_review.py {paper_id}")
    else:
        print(f"\n📋 Next: re-run this tool to continue responding.")
        print(f"   python ../.loop/respond.py {paper_id}")

if __name__ == '__main__':
    main()
