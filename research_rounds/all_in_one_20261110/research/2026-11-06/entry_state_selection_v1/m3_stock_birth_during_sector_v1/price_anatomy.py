from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent;D=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
seal=json.load(open(O/'EVENT_SEAL.json'));assert all(sha(O/n)==h for n,h in seal['outputs'].items())
allx=pd.read_csv(O/'SEALED_ALL_BIRTH_EVENTS.csv',dtype={'window':str},parse_dates=['day','sector_run_start'])
named=['300085.SZ','002583.SZ','603061.SH','300623.SZ','688498.SH','300666.SZ','301611.SZ']
main=allx.I_and_PVR_known&allx.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])&(allx.day.between('2024-09-24','2024-10-31')|allx.window.eq('2026H1_SEMI'))
x=allx[main|allx.sid.isin(named)].copy();x['main_price_scope']=main.loc[x.index];x=x.reset_index(drop=True)
cal=pd.read_parquet(D/'MU5.parquet').index;sm={m['symbol']:m for m in json.load(open(U/'STOCK_MANIFEST.json'))}
hashes={str(p):sha(p) for p in [O/'PROTOCOL.json',O/'PRICE_ANATOMY_SPEC.json',O/'EVENT_SEAL.json',O/'SEALED_ALL_BIRTH_EVENTS.csv',Path(__file__),D/'MU5.parquet']}
records=[];timelines=[]
for sid,g in x.groupby('sid'):
 sp=Path(next(p for p in sm[sid]['source_sha256'] if p.endswith('/signal.parquet')));fp=Path(sm[sid]['refs']['facts']);cp=Path(sm[sid]['refs']['CP1']);hashes[str(sp)]=sha(sp);hashes[str(fp)]=sha(fp);hashes[str(cp)]=sha(cp)
 p=pd.read_parquet(sp).reindex(cal);facts=pd.read_parquet(fp).reindex(cal);cps=pd.read_parquet(cp).reindex(cal)
 for z in g.itertuples():
  d=pd.Timestamp(z.day);k=cal.get_loc(d);r=dict(event_id=z.event_id,window=z.window,day=d,sid=sid,name=z.name,event_type=z.event_type,main_price_scope=z.main_price_scope,I_and_PVR_known=z.I_and_PVR_known,PVR_score=z.PVR_score,sector_run_start=z.sector_run_start,already_invited_at_sector_birth=z.already_invited_at_sector_birth)
  r['original_i_buy']=facts.at[d,'i_buy'];r['original_fresh_CP']=cps.at[d,'receipt'];r['raw_signal_close']=p.at[d,'raw_close'];r['raw_I_floor']=z.i_floor/z.factor if np.isfinite(z.i_floor) and np.isfinite(z.factor) and z.factor>0 else np.nan
  r['next_day']=cal[k+1] if k+1<len(cal) else pd.NaT;r['next_open']=p.raw_open.iloc[k+1] if k+1<len(cal) else np.nan
  r['next_open_gap']=r['next_open']/r['raw_signal_close']-1 if r['raw_signal_close']>0 else np.nan
  r['next_open_below_floor']=bool(r['next_open']<=r['raw_I_floor']) if np.isfinite(r['next_open']) and np.isfinite(r['raw_I_floor']) else None
  for h in [5,20]:
   reason='KNOWN'
   if k+h>=len(cal):reason='RIGHT_CENSORED'
   else:
    w=p.iloc[k:k+h+1];vv=w.observed_bar.eq(True)&w.price_eligible.eq(True)&~w.source_invalid.eq(True)&~w.synthetic_event_bar.eq(True)&w.raw_close.gt(0)&w.raw_open.gt(0)
    if not vv.all():reason='MISSING_OR_INVALID_PRICE'
    elif not w[['source_kind','source_path','segment_id','adjustment_factor']].notna().all().all() or not w[['source_kind','source_path','segment_id','adjustment_factor']].nunique().eq(1).all():reason='SOURCE_OR_FACTOR_CHANGE'
    elif r['next_open_below_floor']:reason='NEXT_OPEN_AT_OR_BELOW_FLOOR'
    else:
     path=w.raw_close.iloc[1:];op=r['next_open'];r[f'ret{h}']=float(path.iloc[-1]/op-1);r[f'mfe{h}']=float(path.max()/op-1);r[f'mae{h}']=float(path.min()/op-1)
     ix=facts.i_target.iloc[k+1:k+h+1];invalid=ix.index[ix.eq(0)];r[f'I_invalid_within{h}']=bool(len(invalid));r[f'first_I_invalid{h}']=invalid[0] if len(invalid) else pd.NaT
   r[f'path{h}_status']=reason
  records.append(r)
  if sid in named:
   for n in range(max(0,k-3),min(len(cal),k+6)):
    dd=cal[n];zz=p.iloc[n];timelines.append(dict(event_id=z.event_id,signal_day=d,day=dd,sid=sid,name=z.name,offset=n-k,raw_open=zz.raw_open,raw_close=zz.raw_close,raw_high=zz.raw_high,raw_low=zz.raw_low,amount=zz.amount,raw_volume=zz.raw_volume,I_target=facts.i_target.iloc[n],I_buy=facts.i_buy.iloc[n],CP_receipt=cps.receipt.iloc[n],source=zz.source_kind,factor=zz.adjustment_factor))
