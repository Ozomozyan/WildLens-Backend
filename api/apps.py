#!/usr/bin/env python3
"""
ai/app.py – WildLens AI micro-service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

• Streams each upload directly into RAM; prediction images are *never* saved.
• Works with either:
    1. a TorchScript file produced by ``torch.jit.save(model)``, or
    2. the training script’s ``torch.save({"classes": classes, **state_dict})``
• Uses the same normalization that the training pipeline applied.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from PIL import Image
import io
import os
import torch
import json
from torchvision import transforms, models
from ai.predict import _latest_run

# ──────────────────────────────────────────────────────────────
# Environment / config
# ──────────────────────────────────────────────────────────────
APP_HOST   = "0.0.0.0"
APP_PORT   = int(os.getenv("PORT", 8001))
model_path_env = os.getenv("MODEL_PATH")
if model_path_env:
    MODEL_PATH = Path(model_path_env)
else:
    MODEL_PATH = _latest_run() / "model.pt"
DEVICE     = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ──────────────────────────────────────────────────────────────
# FastAPI instance (one per process)
# ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="WildLens Footprint Classifier",
    description="Stateless species-prediction micro-service",
    version="1.0",
)

# Optional CORS if you call the AI service directly from the front-end
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # relax as needed
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────
# Model + transforms (loaded once at startup)
# ──────────────────────────────────────────────────────────────
if not MODEL_PATH.exists():
    raise RuntimeError(f"Model weights not found: {MODEL_PATH}")

ckpt = torch.load(MODEL_PATH, map_location=DEVICE)

if isinstance(ckpt, torch.jit.ScriptModule):
    # TorchScript path
    model   = ckpt
    classes = os.getenv("CLASSES", "").split(",")  # fallback if wanted
else:
    # State-dict path (what the training script saves)
    classes = ckpt.pop("classes", None)
    if classes is None:
        classes = json.loads((MODEL_PATH.parent / "labels.json").read_text())
    model   = models.resnet18(weights=None)
    model.fc = torch.nn.Sequential(
        torch.nn.Linear(model.fc.in_features, 256),
        torch.nn.ReLU(inplace=True),
        torch.nn.Dropout(0.4),
        torch.nn.Linear(256, len(classes)),
    )
    model.load_state_dict(ckpt)

model.to(DEVICE).eval()

transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])

# ──────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────
@app.get("/ping", tags=["health"])
def ping():
    """Cheap liveness probe."""
    return {"status": "ok"}

@app.post("/predict", tags=["inference"])
async def predict(file: UploadFile = File(...)):
    """
    Accept **one** image (multipart/form-data “file” field) and
    return the top-1 class name + probability.
    """
    if file.content_type.split("/")[0] != "image":
        raise HTTPException(status_code=415, detail="File must be an image/*")

    try:
        img_bytes = await file.read()
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read image")

    tensor = transform(img).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        logits = model(tensor)
        probs  = torch.softmax(logits, dim=1)
        conf, idx = torch.max(probs, 1)

    label = classes[idx.item()] if classes else int(idx.item())
    return JSONResponse({"species": label, "confidence": round(conf.item(), 6)})

# ──────────────────────────────────────────────────────────────
# Local dev entry-point
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=APP_HOST, port=APP_PORT, reload=False)
