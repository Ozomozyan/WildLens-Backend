from pathlib import Path
import torch
from torchvision.utils import save_image

def make_dummy_dataset(root: Path, n_per_class: int = 4):
    root.mkdir(parents=True, exist_ok=True)
    classes = ["cat", "dog", "bear"]
    for c in classes:
        (root / c).mkdir(exist_ok=True)
        for i in range(n_per_class):
            img = torch.randn(3, 224, 224)
            save_image(img, root / c / f"{c}_{i}.jpg")
