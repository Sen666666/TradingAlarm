"""Narrow subprocess prefix harness. Accepts only explicitly synthetic fixtures."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
from signal_core import Observation, Source, run


def main():
    rows = json.loads(Path(sys.argv[1]).read_text())
    observations = []
    for row in rows:
        if not row["source"]["universe"].startswith("synthetic-"):
            raise ValueError("historical shadow execution is not authorized")
        row["source"] = Source(**row["source"])
        observations.append(Observation(**row))
    state, decisions = run(tuple(observations), "global:synthetic")
    print(json.dumps({"state": asdict(state), "decisions": [asdict(d) for d in decisions],
                      "observations_read": len(rows)}, allow_nan=False))


if __name__ == "__main__":
    main()
