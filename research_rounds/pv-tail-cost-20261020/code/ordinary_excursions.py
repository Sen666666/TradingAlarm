"""Reproduce supplemental saved-path diagnostics in a new output directory."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

ROUND = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "Use a new output directory"
    source = ROUND / "attribution/all-episodes.csv"
    frame = pd.read_csv(source)
    result = {
        "scope": "Exploratory saved-path diagnostic at existing 30% tail observation boundary; not executable profit or rule threshold",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "markets": {},
    }
    for market, group in frame.groupby("market"):
        ordinary = group[(group.label == "ordinary") & (group.signal_close_mfe >= .30)]
        result["markets"][market] = {
            "ordinary_mfe_at_least_30_count": len(ordinary),
            "net_pp": float(ordinary.net_pp.sum()),
            "median_final_net_return_pct": float(ordinary.ret.median() * 100),
            "entries": ordinary[["id", "symbol", "entry", "exit", "ret",
                                 "signal_close_mfe", "net_pp"]].to_dict("records"),
        }
    args.output.mkdir(parents=True)
    (args.output / "ordinary-large-excursions.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
