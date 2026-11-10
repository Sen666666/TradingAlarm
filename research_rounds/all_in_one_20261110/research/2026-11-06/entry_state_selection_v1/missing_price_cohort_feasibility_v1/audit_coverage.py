from pathlib import Path
import ast,hashlib,json,time,resource,sys,collections
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent;J=R/'independent_channel_joint_economic_v1';E=R/'m3_stock_birth_during_sector_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
start=time.monotonic();sm=json.loads((U/'STOCK_MANIFEST.json').read_text());im=json.loads((U/'INDUSTRY_MANIFEST.json').read_text());ids=sorted(x['symbol'] for x in sm)
with np.load(H,allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates']); hids=[str(s) for s in h['symbols']]; hs=h['score']
wins={'2023':('2023-01-01','2023-12-31'),'2024JanAug':('2024-01-01','2024-08-31')};days={w:cal[(cal>=a)&(cal<=b)] for w,(a,b) in wins.items()}
fixture=[next(s for s in ids if s.startswith(p)) for p in ['000','002','300','600','601','688']]
protocol=dict(scope='READ_ONLY_FULL_POOL_COVERAGE_AND_SIX_SID_NON_ECONOMIC_FUNCTION_FIXTURE',fixed_universe=1709,windows=wins,fixture_sids=fixture,selection='lexicographically first fixed-pool sid for each predeclared prefix 000 002 300 600 601 688; no outcome used',fixture_dates={w:[str(x.date()) for x in ds[:20]] for w,ds in days.items()},market_warmup='full original history, not reset at window start',economic_runs=0,reason='Old gate only permits fixed 2022 and 2024SepDec and no PRICE sample-run; do not bypass',no_orders=True,no_outcomes=True,no_new_rights_or_rule_approvals=True)
save('PROTOCOL.json',protocol)
old={str(p):sha(p) for p in J.rglob('*') if p.is_file()};save('OLD_TREE_SHA256_BEFORE.json',old)
sources={str(U/'STOCK_MANIFEST.json'):sha(U/'STOCK_MANIFEST.json'),str(U/'INDUSTRY_MANIFEST.json'):sha(U/'INDUSTRY_MANIFEST.json'),str(H):sha(H),str(__file__):sha(__file__)}
rows=[];factorrows=[];actionrows=[];errors=[];hasherr=[]
cols=['open','high','low','close','raw_open','raw_high','raw_low','raw_close','raw_volume','adjustment_factor','source_kind','source_path','segment_id','observed_bar','is_observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']
for n,m in enumerate(sorted(sm,key=lambda x:x['symbol'])):
 sid=m['symbol']
 try:
  p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));expected={p:m['source_sha256'][p],m['refs']['facts']:m['output_sha256'][m['refs']['facts']],m['refs']['CP1']:m['output_sha256'][m['refs']['CP1']]}
  for pp,h in expected.items():
   actual=sha(pp);sources[pp]=actual
   if actual!=h:hasherr.append(dict(sid=sid,path=pp,expected=h,actual=actual))
  q=pd.read_parquet(p,columns=cols);f=pd.read_parquet(m['refs']['facts']);cp=pd.read_parquet(m['refs']['CP1'],columns=['ready','receipt'])
  for w,ds in days.items():
   z=q.reindex(ds);ff=f.reindex(ds);c=cp.reindex(ds);price=pd.Series(True,index=ds)
   for name in ['open','high','low','close','raw_open','raw_high','raw_low','raw_close','adjustment_factor']:price&=np.isfinite(pd.to_numeric(z[name],errors='coerce'))&pd.to_numeric(z[name],errors='coerce').gt(0)
   for name in ['observed_bar','is_observed_bar','price_eligible']:price&=z[name].eq(True)
   for name in ['source_invalid','synthetic_event_bar']:price&=z[name].eq(False)
   price&=z.source_kind.notna()&z.source_path.notna()&z.segment_id.notna()&z.low.le(z.close)&z.close.le(z.high)
   for name in ['open','high','low','close']:price&=np.isclose(z[name],z['raw_'+name]*z.adjustment_factor,rtol=1e-12,atol=1e-8)
   present=ff.close.notna();match=pd.Series(np.isclose(z.close,pd.to_numeric(ff.close),rtol=1e-12,atol=1e-8)&np.isclose(z.adjustment_factor,pd.to_numeric(ff.factor),rtol=1e-12,atol=1e-10)&z.segment_id.eq(ff.segment_id)&np.isclose(z.raw_close,pd.to_numeric(ff.raw_close),rtol=1e-12,atol=1e-8),index=ds)
   price&=(~present)|match
   rows.append(dict(sid=sid,window=w,common_days=len(ds),raw_rows_on_common=int(ds.isin(q.index).sum()),price_valid_days=int(price.sum()),facts_rows_on_common=int(ds.isin(f.index).sum()),facts_ready=int(ff.e0_ready.eq(1).sum()),coordinate_mismatch_days=int((present&~match).sum()),cp_rows_on_common=int(ds.isin(cp.index).sum()),cp_ready_days=int(c.ready.eq(True).sum()),duplicate_raw_index=bool(q.index.has_duplicates)))
  validq=q[q.adjustment_factor.gt(0)].loc[:'2026-06-30'];prev=validq.shift(1);change=~np.isclose(validq.adjustment_factor,prev.adjustment_factor,rtol=1e-11,atol=0)&prev.adjustment_factor.notna()
  for d in validq.index[change & (validq.index>='2023-01-01')]:factorrows.append(dict(sid=sid,day=str(d.date()),factor_old=float(prev.loc[d,'adjustment_factor']),factor_new=float(validq.loc[d,'adjustment_factor']),same_lineage=all(validq.loc[d,c]==prev.loc[d,c] for c in ['source_kind','source_path','segment_id'])))
  ap=AS/(sid+'.json')
  if ap.exists():
   aa=json.loads(ap.read_text());sources[str(ap)]=sha(ap)
   for e in aa.get('events',[]):
    if '2023-01-01'<=e.get('effective_date','')<='2026-06-30':actionrows.append(dict(sid=sid,day=e['effective_date'],split_ratio=e.get('split_ratio'),cash_per_old_share=e.get('cash_per_old_share'),local_action_only_not_admitted=True))
 except Exception as e:errors.append(dict(sid=sid,error=repr(e)))
 if (n+1)%300==0:print('POOL',n+1,'seconds',round(time.monotonic()-start,2),flush=True)
