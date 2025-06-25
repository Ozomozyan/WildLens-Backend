import httpx, os
AI_URL = os.getenv("AI_SERVICE_URL", "http://ai:8001")  # matches compose

def launch_hp_search(trials: int = 20, study: str = "prod"):
    r = httpx.post(f"{AI_URL}/hpsearch/", json={"trials": trials, "study": study}, timeout=10.0)
    r.raise_for_status()
    return r.json()

def download_best_config(study: str = "prod") -> str:
    r = httpx.get(f"{AI_URL}/hpsearch/{study}/best", timeout=10.0)
    r.raise_for_status()
    return r.text
