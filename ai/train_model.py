#!/usr/bin/env python3
"""
Train a WildLens footprint classifier with
 • transfer-learning (ResNet-18 pretrained on ImageNet)
 • two-phase training: (1) freeze backbone, (2) fine-tune whole net
 • class-balanced WeightedRandomSampler
 • focal-loss with per-class α-weights
 • ReduceLROnPlateau keyed to validation macro-F1

Artifacts are written to:
    ai/runs/<run-id>/model.pt , labels.json , metrics.json , confusion_matrix.png
"""
from __future__ import annotations

# ───────────────────────────── imports ─────────────────────────────
from pathlib import Path
from datetime import datetime, UTC
import argparse, os, json, tempfile, uuid, requests

import torch, torchvision
from torch import nn, optim
from torch.utils.data import DataLoader, WeightedRandomSampler
from torchvision import datasets, transforms
from torchvision.models import resnet18, ResNet18_Weights

from torchmetrics.classification import MulticlassF1Score
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
import matplotlib.pyplot as plt
import supabase
from dotenv import load_dotenv          # pip install python-dotenv

from utils.dataset_stats import class_counts

# ───────────────────────────── constants ──────────────────────────
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

IMG_SIZE     = 224
RUNS_DIR     = Path(__file__).parent / "runs"; RUNS_DIR.mkdir(exist_ok=True)
ACC_STEPS_DEFAULT = int(os.getenv("ACC_STEPS", 4))

IMNET_MEAN = (0.485, 0.456, 0.406)
IMNET_STD  = (0.229, 0.224, 0.225)

# ────────────────────────── tunables ────────────────────────────
PATIENCE      = int(os.getenv("EARLY_STOP_PATIENCE", 4))   # early-stop patience
LABEL_SMOOTH  = float(os.getenv("LABEL_SMOOTH", 0.10))     # 0 → off
WD_HEAD       = float(os.getenv("WD_HEAD", 1e-4))
WD_FINE       = float(os.getenv("WD_FINE", 5e-5))


# ──────────────────────── focal-loss helper ───────────────────────
class FocalLoss(nn.Module):
    """
    Multi-class focal loss with optional per-class α and label smoothing.
    """
    def __init__(self, alpha=None, gamma: float = 2.0, label_smooth: float = 0.0):
        super().__init__()
        self.alpha        = alpha          # tensor [C] or None
        self.gamma        = gamma
        self.label_smooth = label_smooth

    def forward(self, logits, targets):
        ce = nn.functional.cross_entropy(
            logits, targets,
            weight=self.alpha,
            reduction="none",
            label_smoothing=self.label_smooth  # ← just one line!
        )
        pt    = torch.exp(-ce)               # prob of correct class
        focal = ((1 - pt) ** self.gamma) * ce
        return focal.mean()


# ───────────────────────── data helpers ───────────────────────────
def fetch_metadata(sb):
    imgs  = sb.table("footprint_images").select("*").execute().data
    specs = sb.table("infos_especes").select("id,Espèce").execute().data
    name_map = {s["id"]: s["Espèce"] for s in specs}
    for row in imgs:
        row["label"] = name_map[row["species_id"]]
    return imgs

def download_dataset(rows, root: Path):
    from PIL import Image, UnidentifiedImageError
    for r in rows:
        tgt_dir = root / r["label"]; tgt_dir.mkdir(parents=True, exist_ok=True)
        tgt = tgt_dir / r["image_name"]
        if tgt.exists():
            try:
                with Image.open(tgt) as im: im.verify(); continue
            except (UnidentifiedImageError, OSError): tgt.unlink(missing_ok=True)
        try:
            with requests.get(r["image_url"], stream=True, timeout=30) as resp:
                resp.raise_for_status()
                with open(tgt, "wb") as f:
                    for chunk in resp.iter_content(1 << 16): f.write(chunk)
            with Image.open(tgt) as im: im.verify()
        except Exception as e:
            print(f"[WARN] skipped {r['image_url']} – {e}")
            tgt.unlink(missing_ok=True)

