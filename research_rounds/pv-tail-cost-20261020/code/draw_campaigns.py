"""Display saved signals and saved trades only; no account simulation."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
ROUND = Path(__file__).resolve().parents[1]
OLD = ROOT / "TradingAlarm/research/results/pv-event-structure-20261020"
CASES = [
    ("HK09618", "hk7"), ("HK03690", "hk7"), ("HK00101", "hk7"),
    ("HK00700", "hk7"), ("HK02820", "etf17"), ("USHJ515030", "etf17"),
    ("HK02845", "etf17"), ("HK00883", "hk7"), ("USHJ518880", "etf17"),
]


def draw(symbol, group):
    source = OLD / f"{symbol}-signals.csv"
    f = pd.read_csv(source, index_col="date", parse_dates=True).loc["2022-01-01":]
    episodes = json.loads((OLD / f"{group}-pv-base-episodes.json").read_text())
    selected = [e for e in episodes if e["symbol"] == symbol]
    fig, ax = plt.subplots(4, 1, figsize=(15, 10), sharex=True,
                           gridspec_kw={"height_ratios": [3, 1, 1, 1.2]})
    ax[0].plot(f.index, f.close, c="#222222", lw=1, label="saved adjusted signal close")
    ax[0].plot(f.index, np.exp(f.structure_floor), c="#dd7733", lw=.9, label="PV structure floor")
    ax[0].set_yscale("log")
    ax[0].set_title(f"{symbol} | 2022-2026 full path | saved orders, no new account")
    ax[1].bar(f.index, f.volume, width=2, color="#888888")
    ax[1].plot(f.index, f.volume.rolling(21).median(), c="#dd7733", lw=.8)
    ax[1].set_ylabel("Actual volume")
    ax[2].step(f.index, f.target, where="post", lw=1, label="PV structure")
    ax[2].step(f.index, f.price_target+.04, where="post", lw=.8, alpha=.6, label="price control +.04")
    ax[2].set_ylabel("Signal target")
    for e in selected:
        entry = pd.Timestamp(e["entry"])
        if entry not in f.index:
            continue
        positive = e["pnl"] >= 0
        color = "#168672" if positive else "#c65050"
        ax[0].scatter([entry], [f.loc[entry, "close"]], c=color, marker="^", s=16)
        end = pd.Timestamp(e["exit"]) if e.get("exit") else f.index[-1]
        ax[3].plot([entry, end], [e["ret"]*100]*2, c=color, lw=2)
        ax[3].scatter([end], [e["ret"]*100], c=color, marker="o" if e["status"] == "closed" else "x", s=12)
        if e["ret"] >= .3 and e["status"] == "closed":
            ax[3].annotate(f'{e["ret"]*100:.1f}%', (end, e["ret"]*100), fontsize=8)
    ax[3].axhline(0, c="black", lw=.5)
    ax[3].axhline(30, c="#168672", ls=":", lw=.6)
    ax[3].set_ylabel("Saved episode\nnet return %")
    for a in ax:
        a.grid(alpha=.15)
    ax[0].legend(fontsize=8, loc="upper left")
    ax[2].legend(fontsize=8, loc="upper left")
    fig.text(.01, .005, "Entry marker uses signal close on execution date, not fill price. Horizontal episode returns are hindsight diagnostics; x = open/claim.", fontsize=8)
    fig.tight_layout(rect=(0, .02, 1, 1))
    output = ROUND / "figures" / f"{symbol}-full-campaign.png"
    assert not output.exists(), output
    fig.savefig(output, dpi=120)
    plt.close(fig)
    return {
        "symbol": symbol, "group": group, "episodes": len(selected),
        "path": str(output.relative_to(ROUND)),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "image_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    rows = [draw(s, g) for s, g in CASES]
    (ROUND / "figures/campaign-index.json").write_text(
        json.dumps({"selection": "Exploratory: largest ordinary-loss assets from full attribution, plus known retained winners; not acceptance cases", "items": rows},
                   ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(rows, ensure_ascii=False))
