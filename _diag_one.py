"""simplest possible: just run demo for PAPER-C critique, save all output"""
import os, subprocess, time
DEMO = r"F:\Research\_inbox\方法论\zotero_pdf_summary_demo.py"
PY = r"C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.9.25-windows-x86_64-none\python.exe"
PDF = r"F:\Research\calibration_contagion\main.pdf"
LOG = r"F:\Research\_diag_one.log"

t0 = time.time()
print(f"Starting demo for PAPER-C critique at {time.strftime('%H:%M:%S')}")
result = subprocess.run(
    [PY, '-u', DEMO, PDF, '--task', 'critique'],
    capture_output=True, encoding='utf-8',
    cwd=r"F:\Research\calibration_contagion",
    env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
    timeout=60,  # 1 min only
)
elapsed = time.time() - t0
out = (result.stdout or '') + '\n--STDERR--\n' + (result.stderr or '')
with open(LOG, 'w', encoding='utf-8') as f:
    f.write(f"rc={result.returncode}\nelapsed={elapsed:.1f}s\n\n{out}")
print(f"DONE in {elapsed:.1f}s, rc={result.returncode}")
print(f"Log saved to {LOG}")