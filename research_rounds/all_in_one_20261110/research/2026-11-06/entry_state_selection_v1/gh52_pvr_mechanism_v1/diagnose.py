"""One fixed 12-calendar-month close-high/PVR mechanism check. No accounts or orders."""
from pathlib import Path
import json,sys,hashlib,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent; R=O.parent
F=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design/features.py')
MP=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
HP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
sys.path.insert(0,str(F.parent));from features import original_pvr,original_observation_clock
W=.9**np.arange(20,-1,-1);W/=W.sum()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 def clean(v):
  if isinstance(v,dict):return {str(k):clean(a)for k,a in v.items()}
  if isinstance(v,(list,tuple)):return [clean(a)for a in v]
  if isinstance(v,(np.integer,)):return int(v)
  if isinstance(v,(np.bool_,)):return bool(v)
  if isinstance(v,(float,np.floating)):return float(v)if np.isfinite(v)else None
  if isinstance(v,(pd.Timestamp,Path)):return str(v)
  return v
 (O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2))
def calc(p,common):
 z=original_pvr(p);valid,blocks=original_observation_clock(p)
 ix=common[(common>=p.index.min())&(common<=p.index.max())]
 c=p.close.reindex(ix);segment=p.segment_id.reindex(ix)
 priceok=c.gt(0)&np.isfinite(c)
 for col in ['price_eligible','observed_bar','is_observed_bar']:
  if col in p:priceok&=p[col].reindex(ix).fillna(False).astype(bool)
 for col in ['source_invalid','synthetic_event_bar']:
  if col in p:priceok&=~p[col].reindex(ix).fillna(True).astype(bool)
 qq=pd.DataFrame(index=ix,columns=['q','high_close','high_day_age_calendar','missing_common','window_sessions','history_complete'],dtype=float)
 for j,d in enumerate(ix):
  start=d-pd.DateOffset(months=12);k=ix.searchsorted(start,side='right');win=c.iloc[k:j+1];bad=int((~priceok.iloc[k:j+1]).sum())
  hist=bool(p.index.min()<=start)
  qq.loc[d,['missing_common','window_sessions','history_complete']]=[bad,len(win),hist]
  if not hist or bad or segment.iloc[k:j+1].nunique()!=1:continue
  hi=win.max();highdate=win[win.eq(hi)].index[-1]
  qq.loc[d,['q','high_close','high_day_age_calendar']]=[c.iloc[j]/hi,hi,(d-highdate).days]
 z=z.join(qq.reindex(p.index))
 z['e_fused']=z.q*z.e.clip(lower=0)+z.e.clip(upper=0);z['E_fused']=np.nan
 for _,g in p[valid].groupby(blocks[valid],sort=False):
  z.loc[g.index,'E_fused']=z.loc[g.index,'e_fused'].rolling(21,min_periods=21).apply(lambda x:np.dot(W,x),raw=True)
 z['PVR_fused']=50+50*np.tanh(2*z.E_fused);z['score_drop']=z.score-z.PVR_fused
 known=z.PVR_fused.notna();assert (z.loc[known,'q'].between(0,1)).all();assert (z.loc[known,'score_drop']>=-1e-12).all()
 return z
