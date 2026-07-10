#!/usr/bin/env python3
"""Loop Engineering v5.1 — Dual Submission Pipeline
Generates TMLR (anonymous) and arXiv (signed) versions from a single canonical source.
Usage: python dual_submit.py PAPER_ID [--arxiv] [--tmlr] [--all]
"""
import yaml, sys, argparse, re, shutil, subprocess, os
from pathlib import Path

LOOP_DIR = Path(__file__).resolve().parent
AETTL_DIR = LOOP_DIR.parent

AUTHOR_BLOCK = r"""Zewen Liu\\
Independent Researcher\\
\texttt{research@zliu.dev}"""

ACKNOWLEDGMENTS = r"""\section*{Acknowledgments}
The author thanks the anonymous reviewers for their constructive feedback.
Code and data are available at \url{https://github.com/aidless/research}."""

def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def find_paper(paper_id):
    registry = load_yaml(LOOP_DIR / 'registry.yaml')
    for key, p in registry['papers'].items():
        if p['id'] == paper_id:
            return p
    return None

def generate_tmlr_version(content, paper_dir):
    """Strip author info for TMLR anonymous submission."""
    tmlr = content
    
    # Replace author block
    tmlr = re.sub(
        r'\\author\{.*?\}',
        r'\\author{Anonymous Authors}',
        tmlr, flags=re.DOTALL
    )
    
    # Remove date
    tmlr = re.sub(r'\\date\{.*?\}', r'\\date{}', tmlr)
    
    # Remove acknowledgments section
    tmlr = re.sub(
        r'\\section\*\{Acknowledgment[^}]*\}.*?(?=\\section|\n\\end\{document\})',
        '',
        tmlr, flags=re.DOTALL
    )
    
    # Strip PDF metadata
    tmlr = re.sub(
        r'\\hypersetup\{.*?pdfauthor.*?\}',
        r'\\hypersetup{pdfauthor={Anonymous}}',
        tmlr, flags=re.DOTALL
    )
    
    # Remove personal URLs in text (keep figure/ref URLs)
    tmlr = re.sub(
        r'\\url\{https?://github\.com/[^}]*\}',
        r'\\url{https://github.com/anonymous-research}',
        tmlr
    )
    
    out_path = paper_dir / 'main_tmlr.tex'
    out_path.write_text(tmlr, encoding='utf-8')
    return out_path

def generate_arxiv_version(content, paper_dir):
    """Ensure author info is present for arXiv submission."""
    arxiv = content
    
    # Ensure author block exists
    if 'Anonymous Authors' in arxiv or '\\author{}' in arxiv:
        arxiv = re.sub(
            r'\\author\{.*?\}',
            lambda m: '\\author{' + AUTHOR_BLOCK + '}',
            arxiv, flags=re.DOTALL
        )
    
    # Ensure date exists
    if '\\date{}' in arxiv:
        from datetime import datetime
        arxiv = arxiv.replace('\\date{}', '\\date{' + datetime.now().strftime('%B %Y') + '}')
    
    # Add acknowledgments if not present
    if 'Acknowledg' not in arxiv:
        arxiv = arxiv.replace('\\end{document}', ACKNOWLEDGMENTS + '\n\n\\end{document}')
    
    out_path = paper_dir / 'main_arxiv.tex'
    out_path.write_text(arxiv, encoding='utf-8')
    return out_path

def compile_latex(tex_path, workdir):
    """Compile LaTeX to PDF."""
    tex_file = tex_path.name
    result = subprocess.run(
        ['pdflatex', '-interaction=nonstopmode', tex_file],
        cwd=str(workdir), capture_output=True, text=True, timeout=120
    )
    # Run bibtex if needed
    aux_file = tex_path.with_suffix('.aux')
    if aux_file.exists():
        subprocess.run(['bibtex', tex_path.stem], cwd=str(workdir), 
                       capture_output=True, timeout=60)
        subprocess.run(['pdflatex', '-interaction=nonstopmode', tex_file],
                       cwd=str(workdir), capture_output=True, timeout=120)
        subprocess.run(['pdflatex', '-interaction=nonstopmode', tex_file],
                       cwd=str(workdir), capture_output=True, timeout=120)
    
    pdf_path = tex_path.with_suffix('.pdf')
    return pdf_path if pdf_path.exists() else None