df=pd.DataFrame(rows);df.to_csv(O/'FULL_POOL_COVERAGE.csv',index=False)
# Industry coverage is full-pool required source coverage, not only six fixture industries.
inds=[]
for m in im:
 sid=m['series'];p=next(p for p in m['source_sha256'] if '/industry-facts/' in p);f=pd.read_parquet(p);sources[p]=sha(p)
 if sources[p]!=m['source_sha256'][p]:hasherr.append(dict(sid=sid,path=p))
 for w,ds in days.items():
  z=f.reindex(ds);hv=hs[np.ix_(cal.isin(ds),[hids.index(sid)])].ravel() if sid in hids else np.full(len(ds),np.nan)
  inds.append(dict(sector=sid,window=w,common_days=len(ds),rows=int(ds.isin(f.index).sum()),e0_ready=int(z.e0_ready.eq(1).sum()),h1_finite=int(np.isfinite(hv).sum()),h1_missing=int((~np.isfinite(hv)).sum())))
pd.DataFrame(inds).to_csv(O/'INDUSTRY_COVERAGE.csv',index=False)
pvpath=R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet';sources[str(pvpath)]=sha(pvpath);pv=pd.read_parquet(pvpath);pvrows=[]
for w,(a,b) in wins.items():
 z=pv[pv.day.between(a,b)&pv.sid.isin(ids)].copy();z['known']=np.isfinite(z.score)&z.state.ge(0)&z.valid_observation.eq(True)
 pvrows.append(dict(window=w,expected=1709*len(days[w]),rows=len(z),known=int(z.known.sum()),missing_rows=1709*len(days[w])-len(z),unknown_rows=int((~z.known).sum()),sids=z.sid.nunique(),duplicates=int(z.duplicated(['sid','day']).sum())))