def build_dataloaders(root: Path, batch: int):
    tfm = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(IMNET_MEAN, IMNET_STD),
    ])
    full_ds = datasets.ImageFolder(root, tfm)
    if len(full_ds) == 0:
        raise RuntimeError(f"ImageFolder found 0 images in {root}")

    # prune corrupt entries
    ok_indices = [i for i,(p,_) in enumerate(full_ds.samples)
                  if Path(p).is_file()]

    # ─── stratified 80 / 20 split – keeps every class in each split ───
    from collections import defaultdict
    import random
    random.seed(0)                         # reproducible order

    by_cls = defaultdict(list)
    for idx in ok_indices:
        by_cls[ full_ds.targets[idx] ].append(idx)

    train_idx, val_idx = [], []
    for cls, idxs in by_cls.items():
        random.shuffle(idxs)
        k = max(1, int(0.8 * len(idxs)))  # at least 1 sample per split
        train_idx += idxs[:k]
        val_idx   += idxs[k:]


    train_ds = torch.utils.data.Subset(full_ds, train_idx)
    val_ds   = torch.utils.data.Subset(full_ds, val_idx)

    counts, _ = class_counts(root)
    max_n = max(counts.values())
    targets_subset = [full_ds.targets[i] for i in train_idx]
    weights = [max_n / counts[t] for t in targets_subset]
    sampler = WeightedRandomSampler(weights, num_samples=len(weights),
                                    replacement=True)
    
    # quick check that the WeightedRandomSampler sees each class
    from collections import Counter
    drawn = [targets_subset[i] for i in torch.multinomial(
                 torch.tensor(weights), 2000, replacement=True)]
    print("Sampler draw (2 000 samples):", Counter(drawn))


    train_loader = DataLoader(train_ds, batch_size=batch,
                              sampler=sampler, num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=batch,
                              shuffle=False, num_workers=0)

    print("Class counts :", counts)
    print("Sample wgt   :", {k: round(max_n/v,2) for k,v in counts.items()})
    return train_loader, val_loader, full_ds.classes, counts

# ───────────────────────── training logic ─────────────────────────
def evaluate(model, loader, device, n_classes):
    metric = MulticlassF1Score(num_classes=n_classes,
                               average="macro").to(device)
    y_true, y_pred = [], []
    model.eval()
    with torch.no_grad():
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            preds  = model(xb).argmax(1)
            metric.update(preds, yb)
            y_true.append(yb.cpu()); y_pred.append(preds.cpu())
    return metric.compute().item(), torch.cat(y_true).numpy(), torch.cat(y_pred).numpy()