def create_arxiv_zip(paper_dir, paper_id):
    """Package arXiv submission."""
    import zipfile
    
    zip_path = paper_dir / 'arxiv_submit.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Main tex
        zf.write(paper_dir / 'main_arxiv.tex', 'main.tex')
        # Figures
        fig_dir = paper_dir / 'figures'
        if fig_dir.exists():
            for f in fig_dir.glob('*.pdf'):
                zf.write(f, f'figures/{f.name}')
            for f in fig_dir.glob('*.png'):
                zf.write(f, f'figures/{f.name}')
        # Style files
        for sty in paper_dir.glob('*.sty'):
            zf.write(sty, sty.name)
        for bst in paper_dir.glob('*.bst'):
            zf.write(bst, bst.name)
        # Bib
        for bib in paper_dir.glob('*.bib'):
            zf.write(bib, bib.name)
        # PDF (arxiv requires)
        pdf = paper_dir / 'main_arxiv.pdf'
        if pdf.exists():
            zf.write(pdf, 'main.pdf')
    
    return zip_path

def main():
    parser = argparse.ArgumentParser(
        description='Loop Engineering v5.1 — Dual Submission Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dual_submit.py PAPER-A --all       # Generate both versions
  python dual_submit.py PAPER-A --arxiv      # arXiv version only
  python dual_submit.py PAPER-A --tmlr       # TMLR version only
  python dual_submit.py --all-papers --arxiv  # All papers, arXiv versions
        """
    )
    parser.add_argument('paper_id', nargs='?', help='Paper ID')
    parser.add_argument('--arxiv', action='store_true', help='Generate arXiv version')
    parser.add_argument('--tmlr', action='store_true', help='Generate TMLR version')
    parser.add_argument('--all', '-a', action='store_true', help='Both versions')
    parser.add_argument('--all-papers', action='store_true', help='Process all registered papers')
    parser.add_argument('--zip', '-z', action='store_true', help='Create arXiv ZIP')
    args = parser.parse_args()
    
    if args.all:
        args.arxiv = True
        args.tmlr = True
    
    if not (args.arxiv or args.tmlr):
        parser.print_help()
        sys.exit(1)
    
    registry = load_yaml(LOOP_DIR / 'registry.yaml')
    
    if args.all_papers:
        paper_ids = [p['id'] for p in registry['papers'].values()]
    elif args.paper_id:
        paper_ids = [args.paper_id]
    else:
        parser.print_help()
        sys.exit(1)
    
    for paper_id in paper_ids:
        paper = find_paper(paper_id)
        if not paper:
            print(f"❌ {paper_id} not found")
            continue
        
        paper_dir = AETTL_DIR / paper['path']
        src = paper_dir / 'main.tex'
        if not src.exists():
            # Try main_merged.tex
            src = paper_dir / 'main_merged.tex'
        if not src.exists():
            print(f"❌ No main.tex for {paper_id}")
            continue
        
        content = src.read_text(encoding='utf-8', errors='ignore')
        print(f"\n📄 {paper_id}: {paper['short_title'][:40]}")
        
        if args.tmlr:
            tmlr_path = generate_tmlr_version(content, paper_dir)
            pdf = compile_latex(tmlr_path, paper_dir)
            if pdf:
                print(f"   ✅ TMLR:  {pdf.name} ({pdf.stat().st_size//1024}KB)")
            else:
                print(f"   ⚠️  TMLR compilation failed — check log")
        
        if args.arxiv:
            arxiv_path = generate_arxiv_version(content, paper_dir)
            pdf = compile_latex(arxiv_path, paper_dir)
            if pdf:
                print(f"   ✅ arXiv: {pdf.name} ({pdf.stat().st_size//1024}KB)")
            else:
                print(f"   ⚠️  arXiv compilation failed — check log")
            
            if args.zip and pdf:
                zip_path = create_arxiv_zip(paper_dir, paper_id)
                print(f"   📦 ZIP:   {zip_path.name} ({zip_path.stat().st_size//1024}KB)")
    
    print(f"\n{'='*50}")
    print("Done. Submit instructions:")
    print("  TMLR: Upload main_tmlr.pdf to OpenReview")
    print("  arXiv: Upload arxiv_submit.zip to arXiv")

if __name__ == '__main__':
    main()
