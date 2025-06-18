# wildlens-ai/utils/dataset_stats.py
from pathlib import Path
import collections

def class_counts(img_root: Path):
    """
    Traverse img_root/<class_name>/**/*.{jpg,png} and
    return (counts, class_to_idx) where:
        counts = {idx: n_images}
        class_to_idx = {class_name: idx}
    """
    counter = collections.Counter(p.parent.name
                                  for p in img_root.rglob("*.[jp][pn]g"))
    classes = sorted(counter.keys())
    class_to_idx = {c: i for i, c in enumerate(classes)}
    return ({class_to_idx[c]: n for c, n in counter.items()}, class_to_idx)
