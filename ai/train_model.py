#!/usr/bin/env python3
"""
Train a fresh WildLens image-classifier, pulling every row from
`footprint_images` ⇆ `infos_especes`.

The trained model is saved permanently to:

    ai/runs/<run-id>/model.pt
    ai/runs/<run-id>/labels.json
"""
from __future__ import annotations

from torchmetrics.classification import MulticlassF1Score
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
import matplotlib.pyplot as plt

import argparse, os, tempfile, json, uuid, requests
from datetime import datetime, UTC
from pathlib import Path

import supabase
import torch, torchvision
from torchvision import datasets, transforms
from torch import nn, optim

from utils.dataset_stats import class_counts
from torch.utils.data import DataLoader, WeightedRandomSampler


from dotenv import load_dotenv      # ← new: pip install python-dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

# ────────────────────────────────  CONSTANTS  ────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")      # bypasses RLS
IMG_SIZE     = 224                            # keep this fixed

ACC_STEPS_DEFAULT = int(os.getenv("ACC_STEPS", 1))   # gradient-accum steps


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
    """Stream every image; skip if URL dead or file unreadable."""
    import errno
    from PIL import Image, UnidentifiedImageError

    for r in rows:
        tgt_dir = root / r["label"]
        tgt_dir.mkdir(parents=True, exist_ok=True)
        tgt = tgt_dir / r["image_name"]

        if tgt.exists():
            # Quick integrity check — remove if unreadable
            try:
                with Image.open(tgt) as im:
                    im.verify()
                continue                       # fine
            except (FileNotFoundError, UnidentifiedImageError, OSError):
                tgt.unlink(missing_ok=True)    # force re-download

        try:
            with requests.get(r["image_url"], stream=True, timeout=30) as resp:
                resp.raise_for_status()
                with open(tgt, "wb") as f:
                    for chunk in resp.iter_content(1 << 16):
                        f.write(chunk)
            # second integrity check
            with Image.open(tgt) as im:
                im.verify()
        except Exception as e:                 # 404, corruption, etc.
            print(f"[WARN] skipped {r['image_url']} – {e}")
            tgt.unlink(missing_ok=True)        # ensure bad file is gone

def build_dataloaders(root: Path, batch: int):
    tfm = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
    ])
    full_ds = datasets.ImageFolder(root, tfm)

    if len(full_ds) == 0:
        raise RuntimeError(f"ImageFolder found 0 images in {root}")

    # ─── prune out any samples whose files are missing or corrupt ────────────
    ok_indices = [
        i for i, (path, _) in enumerate(full_ds.samples)
        if Path(path).is_file()
    ]
    if len(ok_indices) < len(full_ds):
        print(f"[INFO] pruned {len(full_ds) - len(ok_indices)} broken entries")

    # ─── now do an 80/20 split on only the OK indices ───────────────────────
    n = len(ok_indices)
    split = int(0.8 * n)
    train_idx = ok_indices[:split]
    val_idx   = ok_indices[split:]

    train_ds = torch.utils.data.Subset(full_ds, train_idx)
    val_ds   = torch.utils.data.Subset(full_ds, val_idx)

    # ─── class-balanced sampler ─────────────────────────────────────────────
    counts, _ = class_counts(root)
    max_n = max(counts.values())
    targets_subset = [full_ds.targets[i] for i in train_idx]
    weights = [max_n / counts[t] for t in targets_subset]
    sampler = WeightedRandomSampler(weights,
                                    num_samples=len(weights),
                                    replacement=True)

    train_loader = DataLoader(
        train_ds,
        batch_size=batch,
        sampler=sampler,
        num_workers=4,
    )
    # <<< validation loader with single worker to avoid crashes >>>
    val_loader = DataLoader(
        val_ds,
        batch_size=batch,
        shuffle=False,
        num_workers=0,
    )

    print("Class counts :", counts)
    print("Sample wgt   :", {k: round(max_n/v, 2) for k, v in counts.items()})
    return train_loader, val_loader, full_ds.classes


