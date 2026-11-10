"""Export the frozen market feedback and original realized-PnL timelines."""
from pathlib import Path
import json,csv
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
O=Path(__file__).resolve().parent
rows=json.loads((O/'MARKET_AND_ACCOUNT_DAILY.json').read_text())
for view in ['2022_weak','2024_recovery','strong']:
 z=[x for x in rows if x['market_feedback']['view']==view];d=pd.to_datetime([x['market_feedback']['day'] for x in z]);m=[x['market_feedback'] for x in z];a=[x['original_account'] for x in z]
 v=lambda key:np.array([np.nan if r[key] is None else float(r[key]) for r in m])
 fig,ax=plt.subplots(3,1,figsize=(13,10),sharex=True,layout='constrained')
 ax[0].plot(d,v('median')*100,label='5-close response: weighted median',color='#22577a',lw=1.6)
 ax[0].plot(d,v('p10')*100,label='Weighted p10',color='#bb3e03',lw=1,alpha=.8)
 ax[0].plot(d,v('market_R5_asof')*100,label='Original market: trailing 5-session return',color='#777',lw=.8,alpha=.7)
 ax[0].axhline(0,color='#aaa',lw=.7);ax[0].set_ylabel('Price response (%)');ax[0].legend(loc='upper left',fontsize=8,ncol=2)
 ax[1].plot(d,v('positive_fraction')*100,color='#2a9d8f',label='Weighted positive fraction',lw=1.4);ax[1].axhline(50,color='#aaa',lw=.7);ax[1].set_ylim(0,100);ax[1].set_ylabel('Positive responses (%)')
 counts=ax[1].twinx();counts.bar(d,v('new_mature_events'),width=1.2,color='#8ecae6',alpha=.4,label='Newly mature events');counts.set_ylabel('New mature events');ax[1].legend(loc='upper left',fontsize=8);counts.legend(loc='upper right',fontsize=8)
 ax[2].plot(d,[float(r['A_recent21_sell_realized'])/10000 for r in a],label='A: recent sales realized',color='#9b2226',lw=1.3)
 ax[2].plot(d,[float(r['C_recent21_new_layer_realized'])/10000 for r in a],label='C: recent-entry cohort realized',color='#6a4c93',lw=1.3)
 ax[2].bar(d,[float(r['actual_today_realized'])/10000 for r in a],color='#999',alpha=.25,label='Actual daily realized');ax[2].axhline(0,color='#aaa',lw=.7);ax[2].set_ylabel('Original realized PnL (10k CNY)');ax[2].legend(loc='upper left',fontsize=8,ncol=2)
 for aa in ax:aa.grid(axis='y',alpha=.18);aa.spines[['top','right']].set_visible(False)
 ax[-1].xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5,maxticks=9));ax[-1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax[-1].xaxis.get_major_locator()))
 fig.suptitle(view+' | Frozen H=5 traded quotes; last 5 market-session maturity batches\nMarket response is not execution PnL. Account lines are unchanged original history.',fontsize=12)
 fig.savefig(O/(view+'_TIMELINE.png'),dpi=160);plt.close(fig)

# Retain true last-ever published batch age separately from the recent-window age.
timing=[]
for view in ['2022_weak','2024_recovery','strong']:
 events=json.loads((O/view/'EVENTS.json').read_text());days=sorted({e['maturity_day'] for e in events if e['maturity_day']})
 native=json.loads((O/view/'DAILY_FEEDBACK.json').read_text());all_dates=sorted({e['day'] for e in events}|set(days)|{r['day'] for r in native})
 #Age in exact original calendar is obtained from the already frozen market CSV.
 sm=json.loads((O/'SOURCE_MANIFEST.json').read_text());mp=next(p for p in sm['sources'] if p.endswith('/recovery.csv'));cal=[str(x.date()) for x in pd.read_csv(mp,index_col=0,parse_dates=True).index];ix={d:j for j,d in enumerate(cal)}
 for r in native:
  known=[d for d in days if d<=r['day']];latest=known[-1] if known else None
  timing.append(dict(view=view,day=r['day'],last_published_batch_asof=latest,age_asof=None if latest is None else ix[r['day']]-ix[latest],latest_batch_in_recent_window=r['latest_batch_day'],recent_window_information_age=r['information_age_market_sessions'],primary_feedback_unchanged=r['feedback_state']))
with (O/'ADDITIONAL_TIMING_FIELDS.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=list(timing[0]));w.writeheader();w.writerows(timing)
print('EXPORTED_TIMELINES',len(timing),'days')
