from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import optuna  
from pathlib import Path
import subprocess, os
from optuna.trial import TrialState 
from pydantic import BaseModel

router = APIRouter(prefix="/hpsearch", tags=["hpsearch"])

PYTHON = os.environ.get("PYTHON_EXEC", "python")
# /app/ai/api/hpsearch.py → parent.parent == /app/ai
BASE_DIR = Path(__file__).parent.parent               # /app/ai
HP_SCRIPT = BASE_DIR / "hyperparam_opt.py"            # ✔ /app/ai/hyperparam_opt.py
RUNS_DIR  = BASE_DIR / "runs" / "hpsearch"            #  /app/ai/runs/hpsearch
DB_PATH   = RUNS_DIR  

def _optuna_job(trials: int, study: str):
    subprocess.run([PYTHON, str(HP_SCRIPT),
                    "--trials", str(trials),
                    "--study-name", study])
    
# Request schema  ── JSON body → {"trials": 5, "study": "prod"}
class HpSearchReq(BaseModel):
    trials: int = 20
    study:  str = "prod"


@router.post("/")
def launch(req: HpSearchReq, bg: BackgroundTasks):
    bg.add_task(_optuna_job, req.trials, req.study)
    return {"status": "accepted",
            "trials":  req.trials,
            "study":   req.study}

@router.get("/{study}/best")
def get_best(study: str):
    """Return the best hyper-parameters of a study.

    • If the study does not exist → 404  
    • If the optimisation hasn’t produced a finished trial yet → 202  
    • Otherwise return `{params: …, value: …}` (JSON) **and** expose the YAML
      file when it is already written by `hyperparam_opt.py`.
    """
    db_url = f"sqlite:///{DB_PATH / (study + '.db')}"

    try:
        st = optuna.load_study(study_name=study, storage=db_url)
    except KeyError:
        raise HTTPException(status_code=404,
                            detail=f"Study '{study}' not found")

    # ---- Is at least one trial finished? ----
    finished = [t for t in st.trials if t.state == TrialState.COMPLETE]
    if not finished:
        raise HTTPException(status_code=202,
                            detail="Study is still running")

    # 1. return JSON (always available once a trial is completed)
    payload = {"params": st.best_params,
               "value":  st.best_value}

    # 2. if the YAML file already exists, stream it as attachment
    best_yaml = RUNS_DIR / study / "best_config.yaml"
    if best_yaml.exists():
        return FileResponse(best_yaml,
                            media_type="application/x-yaml",
                            filename="best_config.yaml")

    return payload                    # fallback to pure JSON
