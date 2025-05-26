#!/usr/bin/env python3
"""
Train a fresh WildLens image-classifier, pulling every row from
`footprint_images` ⇆ `infos_especes`.

The trained model is saved permanently to:

    ai/runs/<run-id>/model.pt
    ai/runs/<run-id>/labels.json
"""

from __future__ import annotations
import argparse, os, tempfile, json, uuid, requests
from datetime import datetime, UTC
from pathlib import Path

import supabase
import torch, torchvision
from torchvision import datasets, transforms
from torch import nn, optim

from dotenv import load_dotenv      # ← new: pip install python-dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

# ────────────────────────────────  CONSTANTS  ────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")      # bypasses RLS
IMG_SIZE     = 224                            # keep this fixed

# Permanent location for trained artefacts
RUNS_DIR = Path(__file__).parent / "runs"
RUNS_DIR.mkdir(exist_ok=True, parents=True)

# ────────────────────────────────  HELPERS  ──────────────────────────────────
def fetch_metadata(sb):
    """Return list of images with a human-readable 'label' key."""
    imgs  = sb.table("footprint_images").select("*").execute().data
    specs = sb.table("infos_especes").select("id,Espèce").execute().data
    name_map = {s["id"]: s["Espèce"] for s in specs}
    for row in imgs:
        row["label"] = name_map[row["species_id"]]
    return imgs

def download_dataset(rows, root: Path):
    """Stream every image to data/<species>/<file>; skip if already present."""
    for r in rows:
        lbl_dir = root / r["label"]
        lbl_dir.mkdir(parents=True, exist_ok=True)
        tgt = lbl_dir / r["image_name"]
        if tgt.exists():
            continue
        with requests.get(r["image_url"], stream=True, timeout=30) as resp:
            resp.raise_for_status()
            with open(tgt, "wb") as f:
                for chunk in resp.iter_content(1 << 16):
                    f.write(chunk)

def build_dataloaders(root: Path, batch: int):
    tfm = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
    ])
    ds     = datasets.ImageFolder(root, tfm)
    n      = len(ds)
    split  = int(0.8 * n)
    train_ds, val_ds = torch.utils.data.random_split(ds, [split, n - split])
    train = torch.utils.data.DataLoader(train_ds, batch, shuffle=True, num_workers=4)
    val   = torch.utils.data.DataLoader(val_ds,   batch, num_workers=2)
    return train, val, ds.classes

def train_loop(train, val, n_classes: int, epochs: int):
    model = torchvision.models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, n_classes)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    opt = optim.Adam(model.parameters(), lr=1e-4)
    ce  = nn.CrossEntropyLoss()

    for ep in range(epochs):
        model.train()
        running = 0.0
        for xb, yb in train:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            loss = ce(model(xb), yb)
            loss.backward()
            opt.step()
            running += loss.item()
        print(f"[epoch {ep+1:02d}/{epochs}] train-loss = {running/len(train):.4f}")

    return model

# ────────────────────────────────  MAIN  ─────────────────────────────────────
def main(run_id: str, batch_size: int, epochs: int):
    sb = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)

    # Use a temp dir ONLY for the image cache
    with tempfile.TemporaryDirectory() as tmpdir:
        data_root = Path(tmpdir) / "data"

        print("[*] Fetching metadata …")
        rows = fetch_metadata(sb)
        print(f"    → {len(rows):,} images / {len(set(r['label'] for r in rows))} species")

        print("[*] Downloading images …")
        download_dataset(rows, data_root)

        print("[*] Building dataloaders …")
        train, val, classes = build_dataloaders(data_root, batch_size)

        print(f"[*] Training for {epochs} epochs (batch={batch_size}) …")
        model = train_loop(train, val, len(classes), epochs)

    # ─── Save artefacts permanently ──────────────────────────────────────────
    artefacts = RUNS_DIR / run_id
    artefacts.mkdir(parents=True, exist_ok=False)
    
    torch.save(
        {
            "classes": classes,           # <─ the label names in the order used by the model
            "state_dict": model.state_dict(),
        },
        artefacts / "model.pt",
    )

    torch.save(model.state_dict(), artefacts / "model.pt")
    (artefacts / "labels.json").write_text(
        json.dumps(classes, ensure_ascii=False, indent=2)
    )

    print("[✓] Saved model to", artefacts.relative_to(Path.cwd()))

if __name__ == "__main__":
    argp = argparse.ArgumentParser()
    argp.add_argument(
        "--run-id",
        default=datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6],
        help="unique identifier; auto-generated if omitted",
    )
    argp.add_argument("--batch-size", type=int,
                      default=int(os.getenv("TRAIN_BATCH_SIZE", 32)))
    argp.add_argument("--epochs", type=int,
                      default=int(os.getenv("TRAIN_EPOCHS", 10)))
    main(**vars(argp.parse_args()))
