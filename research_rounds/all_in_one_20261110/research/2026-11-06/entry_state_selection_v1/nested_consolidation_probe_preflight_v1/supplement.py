from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest={x['symbol']:x for x in json.load(open(M))};cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates'])
t=pd.read_csv(O/'FIXED_TARGET_FEATURES.csv');d=pd.read_csv(O/'CASE_DAILY_FEATURES.csv');sources={};facts={};hashes={};checks=[]
for sid in t.sid.unique():
 m=manifest[sid];pp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));fp=Path(m['refs']['facts'])
 sources[sid]=pd.read_parquet(pp);facts[sid]=pd.read_parquet(fp)
 hashes[str(pp)]=sha(pp);hashes[str(fp)]=sha(fp)
for x in t.itertuples():
 if x.status!='KNOWN':continue
 p=cal.get_loc(pd.Timestamp(x.day));v=sources[x.sid].reindex(cal[p-20:p+1]);a=v.iloc[:10];b=v.iloc[10:20];f=v.adjustment_factor.iloc[-1]
 u0=max(a.high);l0=min(a.low);u1=max(b.high);l1=min(b.low);v0=np.median(a.amount);v1=np.median(b.amount)
 value=(u1<=u0 and l1>=l0 and (u1-l1)<(u0-l0) and v1<v0 and v.close.iloc[-1]>u1)
 assert bool(x.candidate)==value
 for n,ref in [('U0',u0/f),('L0',l0/f),('U1',u1/f),('L1',l1/f),('amount_ratio',v1/v0),('range_ratio',(u1-l1)/(u0-l0))]:assert np.isclose(getattr(x,n),ref,rtol=1e-12,atol=1e-12)
 checks.append(dict(sid=x.sid,day=x.day,scalar_recompute_equal=True))
# Synthetic natural-boundary test, no future path used.
def predicate(u0,l0,u1,l1,v0,v1,c):return u1<=u0 and l1>=l0 and u1-l1<u0-l0 and v1<v0 and c>u1
tests=[
 ('local_below_old_ceiling',predicate(110,90,106,94,100,60,107)==True),
 ('amount_expansion_blocks_only_extra_setup',predicate(110,90,106,94,100,120,107)==False),
 ('equal_amount_not_dry',predicate(110,90,106,94,100,100,107)==False),
 ('equal_close_not_break',predicate(110,90,106,94,100,60,106)==False),
 ('higher_recent_high_not_nested',predicate(110,90,111,94,100,60,112)==False),
 ('lower_recent_low_not_nested',predicate(110,90,106,89,100,60,107)==False),
 ('chronology_changes_information',predicate(106,94,110,90,60,100,107)==False),
 ('price_scale_invariant',predicate(1100,900,1060,940,100,60,1070)==True),
 ('amount_scale_invariant',predicate(110,90,106,94,100000,60000,107)==True),
 ('all_ranges_equal_not_contracting',predicate(110,90,110,90,100,60,111)==False)]
assert all(x[1] for x in tests)
unique=d.drop_duplicates(['sid','day']);p=unique[unique.nested.eq(True)&unique.local_break.eq(True)].copy();p['dry_removes']=~p.dry.astype(bool);p.to_csv(O/'PRICE_ONLY_COMPONENT_DIAGNOSTIC.csv',index=False)
e=unique[unique.candidate.eq(True)].copy();out=[]
for x in e.itertuples():
 date=pd.Timestamp(x.day);pos=cal.get_loc(date);raw=sources[x.sid];fr=facts[x.sid].reindex([date]).iloc[0]
 identity=raw.loc[date,['source_kind','source_path','segment_id']].to_list();factor=raw.at[date,'adjustment_factor']
 for ahead in range(0,11):
  if pos+ahead>=len(cal):continue
  dt=cal[pos+ahead];j=raw.reindex([dt]).iloc[0]
  same=all(j[k]==v for k,v in zip(['source_kind','source_path','segment_id'],identity))
  known=same and bool(j.observed_bar==True) and bool(j.price_eligible==True) and j.source_invalid==False and j.synthetic_event_bar==False and pd.notna(j.raw_close) and np.isclose(j.adjustment_factor,factor,rtol=1e-12,atol=1e-12)
  out.append(dict(sid=x.sid,event_day=x.day,known_at=str(dt.date())+' CLOSE',ahead=ahead,scope='POST_EVENT_OBSERVATION_NOT_ENTRY_INPUT' if ahead else 'BIRTH_KNOWN_AT',status='KNOWN' if known else 'UNKNOWN',raw_O=j.raw_open if known else None,raw_H=j.raw_high if known else None,raw_L=j.raw_low if known else None,raw_C=j.raw_close if known else None,fixed_U1=x.U1,fixed_S=x.L1,close_above_U1=bool(j.raw_close>x.U1) if known else None,close_above_S=bool(j.raw_close>x.L1) if known else None,birth_E0=fr.e0_target,birth_I=fr.i_target,birth_i_buy=fr.i_buy,birth_G=fr.g_grade))
pd.DataFrame(out).to_csv(O/'UNIQUE_EVENT_PATHS.csv',index=False);pd.DataFrame(checks).to_csv(O/'SCALAR_FEATURE_CHECKS.csv',index=False)
(O/'SUPPLEMENT_QA.json').write_text(json.dumps(dict(scalar_target_checks=len(checks),synthetic_tests=tests,all_pass=True,unique_known_stockdays=int(unique.status.eq('KNOWN').sum()),unique_price_only_setups=len(p),unique_volume_contracted_setups=len(e),extra_volume_condition_removes=int(p.dry_removes.sum()),new_economic_labels_used=False,inputs_unchanged=all(sha(p)==h for p,h in hashes.items()),source_hashes=hashes),ensure_ascii=False,indent=2)+'\n')
print('SUPPLEMENT',len(checks),len(p),len(e),len(unique))
