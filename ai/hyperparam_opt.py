#!/usr/bin/env python3
"""
Optuna hyper-parameter search for ai/train_model.py
Maximises validation Macro-F1. Best params are saved to
    ai/runs/hpsearch/<study>/best_config.yaml
"""
from __future__ import annotations
import subprocess, sys, json, uuid, yaml, os
from pathlib import Path
import optuna
from optuna.exceptions import TrialPruned

# ───────────────────────── paths ─────────────────────────
THIS_DIR  = Path(__file__).parent
RUNS_DIR  = THIS_DIR / "runs"
HP_DIR    = RUNS_DIR / "hpsearch";   HP_DIR.mkdir(exist_ok=True, parents=True)
TRAIN_PY  = THIS_DIR / "train_model.py"

# ───────────────────── objective fn ──────────────────────
def objective(trial: optuna.Trial) -> float:

    # ── define search space ──────────────────────────────
    lr_head  = trial.suggest_float("lr_head",  1e-5, 5e-3, log=True)
    lr_fine  = trial.suggest_float("lr_fine",  1e-5, 1e-3, log=True)
    wd_head  = trial.suggest_float("wd_head",  1e-6, 1e-3, log=True)
    wd_fine  = trial.suggest_float("wd_fine",  1e-6, 5e-4, log=True)
    dropout  = trial.suggest_float("dropout",  0.0,  0.5)
    batch_sz = trial.suggest_categorical("batch_size", [8, 16, 32])
    acc_steps= trial.suggest_categorical("acc_steps",  [1, 2])

    # ── launch one training run ──────────────────────────
    run_id = f"hp-{trial.number}-{uuid.uuid4().hex[:6]}"
    cmd = [
        sys.executable, str(TRAIN_PY),
        "--run-id",        run_id,
        "--batch-size",    str(batch_sz),
        "--acc-steps",     str(acc_steps),
        "--freeze-epochs", "2",      # so every 6-epoch trial fine-tunes 4
        "--epochs",        "6",
    ]

    env = {
        **os.environ,
        "PYTHONHASHSEED":  "0",
        # names already read inside train_model.py
        "LR_HEAD":  str(lr_head),
        "LR_FINE":  str(lr_fine),
        "WD_HEAD":  str(wd_head),
        "WD_FINE":  str(wd_fine),
        "DROPOUT":  str(dropout),
        # DataLoader housekeeping (optional)
        "NUM_WORKERS": "0",
        "PIN_MEMORY":  "0",
    }

    try:
        subprocess.run(cmd, env=env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as exc:
        # -9 (SIGKILL) or -11 (SIGSEGV)  ⇒ likely out-of-memory – prune
        if exc.returncode in (-9, -11):
            raise TrialPruned()
        raise

    # ── read back the validation score ──────────────────
    metrics = RUNS_DIR / run_id / "metrics.json"
    macro_f1 = json.loads(metrics.read_text())["macro_f1"]

    trial.set_user_attr("run_id", run_id)     # for pretty plots
    return macro_f1

# ────────────────────────── main ─────────────────────────
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials",      type=int, default=30)
    ap.add_argument("--study-name",  default="wildlens_hp")
    args = ap.parse_args()

    storage = f"sqlite:///{HP_DIR / (args.study_name + '.db')}"
    study = optuna.create_study(direction="maximize",
                                study_name=args.study_name,
                                storage=storage,
                                load_if_exists=True)

    study.optimize(objective, n_trials=args.trials, show_progress_bar=True)

    # ── report & save best config ────────────────────────
    if study.best_trial:
        print("\n[✓] Best value :", study.best_value)
        print("[✓] Best params :", study.best_params)

        out_cfg = HP_DIR / args.study_name / "best_config.yaml"
        out_cfg.parent.mkdir(parents=True, exist_ok=True)
        yaml.dump(study.best_params, out_cfg.open("w"))
        print("[✓] saved      :", out_cfg.relative_to(Path.cwd()))

        # ─── persist best model where the API expects it ───────────────
        import shutil                                       # ← std-lib, safe to import here
        best_run = Path(study.best_trial.user_attrs["run_id"])
        src_dir  = RUNS_DIR / best_run
        dst_dir  = RUNS_DIR / "hpsearch"                    # already created on top
        shutil.copy(src_dir / "model.pt",  dst_dir / "model.pt")
        shutil.copy(src_dir / "labels.json", dst_dir / "labels.json")
        print(f"[✓] exported best checkpoint → {dst_dir/'model.pt'}")

    else:
        print("[!] No successful trials – nothing to save.")

