import subprocess, sys, json, uuid, os
from pathlib import Path
from tests.dummy_data import make_dummy_dataset

AI_DIR = Path(__file__).parents[1]
RUNS   = AI_DIR / "runs"

def test_smoke(tmp_path, monkeypatch):
    data_root = tmp_path / "dummy"
    make_dummy_dataset(data_root)

    run_id = f"test-{uuid.uuid4().hex[:6]}"
    env = os.environ.copy()
    env.update({
        "SUPABASE_URL": "http://skip",
        "SUPABASE_KEY": "skip",
        "DUMMY_DATA_ROOT": str(data_root)        # train_model will pick this up
    })

    cmd = [sys.executable, AI_DIR/"train_model.py",
           "--run-id", run_id, "--epochs", "1", "--batch-size", "4",
           "--acc-steps", "2"]
    subprocess.run(cmd, env=env, check=True)

    arte = RUNS / run_id
    assert (arte/"model.pt").is_file()
    metrics = json.loads((arte/"metrics.json").read_text())
    assert "macro_f1" in metrics