res=pd.DataFrame(records);res.to_csv(O/'PRICE_ANATOMY.csv',index=False);pd.DataFrame(timelines).to_csv(O/'FIXED_NAMED_DAILY.csv',index=False)
summary=[]
for (wn,typ),g in res[res.main_price_scope].groupby(['window','event_type']):
 for h in [5,20]:
  v=g[g[f'path{h}_status'].eq('KNOWN')];date=v.groupby('day')[f'ret{h}'].mean()
  summary.append(dict(window=wn,event_type=typ,horizon=h,all_invitation_events=len(g),known_price_paths=len(v),known_dates=v.day.nunique(),unknown=len(g)-len(v),price_positive=int(v[f'ret{h}'].gt(0).sum()),mean_gross_return=v[f'ret{h}'].mean(),date_equal_mean_gross_return=date.mean(),median_gross_return=v[f'ret{h}'].median(),mfe_ge30=int(v[f'mfe{h}'].ge(.3).sum()),original_I_invalid=int(v[f'I_invalid_within{h}'].sum())))
ss=pd.DataFrame(summary);ss.to_csv(O/'PRICE_PATH_SUMMARY.csv',index=False)
counts=[]
for (wn,typ),g in res[res.main_price_scope].groupby(['window','event_type']):
 for h in [5,20]:
  for reason,n in g[f'path{h}_status'].value_counts().items():counts.append(dict(window=wn,event_type=typ,horizon=h,status=reason,n=int(n)))
pd.DataFrame(counts).to_csv(O/'PATH_KNOWLEDGE_COUNTS.csv',index=False)
cases=[]
for wn,g in res[res.main_price_scope&res.event_type.eq('B_STOCK_BIRTH_DURING_SECTOR')&res.path20_status.eq('KNOWN')].groupby('window'):
 for kind,z in [('LOWEST_GROSS20',g.sort_values(['ret20','sid']).head(3)),('HIGHEST_GROSS20',g.sort_values(['ret20','sid'],ascending=[False,True]).head(3))]:
  q=z.copy();q['posthoc_description']=kind;cases.append(q)
case=pd.concat(cases,ignore_index=True) if cases else pd.DataFrame();case.to_csv(O/'TRANSPARENT_POSITIVE_NEGATIVE_EXAMPLES.csv',index=False)
res[res.sid.isin(named)].to_csv(O/'FIXED_NAMED_EVENT_PATHS.csv',index=False)
assert all(sha(O/n)==h for n,h in seal['outputs'].items())
save('PRICE_SOURCE_HASHES.json',hashes);save('PRICE_QA.json',dict(event_seal_unchanged=True,original_signal_rows=len(allx),price_rows=len(res),main_price_scope_rows=int(res.main_price_scope.sum()),future_paths_do_not_select_events=True,no_economic_simulation=True,no_accounts=True,no_winrate_claim=True))
print(ss.to_string(index=False));print('STATUS\n',pd.DataFrame(counts).to_string(index=False))
print('EXAMPLES\n',case[['window','day','sid','name','PVR_score','ret20','mfe20','mae20','I_invalid_within20','first_I_invalid20','posthoc_description']].to_string(index=False))
print('NAMED_B\n',res[res.sid.isin(named)&res.event_type.eq('B_STOCK_BIRTH_DURING_SECTOR')][['window','day','sid','name','I_and_PVR_known','PVR_score','next_day','next_open','next_open_gap','path5_status','ret5','path20_status','ret20','I_invalid_within20']].to_string(index=False))