save('PVR_COVERAGE.json',pvrows)
# Native dated rules actually resolve each common date for all names. No execution and no cache retained.
sys.path.insert(0,str(B/'code'));from market_rules import version_on,market_identity_on
rules=json.loads((B/'inputs-v2/market-rules.json').read_text());proxies=json.loads((B/'inputs-v2/economic-protocol.json').read_text())['approved_proxy_ids'];rr=[]
for p in [B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py']:sources[str(p)]=sha(p)
for w,ds in days.items():
 fail=collections.Counter();examples=[];ok=0
 for sid in ids:
  for d in ds:
   try:
    ident=market_identity_on(rules,sid,str(d.date()),proxies);version_on(rules['fee_versions'][ident['venue']],str(d.date()),proxies);version_on(rules['quantity_versions'][sid],str(d.date()),proxies);assert float(rules['security_metadata'][sid]['par_value'])>0;ok+=1
   except Exception as e:
    fail[str(e)]+=1
    if len(examples)<15:examples.append(dict(sid=sid,day=str(d.date()),error=str(e)))
 rr.append(dict(window=w,passed=ok,total=1709*len(ds),failed=sum(fail.values()),reasons=dict(fail),examples=examples))
save('DATED_RULE_COVERAGE.json',rr)
# Admitted event sets are not blanket financial coverage. Count source-date matching only.
a22=pd.read_csv(E/'cash_dividend_source_feasibility_v1/EVENT_FACTS_WITH_DOCUMENTED_COMPOSITES.csv',dtype=str);a22=a22[a22.coverage_status.isin(['CURRENT_PUBLIC_FACTS_MATCHED_NOT_PIT_OR_TAX_CERTIFIED','PUBLIC_NOTICE_DOCUMENTED_COMPOSITE_NOT_PIT_OR_TAX_CERTIFIED'])]
b22=pd.read_csv(E/'cash_dividend_precision_24_v1/ADJUDICATED_24.csv',dtype=str)
c22=pd.read_csv(E/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv',dtype=str);c22=c22[c22.status.eq('FACTOR_AT_ENTRY_UNKNOWN')]
a24=json.loads((E/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json').read_text())
right22={(r.sid,r.status_day) for r in pd.concat([a22,b22]).itertuples()};coord22=right22|{(r.sid,r.status_day) for r in c22.itertuples()};right24={(r['sid'],r['ex_date']) for r in a24}
for row in factorrows:
 key=(row['sid'],row['day']);row.update(in_original_2022_coordinate_set=key in coord22,in_original_2022_entitlement_set=key in right22,in_original_2024_entitlement_set=key in right24,in_union_entitlement_set=key in right22|right24)
for row in actionrows:
 key=(row['sid'],row['day']);row.update(in_original_2022_entitlement_set=key in right22,in_original_2024_entitlement_set=key in right24,in_union_entitlement_set=key in right22|right24)
pd.DataFrame(factorrows).to_csv(O/'FACTOR_TRANSITION_COVERAGE.csv',index=False);pd.DataFrame(actionrows).to_csv(O/'LOCAL_ACTION_COVERAGE.csv',index=False)
ab=E/'SEALED_ALL_BIRTH_EVENTS.csv';sources[str(ab)]=sha(ab);ev=pd.read_csv(ab,parse_dates=['day']);absummary={w:dict(rows=int(ev.day.between(a,b).sum()),available_windows=ev.window.value_counts().to_dict()) for w,(a,b) in wins.items()}
summary=dict(result='COVERAGE_AUDIT_NOT_ECONOMIC_LABEL_CERTIFICATION',stock_count=len(sm),industry_count=len(im),common_days={w:len(ds) for w,ds in days.items()},pool=df.groupby('window').agg({c:'sum' for c in ['common_days','raw_rows_on_common','price_valid_days','facts_rows_on_common','facts_ready','coordinate_mismatch_days','cp_rows_on_common','cp_ready_days']}).to_dict('index'),zero_observation_sids={w:g[g.raw_rows_on_common.eq(0)].sid.tolist() for w,g in df.groupby('window')},industry=pd.DataFrame(inds).groupby('window').sum(numeric_only=True).to_dict('index'),pvr=pvrows,dated_rules=rr,ab=absummary,source_hash_mismatches=hasherr,errors=errors,rights_sets=dict(original2022_coordinates=len(coord22),original2022_entitlements=len(right22),original2024_entitlements=len(right24),union_for_count_only=len(right22|right24)),elapsed_seconds=time.monotonic()-start,peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20)
save('SOURCE_SHA256.json',sources);save('COVERAGE_QA.json',summary);print(json.dumps(summary,ensure_ascii=False,default=str),flush=True)
assert all(sha(p)==h for p,h in old.items()),'LEGACY_TREE_CHANGED';save('OLD_TREE_UNCHANGED.json',dict(files=len(old),unchanged=True))
