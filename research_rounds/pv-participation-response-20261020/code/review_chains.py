"""Audit every saved v0 memory and draw every independent recovery, without PnL.

No candidate, upstream detector, or account is imported/recomputed. All later
observations are retrospective chain diagnostics, never inputs to event labels.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / "results/v0"
REVIEWS = BASE / "reviews"
FIGURES = REVIEWS / "event-chain-figures"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def string_date(value):
    return pd.Timestamp(value).strftime("%Y-%m-%d") if pd.notna(value) else ""


def dump(path, value):
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def first_index(frame, column, start):
    found = np.flatnonzero(frame[column].to_numpy()[start:] == 1)
    return int(start + found[0]) if len(found) else None


def event_chain(symbol, row, frame, all_events):
    created = int(frame.index.get_loc(pd.Timestamp(row.created_date)))
    resolved = int(frame.index.get_loc(pd.Timestamp(row.resolved_date))) if pd.notna(row.resolved_date) else None
    end = resolved if resolved is not None else len(frame) - 1
    original_before = frame.iloc[created:end]
    same_all = all_events.loc[all_events.created_date.eq(row.created_date)]
    record = {
        "key": f"{symbol}-E{int(row.id):03d}", "symbol": symbol,
        **row.to_dict(),
        "original_active_at_create": int(frame.original_target.iloc[created]),
        "original_active_before_resolution": bool(original_before.original_target.eq(1).any()),
        "original_entries_during_memory": int(frame.original_entered.iloc[created:end + 1].sum()),
        "original_active_at_resolution": int(frame.original_target.iloc[resolved]) if resolved is not None else None,
        "same_created_date_in_all_declines": bool(len(same_all)),
        "all_same_date_outcome": str(same_all.iloc[0].outcome) if len(same_all) else "",
        "all_same_date_waiting": int(same_all.iloc[0].waiting_observations) if len(same_all) else None,
        "all_same_date_independent": int(same_all.iloc[0].independent_entry) if len(same_all) else None,
        "memory_older_than21": bool(row.waiting_observations > 21),
        "first_failure_date": "", "eligible_observations_until_failure": None,
        "next_original_entry_date": "", "original_entry_delay": None,
        "extra_eligibility_before_first_failure": None,
        "missing_eligibility_before_first_failure": None,
        "comparison_through_date": "", "extra_eligibility_through_exit_plus20": None,
        "missing_eligibility_through_exit_plus20": None,
        "first_failure_within5": None, "next_candidate_entry_after_failure": "",
        "retry_gap_observations": None, "retry_within5": None,
        "failure_floor_above_event_lower": None,
    }
    if resolved is not None and row.outcome in ("reclaimed", "base_confirmed"):
        failure = first_index(frame, "exited", resolved + 1)
        stop = failure if failure is not None else len(frame)
        chain = frame.iloc[resolved:stop]
        comparison_stop = min(len(frame), failure + 21) if failure is not None else len(frame)
        comparison = frame.iloc[resolved:comparison_stop]
        next_original = first_index(frame, "original_entered", resolved)
        retry = first_index(frame, "entered", failure + 1) if failure is not None else None
        record.update(
            first_failure_date=string_date(frame.index[failure]) if failure is not None else "",
            eligible_observations_until_failure=stop - resolved,
            failure_censored=failure is None,
            next_original_entry_date=string_date(frame.index[next_original]) if next_original is not None else "",
            original_entry_delay=next_original - resolved if next_original is not None else None,
            extra_eligibility_before_first_failure=int(((chain.target == 1) & (chain.original_target == 0)).sum()),
            missing_eligibility_before_first_failure=int(((chain.target == 0) & (chain.original_target == 1)).sum()),
            comparison_through_date=string_date(comparison.index[-1]),
            extra_eligibility_through_exit_plus20=int(((comparison.target == 1) & (comparison.original_target == 0)).sum()),
            missing_eligibility_through_exit_plus20=int(((comparison.target == 0) & (comparison.original_target == 1)).sum()),
            first_failure_within5=bool(stop - resolved <= 5) if failure is not None else False,
            next_candidate_entry_after_failure=string_date(frame.index[retry]) if retry is not None else "",
            retry_gap_observations=retry - failure if retry is not None else None,
            retry_within5=bool(retry - failure <= 5) if retry is not None else False,
            failure_floor_above_event_lower=bool(
                frame.floor.iloc[failure] > row.lower
                and not np.isclose(frame.floor.iloc[failure], row.lower, atol=1e-10, rtol=1e-10)
            ) if failure is not None else None,
        )
    return record


def chart_window(record, frame):
    created = int(frame.index.get_loc(pd.Timestamp(record["created_date"])))
    resolved = int(frame.index.get_loc(pd.Timestamp(record["resolved_date"])))
    failure = int(frame.index.get_loc(pd.Timestamp(record["first_failure_date"]))) if record["first_failure_date"] else None
    start = max(0, created - 20)
    end = min(len(frame) - 1, max(resolved + 20, failure + 20 if failure is not None else len(frame) - 1))
    return frame.iloc[start:end + 1], created, resolved, failure, start, end


def draw_panel(fig, spec, record, frame, compact=False):
    q, created, resolved, failure, start, end = chart_window(record, frame)
    sub = spec.subgridspec(3, 1, height_ratios=[3.2, 1, 1.1], hspace=.08)
    price = fig.add_subplot(sub[0])
    volume = fig.add_subplot(sub[1], sharex=price)
    state = fig.add_subplot(sub[2], sharex=price)
    x = np.arange(len(q))
    for n, bar in enumerate(q.itertuples()):
        color = "#29779a" if bar.close >= bar.open else "#bb6848"
        price.vlines(n, bar.low, bar.high, color=color, lw=.65)
        bottom, top = min(bar.open, bar.close), max(bar.open, bar.close)
        if bottom == top:
            price.hlines(bar.close, n - .3, n + .3, color=color, lw=1)
        else:
            price.add_patch(Rectangle((n - .3, bottom), .6, top - bottom,
                                      facecolor=color, edgecolor=color, linewidth=.4))
    price.plot(x, q.floor, color="#176a3f", lw=1, label="Candidate floor")
    price.plot(x, q.original_floor, color="#777777", lw=.9, ls=":", label="Original floor")
    price.hlines(record["reclaim"], created - start, len(q) - 1,
                 color="#3160a6", ls="--", lw=1, label="A: previous close")
    price.hlines(record["lower"], created - start, len(q) - 1,
                 color="#af4d58", ls="--", lw=1, label="B: event low")
    marks = [
        (created, "#b48311", "Create"), (resolved, "#1b8546", "Recover"),
    ]
    if failure is not None:
        marks.append((failure, "#87459d", "First invalidation"))
    for absolute, color, label in marks:
        for axis in (price, volume, state):
            axis.axvline(absolute - start, color=color, lw=.8, ls=":")
        price.scatter(absolute - start, frame.close.iloc[absolute], color=color, s=25, zorder=5)
    for axis in (price, volume, state):
        axis.axvspan(resolved - start + .5, len(q) - .5, color="#d9dfe5", alpha=.16)
        axis.grid(alpha=.13)
    price.set_yscale("log")
    price.set_title(
        f"{record['key']} | {record['created_date']} -> {record['resolved_date']}\n"
        f"wait {int(record['waiting_observations'])}; to first invalidation "
        f"{record['eligible_observations_until_failure']} obs; extra {record['extra_eligibility_before_first_failure']}",
        fontsize=9 if compact else 11,
    )
    price.legend(fontsize=5.8 if compact else 7, ncol=2, loc="best")
    price.tick_params(axis="y", labelsize=7 if compact else 8)
    volume.bar(x, q.volume, color="#929c9f", width=.75)
    full_reference = frame.volume.shift(1).rolling(21, min_periods=21).median()
    volume.plot(x, full_reference.reindex(q.index), color="#b4820c", lw=.9)
    volume.set_ylim(bottom=0)
    volume.set_ylabel("Volume", fontsize=7 if compact else 9)
    volume.tick_params(axis="y", labelsize=6 if compact else 8)
    for offset, field, label, color in (
        (3, "target", "candidate", "#176a3f"),
        (1.5, "original_target", "original", "#555555"),
        (0, "all_target", "all declines", "#99529c"),
    ):
        state.step(x, q[field] + offset, where="post", color=color, lw=1)
        state.text(.005, offset + .35, label, transform=state.get_yaxis_transform(),
                   fontsize=6 if compact else 8, bbox=dict(facecolor="white", edgecolor="none", alpha=.7))
    state.set_yticks([0, 1, 1.5, 2.5, 3, 4], ["0", "1", "0", "1", "0", "1"], fontsize=6)
    ticks = np.unique(np.linspace(0, len(q) - 1, min(5 if compact else 8, len(q))).astype(int))
    state.set_xticks(ticks, q.index[ticks].strftime("%Y-%m-%d"), rotation=20, ha="right",
                    fontsize=6 if compact else 8)
    plt.setp(price.get_xticklabels(), visible=False)
    plt.setp(volume.get_xticklabels(), visible=False)
    return {
        "first": string_date(q.index[0]), "last": string_date(q.index[-1]),
        "prior_observations": created - start, "following_resolution_observations": end - resolved,
        "following_first_failure_observations": end - failure if failure is not None else None,
        "source_end_censored": end == len(frame) - 1,
    }


def ledger_summary(frame):
    if frame.empty:
        return {"events": 0}
    waiting = pd.to_numeric(frame.waiting_observations)
    return {
        "events": len(frame), "outcomes": {str(k): int(v) for k, v in frame.outcome.value_counts().items()},
        "independent_entries": int(pd.to_numeric(frame.independent_entry).sum()),
        "waiting_median": float(waiting.median()), "waiting_max": int(waiting.max()),
        "waiting_over21": int(waiting.gt(21).sum()),
        "created_on_exit": int(pd.to_numeric(frame.created_on_exit).sum()),
    }


def main():
    destinations = [
        REVIEWS / "event-chains.csv", REVIEWS / "all-declines-event-chains.csv",
        REVIEWS / "event-chain-summary.json", REVIEWS / "event-chain-figure-index.json",
    ]
    if FIGURES.exists() or any(path.exists() for path in destinations):
        raise FileExistsError("Refuse overwrite of event-chain review")
    source_manifest = json.loads((SOURCE / "manifest.json").read_text())
    frames, records, allrecords, sources = {}, [], [], {}
    for path in sorted(SOURCE.glob("*-volume-events.csv")):
        symbol = path.name.removesuffix("-volume-events.csv")
        state_path, all_path = SOURCE / f"{symbol}-states.csv", SOURCE / f"{symbol}-all-events.csv"
        for item in (path, state_path, all_path):
            assert sha(item) == source_manifest[item.name], item
            sources[str(item.relative_to(BASE))] = sha(item)
        frame = pd.read_csv(state_path, index_col="date", parse_dates=True)
        events, allevents = pd.read_csv(path), pd.read_csv(all_path)
        frames[symbol] = frame
        assert int(frame.independent_entry.sum()) == int(events.independent_entry.sum())
        assert len(events) == int(frame.created.sum())
        for _, row in events.iterrows():
            records.append(event_chain(symbol, row, frame, allevents))
        allrecords.extend(allevents.assign(symbol=symbol).to_dict("records"))
    table, alltable = pd.DataFrame(records), pd.DataFrame(allrecords)
    assert len(table) == 226 and int(table.independent_entry.sum()) == 26
    independent = table.loc[table.independent_entry.eq(1)].sort_values(["symbol", "created_date"])
    REVIEWS.mkdir(exist_ok=True)
    FIGURES.mkdir()
    table.to_csv(REVIEWS / "event-chains.csv", index=False)
    alltable.to_csv(REVIEWS / "all-declines-event-chains.csv", index=False)
    figures = []
    for record in independent.to_dict("records"):
        fig = plt.figure(figsize=(12, 8))
        layout = fig.add_gridspec(1, 1, left=.08, right=.98, bottom=.09, top=.91)
        bounds = draw_panel(fig, layout[0], record, frames[record["symbol"]])
        fig.text(.01, .01, "All independent recoveries included. Gray area: later chain diagnosis, not event-day information. No trades or PnL.",
                 fontsize=8, color="#555555")
        destination = FIGURES / f"{record['key']}.png"
        fig.savefig(destination, dpi=120)
        plt.close(fig)
        figures.append({
            "key": record["key"], "file": str(destination.relative_to(BASE)),
            "sha256": sha(destination), **bounds,
        })
    sheets = []
    records = independent.to_dict("records")
    for start in range(0, len(records), 4):
        group = records[start:start + 4]
        fig = plt.figure(figsize=(18, 14))
        layout = fig.add_gridspec(2, 2, left=.055, right=.985, top=.95, bottom=.055, hspace=.25, wspace=.16)
        for n, record in enumerate(group):
            draw_panel(fig, layout[n // 2, n % 2], record, frames[record["symbol"]], compact=True)
        fig.suptitle(f"All independent recovery chains | Sheet {start // 4 + 1} / 7", fontsize=15)
        fig.text(.01, .012, "Create=gold; Recover=green; First invalidation=purple. Gray area is retrospective follow-through. No PnL. Inputs: saved v0, numerical audit pending.",
                 fontsize=10, color="#555555")
        destination = FIGURES / f"sheet-{start // 4 + 1:02d}.png"
        fig.savefig(destination, dpi=120)
        plt.close(fig)
        sheets.append({"file": str(destination.relative_to(BASE)), "keys": [r["key"] for r in group], "sha256": sha(destination)})
    summary = {
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "Saved-v0 chain diagnosis; numerical validation has unresolved boundaries; no promotion claim",
        "code_sha256": sha(Path(__file__)), "source_manifest_sha256": sha(SOURCE / "manifest.json"),
        "input_files": sources,
        "definitions": {
            "independent": "Saved independent_entry flag; not assumed to mean better or profitable",
            "first_failure": "First later candidate exited=1, on eligible price observation clock",
            "extra_before_failure": "Candidate=1 and original=0 from recovery through before first candidate invalidation",
            "extended_comparison": "Recovery through first invalidation plus 20 observations, or data end",
            "short5": "Descriptive <=5-observation failure/retry bin, not an algorithm parameter",
            "long_memory21": "Descriptive >21-observation waiting bin, not an expiry rule",
            "post_event": "All later observations explicitly retrospective, never used as event-day input",
        },
        "volume": ledger_summary(table), "all_declines": ledger_summary(alltable),
        "independent": {
            "count": len(independent),
            "original_active_at_create": int(independent.original_active_at_create.sum()),
            "original_active_at_recovery": int(independent.original_active_at_resolution.sum()),
            "original_entered_during_memory": int(independent.original_entries_during_memory.sum()),
            "failure_within5": int(independent.first_failure_within5.sum()),
            "retry_within5_after_failure": int(independent.retry_within5.sum()),
            "median_observations_to_failure": float(independent.eligible_observations_until_failure.median()),
            "max_observations_to_failure": int(independent.eligible_observations_until_failure.max()),
            "extra_eligibility_before_first_failure": int(independent.extra_eligibility_before_first_failure.sum()),
            "missing_eligibility_before_first_failure": int(independent.missing_eligibility_before_first_failure.sum()),
            "extra_eligibility_through_exit_plus20": int(independent.extra_eligibility_through_exit_plus20.sum()),
            "missing_eligibility_through_exit_plus20": int(independent.missing_eligibility_through_exit_plus20.sum()),
            "extended_windows_overlap_warning": "Extended counts may overlap across events and are not unique asset-day or account statistics",
            "same_created_date_in_all_declines": int(independent.same_created_date_in_all_declines.sum()),
            "by_symbol": {str(k): int(v) for k, v in independent.symbol.value_counts().items()},
        },
        "same_date_event_matching": {
            "volume_events_also_created_in_all_declines": int(table.same_created_date_in_all_declines.sum()),
            "interpretation": "Other events can be absent because an earlier all-decline memory or structure occupies that period; not a randomized volume treatment",
        },
        "account_runs": 0, "candidate_runs": 0, "pnl_calculations": 0,
    }
    dump(REVIEWS / "event-chain-summary.json", summary)
    dump(REVIEWS / "event-chain-figure-index.json", {
        "created_utc": summary["created_utc"], "figures": figures, "sheets": sheets,
        "source_files": sources, "code_sha256": summary["code_sha256"],
        "every_independent_entry_plotted": len(figures) == 26,
    })
    print(json.dumps({"volume": summary["volume"], "all_declines": summary["all_declines"], "independent": summary["independent"]}))


if __name__ == "__main__":
    main()
