#!/usr/bin/env python3
"""
Run an Optuna study that launches multiple training runs of
ai/train_model.py and maximises Macro-F1 on the validation set.

The best config is written to:
    ai/runs/hpsearch/<study_name>/best_config.yaml
"""

from __future__ import annotations
import subprocess, sys, json, uuid, yaml, shutil
from pathlib import Path
import optuna

THIS_DIR   = Path(__file__).parent
RUNS_DIR   = THIS_DIR / "runs"
HP_DIR     = RUNS_DIR / "hpsearch"
HP_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_PY   = THIS_DIR / "train_model.py"

# -------------------------------------------------------------------------
def objective(trial: optuna.Trial) -> float:
    # ---- define the search space ----------------------------------------
    lr          = trial.suggest_loguniform("lr",          1e-5,  1e-2)
    wd          = trial.suggest_loguniform("weight_decay",1e-6,  1e-3)
    dropout     = trial.suggest_float      ("dropout",    0.0,   0.5)
    batch_size  = trial.suggest_categorical("batch_size", [16, 32, 64])
    acc_steps   = trial.suggest_categorical("acc_steps",  [1, 2, 4])

    # ---- launch one training run ----------------------------------------
    run_id = f"hp-{trial.number}-{uuid.uuid4().hex[:6]}"
    cmd = [
        sys.executable, str(TRAIN_PY),
        "--run-id",    run_id,
        "--batch-size",str(batch_size),
        "--acc-steps", str(acc_steps),
        "--epochs",    "6",                 # keep it short per trial
    ]
    # pass LR / WD / dropout via env vars understood inside train_model.py
    env = {**os.environ,
           "PYTHONHASHSEED":"0",
           "LR_OVERRIDE": str(lr),
           "WD_OVERRIDE": str(wd),
           "DROPOUT":     str(dropout)}
    subprocess.run(cmd, env=env, check=True, stdout=subprocess.DEVNULL)

    # ---- read back the macro-F1 -----------------------------------------
    metrics_path = RUNS_DIR / run_id / "metrics.json"
    with open(metrics_path) as f:
        macro_f1 = json.load(f)["macro_f1"]

    # Let Optuna know so it can show pretty plots
    trial.set_user_attr("run_id", run_id)
    return macro_f1

# -------------------------------------------------------------------------
if __name__ == "__main__":
    import os, argparse

    argp = argparse.ArgumentParser()
    argp.add_argument("--trials", type=int, default=30)
    argp.add_argument("--study-name", default="wildlens_hp")
    args = argp.parse_args()

    storage_url = f"sqlite:///{HP_DIR / (args.study_name + '.db')}"
    study = optuna.create_study(direction="maximize",
                                study_name=args.study_name,
                                storage=storage_url,
                                load_if_exists=True)

    study.optimize(objective, n_trials=args.trials, show_progress_bar=True)

    print("[✓] Best value:", study.best_value)
    print("[✓] Best params:", study.best_params)

    # ---- persist best config --------------------------------------------
    out_cfg = HP_DIR / args.study_name / "best_config.yaml"
    out_cfg.parent.mkdir(parents=True, exist_ok=True)
    with open(out_cfg, "w") as f:
        yaml.dump(study.best_params, f)

    print("[✓] saved:", out_cfg.relative_to(Path.cwd()))
