"""use Popen for real-time output to see where demo hangs"""
import os, subprocess, time
DEMO = r"F:\Research\_inbox\方法论\zotero_pdf_summary_demo.py"
PY = r"C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.9.25-windows-x86_64-none\python.exe"
PDF = r"F:\Research\calibration_contagion\main.pdf"
LOG = r"F:\Research\_diag_realtime.log"

print(f"Starting demo at {time.strftime('%H:%M:%S')}")
with open(LOG, 'w', encoding='utf-8') as f:
    t0 = time.time()
    proc = subprocess.Popen(
        [PY, '-u', DEMO, PDF, '--task', 'critique'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        cwd=r"F:\Research\calibration_contagion",
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
    )
    while True:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            if time.time() - t0 > 60:
                proc.kill()
                f.write(f"\n[TIMEOUT after 60s, killed]\n")
                break
            time.sleep(0.1)
            continue
        f.write(line)
        f.flush()
        print(line.rstrip())
    rc = proc.wait() if proc.poll() is None else proc.poll()
    elapsed = time.time() - t0
    f.write(f"\n\nrc={rc}\nelapsed={elapsed:.1f}s\n")
    print(f"\nDONE: rc={rc}, elapsed={elapsed:.1f}s")
print(f"Log: {LOG}")