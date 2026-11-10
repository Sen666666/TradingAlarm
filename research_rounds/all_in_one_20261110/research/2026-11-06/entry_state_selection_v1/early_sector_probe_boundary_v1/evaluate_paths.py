"""Forward-price descriptions, run only after immutable opportunity selection."""
import sys,json,gzip,hashlib,math
from pathlib import Path
from collections import Counter
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
P=ROOT/'account_comparison_continuous_v1/run_1200000/pair'
END='2026-05-15'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def out(n,x):
 p=O/n;assert not p.exists(),p;p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def periods():return [('ALL',None,None)]+[(str(y),f'{y}-01-01',f'{y}-12-31') for y in range(2022,2027)]+[('2024_924','2024-09-24','2024-10-31'),('2026Jan15_30','2026-01-15','2026-01-30')]
def per(s,a,b):return s if a is None else s[s.day.between(a,b)]
def main():
 seal=read(O/'SELECTION_SEAL.json');assert all(sha(p)==h for p,h in seal['hashes'].items())
 assert not (O/'EVALUATION_STARTED.json').exists()
 out('EVALUATION_STARTED.json',dict(created_utc=pd.Timestamp.now(tz='UTC').isoformat(),selection_seal_sha256=sha(O/'SELECTION_SEAL.json'),fixed_one_scheme=True))
 s=pd.read_csv(O/'SEALED_EPISODE_FIRST_PROBES.csv');d=pd.read_parquet(O/'DOMAIN.parquet');i=pd.read_parquet(O/'NEXT_OPEN_INPUTS.parquet')
 # Named sea case is an audit, never an extra allocation.
 named=d[d.sid.eq('002583.SZ') & d.day.between('2024-09-01','2024-10-31')].merge(i,on=['row','sid','day'])
 targets=pd.concat([s[['row','sid','day','adjusted_open']],named[['row','sid','day','adjusted_open']]]).drop_duplicates('row')
 cal=pd.DatetimeIndex([json.loads(l)['at'][:10] for l in gzip.open(P/'daily.jsonl.gz','rt') if json.loads(l)['account']=='PVR'])
 sm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
 rows=[];src={str(U/'STOCK_MANIFEST.json'):sha(U/'STOCK_MANIFEST.json'),str(Path(__file__)):sha(Path(__file__))}
 for sid,g in targets.groupby('sid'):
  pp=sm[sid]['refs']['facts'];src[pp]=sha(pp);f=pd.read_parquet(pp).reindex(cal);C=f.close.to_numpy(float)
  for r in g.itertuples():
   t=cal.get_loc(pd.Timestamp(r.day));en=t+1;op=float(r.adjusted_open) if pd.notna(r.adjusted_open) else np.nan
   a=dict(row=r.row,sid=sid,day=r.day,adjusted_next_open=op)
   for h in [5,20,60]:
    end=t+h;reason='RIGHT_CENSORED' if end>=len(cal) else 'MISSING_NEXT_OPEN' if not math.isfinite(op) or op<=0 else 'MISSING_CLOSE' if not(np.isfinite(C[en:end+1])&(C[en:end+1]>0)).all() else 'COMPLETE'
    ok=reason=='COMPLETE';a[f'status{h}']=reason;a[f'complete{h}']=ok;a[f'end_day{h}']=str(cal[end].date()) if end<len(cal) else None
    a[f'ret{h}']=C[end]/op-1 if ok else np.nan
    a[f'mfe{h}']=max(0.,C[en:end+1].max()/op-1) if ok else np.nan
    a[f'mae{h}']=min(0.,C[en:end+1].min()/op-1) if ok else np.nan
   a['big60']=bool(a['complete60'] and a['mfe60']>=.30 and a['ret60']>=.20);rows.append(a)
 labels=pd.DataFrame(rows);labels.to_csv(O/'FIRST_PROBE_PRICE_LABELS.csv',index=False)
 ep=pd.read_csv(O/'EPISODE_CALENDAR.csv')
 for col in ['E0_end','first_accepted_CP','first_raw_CP']:ep.loc[ep[col]>END,col]=None
 ep['episode_end_censored']=ep.E0_end.isna()
 s=s.merge(labels,on=['row','sid','day'],validate='one_to_one').merge(ep[['sector','episode','E0_end','first_accepted_CP','first_raw_CP','episode_end_censored']],on=['sector','episode'],validate='many_to_one')
 s['first_CP_after_probe_signal_sessions']=[cal.get_loc(pd.Timestamp(x.first_accepted_CP))-cal.get_loc(pd.Timestamp(x.day)) if pd.notna(x.first_accepted_CP) and pd.Timestamp(x.first_accepted_CP) in cal else np.nan for x in s.itertuples()]
 s.to_csv(O/'EPISODE_FIRST_PROBE_RESULTS.csv',index=False)
 results=[];cens=[]
 for period,a,b in periods():
  for scope,ss in [('ALL_FIRST_PROBES',per(s,a,b)),('NON_LEFT_TRUNCATED',per(s[~s.left_truncated],a,b))]:
   for h in [5,20,60]:
    v=ss[ss[f'complete{h}']]
    cens.append(dict(period=period,scope=scope,horizon=h,first_episode_probes=len(ss),complete=len(v),right_censored=int(ss[f'status{h}'].eq('RIGHT_CENSORED').sum()),missing_close=int(ss[f'status{h}'].eq('MISSING_CLOSE').sum()),missing_open=int(ss[f'status{h}'].eq('MISSING_NEXT_OPEN').sum())))
    if len(v):
     z=v[f'ret{h}'];results.append(dict(period=period,scope=scope,horizon=h,n=len(v),gross_price_positive=int(z.gt(0).sum()),gross_price_positive_fraction=float(z.gt(0).mean()),price_positive_after40bp=int(z.gt(.004).sum()),price_positive_after40bp_fraction=float(z.gt(.004).mean()),mean_ret=float(z.mean()),median_ret=float(z.median()),p10_ret=float(z.quantile(.1)),mean_mfe=float(v[f'mfe{h}'].mean()),mean_mae=float(v[f'mae{h}'].mean()),worst_mae=float(v[f'mae{h}'].min()),big60=int(v.big60.sum()) if h==60 else None))
 pd.DataFrame(results).to_csv(O/'PRICE_PATH_SUMMARY.csv',index=False);pd.DataFrame(cens).to_csv(O/'HORIZON_CENSORING.csv',index=False)
 # Mechanical best/worst examples, descriptive only, not new decisions.
 cases=[]
 for period,a,b in periods():
  if period not in ['2022','2023','2024','2025','2026','2024_924','2026Jan15_30']:continue
  ss=per(s,a,b)
  for h in [20,60]:
   v=ss[ss[f'complete{h}']]
   if len(v):
    for kind,row in [('WORST_TERMINAL',v.sort_values([f'ret{h}','day','priority_rank']).iloc[0]),('BEST_TERMINAL',v.sort_values([f'ret{h}','day','priority_rank'],ascending=[False,True,True]).iloc[0])]:
     cases.append(dict(period=period,case_label=kind,horizon=h,**row.to_dict()))
 pd.DataFrame(cases).to_csv(O/'DESCRIPTIVE_FIXED_WINDOW_CASES.csv',index=False)
 audit=pd.read_csv(O/'ALL_BOUNDARY_DECISIONS.csv')
 sea=audit[audit.sid.eq('002583.SZ') & audit.day.between('2024-09-01','2024-10-31')].merge(labels,on=['row','sid','day'],how='left')
 sea.to_csv(O/'HAINENGDA_2024_AUDIT.csv',index=False)
 semi=audit[audit.industry_name.eq('半导体') & audit.day.between('2026-01-01','2026-01-30')]
 semi.to_csv(O/'SEMICONDUCTOR_2026_AUDIT.csv',index=False)
 out('EVALUATION_HASHES.json',src)
 out('EVALUATION_QA.json',dict(first_probes=len(s),first_probes60_complete=int(s.complete60.sum()),big60=int(s.big60.sum()),selected_after_seal=False,full_net_round_win_rate_measured=False,real_executability_measured=False,new_account=False,dates_end=END,named_sea_rows=len(sea),semiconductor_Jan_rows=len(semi)))
 print(read(O/'EVALUATION_QA.json'));print(pd.DataFrame(results)[lambda x:x.scope.eq('ALL_FIRST_PROBES')].to_string(index=False))
if __name__=='__main__':main()
