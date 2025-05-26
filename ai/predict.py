#!/usr/bin/env python3
"""
WildLens – footprint inference helper
=====================================

  $ python ai/predict.py photo.jpg
  Beaver (93.7%)

The script looks for the *latest* run in ai/runs/, reconstructs the model
and returns the predicted class + confidence.
"""

from __future__ import annotations
from pathlib import Path
import argparse, json
import torch, torchvision
from torchvision import transforms
from torch import nn
from PIL import Image

# ───────────────────────── configuration ─────────────────────────
IMG_SIZE = 224
RUNS_DIR = Path(__file__).parent / "runs"

# ────────────────────────── core helpers ─────────────────────────
def _latest_run() -> Path:
    runs = [p for p in RUNS_DIR.iterdir() if p.is_dir()]
    if not runs:
        raise RuntimeError(f"No runs found in {RUNS_DIR}")
    # run-id starts with YYYYMMDD-HHMMSS so lexicographic max == newest
    return max(runs, key=lambda p: p.name)

def load_model(device: str | torch.device = "cpu"):
    run_dir = _latest_run()
    labels  = json.loads((run_dir / "labels.json").read_text())
    n_cls   = len(labels)

    model = torchvision.models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, n_cls)

    state = torch.load(run_dir / "model.pt", map_location=device)
    model.load_state_dict(state)
    model.to(device).eval()
    return model, labels

_tf = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),                         # training used no normalisation
])

@torch.inference_mode()
def predict(img_path: str | Path, model=None, labels=None,
            device: str | torch.device | None = None):
    if model is None or labels is None:
        device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        model, labels = load_model(device)

    device = next(model.parameters()).device if device is None else device
    img = Image.open(img_path).convert("RGB")
    tensor = _tf(img).unsqueeze(0).to(device)

    logits = model(tensor)
    probs  = torch.softmax(logits, 1)
    conf, idx = torch.max(probs, 1)
    return labels[idx.item()], conf.item()

# ───────────────────────────── CLI ───────────────────────────────
def _cli():
    ap = argparse.ArgumentParser("WildLens footprint predictor")
    ap.add_argument("image", type=Path, help="path to an image file")
    args = ap.parse_args()

    label, conf = predict(args.image)
    print(f"{label} ({conf:.1%})")

if __name__ == "__main__":
    _cli()
