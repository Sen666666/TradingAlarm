import json,hashlib,sys
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
base=Path(__file__).resolve().parents[1];out=base/'results';protocol=json.loads((out/'protocol.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(Path(__file__))==protocol['code_sha256']
for path,digest in protocol['inputs'].items():assert sha(Path(path))==digest
source=Path(protocol['source']);sys.path.insert(0,str(source/'code'))
from trend_price_region import region_frame, quantiles
assert not (out/'summary.json').exists()
# Exact endpoint counterexample: reversing a closed price-volume loop preserves
# the block distribution and total squared returns, including equal final |r|.
warm=.001*np.sin(np.arange(100)*2*np.pi/10)
loop=np.array([0,.01,.023,.037,.041,.033,.028,.019,.008,.003,-.004,-.014,-.029,-.039,-.043,-.036,-.027,-.018,-.012,-.01,0.])
weight=100+50*np.cos(np.arange(21)*2*np.pi/20)
ix=pd.bdate_range('2020-01-01',periods=121);pair=[]
fig,ax=plt.subplots(3,1,figsize=(10,7),sharex=True)
for name,z,v in [('last_recovery',loop,weight),('last_decline',loop[::-1],weight[::-1])]:
 c=pd.Series(np.exp(np.r_[warm,z]),index=ix);vol=pd.Series(np.r_[np.full(100,100.),v],index=ix)
 f=region_frame(c,vol);r=np.log(c).diff();sigma=r.shift(1).pow(2).rolling(63).mean().pow(.5)
 record=dict(name=name,advance=float(f.advance.iloc[-1]),entry_score=float(f.entry_score.iloc[-1]),sigma=float(sigma.iloc[-1]),r5=float(np.log(c.iloc[-1]/c.iloc[-6])),recent_q25=float(f.recent_q25.iloc[-1]),recent_q50=float(f.recent_q50.iloc[-1]),recent_q75=float(f.recent_q75.iloc[-1]),target=float(f.target.iloc[-1]))
 pair.append(record);f['close']=c;f['volume']=vol;f.to_csv(out/f'{name}.csv',index_label='date')
 ax[0].plot(ix[-21:],c.iloc[-21:],label=name);ax[1].plot(ix[-21:],vol.iloc[-21:],label=name);ax[2].plot(ix[-21:],f.advance.iloc[-21:],label=name)
for key in ['advance','entry_score','sigma','recent_q25','recent_q50','recent_q75']:
 assert np.isclose(pair[0][key],pair[1][key],atol=1e-12),key
assert pair[0]['r5']*pair[1]['r5']<0
ax[0].legend();ax[0].set_ylabel('Price');ax[1].set_ylabel('Volume');ax[2].set_ylabel('Region advance');ax[0].set_title('Same endpoint region evidence; opposite last-five direction');fig.tight_layout();fig.savefig(out/'order-counterexample.png',dpi=120);plt.close(fig)
tie_a=quantiles(np.array([0.,0.,1.]),np.array([1.,9.,1.]))
tie_b=quantiles(np.array([0.,0.,1.]),np.array([9.,1.,1.]))
assert not np.allclose(tie_a,tie_b)
(out/'tie-order-artifact.json').write_text(json.dumps(dict(prices=[0,0,1],weights_a=[1,9,1],weights_b=[9,1,1],quantiles_a=tie_a.tolist(),quantiles_b=tie_b.tolist(),interpretation='Same weighted empirical mass, different interpolation due stable-sort tie order; estimator artifact, not useful path information'),indent=2))
all_events=[];cases=[];all_frames={}
for path in sorted(source.glob('*-signals.csv')):
 symbol=path.name.removesuffix('-signals.csv');f=pd.read_csv(path,index_col='date',parse_dates=True)
 valid=f.close.gt(0)&f.volume.gt(0)&np.isfinite(f.close)&np.isfinite(f.volume);d=f.loc[valid].copy();y=np.log(d.close)
 d['r5']=y.diff(5);d['r21']=y.diff(21);d['vol5_ratio']=d.volume.rolling(5).mean()/d.volume.shift(5).rolling(21).median()
 d['signed_activity5']=(y.diff()*np.sqrt(d.volume)).rolling(5).sum()/np.sqrt(d.volume).rolling(5).sum()
 d['floor_gap']=y-d.structure_floor
 for q in ['25','50','75']:
  d['new_delta'+q]=d['recent_q'+q].diff();d['old_delta'+q]=d['prior_q'+q].diff()
 d['symbol']=symbol;all_frames[symbol]=d
 for date,row in d.loc[d.entered.eq(1)|d.exited.eq(1)].iterrows():
  record={k:row[k] for k in ['symbol','advance','entry_score','r5','r21','vol5_ratio','signed_activity5','floor_gap','new_delta25','old_delta25','new_delta50','old_delta50','new_delta75','old_delta75']};record.update(date=str(date.date()),event='entry' if row.entered else 'exit');all_events.append(record)
pd.DataFrame(all_events).to_csv(out/'all-events.csv',index=False)
for c in protocol['cases']:
 d=all_frames[c['symbol']].loc[c['start']:c['end']].copy();held=d.target.eq(1)
 # These are observed state descriptions, not trade labels or filters.
 counts=dict(id=c['id'],symbol=c['symbol'],rows=len(d),held=int(held.sum()),held_advance_nonpositive=int((held&d.advance.le(0)).sum()),held_r5_negative=int((held&d.r5.lt(0)).sum()),entries=int(d.entered.sum()),exits=int(d.exited.sum()),flat_score_gt1=int((~held&d.entry_score.gt(1)).sum()))
 cases.append(counts);d.to_csv(out/f"{c['id']}-diagnostic.csv",index_label='date')
 # Last case-specific actual exit and subsequent off stretch remain in CSV.
 fig,ax=plt.subplots(4,1,figsize=(11,8),sharex=True)
 ax[0].plot(d.index,d.close,color='black');ax[0].plot(d.index,np.exp(d.structure_floor),label='floor',alpha=.7);ax[0].set_yscale('log');ax[0].set_title(c['id']+' '+c['symbol']);ax[0].legend()
 ax[1].plot(d.index,d.advance,label='advance');ax[1].axhline(0,color='gray');ax[1].legend()
 ax[2].plot(d.index,d.r5*100,label='past 5 log %');ax[2].plot(d.index,d.r21*100,label='past 21 log %');ax[2].axhline(0,color='gray');ax[2].legend()
 ax[3].plot(d.index,d.signed_activity5*100,label='activity-weighted daily return, 5 obs');ax[3].step(d.index,d.target,label='target',alpha=.4);ax[3].legend(fontsize=7)
 for date,row in d.loc[d.entered.eq(1)|d.exited.eq(1)].iterrows():ax[0].scatter(date,row.close,marker='^' if row.entered else 'v',color='green' if row.entered else 'red',s=30)
 fig.tight_layout();fig.savefig(out/f"{c['id']}-diagnostic.png",dpi=100);plt.close(fig)
pd.DataFrame(cases).to_csv(out/'case-summary.csv',index=False)
e=pd.DataFrame(all_events);entry=e[e.event.eq('entry')];ex=e[e.event.eq('exit')]
summary=dict(counterexample=pair,entry_n=len(entry),entry_r5_negative=int(entry.r5.lt(0).sum()),entry_r21_negative=int(entry.r21.lt(0).sum()),exit_n=len(ex),exit_advance_positive=int(ex.advance.gt(0).sum()),cases=cases)
(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
