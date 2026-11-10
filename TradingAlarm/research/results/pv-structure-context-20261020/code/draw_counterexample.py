"""Illustration selected AFTER review; explanatory evidence, not a new test."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

base = Path(__file__).resolve().parents[1]
out = base / "counterexample.png"
if out.exists():
    raise FileExistsError(out)
fig, axes = plt.subplots(3, 2, figsize=(13, 7), sharex="col",
                         gridspec_kw={"height_ratios": [3, 1, 1]})
for col, (symbol, start, end, title) in enumerate([
    ("USHJ518880", "2024-02-01", "2024-08-30", "Gold ETF | advance, then high range"),
    ("HK09618", "2024-09-02", "2024-12-31", "JD | advance, then persistent erosion"),
]):
    q = pd.read_csv(base / "v1" / f"{symbol}-states.csv",
                    index_col="date", parse_dates=True).loc[start:end]
    scale = 100 / q.close.iloc[0]
    axes[0, col].plot(q.index, q.close * scale, color="#202936", label="price (start = 100)")
    axes[0, col].plot(q.index, np.exp(q.structure_floor) * scale,
                      color="#2176ae", label="v0/v1 structural floor")
    mask = q.phase.eq("orderly")
    axes[0, col].fill_between(q.index, 0, 1, where=mask,
                              transform=axes[0, col].get_xaxis_transform(),
                              color="#e0a832", alpha=.18,
                              label="lower activity + slower counter-leg")
    axes[0, col].set_title(title)
    axes[0, col].legend(fontsize=7, loc="upper left")
    axes[1, col].bar(q.index, q.volume, color="#929fa9", width=1)
    axes[1, col].set_ylabel("volume")
    axes[2, col].plot(q.index, q.e.clip(0, 4), label="relative activity", color="#2176ae")
    axes[2, col].plot(q.index, q.s.clip(0, 4), label="relative speed", color="#cf5d2a")
    axes[2, col].axhline(1, ls=":", color="gray")
    axes[2, col].set_ylim(0, 4)
    axes[2, col].legend(fontsize=7)
    axes[2, col].tick_params(axis="x", rotation=25)
    for row in range(3):
        axes[row, col].grid(alpha=.12)
fig.suptitle("A quiet, slow retreat is not proof of a healthy trend", fontsize=16)
fig.text(.5, .008, "Saved adjusted close + volume. Shading is descriptive; no trades, positions or account returns.",
         ha="center", fontsize=9)
fig.tight_layout(rect=[0, .03, 1, .95])
fig.savefig(out, dpi=130)
plt.close(fig)
