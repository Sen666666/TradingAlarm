from pathlib import Path
import pandas as pd,numpy as np,json,math
O=Path(__file__).resolve().parent
z=pd.read_csv(O/'ALL_ORIGINAL_FIRST_ASSOCIATIONS.csv');z['signal_year']=pd.to_datetime(z.signal_day).dt.year
HP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');cal=pd.DatetimeIndex(np.load(HP,allow_pickle=False)['dates']);idx=cal.get_indexer(pd.to_datetime(z.signal_day));assert (idx>=0).all();z['date_block20']=idx//20
rng=np.random.default_rng(20261106)
def auc(y,s,w=None):
 y=np.asarray(y,dtype=bool);s=np.asarray(s);w=np.ones(len(y))if w is None else np.asarray(w,dtype=float)
 order=np.argsort(s,kind='stable');y=y[order];s=s[order];w=w[order];p=w[y].sum();n=w[~y].sum()
 if p==0 or n==0:return np.nan
 start=np.r_[0,np.flatnonzero(s[1:]!=s[:-1])+1];wp=np.add.reduceat(w*y,start);wn=np.add.reduceat(w*(~y),start);lower=np.cumsum(wn)-wn
 return float((wp*(lower+.5*wn)).sum()/(p*n))
rows=[];boot=[];dist=[]
for year,g0 in z.groupby('signal_year'):
 for sample,g in [('terminal_closed',g0[g0.closed]),('year2022_end_only',g0[g0.closed_in_entry_year])]:
  if sample=='year2022_end_only'and year!=2022:continue
  base=dict(signal_year=int(year),sample=sample,all_original_firsts=len(g0),unclosed=int((~g0.closed).sum()),cross_entry_year=int((g0.year!=g0.signal_year).sum()),closed_n=len(g),unknown=int(g.health.isna().sum()),partial_warm_finite=int((g.health.notna()&~g.fully_warmed).sum()))
  for col in ['health','plain_health','PVR_decision','advance_fraction']:
   q=g[g[col].notna()];rows.append(base|dict(feature=col,AUC=auc(q.win,q[col]),known_n=len(q),winners=int(q.win.sum())))
   for win,v in q.groupby('win'):dist.append(dict(signal_year=int(year),sample=sample,feature=col,win=bool(win),n=len(v),median=float(v[col].median()),q25=float(v[col].quantile(.25)),q75=float(v[col].quantile(.75))))
 q=g0[g0.closed].dropna(subset=['health','plain_health','PVR_decision']).copy();blocks=np.unique(q.date_block20);bid={b:i for i,b in enumerate(blocks)};by=np.array([bid[b]for b in q.date_block20]);cols=['health','plain_health','PVR_decision'];point={c:auc(q.win,q[c])for c in cols};draws=[]
 for _ in range(1000):
  cnt=np.bincount(rng.integers(0,len(blocks),len(blocks)),minlength=len(blocks));ww=cnt[by];v={c:auc(q.win,q[c],ww)for c in cols};draws.append([v['health'],v['health']-v['plain_health'],v['health']-v['PVR_decision']])
 a=np.asarray(draws)
 for j,metric in enumerate(['health_AUC','health_minus_plain_AUC','health_minus_PVR_AUC']):
  est=[point['health'],point['health']-point['plain_health'],point['health']-point['PVR_decision']][j];valid=a[:,j][np.isfinite(a[:,j])]
  boot.append(dict(signal_year=int(year),sample='terminal_closed_common_features',metric=metric,n=len(q),wins=int(q.win.sum()),date_blocks=len(blocks),point=est,lo95=float(np.quantile(valid,.025)),hi95=float(np.quantile(valid,.975)),valid_bootstraps=len(valid),resamples=1000,block_size=20,seed=20261106))
pd.DataFrame(rows).to_csv(O/'SIGNAL_YEAR_ASSOCIATIONS.csv',index=False);pd.DataFrame(boot).to_csv(O/'DATE_BLOCK_AUC_INTERVALS.csv',index=False);pd.DataFrame(dist).to_csv(O/'SIGNAL_YEAR_WIN_LOSS_DISTRIBUTIONS.csv',index=False)
period=[];detail=[]
for name,lo,hi in [('2024_acceleration','2024-09-19','2024-10-08'),('2026_Q1','2026-01-01','2026-03-31')]:
 p=z[z.signal_day.between(lo,hi)]
 for sub,q in [('all_original_firsts',p),('original_closed_winners',p[p.closed&p.win]),('original_closed_losses',p[p.closed&~p.win]),('original_mature60_big',p[p.complete60&p.big60_posthoc])]:
  k=q[q.health.notna()];period.append(dict(period=name,subset=sub,total=len(q),known=len(k),unknown=int(q.health.isna().sum()),unclosed=int((~q.closed).sum()),mature60=int(q.complete60.sum()),health_median=k.health.median(),health_min=k.health.min(),health_max=k.health.max(),mean_nominal_probe_risk_reduction=(1-k.health).mean(),median_nominal_probe_risk_reduction=(1-k.health).median(),meaning='Research b/b0 only; not missed-signal, volume, PnL or complete root capture estimate'))
 detail.append(p.assign(period=name))
pd.DataFrame(period).to_csv(O/'MAJOR_PERIOD_RISK_EFFECTS.csv',index=False);pd.concat(detail,ignore_index=True).to_csv(O/'MAJOR_PERIOD_ORIGINAL_FIRSTS.csv',index=False)
scale=dict(economic_floor=math.log1p(.001),floor_unit='one observation dimensionless log return',first_states=len(z),known=int(z.sigma.notna().sum()),min_sigma=float(z.sigma.min()),max_sigma=float(z.sigma.max()),floor_hits=int(np.isclose(z.sigma,math.log1p(.001),rtol=0,atol=1e-15).sum()),min_health=float(z.health.min()),max_health=float(z.health.max()),health_finite_bounds_pass=bool(z.health.dropna().between(0,1).all()),max_damage=float(z.damage.max()),cross_entry_year=int((z.year!=z.signal_year).sum()))
(O/'SCALE_AND_CLOCK_AUDIT.json').write_text(json.dumps(scale,indent=2))
print(pd.DataFrame(boot).round(6).to_string(index=False));print(pd.DataFrame(period).round(6).to_string(index=False));print(scale)
