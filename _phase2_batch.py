"""Phase 2 batch: 10 个 mm3.md 顺序生成 (simplified)
直接 subprocess 调用 demo 脚本
"""
import subprocess, os, time, sys
# force unbuffered
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

DEMO = r"F:\Research\_inbox\方法论\zotero_pdf_summary_demo.py"
PY = r"C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.9.25-windows-x86_64-none\python.exe"

TASKS = [
    ('PAPER-C', 'summary', r'F:\Research\calibration_contagion'),
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

total = len(TASKS)
results = []
print(f"Phase 2 batch: {total} mm3.md files to generate")
print("=" * 60)

for i, (paper_id, task, paper_dir) in enumerate(TASKS, 1):
    pdf = f"{paper_dir}/main.pdf"
    out_file = f"{paper_dir}/llm_summaries/main.{task}.mm3.md"
    if not os.path.exists(pdf):
        print(f"[{i}/{total}] {paper_id} {task}: SKIP (no PDF)")
        results.append((paper_id, task, 'skip', 0))
        continue
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    cmd = [PY, DEMO, pdf, '--task', task]
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, encoding='utf-8',
            cwd=paper_dir,  # demo 写到 ./llm_summaries/
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
            timeout=180,  # 3 min per call
        )
        elapsed = time.time() - t0
        if os.path.exists(out_file):
            sz = os.path.getsize(out_file)
            status = 'OK' if result.returncode == 0 else f'CRASH(rc={result.returncode})'
            print(f"[{i}/{total}] {paper_id} {task}: {status} ({elapsed:.1f}s, {sz:,} bytes)")
            results.append((paper_id, task, status, sz))
        else:
            print(f"[{i}/{total}] {paper_id} {task}: NO FILE ({elapsed:.1f}s, rc={result.returncode})")
            # 保存 stderr 帮助 debug
            with open(f"F:\Research\_phase2_err_{paper_id}_{task}.txt", "w", encoding="utf-8") as f:
                f.write(result.stderr[:2000])
            results.append((paper_id, task, 'no_file', 0))
    except subprocess.TimeoutExpired:
        print(f"[{i}/{total}] {paper_id} {task}: TIMEOUT")
        results.append((paper_id, task, 'timeout', 0))
    except Exception as e:
        print(f"[{i}/{total}] {paper_id} {task}: ERROR {e}")
        results.append((paper_id, task, f'error:{e}', 0))

# 总结
print()
print("=" * 60)
print("PHASE 2 BATCH SUMMARY")
print("=" * 60)
ok = sum(1 for r in results if r[2] == 'OK')
print(f"  Total: {len(results)}, OK: {ok}, Failed: {len(results)-ok}")
for r in results:
    print(f"  {r[0]} {r[1]}: {r[2]}")