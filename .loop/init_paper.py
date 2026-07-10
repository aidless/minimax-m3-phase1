#!/usr/bin/env python3
"""Loop Engineering v4.1 — Paper Initializer
Creates a standardized paper skeleton from templates.

Usage:
    python init_paper.py PAPER_ID "Paper Title"
    python init_paper.py PAPER_ID "Paper Title" --venue TMLR --type empirical_study
    python init_paper.py --help
"""
import yaml
import sys
import os
import shutil
import argparse
from pathlib import Path
from datetime import datetime

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent
TEMPLATES = LOOP_DIR / 'templates'

PAPER_SKELETON = {
    'directories': [
        'src',
        'experiments',
        'experiments/results',
        'experiments/logs',
        'notes',
        'figures',
        '.loop/reviews',
    ],
    'files': {
        'README.md': """# {title}

- **Venue**: {venue}
- **Type**: {paper_type}
- **Status**: Phase 0 — Initialized
- **Created**: {date}
- **Loop**: v4.0

## Quick Start
```bash
# View paper status
python ../.loop/status.py {paper_id}

# Run pre-review
python ../.loop/pre_review.py {paper_id}
```

## Directory Structure
```
{dirname}/
├── main.tex           # Primary manuscript
├── src/               # Reproducible code
├── experiments/       # Configs, logs, results
├── notes/             # Reading notes, ideas
├── figures/           # All figures (PDF)
└── .loop/             # Automation hub
```
""",
        'main.tex': r"""% {title}
% Target: {venue}
% Created: {date}

\documentclass[11pt]{{article}}

\usepackage{{tmlr}}
\usepackage[T1]{{fontenc}}
\usepackage[utf8]{{inputenc}}
\usepackage{{amsmath,amssymb}}
\usepackage{{natbib}}
\usepackage{{booktabs}}
\usepackage{{graphicx}}
\usepackage[colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue]{{hyperref}}
\usepackage{{enumitem}}
\usepackage{{microtype}}
\usepackage{{float}}
\usepackage{{fancyhdr}}
\setlength{{\headheight}}{{14pt}}

\graphicspath{{{{./figures/}}}}

\title{{{title}}}

\author{{Anonymous Authors}}

\date{{}}

\begin{{document}}
\maketitle

\begin{{abstract}}
% TODO: Write abstract
\end{{abstract}}

\section{{Introduction}}
% TODO

\end{{document}}
""",
        '.loop/config.yaml': """# Loop Configuration — {paper_id}
loop_name: "TMLR Paper Writing Loop"
loop_version: "4.0"
paper_title: "{title}"

global:
  cooldown_hours: 24
  git:
    auto_commit: false
  marginal_benefit:
    enabled: true
    max_consecutive_zero_new_issues: 2
    min_rounds_before_early_exit: 2
  regression_testing:
    enabled: true
  severity_levels:
    critical:
      label: "Critical"
      description: "Will cause desk reject"
    important:
      label: "Important"
      description: "Significantly affects quality"
    minor:
      label: "Minor"
      description: "Nice to fix"

phases:
  phase_0:
    name: "基线评估"
    max_rounds: 1
  phase_1:
    name: "格式转换"
    max_rounds: 3
  phase_2:
    name: "内容审阅"
    max_rounds: 7
  phase_3:
    name: "润色"
    max_rounds: 3
  phase_4:
    name: "匿名化"
    max_rounds: 3
  phase_5:
    name: "提交就绪"
    max_rounds: 3
""",
    }
}

