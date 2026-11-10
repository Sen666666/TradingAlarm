"""Read-only arithmetic on all v0-verified volume-event signal ledgers."""
from pathlib import Path
import hashlib
import json
import os
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/tradingalarm-event-chain-mpl")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROUND = Path(__file__).resolve().parents[1]
SOURCE = ROUND / "results/v0-verified"
OUT = Path(__file__).resolve().parent
FIG = OUT / "supplemental"
FIG.mkdir(exist_ok=True)
inputs = []
rows = []
states = {}
ledger_count = 0
for path in sorted(SOURCE.glob("*-volume-events.csv")):
    symbol = path.name.removesuffix("-volume-events.csv")
    ledger_count += 1
    try:
        events = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        events = pd.DataFrame()
    state_path = SOURCE / f"{symbol}-states.csv"
    frame = pd.read_csv(state_path)
    assert frame.date.is_unique and frame.date.is_monotonic_increasing
    states[symbol] = frame
    index = {d: i for i, d in enumerate(frame.date)}
    inputs.append({"symbol": symbol, "ledger": path.name, "events": len(events),
                   "ledger_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                   "states_sha256": hashlib.sha256(state_path.read_bytes()).hexdigest()})
    for _, e in events.iterrows():
        event_id, start = int(e.id), str(e.created_date)
        outcome = int(e.outcome)
        end = str(e.resolved_date) if pd.notna(e.resolved_date) else None
        a, b = index[start], index[end] if end else len(frame)-1
        pending_rows = frame.loc[frame.pending_id.eq(event_id)]
        blocked_dates = pending_rows.loc[pending_rows.blocked_price_event.eq(1), "date"].tolist()
        record = {
            "symbol": symbol, "event_id": event_id, "created_date": start,
            "resolved_date": end, "outcome": outcome, "observed_through": frame.date.iloc[-1],
            "wait_observations": b-a, "wait_calendar_days": (pd.Timestamp(frame.date.iloc[b])-pd.Timestamp(start)).days,
            "wait_is_censored": end is None, "pending_rows_including_creation": len(pending_rows),
            "event_high": e.high, "event_low": e.low,
            "width_pct": (e.high/e.low-1)*100, "volume_ratio": e.volume_ratio,
            "attempt": e.attempt, "reference_peak": e.reference_peak, "reference_trough": e.reference_trough,
            "blocked_original_up_count": len(blocked_dates),
            "blocked_original_up_dates": "|".join(blocked_dates),
            "resolution_day_original_up": int(frame.loc[b, "price_event"] == 1) if end else None,
            "down_resolution_same_day_up_veto": int(outcome == -1 and frame.loc[b, "price_event"] == 1) if end else None,
            "resolution_day_entered": int(frame.loc[b, "entered"]) if end else None,
            "resolution_day_entry_kind": frame.loc[b, "entry_kind"] if end else None,
            "first_invalidated_date": None, "up_to_invalidation_observations": None,
            "up_invalidation_censored_at_end": None, "up_observed_survival_observations": None,
            "next_up_after_down_date": None, "down_to_next_up_observations": None,
            "next_up_after_down_kind": None, "next_up_after_invalidation_date": None,
            "invalidation_to_next_up_observations": None, "next_up_after_invalidation_kind": None,
            "next_volume_event_date": None, "resolution_to_next_volume_event_observations": None,
        }
        assert int(frame.loc[a, "created"]) == 1
        assert int(frame.loc[a, "pending_id"]) == event_id
        if end:
            assert int(frame.loc[b, "resolved"]) == outcome
            assert int(frame.loc[b, "resolution_id"]) == event_id
        if outcome == 1:
            assert frame.loc[b, "entered"] == 1 and frame.loc[b, "target"] == 1
            later = frame.loc[b+1:]
            invalid = later.index[later.exited.eq(1)]
            if len(invalid):
                stop = int(invalid[0])
                record["first_invalidated_date"] = frame.loc[stop, "date"]
                record["up_to_invalidation_observations"] = stop-b
                record["up_invalidation_censored_at_end"] = False
                subsequent = frame.loc[stop+1:]
                retry = subsequent.index[subsequent.entered.eq(1)]
                if len(retry):
                    n = int(retry[0])
                    record["next_up_after_invalidation_date"] = frame.loc[n, "date"]
                    record["invalidation_to_next_up_observations"] = n-stop
                    record["next_up_after_invalidation_kind"] = frame.loc[n, "entry_kind"]
            else:
                record["up_invalidation_censored_at_end"] = True
            record["up_observed_survival_observations"] = (
                record["up_to_invalidation_observations"] if len(invalid) else len(frame)-1-b)
        if outcome == -1:
            later = frame.loc[b+1:]
            retry = later.index[later.entered.eq(1)]
            if len(retry):
                n = int(retry[0])
                record["next_up_after_down_date"] = frame.loc[n, "date"]
                record["down_to_next_up_observations"] = n-b
                record["next_up_after_down_kind"] = frame.loc[n, "entry_kind"]
        if end:
            later_events = events.loc[events.created_date.gt(end)]
            if len(later_events):
                next_date = str(later_events.sort_values("created_date").iloc[0].created_date)
                record["next_volume_event_date"] = next_date
                record["resolution_to_next_volume_event_observations"] = index[next_date]-b
        rows.append(record)

result = pd.DataFrame(rows).sort_values(["created_date", "symbol", "event_id"]).reset_index(drop=True)
assert ledger_count == 14
assert len(result) == 23
result.to_csv(OUT / "event-chain-review.csv", index=False)
selected = []
for outcome in [-1, 0, 1]:
    group = result.loc[result.outcome.eq(outcome)]
    if len(group):
        selected.append((f"earliest_outcome_{outcome}", group.iloc[0]))
longest = result.sort_values(["wait_observations", "created_date"], ascending=[False, True]).iloc[0]
selected.append(("longest_observed_pending", longest))
seen = set()
plots = []
for reason, e in selected:
    key = (e.symbol, int(e.event_id))
    if key in seen:
        continue
    seen.add(key)
    d = states[e.symbol]
    a = int(d.index[d.date.eq(e.created_date)][0])
    b = int(d.index[d.date.eq(e.resolved_date)][0]) if pd.notna(e.resolved_date) else len(d)-1
    lo, hi = max(0, a-25), min(len(d), b+41)
    window = d.iloc[lo:hi].copy()
    fig, axes = plt.subplots(3, 1, figsize=(15, 9), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1, 1]}, layout="constrained")
    for j, (_, row) in enumerate(window.iterrows()):
        color = "#c63737" if row.close >= row.open else "#147e76"
        axes[0].vlines(j, row.low, row.high, color=color, linewidth=.8)
        if abs(row.close-row.open) > 1e-12:
            axes[0].add_patch(Rectangle((j-.32, min(row.open,row.close)), .64,
                                       abs(row.close-row.open), color=color, linewidth=.2))
        else:
            axes[0].hlines(row.close, j-.32, j+.32, color=color, linewidth=.8)
        if np.isfinite(row.volume):
            axes[1].bar(j, row.volume, color=color, width=.7)
    for value in [e.event_low, e.event_high]:
        axes[0].hlines(value, a-lo, b-lo, linestyle="--", color="#ba8b17", linewidth=1.4)
    axes[0].axvspan(a-lo, b-lo, alpha=.1, color="#ba8b17")
    axes[0].axvline(a-lo, color="#ba8b17", label="event created")
    if pd.notna(e.resolved_date):
        axes[0].axvline(b-lo, color="#633ba4", label="event resolved")
    if pd.notna(e.first_invalidated_date):
        failure = int(d.index[d.date.eq(e.first_invalidated_date)][0])
        if lo <= failure < hi:
            axes[0].axvline(failure-lo, color="#333333", linestyle=":", label="first UP invalidation")
    axes[2].step(range(len(window)), window.original_target, where="post", color="#777777", label="original", alpha=.8)
    axes[2].step(range(len(window)), window.target, where="post", color="#14835a", label="candidate", alpha=.8)
    axes[2].step(range(len(window)), window.pending, where="post", color="#ba8b17", label="pending", linestyle="--")
    ticks = np.linspace(0, len(window)-1, min(9,len(window)), dtype=int)
    axes[2].set_xticks(ticks, window.date.iloc[ticks], rotation=30, ha="right")
    axes[0].set_title(f"{reason} | {e.symbol} event {int(e.event_id)} | {e.created_date} | outcome {int(e.outcome)}\n"
                      "Exploratory saved-signal review; no accounts or trade returns")
    axes[0].set_ylabel("Adjusted OHLC"); axes[1].set_ylabel("Saved volume")
    axes[2].set_ylabel("Signal only"); axes[2].set_ylim(-.1, 1.1)
    axes[0].legend(loc="best"); axes[2].legend(loc="upper left", ncol=3)
    for ax in axes:
        ax.grid(alpha=.15)
    path = FIG / f"{reason}-{e.symbol}-{int(e.event_id)}.png"
    fig.savefig(path, dpi=120); plt.close(fig)
    plots.append({"reason": reason, "symbol": e.symbol, "event_id": int(e.event_id),
                  "file": str(path.relative_to(OUT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "window_start": window.date.iloc[0], "window_end": window.date.iloc[-1]})
summary = {
    "source": str(SOURCE), "scope": "All 14 volume-event ledgers; 23 signal events; no accounts or PnL",
    "definitions": {
        "wait_observations": "Audited price observations after creation through resolution, or last observed date; creation has age zero",
        "blocked_original_up": "Stored blocked_price_event==1 rows assigned by pending_id; includes creation day if blocked there",
        "up_survival": "Audited observations after up resolution to first candidate exited==1; end-of-data is right censored",
        "retry": "Next candidate entered==1 after negative resolution or first UP invalidation; may use unchanged original event",
        "event_width": "Frozen high/low - 1, descriptive only; not normalized risk or account exposure",
        "plots": "Post-result exploratory selection: earliest created event for each outcome and longest observed pending; deduplicated; +40 post-resolution observations",
    },
    "ledger_count": ledger_count, "event_count": len(result),
    "outcomes": {str(k):int(v) for k,v in result.outcome.value_counts().sort_index().items()},
    "resolved_wait": result.loc[result.outcome.ne(0),"wait_observations"].describe().to_dict(),
    "pending_blocked_count": int(result.blocked_original_up_count.sum()),
    "events_with_pending_block": int(result.blocked_original_up_count.gt(0).sum()),
    "down_resolution_same_day_up_veto": int(result.down_resolution_same_day_up_veto.fillna(0).sum()),
    "inputs": inputs, "plots": plots,
    "csv_sha256": hashlib.sha256((OUT/"event-chain-review.csv").read_bytes()).hexdigest(),
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
(OUT/"event-chain-review-summary.json").write_text(json.dumps(summary, indent=2)+"\n")
print(result[["symbol","event_id","created_date","resolved_date","outcome","wait_observations","width_pct",
              "blocked_original_up_count","first_invalidated_date","up_to_invalidation_observations",
              "next_up_after_down_date","down_to_next_up_observations",
              "next_up_after_invalidation_date","invalidation_to_next_up_observations"]].round(3).to_string(index=False))
print(json.dumps({k:summary[k] for k in ["outcomes","resolved_wait","pending_blocked_count","events_with_pending_block","down_resolution_same_day_up_veto"]}))
