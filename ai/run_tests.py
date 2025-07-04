#!/usr/bin/env python3
"""
Runs pytest inside the container and prints a PASSED / FAILED summary.
"""

import subprocess, sys, pathlib, textwrap

AI_DIR = pathlib.Path(__file__).parent
result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "tests"],
    cwd=str(AI_DIR)
)
banner = "PASSED 🎉" if result.returncode == 0 else "FAILED ❌"
print(textwrap.dedent(f"""
─────────────────────────────────────────────
      Smoke-tests {banner}
─────────────────────────────────────────────
"""))
sys.exit(result.returncode)
