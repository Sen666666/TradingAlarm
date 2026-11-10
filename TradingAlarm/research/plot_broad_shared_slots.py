from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
out=Path('results/broad-shared-slots')
fig,axes=plt.subplots(3,1,figsize=(12,10),sharex=True)
for case in ['rank','random','group_gate','group_gate_cap']:
 p=pd.read_parquet(out/f'{case}-base-path.parquet')
 axes[0].plot(p.index,p.nav,label=case);axes[1].plot(p.index,p.drawdown*100);axes[2].plot(p.index,p.cash/(1e6*p.nav)*100)
for ax in axes:
 ax.axvline(pd.Timestamp('2026-06-01'),color='grey',linestyle=':',alpha=.7);ax.grid(alpha=.2)
axes[0].axhline(1,color='black',linewidth=.6);axes[0].legend();axes[0].set_ylabel('NAV');axes[1].set_ylabel('Drawdown %');axes[2].set_ylabel('Cash %')
fig.suptitle('A485 shared-capital research | 9 slots, 10% initial target\nAdjusted fractional prices, selected survivors, development data')
fig.tight_layout();fig.savefig(out/'paths.png',dpi=150)
