"""Render the two reviewed phases; future outcomes shown only as evaluation."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/tradingalarm-mpl')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/tradingalarm-cache')
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path('results/trajectory-break-diagnostic');f=pd.read_csv(p/'semiconductor-case.csv',parse_dates=['date'])
fig,axes=plt.subplots(2,2,figsize=(13,7),layout='constrained')
for col,(title,start,end) in enumerate([('Pullback before June rally','2026-05-25','2026-06-05'),('July reversal','2026-07-01','2026-07-10')]):
    q=f.loc[f.date.between(start,end)];x=range(len(q));labels=q.date.dt.strftime('%m-%d')
    for model in ['linear','quadratic','random_walk']:axes[0,col].plot(x,q[model+'_z'],marker='.',label=model)
    axes[0,col].axhline(-2,color='grey',ls='--');axes[0,col].set_ylim(-4.5,4);axes[0,col].set_title(title);axes[0,col].legend(fontsize=8);axes[0,col].set_ylabel('Forecast error / prior return RMS')
    axes[1,col].bar(x,q.next21_return*100,color=['#059669' if v>0 else '#dc2626' for v in q.next21_return]);axes[1,col].set_ylim(-40,50);axes[1,col].set_ylabel('Next 21-bar return % (hindsight)')
    for row in range(2):axes[row,col].set_xticks(list(x),labels,rotation=45);axes[row,col].grid(alpha=.15)
fig.suptitle('512480: large negative forecast error occurs before both rally and decline')
fig.savefig(p/'phase-errors.png',dpi=140)
