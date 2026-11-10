"""Post-run independent arithmetic and immutable-source audit, no new fit."""
from pathlib import Path
import hashlib,json,datetime
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'results/v0'
freeze=json.loads((HERE/'freeze.json').read_text())
for p,h in freeze['hashes'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
d=pd.read_csv(HERE.parent/'gold-chart-fit-20261024/data/sina-AU0.csv',index_col='date',parse_dates=True)
f=pd.read_parquet(OUT/'features.parquet');c=np.log(d.close.to_numpy());r=np.r_[np.nan,np.diff(c)];v=d.volume.to_numpy()
sigma=np.full(len(d),np.nan);q=np.full(len(d),np.nan);atr=np.full(len(d),np.nan)
for i in range(1,len(d)):
    if i>=64:sigma[i]=np.sqrt(np.mean(r[i-63:i]**2))
    if i>=21:q[i]=v[i]/np.median(v[i-21:i])
    if i>=15:
        values=[]
        for j in range(i-14,i):values.append(max(d.high.iloc[j]-d.low.iloc[j],abs(d.high.iloc[j]-d.close.iloc[j-1]),abs(d.low.iloc[j]-d.close.iloc[j-1]))/d.close.iloc[j-1])
        atr[i]=np.mean(values)
np.testing.assert_allclose(sigma[64:],f.sigma.iloc[64:],atol=1e-14,rtol=1e-12)
np.testing.assert_allclose(q[64:],f.q.iloc[64:],atol=1e-14,rtol=1e-12)
np.testing.assert_allclose(atr[64:],f.atr.iloc[64:],atol=1e-14,rtol=1e-12)
w=np.sqrt(np.clip(np.nan_to_num(q,nan=1.),.25,4));slope=np.full(len(d),np.nan)
for i in range(64,len(d)):
    x=np.column_stack([np.ones(20),np.arange(20)]);ww=np.sqrt(w[i-19:i+1]);beta=np.linalg.lstsq(x*ww[:,None],c[i-19:i+1]*ww,rcond=None)[0][1]
    slope[i]=beta*np.sqrt(20)/sigma[i]
np.testing.assert_allclose(slope[64:],f.slope_20_PV.iloc[64:],atol=1e-10,rtol=1e-10)
best='slope-20-PV-e1-x0-trail2-broken_peak';saved=pd.read_parquet(OUT/'daily'/f'{best}.parquet')
live=False;peak=line=np.nan;broken=-np.inf;ever=False;rows=[]
for i in range(len(d)):
    entered=exited=0
    if live:
        peak=max(peak,c[i]);line=max(line,peak-2*atr[i])
        if slope[i]<=0 or c[i]<=line:live=False;exited=1;broken=max(broken,peak)
    elif i>=64 and slope[i]>=1 and (not ever or c[i]>broken):
        live=True;entered=1;ever=True;peak=c[i];line=peak-2*atr[i]
    rows.append((int(live),entered,exited))
for col,arr in zip(['target','entered','exited'],np.array(rows).T):np.testing.assert_array_equal(arr,saved[col])
pack=np.load(OUT/'all-states.npz',allow_pickle=False)
np.testing.assert_array_equal(pack['target'],np.cumsum(pack['entered']-pack['exited'],axis=1))
assert ((pack['entered']+pack['exited'])<=1).all()
idx=pd.to_datetime(pack['dates']);mask=(idx>=pd.Timestamp('2025-01-02'))&(idx<=pd.Timestamp('2026-10-13'));ev=idx[mask]
ref=json.loads((OUT/'reference.json').read_text());points=ref['points']
sequence=sorted([(int(i),'start') for i in np.flatnonzero(saved.reindex(ev).entered)]+[(int(i),'end') for i in np.flatnonzero(saved.reindex(ev).exited)])
assert len(sequence)==len(points)==10
cost=sum(max(t['lo']-i,0,i-t['hi']) for (i,k),t in zip(sequence,points) if k==t['kind']);assert cost==9
assert all(k==t['kind'] for (_,k),t in zip(sequence,points))
rs=pd.read_csv(OUT/'reference-state.csv');actual=saved.reindex(ev).target.to_numpy();known=rs.known_state.to_numpy(dtype=bool)
errors=int((actual[known]!=rs.reference_rightside.to_numpy()[known]).sum());assert errors==6 and known.sum()==374
score=.5*errors/known.sum()+.5*cost/300
rank=pd.read_csv(OUT/'ranking.csv');rr=rank.loc[rank.model.eq(best)].iloc[0];assert abs(score-rr.score)<1e-12
pred=pd.read_parquet(OUT/'stage-predictions.parquet');labels=pd.read_csv(HERE.parent/'gold-temperature-inference-20261024/measured-daily.csv',index_col='date',parse_dates=True)
lab=labels.loc[labels.known.eq(1)&labels.level.gt(0)];stage=pred[best+'|volume_peak'].reindex(lab.index)
correct=int(stage.eq(lab.level).sum());assert correct==47 and len(lab)==68
result=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),frozen_files_unchanged=len(freeze['hashes']),all_saved_state_series=len(pack['models']),state_transition_identity=True,
    independent_weighted_least_squares_rows=len(d)-64,independent_best_state_rows=len(d),best_event_cost=cost,best_state_errors=errors,best_known_state_rows=int(known.sum()),best_color_matches=correct,best_color_reference_rows=len(lab),passed=True,
    limits='Audit proves arithmetic and saved-output consistency only; no source identity/uniqueness/profitability assertion.')
with (OUT/'independent-audit.json').open('x') as fp:json.dump(result,fp,ensure_ascii=False,indent=2);fp.write('\n')
print(json.dumps(result,ensure_ascii=False))
