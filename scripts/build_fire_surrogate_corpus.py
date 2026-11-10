"""Build a deterministic synthetic fire-surrogate corpus from the WS4 kernel."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    """Generate and save a corpus."""
    from ws4.fire.surrogate import generate_corpus, save_corpus

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "notes" / "reports" / "p159-corpus")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=159)
    parser.add_argument("--rows", type=int, default=24)
    parser.add_argument("--cols", type=int, default=24)
    parser.add_argument("--duration", type=float, default=60.0)
    args = parser.parse_args()
    corpus = generate_corpus(
        count=args.count,
        seed=args.seed,
        rows=args.rows,
        cols=args.cols,
        duration_min=args.duration,
    )
    manifest = save_corpus(corpus, args.output)
    print(manifest)


if __name__ == "__main__":
    main()
