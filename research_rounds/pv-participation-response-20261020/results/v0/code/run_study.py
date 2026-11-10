"""Fixed signal-only study. New output directories, no account imports."""
from pathlib import Path
import argparse, datetime as dt, hashlib, json, shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from numeric import event_frame_numeric
from legacy_event_structure import event_frame
from participation import participation_frame
from data_utils import load_inputs
from ranking import rank_frames
ROOT = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def draw(case, d, out):
    q = d.loc[case["start"]:case["end"]]
    x = np.arange(len(q))
    fig, ax = plt.subplots(3, 1, figsize=(15, 10), sharex=True,
                           gridspec_kw={"height_ratios": [3, 1, 1.4]})
    for i, (_, b) in enumerate(q.iterrows()):
        color = "#237b9e" if b.close >= b.open else "#c96c48"
        ax[0].vlines(i, b.low, b.high, color=color, lw=.65)
        ax[0].add_patch(Rectangle((i-.3, min(b.open, b.close)), .6,
                                  abs(b.close-b.open) or b.close*1e-5,
                                  facecolor=color, edgecolor=color, lw=.4))
    ax[0].plot(x, q["floor"], color="#177447", lw=1.1, label="Candidate structure floor")
    ax[0].plot(x, q.original_floor, color="#777777", ls=":", lw=.9, label="Numeric baseline floor")
    ax[0].plot(x, q.pending_reclaim, color="#b48519", ls="--", lw=1, label="Reclaim / invalidation reference")
    ax[0].plot(x, q.pending_lower, color="#b48519", ls="--", lw=1)
    for col, marker, color, label in [
        ("created", "s", "#bf8c16", "High-participation decline recorded"),
        ("entered", "^", "#077b3e", "Candidate UP established"),
        ("exited", "v", "#ab3030", "Candidate invalidated")]:
        mask = q[col].eq(1).to_numpy()
        ax[0].scatter(x[mask], q.close.iloc[np.flatnonzero(mask)], marker=marker,
                      color=color, s=25, label=label, zorder=4)
    ax[0].set_yscale("log")
    ax[0].set_ylabel("Adjusted OHLC / log scale")
    ax[0].legend(loc="best", fontsize=7, ncol=2)
    ax[0].set_title(f'{case["id"]} | {case["symbol"]} | Participation-response v0\n'
                    "Signal states only; markers are not trades")
    ax[1].bar(x, q.volume_ratio.clip(upper=8), color="#9aa3a6", width=.8)
    ax[1].axhline(2, color="#bf8c16", ls="--", lw=1)
    ax[1].set_ylabel("V / prior21 median\n(display capped 8)")
    for offset, col, label, color in [
        (4.5, "target", "candidate", "#177447"),
        (3, "original_target", "numeric PV base", "#555555"),
        (1.5, "all_target", "all declines", "#a763a0"),
        (0, "price_target", "price original", "#217baf")]:
        ax[2].step(x, q[col] + offset, where="post", color=color, lw=1.2)
        ax[2].text(.003, offset+.35, label, transform=ax[2].get_yaxis_transform(),
                   fontsize=8, color=color, bbox={"facecolor":"white", "alpha":.8,"edgecolor":"none"})
    ax[2].set_yticks([0,1,1.5,2.5,3,4,4.5,5.5], ["0","1","0","1","0","1","0","1"])
    ax[2].set_ylabel("UP structure eligibility")
    ticks = np.unique(np.linspace(0, len(q)-1, min(9, len(q))).astype(int))
    ax[2].set_xticks(ticks, q.index[ticks].strftime("%Y-%m-%d"), rotation=30, ha="right")
    for a in ax:
        a.grid(alpha=.15)
    fig.text(.01,.005,"Seen development history. All-declines ablates only the NEW volume selection; "
             "upstream event detector remains PV. No account results.",fontsize=8,color="#555555")
    fig.tight_layout(rect=(0,.025,1,1))
    fig.savefig(out, dpi=120)
    plt.close(fig)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    out = Path(args.output).resolve()
    if out.parent != (ROOT / "results").resolve():
        raise ValueError("output must be a direct child of this round's results")
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    (out / "code").mkdir()
    (out / "figures").mkdir()
    files = ["numeric.py", "legacy_event_structure.py", "participation.py",
             "ranking.py", "data_utils.py", "run_study.py"]
    freeze = {
        "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "code": {f: sha(ROOT / "code" / f) for f in files},
        "protocol_sha256": sha(ROOT / "protocol.md"),
        "inputs_manifest_sha256": sha(ROOT / "inputs/manifest.json"),
        "account_calls": 0,
    }
    for f in files:
        shutil.copy2(ROOT / "code" / f, out / "code" / f)
    shutil.copy2(ROOT / "protocol.md", out / "protocol.md")
    (out / "run-freeze.json").write_text(json.dumps(freeze, indent=2))
    frames, cases, _ = load_inputs(ROOT)
    ranks = rank_frames(frames)
    summaries, checks, case_stats = [], [], []
    for symbol, bars in frames.items():
        source = pd.read_csv(ROOT / "inputs" / f"{symbol}.csv", index_col="date", parse_dates=True)
        original = event_frame_numeric(source.close, source.volume)
        price = event_frame_numeric(source.close, source.volume, joint=False)
        legacy = event_frame(source.close, source.volume)
        none, _ = participation_frame(bars, original, "none")
        expected = original.reindex(bars.index)
        differences = {col: int(none[col].ne(expected[col]).sum())
                       for col in ("target", "entered", "exited")}
        np.testing.assert_allclose(none.floor, expected.structure_floor_price, equal_nan=True,
                                   atol=1e-10, rtol=1e-10)
        assert not any(differences.values()), (symbol, differences)
        excluded = original.loc[~original.index.isin(bars.index)]
        assert excluded[["event", "entered", "exited"]].eq(0).all().all()
        checks.append({"symbol": symbol, "none_identity": differences,
                       "excluded_transition_count": int(excluded.event.ne(0).sum())})
        candidate, ledger = participation_frame(bars, original, "volume")
        all_declines, all_ledger = participation_frame(bars, original, "all")
        d = bars[["open", "high", "low", "close", "volume"]].join(candidate).join(ranks[symbol])
        d["original_target"] = expected.target
        d["original_floor"] = expected.structure_floor_price
        d["original_entered"] = expected.entered
        d["original_exited"] = expected.exited
        d["price_target"] = price.target.reindex(bars.index)
        d["all_target"] = all_declines.target
        d["legacy_target"] = legacy.target.reindex(bars.index)
        d.to_csv(out / f"{symbol}-states.csv")
        ledger.to_csv(out / f"{symbol}-volume-events.csv", index=False)
        all_ledger.to_csv(out / f"{symbol}-all-events.csv", index=False)
        original.to_csv(out / f"{symbol}-upstream.csv")
        summary = {
            "symbol": symbol, "observations": len(d), "created": int(d.created.sum()),
            "independent_entries": int(d.independent_entry.sum()),
            "base_consumptions": int(d.consumed_by_base.sum()),
            "pending_days": int(d.pending.sum()),
            "entries": int(d.entered.sum()), "original_entries": int(expected.entered.sum()),
            "changed_vs_original": int(d.target.ne(d.original_target).sum()),
            "changed_vs_all_declines": int(d.target.ne(d.all_target).sum()),
            "numeric_vs_legacy_days": int(d.original_target.ne(d.legacy_target).sum()),
            "rejected_events": int(ledger.outcome.eq("rejected").sum()),
            "open_events": int(ledger.outcome.eq("open").sum()),
        }
        summaries.append(summary)
        for case in (c for c in cases if c["symbol"] == symbol):
            q = d.loc[case["start"]:case["end"]]
            draw(case, d, out / "figures" / f'{case["id"]}-trajectory.png')
            case_stats.append({**case, "observations": len(q),
                               "created": int(q.created.sum()),
                               "independent_entries": int(q.independent_entry.sum()),
                               "candidate_entries": int(q.entered.sum()),
                               "changed_vs_original": int(q.target.ne(q.original_target).sum()),
                               "changed_vs_all_declines": int(q.target.ne(q.all_target).sum())})
        print(json.dumps(summary), flush=True)
    pd.DataFrame(summaries).to_csv(out / "series-summary.csv", index=False)
    pd.DataFrame(case_stats).to_csv(out / "case-summary.csv", index=False)
    totals = pd.DataFrame(summaries).drop(columns="symbol").sum().astype(int).to_dict()
    summary = {"totals": totals, "series": len(frames), "cases": len(cases), "account_calls": 0}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    (out / "identity.json").write_text(json.dumps(checks, indent=2))
    for f, digest in freeze["code"].items():
        assert sha(ROOT / "code" / f) == digest, ("code changed during run", f)
    manifest = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