def main():
 t=time.monotonic();cases=json.loads((R/'lifecycle_ordered_damage_v1/FIXED_CASES_BEFORE_COMPUTE.json').read_text())
 extra=[('601607.SH','2022-03-24'),('300085.SZ','2024-09-24'),('002583.SZ','2024-09-24'),('300666.SZ','2026-01-15'),('603061.SH','2026-01-15'),('301611.SZ','2026-01-15')]
 cases.extend(dict(sid=s,day=d,selection='previous_named_case')for s,d in extra)
 save('FREEZE.json',dict(formula='Q=C/max(C_u for t-12 calendar months < u <= t); e*=Q max(e,0)+min(e,0); original21/.9 aggregation and score transform',one_formula_only=True,price_field='causal same-source adjusted CLOSE, not intraday high; explicit daily adaptation, not exact CRSP replication',calendar='past12 actual calendar months including t, not last252 observed bars; require full year source history and every common market date valid; missing/suspension not filled',unknown='preserve old score and slot if ever used; no actual rank run here',cases=cases,focus_windows=['2024-09-01..2024-10-31','2025-12-01..2026-01-30'],other_windows='each named day -40 calendar days .. +40 calendar days',scope='fixed known case diagnostic, not OOS; no future return labels, accounts, parameters or trades',sources={str(x):sha(x)for x in [F,MP,HP,Path(__file__)]}))
 m={r['symbol']:r for r in json.load(open(MP))};h=np.load(HP,allow_pickle=False);common=pd.DatetimeIndex(h['dates']);rows=[];daily=[];audit=[];prefix=[];sources={}
 for sid in sorted({x['sid']for x in cases}):
  cc=[x for x in cases if x['sid']==sid];r=m[sid];sp=next(x for x in r['source_sha256']if x.endswith('/signal.parquet'))
  p=pd.read_parquet(sp);before=sha(sp);sources[sp]=before;assert before==r['source_sha256'][sp];assert p.symbol.dropna().eq(sid).all()
  end=max(pd.Timestamp(x['day'])+pd.Timedelta(days=40)for x in cc)
  if sid in ['300085.SZ','002583.SZ']:end=max(end,pd.Timestamp('2024-10-31'))
  if sid in ['300666.SZ','603061.SH','301611.SZ']:end=max(end,pd.Timestamp('2026-01-30'))
  p=p.loc[:end];z=calc(p,common);facts=pd.read_parquet(r['refs']['facts']);cp=pd.read_parquet(r['refs']['CP1'])
  for path in [r['refs']['facts'],r['refs']['CP1']]:sources[path]=sha(path)
  basepath=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1/artifacts')/(sid+'.parquet')
  base=pd.read_parquet(basepath).set_index('day');base.index=pd.DatetimeIndex(base.index);ix=z.index.intersection(base.index);diff=(z.score.reindex(ix)-base.pvr__score.reindex(ix)).abs();mx=diff.max()
  audit.append(dict(sid=sid,full_rows=len(p),baseline_maxerr=mx,source_unchanged=sha(sp)==before))
  ranges=[]
  for c in cc:
   d=pd.Timestamp(c['day']);zz=calc(p.loc[:d],common);pd.testing.assert_frame_equal(zz,z.loc[:d],check_exact=True);prefix.append(dict(sid=sid,day=c['day'],exact=True))
   row=dict(c);row['legacy_cache_baseline_difference']=float(z.loc[d,'score']-base.loc[d,'pvr__score']) if d in base.index else np.nan;row.update(z.loc[d].to_dict());row.update(close=p.loc[d,'close'],raw_close=p.loc[d,'raw_close'],i_buy=bool(facts.loc[d,'i_buy']),i_target=float(facts.loc[d,'i_target']),CP=bool(cp.loc[d,'receipt']));rows.append(row);ranges.append((d-pd.Timedelta(days=40),d+pd.Timedelta(days=40)))
  if sid in ['300085.SZ','002583.SZ']:ranges.append((pd.Timestamp('2024-09-01'),pd.Timestamp('2024-10-31')))
  if sid in ['300666.SZ','603061.SH','301611.SZ']:ranges.append((pd.Timestamp('2025-12-01'),pd.Timestamp('2026-01-30')))
  mask=pd.Series(False,index=z.index)
  for lo,hi in ranges:mask|=(z.index>=lo)&(z.index<=hi)
  a=z.loc[mask].copy();a['close']=p.close;a['raw_close']=p.raw_close;a['sid']=sid;a['CP']=cp.receipt;a['i_buy']=facts.i_buy;a['i_target']=facts.i_target;a['day']=a.index.strftime('%Y-%m-%d');daily.append(a.reset_index(drop=True))
 out=pd.DataFrame(rows);out.to_csv(O/'FIXED_CASES.csv',index=False);dd=pd.concat(daily,ignore_index=True);dd.to_csv(O/'DAILY_DIAGNOSTICS.csv',index=False);save('AUDIT.json',dict(rows=len(out),stocks=len(audit),daily_rows=len(dd),fixed_known=int(out.PVR_fused.notna().sum()),daily_known=int(dd.PVR_fused.notna().sum()),prefix_checks=prefix,source_audit=audit,sources=sources,seconds=time.monotonic()-t,existing_source_hashes_unchanged=all(sha(p)==v for p,v in sources.items())))
 print(out[['sid','day','q','score','PVR_fused','score_drop','CP','i_buy','original_round_pnl']].to_string(index=False));print('seconds',time.monotonic()-t)
if __name__=='__main__':main()
