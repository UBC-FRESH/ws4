"""Run the synthetic stochastic fire demo.

This is the end-to-end example for the P144 fire vertical slice. It builds a small grid
landscape, runs thirty years of Poisson ignitions, state-dependent spread, cohort mortality,
and salvage, then prints the account summary and the replay digest.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ws4.ecosystem import run_fire_demo  # noqa: E402


def main() -> None:
    """Run the demo and print its account summary."""
    result = run_fire_demo(rows=5, cols=5, years=30, seed=7)
    accounts = result.accounts
    final_year = accounts[accounts["year"] == accounts["year"].max()]
    print("Synthetic stochastic fire demo")
    print(f"events: {len(result.log.events)}")
    print(f"fire events: {len(result.fires)}")
    print(f"salvage events: {len(result.salvage)}")
    print(f"replay digest: {result.log.replay_token}")
    print("final-year accounts:")
    for row in final_year.sort_values("account").itertuples(index=False):
        print(f"  {row.account}: {row.value:.3f}")


if __name__ == "__main__":
    main()
