"""Train the compact P159 fire surrogate on a generated corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _mask_iou(first: np.ndarray, second: np.ndarray) -> float:
    """Return the intersection over union of two boolean masks."""
    union = np.logical_or(first, second).sum()
    if union == 0:
        return 1.0
    return float(np.logical_and(first, second).sum() / union)


def main() -> None:
    """Generate a corpus, fit the surrogate, and write the training record."""
    from ws4.fire.surrogate import generate_corpus, save_corpus
    from ws4.fire.surrogate_model import SurrogateModel

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "notes" / "reports" / "p159-corpus")
    parser.add_argument("--output", type=Path, default=ROOT / "notes" / "reports" / "p159-model")
    parser.add_argument("--count", type=int, default=120)
    parser.add_argument("--seed", type=int, default=159)
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--cols", type=int, default=32)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--hidden", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    args = parser.parse_args()
    corpus = generate_corpus(
        count=args.count,
        seed=args.seed,
        rows=args.rows,
        cols=args.cols,
        duration_min=args.duration,
    )
    corpus_manifest = save_corpus(corpus, args.corpus)
    model = SurrogateModel.fit(
        corpus,
        hidden_units=args.hidden,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        seed=args.seed,
    )
    model_path = model.save(args.output)
    validation = [sample for sample in corpus.samples if sample.split == "validation"]
    ious = [
        _mask_iou(model.predict_mask(sample), np.asarray(sample.burned_mask))
        for sample in validation
    ]
    record = {
        "corpus_manifest": str(corpus_manifest),
        "corpus": corpus.manifest(),
        "model": model.to_dict(),
        "validation_mask_iou_mean": float(np.mean(ious)),
        "validation_mask_iou_min": float(np.min(ious)),
        "validation_mask_iou_max": float(np.max(ious)),
        "model_path": str(model_path),
    }
    (args.output / "training.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(record["model"], indent=2, sort_keys=True))
    print("validation mask IoU mean", record["validation_mask_iou_mean"])


if __name__ == "__main__":
    main()
