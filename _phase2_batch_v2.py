"""Phase 2 v2 batch: 跑剩余 9 mm3 (用加固 demo)
每个任务之间 sleep 5s 让 DNS 喘口气
"""
import os, subprocess, time, sys
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

DEMO = r"F:\Research\_inbox\方法论\zotero_pdf_summary_demo.py"
PY = r"C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.9.25-windows-x86_64-none\python.exe"

ALL_TASKS = [
    ('PAPER-C', 'critique', r'F:\Research\calibration_contagion'),
    ('PAPER-B', 'summary', r'F:\Research\TEMPORAL_DYNAMICS'),
    ('PAPER-B', 'methods', r'F:\Research\TEMPORAL_DYNAMICS'),
    ('PAPER-B', 'experiments', r'F:\Research\TEMPORAL_DYNAMICS'),
    ('PAPER-B', 'critique', r'F:\Research\TEMPORAL_DYNAMICS'),
    ('PAPER-D', 'summary', r'F:\Research\CALIBRATION_EFFECTS'),
    ('PAPER-D', 'methods', r'F:\Research\CALIBRATION_EFFECTS'),
    ('PAPER-D', 'experiments', r'F:\Research\CALIBRATION_EFFECTS'),
    ('PAPER-D', 'critique', r'F:\Research\CALIBRATION_EFFECTS'),
]

# 只跑缺失的
missing = []
for paper_id, task, paper_dir in ALL_TASKS:
    out = f"{paper_dir}/llm_summaries/main.{task}.mm3.md"
    if not os.path.exists(out):
        missing.append((paper_id, task, paper_dir))

print(f"Missing: {len(missing)} of {len(ALL_TASKS)}")
total = len(missing)
for i, (paper_id, task, paper_dir) in enumerate(missing, 1):
    pdf = f"{paper_dir}/main.pdf"
    out_file = f"{paper_dir}/llm_summaries/main.{task}.mm3.md"
    print(f"\n[{i}/{total}] {paper_id} {task}: starting...")
    sys.stdout.flush()
    cmd = [PY, '-u', DEMO, pdf, '--task', task, '--retry', '2', '--retry-delay', '20', '--endpoint', 'cn']
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, encoding='utf-8',
            cwd=paper_dir,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
            timeout=180,  # 3 min
        )
        elapsed = time.time() - t0
        if os.path.exists(out_file):
            sz = os.path.getsize(out_file)
            print(f"  ✓ {paper_id} {task}: OK ({elapsed:.1f}s, {sz:,} bytes, rc={result.returncode})")
        else:
            print(f"  ✗ {paper_id} {task}: NO FILE ({elapsed:.1f}s, rc={result.returncode})")
    except subprocess.TimeoutExpired:
        print(f"  ✗ {paper_id} {task}: TIMEOUT (3 min)")
    except Exception as e:
        print(f"  ✗ {paper_id} {task}: ERROR {e}")
    sys.stdout.flush()
    # sleep 5s between tasks
    if i < total:
        time.sleep(5)

# 总结
print()
print("=" * 60)
have = 0
for paper_id, task, paper_dir in ALL_TASKS:
    out = f"{paper_dir}/llm_summaries/main.{task}.mm3.md"
    if os.path.exists(out):
        have += 1
print(f"GENERATED (excluding PAPER-A 4): {have}/{len(ALL_TASKS)}")
print("=" * 60)