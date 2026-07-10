"""Step 1: PAPER-A detector 验证 (用 v5.1)"""
import os, sys
sys.path.insert(0, r'F:\Research\.loop')
from hallucination_check import run_hallucination_hook

print("=" * 60)
print("Step 1: PAPER-A (RESAMPLING_CALIBRATION) v5.1 detector 验证")
print("=" * 60)
passed, n_high, n_med, n_low, _ = run_hallucination_hook("PAPER-A", verbose=True)
print()
print("=" * 60)
print(f"FINAL: passed={passed}, HIGH={n_high}, MEDIUM={n_med}, LOW={n_low}")
print("=" * 60)