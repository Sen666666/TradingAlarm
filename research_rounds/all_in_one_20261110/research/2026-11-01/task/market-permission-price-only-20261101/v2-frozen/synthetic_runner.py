"""Narrow subprocess prefix harness. Accepts only explicitly synthetic fixtures."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
from signal_core import Observation, Source, loads, run, step


def main():
    rows = json.loads(Path(sys.argv[1]).read_text())
    observations = []
    for row in rows:
        if not row["source"]["universe"].startswith("synthetic-"):
            raise ValueError("historical shadow execution is not authorized")
        row["source"] = Source(**row["source"])
        observations.append(Observation(**row))
    if len(sys.argv) == 3:
        state = loads(Path(sys.argv[2]).read_text())
        if state.source is not None and not state.source.universe.startswith("synthetic-"):
            raise ValueError("historical checkpoint execution is not authorized")
        decisions = []
        for observation in observations:
            state, decision = step(state, observation)
            decisions.append(decision)
    else:
        state, decisions = run(tuple(observations), "global:synthetic")
    print(json.dumps({"state": asdict(state), "decisions": [asdict(d) for d in decisions],
                      "observations_read": len(rows)}, allow_nan=False))


if __name__ == "__main__":
    main()
