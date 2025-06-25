import torch, torchvision
from pathlib import Path

MODEL_PATH = Path(__file__).parents[1] / "runs" / "latest" / "model.pt"

def load_model():
    model = torchvision.models.resnet18(weights=None)
    model.fc = torch.nn.Linear(model.fc.in_features, 13)   # adjust #classes later

    if MODEL_PATH.exists():
        ckpt = torch.load(MODEL_PATH, map_location="cpu")
        # New format has {"state_dict": ..., "classes": [...]}
        if isinstance(ckpt, dict) and "state_dict" in ckpt:
            model.load_state_dict(ckpt["state_dict"])
            classes = ckpt.get("classes", [])
        else:                                              # legacy file
            model.load_state_dict(ckpt)
            classes = []
        print(f"[AI] model loaded from {MODEL_PATH}")
    else:
        print(f"[AI] WARNING: {MODEL_PATH} not found – using random weights")
        classes = []

    model.eval()
    return model, classes

model, CLASSES = load_model()
