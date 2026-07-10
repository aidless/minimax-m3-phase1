"""Phase 2 Batch 卡住诊断
4 个步骤:
  1. 单次 demo 调用 (PAPER-C critique) - 测 demo 自身是否正常
  2. 串行 2 次 demo 调用 - 测是否有 rate limit
  3. 串行 3 次 + 手动 sleep - 测 rate limit 恢复时间
  4. 检查 .env key 状态
"""
import os, subprocess, time, sys
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

DEMO = r"F:\Research\_inbox\方法论\zotero_pdf_summary_demo.py"
PY = r"C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.9.25-windows-x86_64-none\python.exe"

def run_one(label, pdf, task, timeout=180):
    print(f"\n[{label}] {task} from {os.path.basename(pdf)}...")
    sys.stdout.flush()
    t0 = time.time()
    try:
        result = subprocess.run(
            [PY, '-u', DEMO, pdf, '--task', task],
            capture_output=True, encoding='utf-8',
            cwd=os.path.dirname(pdf),
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
            timeout=timeout,
        )
        elapsed = time.time() - t0
        out_file = os.path.join(os.path.dirname(pdf), 'llm_summaries', f'main.{task}.mm3.md')
        if os.path.exists(out_file):
            sz = os.path.getsize(out_file)
            print(f"  OK ({elapsed:.1f}s, {sz:,} bytes, rc={result.returncode})")
            return True, elapsed
        else:
            print(f"  NO FILE ({elapsed:.1f}s, rc={result.returncode})")
            # 写 stderr
            err_file = f"F:\Research\_diag_{label}.txt"
            with open(err_file, "w", encoding="utf-8") as f:
                f.write(f"=== stdout (last 1000 chars) ===\n{result.stdout[-1000:]}\n\n=== stderr (last 2000 chars) ===\n{result.stderr[-2000:]}")
            print(f"  stderr saved to {err_file}")
            return False, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        print(f"  TIMEOUT ({elapsed:.1f}s > {timeout}s)")
        return False, elapsed
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  ERROR: {e}")
        return False, elapsed

print("=" * 70)
print("PHASE 2 BATCH 卡住诊断")
print("=" * 70)

# Step 1: 单次 (PAPER-C critique - 之前 batch 在这步之后卡住)
print("\n--- Step 1: 单次 PAPER-C critique ---")
ok, t = run_one("step1_single", r"F:\Research\calibration_contagion\main.pdf", "critique")

# Step 2: 连续 2 次 (不 sleep)
print("\n--- Step 2: 连续 2 次 (无 sleep) ---")
ok, t = run_one("step2_first", r"F:\Research\TEMPORAL_DYNAMICS\main.pdf", "summary")
ok, t = run_one("step2_second", r"F:\Research\TEMPORAL_DYNAMICS\main.pdf", "methods")

# Step 3: 检查 .env key
print("\n--- Step 3: 检查 API key ---")
from pathlib import Path
key_paths = [
    Path.home() / '.env',
    Path.home() / 'minimax.env',
    Path('F:/Research/.env'),
    Path('F:/Research/.loop/.env'),
]
for p in key_paths:
    if p.exists():
        content = p.read_text(encoding='utf-8', errors='ignore')
        if 'MINIMAX' in content or 'API_KEY' in content:
            masked = '\n'.join(
                line if 'KEY' not in line or not '=' in line
                else f"{line.split('=')[0]}=sk-***..."
                for line in content.splitlines() if line.strip()
            )
            print(f"  {p}: {len(content)} bytes")
            print(f"    {masked[:300]}")
            break
else:
    print("  No .env found!")

print()
print("=" * 70)
print("DONE")
print("=" * 70)