def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_yaml(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

def create_state_yaml(paper_id, title):
    return {
        'loop_name': 'TMLR Paper Writing Loop',
        'loop_version': '4.0',
        'paper': paper_id,
        'created': datetime.now().strftime('%Y-%m-%d'),
        'current_phase': 0,
        'overall_status': 'in_progress',
        'phases': {
            f'phase_{i}': {
                'status': 'in_progress' if i == 0 else 'pending',
                'rounds_completed': 0,
                'max_rounds': [1, 3, 7, 3, 3, 3][i],
                'artifacts': [],
                'issues_summary': {'critical': 0, 'important': 0, 'minor': 0}
            } for i in range(6)
        },
        'session_history': [{
            'date': datetime.now().strftime('%Y-%m-%d'),
            'action': 'paper_initialized',
            'note': f'Paper skeleton created via init_paper.py. Title: {title}'
        }]
    }

def register_in_registry(paper_id, dirname, title, venue, paper_type):
    registry_path = LOOP_DIR / 'registry.yaml'
    registry = load_yaml(registry_path)
    
    # Find next available PAPER-X ID
    existing = [p['id'] for p in registry['papers'].values()]
    if paper_id not in existing:
        registry['papers'][paper_id] = {
            'id': paper_id,
            'path': f'{dirname}/',
            'title': title,
            'short_title': title[:40],
            'venue': venue,
            'type': paper_type,
            'phase': 0,
            'phase_name': '基线评估',
            'score_self': None,
            'score_tmlr_calibrated': None,
            'has_loop': True,
            'loop_version': '4.0',
            'last_review': None,
            'reviewer_comments': False,
            'experiments_complete': False,
            'notes': f'Initialized {datetime.now().strftime("%Y-%m-%d")}'
        }
        registry['summary']['total_papers'] = len(registry['papers'])
        registry['summary']['papers_with_loop'] += 1
        save_yaml(registry_path, registry)
        return True
    return False

def main():
    parser = argparse.ArgumentParser(
        description='Loop Engineering v4.1 — Paper Initializer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python init_paper.py my_calib "My Calibration Study"
  python init_paper.py my_calib "My Study" --venue TMLR --type empirical_study
  python init_paper.py my_calib "My Study" --force  # Overwrite existing
        """
    )
    parser.add_argument('paper_id', help='Paper ID (lowercase, underscores, e.g., my_calibration)')
    parser.add_argument('title', help='Full paper title (in quotes)')
    parser.add_argument('--venue', '-v', default='TMLR', help='Target venue (default: TMLR)')
    parser.add_argument('--type', '-t', default='empirical_study', dest='paper_type',
                        help='Paper type (default: empirical_study)')
    parser.add_argument('--force', '-f', action='store_true', help='Overwrite existing directory')
    args = parser.parse_args()
    
    paper_id = args.paper_id
    title = args.title
    venue = args.venue
    paper_type = args.paper_type
    
    # Create directory name from paper_id (lowercase, underscores)
    dirname = paper_id.lower().replace('-', '_')
    paper_dir = AETTL_DIR / dirname
    
    if paper_dir.exists():
        print(f"❌ Directory already exists: {paper_dir}")
        print("   Remove it first or use a different PAPER_ID.")
        sys.exit(1)
    
    print(f"\n🔧 Initializing paper: {paper_id}")
    print(f"   Title: {title[:60]}...")
    print(f"   Venue: {venue} | Type: {paper_type}")
    print(f"   Directory: {dirname}/")
    print()
    
    # Create directories
    for d in PAPER_SKELETON['directories']:
        path = paper_dir / d
        path.mkdir(parents=True, exist_ok=True)
        print(f"   📁 {d}/")
    
    # Create files
    context = {
        'title': title,
        'venue': venue,
        'paper_type': paper_type,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'paper_id': paper_id,
        'dirname': dirname,
    }
    
    for filename, template in PAPER_SKELETON['files'].items():
        filepath = paper_dir / filename
        content = template.format(**context)
        filepath.write_text(content, encoding='utf-8')
        print(f"   📄 {filename}")
    
    # Create state.yaml
    state = create_state_yaml(paper_id, title)
    save_yaml(paper_dir / '.loop' / 'state.yaml', state)
    print(f"   📄 .loop/state.yaml")
    
    # Register in global registry
    registered = register_in_registry(paper_id, dirname, title, venue, paper_type)
    if registered:
        print(f"\n✅ Paper registered as {paper_id} in .loop/registry.yaml")
    else:
        print(f"\n⚠️  Paper ID {paper_id} already exists in registry. Skipping registration.")
    
    print(f"\n{'='*50}")
    print(f"✅ Paper '{paper_id}' initialized successfully!")
    print(f"   Location: {paper_dir}")
    print(f"   Next: cd {dirname} && python ../.loop/pre_review.py {paper_id}")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
