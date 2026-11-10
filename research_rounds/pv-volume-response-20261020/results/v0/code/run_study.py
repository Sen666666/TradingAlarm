"""Finite signal experiment. Outputs must be new; never imports an account."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from baseline_event_structure import event_frame
from volume_response import response_frame
from data_utils import load_inputs

ROOT = Path(__file__).resolve().parents[1]

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

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
    ax[0].plot(x, q.original_floor, color="#777777", ls=":", lw=.9, label="Frozen original floor")
    ax[0].plot(x, q.pending_high, color="#b48519", ls="--", lw=1, label="Unresolved event range")
    ax[0].plot(x, q.pending_low, color="#b48519", ls="--", lw=1)
    for col, marker, color, label in [
        ("created", "s", "#bf8c16", "Volume conflict created"),
        ("entered", "^", "#077b3e", "Candidate UP established"),
        ("exited", "v", "#ab3030", "Candidate invalidated")]:
        mask = q[col].eq(1).to_numpy()
        ax[0].scatter(x[mask], q.close.iloc[np.flatnonzero(mask)], marker=marker,
                      color=color, s=25, label=label, zorder=4)
    ax[0].set_yscale("log")
    ax[0].set_ylabel("Adjusted OHLC / log scale")
    ax[0].legend(loc="best", fontsize=7, ncol=2)
    ax[0].set_title(f'{case["id"]} | {case["symbol"]} | Volume-response v0\n'
                    "Signal states only; markers are not trades")
    ax[1].bar(x, q.volume_ratio.clip(upper=8), color="#9aa3a6", width=.8)
    ax[1].axhline(2, color="#bf8c16", ls="--", lw=1)
    ax[1].set_ylabel("V / prior21 median\n(display capped 8)")
    for offset, col, label, color in [
        (4.5, "target", "candidate", "#177447"),
        (3, "original_target", "original PV", "#555555"),
        (1.5, "all_target", "all price conflicts", "#a763a0"),
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
    fig.text(.01,.005,"Seen development history. All-conflicts ablates only the NEW volume selection; "
             "upstream event detector remains PV. No account results.",fontsize=8,color="#555555")
    fig.tight_layout(rect=(0,.025,1,1))
    fig.savefig(out, dpi=120)
    plt.close(fig)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    out = Path(args.output).resolve()
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    (out / "figures").mkdir()
    (out / "code").mkdir()
    code_files = ["volume_response.py", "baseline_event_structure.py", "data_utils.py", "run_study.py"]
    freeze = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "protocol_sha256": sha(ROOT/"protocol.md"),
              "code": {f:sha(ROOT/"code"/f) for f in code_files},
              "inputs_manifest_sha256":sha(ROOT/"inputs/manifest.json"),
              "account_calls":0}
    (out/"run-freeze.json").write_text(json.dumps(freeze,indent=2))
    for f in code_files:
        shutil.copy2(ROOT/"code"/f,out/"code"/f)
    shutil.copy2(ROOT/"protocol.md",out/"protocol.md")
    frames, cases, manifest = load_inputs(ROOT)
    summaries, case_stats, checks, outputs = [], [], [], {}
    for symbol, bars in frames.items():
        raw = pd.read_csv(ROOT/"inputs"/f"{symbol}.csv", index_col="date", parse_dates=True)
        ev = event_frame(raw.close, raw.volume)
        price = event_frame(raw.close, raw.volume, joint=False)
        valid = np.isfinite(raw.close) & raw.close.gt(0) & np.isfinite(raw.volume) & raw.volume.gt(0)
        bars.attrs["source_first_close"] = float(raw.loc[valid].close.iloc[0])
        none, _ = response_frame(bars, ev, "none")
        identity = int(none.target.ne(ev.target.reindex(bars.index)).sum())
        checks.append({"symbol":symbol,"no_conflicts_target_mismatches":identity,
                       "excluded_source_events":int(ev.loc[~ev.index.isin(bars.index),"event"].ne(0).sum())})
        if identity:
            (out/"failed-identity.json").write_text(json.dumps(checks,indent=2))
            raise AssertionError(f"{symbol} none mismatch {identity}")
        candidate, ledger = response_frame(bars, ev, "volume")
        allconf, allledger = response_frame(bars, ev, "all")
        data = bars[["open","high","low","close","volume"]].join(candidate)
        data["original_target"] = ev.target.reindex(bars.index)
        data["original_floor"] = np.exp(ev.structure_floor.reindex(bars.index))
        data["price_target"] = price.target.reindex(bars.index)
        data["all_target"] = allconf.target
        data.to_csv(out/f"{symbol}-states.csv",index_label="date")
        ledger.to_csv(out/f"{symbol}-volume-events.csv",index=False)
        allledger.to_csv(out/f"{symbol}-all-events.csv",index=False)
        ev.to_csv(out/f"{symbol}-upstream.csv",index_label="date")
        outputs[symbol] = data
        summaries.append({"symbol":symbol,"observations":len(data),
                          "created":int(candidate.created.sum()),
                          "resolved_up":int(candidate.resolved.eq(1).sum()),
                          "resolved_down":int(candidate.resolved.eq(-1).sum()),
                          "pending_days":int(candidate.pending.sum()),
                          "blocked_price_events":int(candidate.blocked_price_event.sum()),
                          "entries":int(candidate.entered.sum()),
                          "original_entries":int(ev.entered.reindex(bars.index).sum()),
                          "changed_vs_original":int(data.target.ne(data.original_target).sum()),
                          "changed_vs_all_conflicts":int(data.target.ne(data.all_target).sum())})
    for case in cases:
        data = outputs[case["symbol"]]
        q = data.loc[case["start"]:case["end"]]
        draw(case,data,out/"figures"/f'{case["id"]}-trajectory.png')
        case_stats.append({**case,"observations":len(q),
                           "created":int(q.created.sum()),
                           "blocked_price_events":int(q.blocked_price_event.sum()),
                           "resolved_up":int(q.resolved.eq(1).sum()),
                           "resolved_down":int(q.resolved.eq(-1).sum()),
                           "candidate_entries":int(q.entered.sum()),
                           "changed_vs_original":int(q.target.ne(q.original_target).sum()),
                           "changed_vs_all_conflicts":int(q.target.ne(q.all_target).sum())})
    pd.DataFrame(summaries).to_csv(out/"series-summary.csv",index=False)
    pd.DataFrame(case_stats).to_csv(out/"case-summary.csv",index=False)
    (out/"identity.json").write_text(json.dumps(checks,indent=2))
    totals = {k:sum(s[k] for s in summaries) for k in summaries[0] if k!="symbol"}
    (out/"summary.json").write_text(json.dumps({"totals":totals,"series":len(frames),
                                              "cases":len(cases),"account_calls":0},indent=2))
    (out/"manifest.json").write_text(json.dumps(
        {str(p.relative_to(out)):sha(p) for p in out.rglob("*") if p.is_file()},indent=2))
    print(json.dumps(totals))

if __name__=="__main__":
    main()
