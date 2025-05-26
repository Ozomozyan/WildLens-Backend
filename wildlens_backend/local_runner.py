# local_runner.py  (replace the start_training() definition)

from django.conf import settings          # add this import near the top
import sys, datetime
import concurrent.futures
import threading

import subprocess

def _run_script(cmd):
    subprocess.run(cmd, check=True)

_RUNNING = False
_LOCK = threading.Lock()
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1)


# ─────────────────────────────────────────────────────────────────────────────
# Resolve the training script once at import-time.
#   settings.BASE_DIR → <repo-root>  (set in settings.py)
# Adjust the ../ai/ path as needed if you move things later.
TRAIN_SCRIPT = (settings.BASE_DIR / "ai" / "train_model.py").resolve()
if not TRAIN_SCRIPT.exists():
    raise FileNotFoundError(f"train_model.py not found at {TRAIN_SCRIPT}")

def start_training(batch_size: int, epochs: int) -> bool:
    """
    Kick off a background training job.
    Returns True if accepted, False if another run is already active.
    """
    global _RUNNING
    with _LOCK:
        if _RUNNING:
            return False
        _RUNNING = True

    cmd = [
        sys.executable,            # same interpreter that runs Django
        str(TRAIN_SCRIPT),
        "--run-id", datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S"),
        "--batch-size", str(batch_size),
        "--epochs",     str(epochs),
    ]
    _EXECUTOR.submit(_run_script, cmd)
    return True
