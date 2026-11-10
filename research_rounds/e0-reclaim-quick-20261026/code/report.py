from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
O=Path(__file__).resolve().parents[1]
e=pd.read_csv(O/'events.csv');a=pd.read_csv(O/'audit.csv');summary={'stocks':len(a),'verified_history_rows':int(a.rows.sum()),'independent_reclaims':len(e),'already_on_without_reclaim':int(e.b_active.sum()),'extra_state_days':int(a.extra.sum()),'missing_state_days':int(a.missing.sum()),'accounts':0}
for h in [21,63]:
 q=e.dropna(subset=[f'ret{h}']);summary[str(h)]=dict(complete=len(q),unknown=len(e)-len(q),positive=int((q[f'ret{h}']>0).sum()),negative=int((q[f'ret{h}']<0).sum()),median_return=float(q[f'ret{h}'].median()),mean_return=float(q[f'ret{h}'].mean()),initial_floor_broken=int(q[f'break{h}'].astype(bool).sum()),max_close_gain_30pct=int((q[f'max{h}']>=.3).sum()))
q=e[e.b_active==0];summary['delay']=dict(known=int(q.b_delay.notna().sum()),not_yet=int(q.b_delay.isna().sum()),median=float(q.b_delay.median()),within5=int(q.b_delay.le(5).sum()),within1=int(q.b_delay.le(1).sum()))
q=e.dropna(subset=['ret21']);p=q[q.past21<0];summary['prior_down21']=dict(n=len(p),future_down21=int((p.ret21<0).sum()),median=float(p.ret21.median()))
sel=[q.ret21.idxmin(),q.ret21.idxmax(),(q.ret21-q.ret21.median()).abs().idxmin()];bad=q[(q.past21<0)&(q.ret21<0)].sort_values(['date','symbol']);sel+=[bad.index[0]] if len(bad) else []
e.loc[sel].to_csv(O/'selected.csv',index=False)
fig=plt.figure(figsize=(17,12));gs=fig.add_gridspec(2,2,hspace=.32,wspace=.2)
for panel,idx in enumerate(sel):
 r=e.loc[idx];f=pd.read_parquet(O/'states'/f'{r.symbol}.parquet');t=pd.Timestamp(r.date);n=f.index.get_loc(t);s=max(0,n-35);x=f.iloc[s:n+64];xx=np.arange(len(x));sub=gs[panel//2,panel%2].subgridspec(3,1,height_ratios=[3,1,1],hspace=.08);ax=fig.add_subplot(sub[0]);av=fig.add_subplot(sub[1],sharex=ax);az=fig.add_subplot(sub[2],sharex=ax)
 for j,b in enumerate(x.itertuples()):
  color='#c54d48' if b.close<b.open else '#228276';ax.vlines(j,b.low,b.high,color=color,lw=.7);ax.add_patch(Rectangle((j-.3,min(b.open,b.close)),.6,max(abs(b.open-b.close),b.close*.0001),color=color,lw=.4))
 ax.axhline(r.lower,color='#bd5438',ls='--',lw=.8,label='initial floor');ax.axhline(r.reclaim,color='#5476b6',ls=':',lw=.8,label='reclaim level');ax.plot(xx,x.floor_a,color='#29903b',alpha=.7,label='E0 floor');ax.set_title(f'{r.symbol} / {r.date} | next21 {r.ret21:+.1%}, next63 {r.ret63:+.1%}',fontsize=10);ax.legend(fontsize=7)
 av.bar(xx,x.volume,color='#8899aa');av.set_ylabel('Shares');az.step(xx,x.a.astype(float),where='post',label='E0',color='#228276');az.step(xx,x.b.astype(float)-1.4,where='post',label='no reclaim',color='#555555');az.legend(fontsize=7,loc='lower right');az.set_ylim(-1.6,1.3)
 for z in [ax,av,az]:z.axvline(n-s,color='#b03da6',ls='--');z.grid(alpha=.15)
 ticks=np.linspace(0,len(x)-1,5).astype(int);az.set_xticks(ticks,[x.index[j].strftime('%Y-%m-%d') for j in ticks],fontsize=7);ax.tick_params(labelbottom=False);av.tick_params(labelbottom=False)
fig.suptitle('E0 recovery audit: original OHLC / volume / state; vertical = recovery. Retrospective examples.',fontsize=13);fig.savefig(O/'examples.png',dpi=150,bbox_inches='tight');plt.close(fig)
(O/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n');print(json.dumps(summary,indent=2,ensure_ascii=False));print(e.loc[sel].to_string(index=False))
files=[O/'PROTOCOL.md',*sorted((O/'code').glob('*.py')),O/'events.csv',O/'audit.csv',O/'summary.json'];(O/'manifest.json').write_text(json.dumps({str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2)+'\n')
