#!/usr/bin/env python3
"""
Breakpoint model — standalone test runner.

Run from anywhere:  python run_tests.py
No pytest required. It discovers every test_* function in test_engine.py,
runs them, and prints a pass/fail summary. If pytest IS installed you can also
just run:  python -m pytest model/test_engine.py -v -s

These tests are the guarantee the economics are sound (calibration targets,
conservation invariants, the structural retailer P&L). Keep them green after
any change under model/.
"""
import sys
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
# test_engine.py and the model modules it imports (engine, mechanics, ...) all
# live in model/ now; put it on sys.path so the bare imports resolve.
sys.path.insert(0, str(_ROOT / "model"))

import test_engine as T  # noqa: E402

def main():
    tests = [getattr(T, n) for n in dir(T) if n.startswith("test_") and callable(getattr(T, n))]
    passed, failed = 0, []
    print(f"Discovered {len(tests)} tests in test_engine.py\n")
    for t in sorted(tests, key=lambda f: f.__name__):
        try:
            t()
            passed += 1
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            failed.append((t.__name__, e))
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed.")
    if failed:
        print("\nFailures:")
        for name, e in failed:
            print(f"\n--- {name} ---")
            traceback.print_exception(type(e), e, e.__traceback__)
        sys.exit(1)
    print("All model tests green.")

if __name__ == "__main__":
    main()
