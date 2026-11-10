from pathlib import Path
import json,hashlib,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent; R=O.parent
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p):p=Path(p);H[str(p)]=sha(p);return p
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,pd.Timestamp):return str(x.date())
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x
def save(n,x):
 with (O/n).open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2);f.write('\n')
def out(n,x):
 with (O/n).open('x') as f:x.to_csv(f,index=False)
def derive(f,cp):
 rows=[];prev_target=None;prev_segment=None;birth=None;known=False;h=math.nan;ni=nc=0
 for day,r in f.iterrows():
  valid=np.isfinite(r.close) and r.close>0 and pd.notna(r.i_target) and pd.notna(r.segment_id)
  same=prev_segment is not None and r.segment_id==prev_segment
  t=bool(r.i_target==1) if valid else None
  if not valid or not same:birth=None;known=False;h=math.nan;ni=nc=0
  kind='INACTIVE' if t is False else 'UNKNOWN'
  if t is True:
   if same and prev_target is False:birth=day;known=True;h=math.nan;ni=nc=0;kind='FIRST_I_DAY'
   elif known:kind='NEW_I_HWM' if r.close>h+32*np.finfo(float).eps*max(abs(r.close),abs(h),1.) else 'BELOW_OR_EQUAL_I_HWM'
   ib=bool(r.i_buy) if pd.notna(r.i_buy) else None
   cc=cp.loc[day] if day in cp.index else None
   cr=bool(cc.receipt) if cc is not None and bool(cc.ready) and pd.notna(cc.receipt) else None
   priorni=ni;priornc=nc
   if ib:ni+=1
   if cr:nc+=1
   ik='UNKNOWN' if not known or ib is None else 'NO_CURRENT_I_BUY' if not ib else 'FIRST_I_BUY' if ni==1 else 'REPEATED_I_BUY'
   ck='UNKNOWN' if not known or cr is None else 'NO_CURRENT_CP' if not cr else 'FIRST_CP' if nc==1 else 'REPEATED_CP'
   rows.append(dict(day=day,I_known_birth=birth,I_lineage_known=known,I_hwm_class=kind,I_hwm_previous=h,I_prior_i_buy_count=priorni,I_buy_class=ik,I_prior_cp_count=priornc,CP_class=ck,original_i_target=t,original_i_buy=ib,original_cp=cr,native_close=r.close,raw_close=r.raw_close,source_segment=r.segment_id))
   h=max(h,r.close) if np.isfinite(h) else r.close
  else:
   rows.append(dict(day=day,I_known_birth=None,I_lineage_known=False,I_hwm_class=kind,I_hwm_previous=None,I_prior_i_buy_count=None,I_buy_class=kind,I_prior_cp_count=None,CP_class=kind,original_i_target=t,original_i_buy=None,original_cp=None,native_close=r.close,raw_close=r.raw_close,source_segment=r.segment_id))
   birth=None;known=False;h=math.nan;ni=nc=0
  prev_target=t;prev_segment=r.segment_id if valid else None
 return pd.DataFrame(rows).set_index('day')
manifest={x['symbol']:x for x in json.loads(src(M).read_text())}
case=pd.read_csv(src(R/'e0_frontier_confirmation_preflight_v1/CASE_CONFIRMATION_SUMMARY.csv'));case['day']=pd.to_datetime(case.day)
panel=pd.read_csv(src(R/'e0_frontier_confirmation_preflight_v1/KLINE_PATHS.csv'));panel['day']=pd.to_datetime(panel.day)
assert len(case)==22 and case.sid.nunique()==19
src(O/'PROTOCOL.json');src(__file__)
allrows=[];qa=[]
for sid,g in panel.groupby('sid'):
 f=pd.read_parquet(src(manifest[sid]['refs']['facts']));cp=pd.read_parquet(src(manifest[sid]['refs']['CP1']))
 d=derive(f.loc[:g.day.max()],cp);z=g.merge(d.reset_index(),on='day',validate='one_to_one')
 assert np.allclose(z.close,z.native_close,rtol=1e-12,atol=1e-10)
 assert z.old_I_target.eq(z.original_i_target.astype(float)).all()
 assert z.loc[z.old_I_target.eq(1),'old_i_buy'].eq(z.loc[z.old_I_target.eq(1),'original_i_buy']).all()
 def reason(r):
  if not bool(r.old_i_buy):return 'NO_I_BUY'
  s=r.old_G_up_reasons if isinstance(r.old_G_up_reasons,str) else ''
  return 'PURE_S21_FRONTIER' if s=='new_price_frontier_in_confirmed_up_structure' else 'CONFIRMATION_OR_MIXED' if s else 'UNKNOWN_REASON'
 z['reason_class']=z.apply(reason,axis=1)
 for cut in case.loc[case.sid.eq(sid),'day']:
  a=derive(f.loc[:cut],cp.loc[:cut]);b=d.loc[:cut];assert a.equals(b)
  qa.append(dict(sid=sid,cut=cut,prefix_equal=True))
 allrows.append(z)
x=pd.concat(allrows,ignore_index=True)
out('FIXED_WINDOWS_WITH_I_HIGH_WATER.csv',x)
y=case.merge(x[['sid','day','I_known_birth','I_lineage_known','I_hwm_class','I_hwm_previous','I_prior_i_buy_count','I_buy_class','I_prior_cp_count','CP_class','reason_class','native_close']],on=['sid','day'],validate='one_to_one');y['distance_from_I_prior_high']=y.native_close/y.I_hwm_previous-1
out('FIXED_CASE_CLASSIFICATION.csv',y)
counts=x.groupby(['reason_class','I_hwm_class'],dropna=False).size().reset_index(name='n');out('WINDOW_COUNTS.csv',counts)
changes=[p for p,h in H.items() if sha(p)!=h];assert not changes
save('QA.json',dict(fixed_cases=len(y),stocks=y.sid.nunique(),daily=len(x),prefix=qa,source_unchanged=True,consumers=0,new_economic_runs=0,new_signals=0,trading_gate=0,parameter_searches=0))
save('SOURCE_HASHES.json',H)
print(y[['sid','day','name','old_price_net','I_known_birth','I_buy_class','I_prior_i_buy_count','CP_class','reason_class','I_hwm_class','distance_from_I_prior_high']].to_string(index=False))
print(counts.to_string(index=False))
