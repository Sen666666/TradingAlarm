"""Join saved current-event facts with separate +5 response labels for review only."""
from pathlib import Path
import argparse
import pandas as pd

base = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    raise FileExistsError("Do not overwrite saved review evidence")
source = base / "results/v0"
events = pd.read_csv(source / "selected-events.csv")
facts = pd.read_csv(source / "daily-facts.csv")
outcomes = pd.read_csv(source / "response-outcomes.csv")
joined = events.loc[events.boundary != "none"].merge(
    facts, on=["case", "date", "boundary"], suffixes=("", "_ledger")
)
joined = joined.merge(
    outcomes.loc[outcomes.horizon == 5, [
        "event_id", "response_date", "response_close",
        "close_outside", "future_outside_count_observed",
    ]],
    on="event_id", suffixes=("", "_at_5"),
)
joined[[
    "event_id", "date", "boundary", "close", "boundary_value", "q",
    "close_location", "close_outside", "response_date", "response_close",
    "close_outside_at_5", "future_outside_count_observed",
]].to_csv(args.output, index=False)