def train_loop(train, val, n_classes: int, epochs: int, acc_steps: int):
    model = torchvision.models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, n_classes)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    
    lr = float(os.getenv("LR_OVERRIDE", 1e-4))        # Optuna sets these
    wd = float(os.getenv("WD_OVERRIDE", 0.0))
    dp = float(os.getenv("DROPOUT",     0.0))

    # override dropout probability in every Dropout layer, if any
    if dp > 0:
        for m in model.modules():
            if isinstance(m, nn.Dropout):
                m.p = dp

    opt = optim.Adam(model.parameters(), lr=lr, weight_decay=wd)
    ce  = nn.CrossEntropyLoss()

    eff_batch = train.batch_size * acc_steps
    print(f"[INFO] mini-batch={train.batch_size}  acc_steps={acc_steps}  "
          f"→ effective_batch={eff_batch}")

    best_f1 = 0.0
    for ep in range(epochs):
        model.train()
        running = 0.0
        opt.zero_grad()                         # clear once per epoch

        for i, (xb, yb) in enumerate(train, 1):
            xb, yb = xb.to(device), yb.to(device)
            loss = ce(model(xb), yb) / acc_steps   # scale
            loss.backward()

            if i % acc_steps == 0 or i == len(train):
                opt.step()
                opt.zero_grad()

            running += loss.item() * acc_steps     # undo scaling for log

        # after the training loop for this epoch, evaluate on validation set
        macro_f1, _, _ = evaluate(model, val, device, n_classes)
        print(f"[epoch {ep+1:02d}/{epochs}] "
            f"loss={running/len(train):.4f}  macroF1={macro_f1:.4f}")
        
        best_f1 = max(best_f1, macro_f1)

    return model


def evaluate(model, loader, device, n_classes: int):
    """Return (macro_f1, y_true, y_pred) on the given loader."""
    metric = MulticlassF1Score(num_classes=n_classes,
                               average="macro").to(device)
    model.eval()
    all_true, all_pred = [], []

    with torch.no_grad():
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            logits = model(xb)
            preds  = logits.argmax(dim=1)
            metric.update(preds, yb)
            all_true.append(yb.cpu())
            all_pred.append(preds.cpu())

    macro_f1 = metric.compute().item()
    y_true = torch.cat(all_true).numpy()
    y_pred = torch.cat(all_pred).numpy()
    return macro_f1, y_true, y_pred


# ────────────────────────────────  MAIN  ─────────────────────────────────────
def main(run_id: str, batch_size: int, epochs: int, acc_steps: int):
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

        print(f"[*] Training for {epochs} epochs (batch={batch_size}, acc_steps={acc_steps}) …")
        model = train_loop(train, val, len(classes), epochs, acc_steps)

        # ─── FINAL EVAL + CONFUSION MATRIX ────────────────────────────────────
        device = "cuda" if torch.cuda.is_available() else "cpu"    # <─ NEW
        macro_f1, y_true, y_pred = evaluate(model, val, device, len(classes))
        print(f"[✓] FINAL Macro-F1 = {macro_f1:.4f}")

        cm = confusion_matrix(y_true, y_pred, labels=range(len(classes)))
        fig, ax = plt.subplots(figsize=(6, 6))
        disp = ConfusionMatrixDisplay(cm, display_labels=classes)
        disp.plot(ax=ax, colorbar=False, xticks_rotation=45)
        fig.tight_layout()

        # Create the run directory and persist artifacts
        artefacts = RUNS_DIR / run_id
        artefacts.mkdir(parents=True, exist_ok=False)

        fig.savefig(artefacts / "confusion_matrix.png")
        plt.close(fig)

        (artefacts / "metrics.json").write_text(json.dumps({
            "macro_f1": macro_f1,
            "epochs": epochs,
            "effective_batch": batch_size * acc_steps
        }, indent=2))
        # ────────────────────────────────────────────────────────────────────────

        # ─── THEN save the model + labels as before ───────────────────────────
        torch.save(
            {"classes": classes, "state_dict": model.state_dict()},
            artefacts / "model.pt",
        )
        (artefacts / "labels.json").write_text(
            json.dumps(classes, ensure_ascii=False, indent=2)
        )

        print("[✓] Saved model and metrics to", artefacts.relative_to(Path.cwd()))

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
    argp.add_argument("--acc-steps", type=int, default=ACC_STEPS_DEFAULT,
                    help="number of gradient-accumulation steps (>=1)")
    main(**vars(argp.parse_args()))
