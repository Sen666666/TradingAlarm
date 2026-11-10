"""Publication-style static research plots; no external scripts or tracking."""
from pathlib import Path
import json
import os
cache_root=Path(__file__).resolve().parent/'.venv'/'plot-cache'
cache_root.mkdir(parents=True,exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR',str(cache_root/'matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME',str(cache_root))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd

ROOT=Path(__file__).resolve().parent/'results/portfolio-v3'
base=pd.read_csv(ROOT/'portfolio-frozen_trend_guard-path.csv',index_col=0,parse_dates=True)
passive=pd.read_csv(ROOT/'portfolio-passive_without_budget-path.csv',index_col=0,parse_dates=True)
diagnostics=json.loads((ROOT/'diagnostics.json').read_text())
scale=diagnostics['controls']['ex_post_risk_matched_passive']['scale']
matched=(1+passive.return_daily*scale).cumprod()
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                     'axes.grid':True,'grid.alpha':.2,'figure.facecolor':'white'})
fig,axes=plt.subplots(3,1,figsize=(11,10),sharex=True,gridspec_kw={'height_ratios':[2,1,1]})
axes[0].plot(base.index,base.nav,label='Trend + risk budget v3',color='#176280',lw=2)
axes[0].plot(passive.index,passive.nav,label='Passive, no scenario budget',color='#8c909a',lw=1.3)
axes[0].plot(matched.index,matched,label='Passive matched realized vol (ex-post)',color='#d39335',lw=1.5)
axes[0].set_ylabel('Net asset value (initial = 1)');axes[0].legend(loc='upper left',frameon=False)
axes[1].fill_between(base.index,base.drawdown,0,color='#176280',alpha=.25)
axes[1].plot(base.index,base.drawdown,color='#176280',lw=1)
axes[1].axhline(-.25,color='#b34b43',ls='--',label='25% research target')
axes[1].set_ylabel('Drawdown');axes[1].yaxis.set_major_formatter(PercentFormatter(1));axes[1].legend(frameon=False,loc='lower left')
axes[2].plot(base.index,base.cash/(base.nav*1e6),color='#3e8b68')
axes[2].set_ylabel('CNY cash weight');axes[2].yaxis.set_major_formatter(PercentFormatter(1));axes[2].set_ylim(0,1)
fig.suptitle('A-share / Hong Kong ETF portfolio — historical research, not live performance',fontsize=13)
fig.text(.08,.015,'2022-01-03 to 2026-10-16 | Costs, FX, dividends, splits and board lots included with stated approximations.',fontsize=9,color='#56616b')
fig.tight_layout(rect=[0,.035,1,.96]);fig.savefig(ROOT/'portfolio-overview.png',dpi=160);fig.savefig(ROOT/'portfolio-overview.svg');plt.close(fig)
fig,ax=plt.subplots(figsize=(11,4.5))
for file,label,color in [('portfolio-frozen_trend_guard-path.csv','Observed history','#176280'),
                         ('recomputed_market_shock-path.csv','Injected market shock; signals recomputed','#b34b43'),
                         ('shock_high_cost_delayed-path.csv','Shock + high cost + delayed fills','#d39335')]:
    p=pd.read_csv(ROOT/file,index_col=0,parse_dates=True)
    ax.plot(p.index,p.drawdown,label=label,color=color,lw=1.4)
ax.axhline(-.25,color='#444',ls='--',lw=1);ax.yaxis.set_major_formatter(PercentFormatter(1))
ax.set_ylabel('Drawdown from all-time high');ax.legend(frameon=False,loc='lower left',fontsize=9)
ax.set_title('Adversarial scenario stress — not a future loss probability')
fig.tight_layout();fig.savefig(ROOT/'portfolio-stress.png',dpi=160);plt.close(fig)
print(ROOT/'portfolio-overview.png')
