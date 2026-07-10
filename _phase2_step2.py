"""Step 1-5: 完整 Phase 2 测试 - 4 paper × 4 task
直接调用 detector 公共 API, 不需要 LLM 调用 (因为只有 PAPER-A 有完整 4 mm3)
"""
import os, sys
sys.path.insert(0, r'F:\Research\.loop')
from hallucination_check import run_hallucination_hook

PAPERS = ['PAPER-A', 'PAPER-B', 'PAPER-C', 'PAPER-D']
print("=" * 60)
print("Phase 2 Test: 4 paper × 4 task = 16 mm3 detector 验证")
print("=" * 60)
print()

total_h, total_m, total_l, total_files = 0, 0, 0, 0
results = []
for paper_id in PAPERS:
    print(f"\n--- {paper_id} ---")
    try:
        passed, n_high, n_med, n_low, issues = run_hallucination_hook(paper_id, verbose=True)
        n_files = len(issues) if isinstance(issues, list) else 0
        total_h += n_high
        total_m += n_med
        total_l += n_low
        total_files += n_files
        results.append({
            'paper': paper_id,
            'files': n_files,
            'high': n_high,
            'medium': n_med,
            'low': n_low,
            'passed': passed,
        })
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({'paper': paper_id, 'error': str(e)})

print()
print("=" * 60)
print("Phase 2 SUMMARY")
print("=" * 60)
for r in results:
    if 'error' in r:
        print(f"  {r['paper']}: ERROR {r['error']}")
    else:
        print(f"  {r['paper']}: files={r['files']} HIGH={r['high']} MED={r['medium']} LOW={r['low']} passed={r['passed']}")
print()
print(f"TOTAL: {total_files} files, HIGH={total_h}, MEDIUM={total_m}, LOW={total_l}")
print("=" * 60)