def train_loop(train, val, n_classes, counts,
               epochs: int, acc_steps: int, freeze_epochs: int):
    """
    Two-phase training:
        phase-1 (frozen backbone)  : Adam on classifier head
        phase-2 (fine-tune entire) : Adam + cosine annealing
    Early-stops when val-macro-F1 hasn’t improved for PATIENCE epochs.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # ─── create model ───
    model = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
    model.fc = nn.Linear(model.fc.in_features, n_classes)

    for p in model.parameters():   p.requires_grad = False
    for p in model.fc.parameters(): p.requires_grad = True
    model.to(device)

    # ─── optimiser + scheduler (phase-1) ───
    lr_head = float(os.getenv("LR_HEAD", 5e-4))
    opt  = optim.Adam(model.fc.parameters(), lr=lr_head, weight_decay=WD_HEAD)
    sched = optim.lr_scheduler.ReduceLROnPlateau(
        opt, mode="max", factor=0.5, patience=2, min_lr=1e-5)

    # ─── focal-loss with label smoothing ───
    max_n  = max(counts.values())
    alpha  = torch.tensor([max_n / counts[c] for c in range(n_classes)],
                          dtype=torch.float, device=device)
    criterion = FocalLoss(alpha=alpha, gamma=2.0, label_smooth=LABEL_SMOOTH)

    best_f1      = 0.
    epochs_since = 0                       # early-stop counter

    eff_batch = train.batch_size * acc_steps
    print(f"[INFO] mini-batch={train.batch_size}  acc_steps={acc_steps}  "
          f"-> effective_batch={eff_batch}")

    for ep in range(epochs):

        # ─── switch to fine-tuning (unfreeze) ───
        if ep == freeze_epochs:
            for p in model.parameters(): p.requires_grad = True
            lr_fine = float(os.getenv("LR_FINE", 1e-4))
            opt  = optim.Adam(model.parameters(), lr=lr_fine, weight_decay=WD_FINE)
            sched = torch.optim.lr_scheduler.CosineAnnealingLR(
                opt, T_max=epochs-ep, eta_min=1e-6)
            print(f"[INFO] ↻ unfreezing backbone (lr={lr_fine}, wd={WD_FINE})")

        # ─── one epoch of training ───
        model.train()
        running = 0.
        opt.zero_grad()

        for i, (xb, yb) in enumerate(train, 1):
            xb, yb = xb.to(device), yb.to(device)
            loss   = criterion(model(xb), yb) / acc_steps
            loss.backward()

            if i % acc_steps == 0 or i == len(train):
                opt.step()
                opt.zero_grad()

            running += loss.item() * acc_steps

        # ─── evaluate ───
        val_f1,  _, _ = evaluate(model, val,   device, n_classes)
        train_f1, _, _ = evaluate(model, train, device, n_classes)
        print(f"[epoch {ep+1:02d}/{epochs}] "
              f"loss={running/len(train):.4f}  "
              f"trainF1={train_f1:.3f}  valF1={val_f1:.3f}")

        # update scheduler
        if isinstance(sched, optim.lr_scheduler.ReduceLROnPlateau):
            sched.step(val_f1)
        else:  # cosine
            sched.step()

        # ─── early stopping ───
        if val_f1 > best_f1 + 1e-4:
            best_f1      = val_f1
            epochs_since = 0
        else:
            epochs_since += 1
            if epochs_since >= PATIENCE:
                print(f"[INFO] Early-stopping after {ep+1} epochs "
                      f"(no valF1 gain for {PATIENCE} epochs)")
                break

    return model, best_f1

# ────────────────────────────── main ──────────────────────────────
def main(run_id, batch_size, epochs, acc_steps, freeze_epochs):

    dummy_root = os.getenv("DUMMY_DATA_ROOT")
    use_dummy  = bool(dummy_root)

    # 0. choose data source ---------------------------------------------------
    if use_dummy:
        print("[INFO] DUMMY_DATA_ROOT detected – skipping Supabase")
        rows = []                                      # not used
        data_parent = Path(dummy_root).expanduser().resolve()
    else:
        sb   = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)
        rows = fetch_metadata(sb)

    # 1. prepare workspace dir ------------------------------------------------
    if use_dummy:
        root = Path(tempfile.mkdtemp()) / "data"
        import shutil
        for src in data_parent.rglob("*.jpg"):
            dst = root / src.relative_to(data_parent)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    else:
        tmpdir = tempfile.TemporaryDirectory()         # keep reference!
        root   = Path(tmpdir.name) / "data"

        print("[*] Fetching metadata …")
        print(f"    → {len(rows):,} images / "
            f"{len(set(r['label'] for r in rows))} species")

        print("[*] Downloading images …")
        download_dataset(rows, root)

    # 2. common code: build loaders, train, save artefacts --------------------
    print("[*] Building dataloaders …")
    train, val, classes, counts = build_dataloaders(root, batch_size)

    print(f"[*] Training ({epochs} epochs)…")
    model, _ = train_loop(train, val, len(classes),
                        counts, epochs, acc_steps, freeze_epochs)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    macro_f1, y_true, y_pred = evaluate(model, val, device, len(classes))
    # … (rest of the saving code unchanged) …

    print(f"[OK] FINAL Macro-F1 = {macro_f1:.4f}")

    cm = confusion_matrix(y_true,y_pred,labels=range(len(classes)))
    fig,ax = plt.subplots(figsize=(6,6))
    disp = ConfusionMatrixDisplay(cm, display_labels=classes)
    disp.plot(ax=ax, colorbar=False, xticks_rotation=45)
    fig.tight_layout()

    artefacts = RUNS_DIR / run_id; artefacts.mkdir(parents=True, exist_ok=False)
    fig.savefig(artefacts/"confusion_matrix.png"); plt.close(fig)
    (artefacts/"metrics.json").write_text(json.dumps({
        "macro_f1": macro_f1,
        "epochs":   epochs,
        "effective_batch": batch_size*acc_steps
    },indent=2))

    torch.save({"classes":classes, "state_dict":model.state_dict()},
                artefacts/"model.pt")
    (artefacts/"labels.json").write_text(json.dumps(classes,ensure_ascii=False,indent=2))
    print("[OK] Saved model and metrics to", artefacts.relative_to(Path.cwd()))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=datetime.now(UTC).strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:6])
    ap.add_argument("--batch-size", type=int, default=int(os.getenv("TRAIN_BATCH_SIZE", 32)))
    ap.add_argument("--epochs",     type=int, default=int(os.getenv("TRAIN_EPOCHS",   30)))
    ap.add_argument("--acc-steps",  type=int, default=ACC_STEPS_DEFAULT)
    ap.add_argument("--freeze-epochs", type=int, default=int(os.getenv("FREEZE_EPOCHS", 5)),
                    help="epochs to train head-only before fine-tuning backbone")
    main(**vars(ap.parse_args()))
