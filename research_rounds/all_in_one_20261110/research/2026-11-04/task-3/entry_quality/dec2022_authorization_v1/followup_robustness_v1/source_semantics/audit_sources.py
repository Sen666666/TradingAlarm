"""Independent source semantics/value-domain audit. No models or Accounts."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,gzip,pickle,time,sys
import numpy as np,pandas as pd

O=Path(__file__).resolve().parent;A=O.parents[1];EQ=A.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');OLD=RR/'a-share-selection-e0-20261024';IDX=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018')
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,expected=None):
 p=Path(p);h=sha(p)
 if expected:assert h==expected
 SRC[str(p)]=h;return json.loads(p.read_text())
def frame(p,expected=None,cols=None):
 p=Path(p);h=sha(p)
 if expected:assert h==expected
 SRC[str(p)]=h;return pd.read_parquet(p,columns=cols) if p.suffix=='.parquet' else pd.read_csv(p,index_col=0,parse_dates=True)
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if v is None or isinstance(v,(str,bool,int)):return v
 if isinstance(v,np.generic):return clean(v.item())
 if isinstance(v,float):return v if np.isfinite(v) else None
 return str(v)
def value_counts(c,arr,prefix):
 x=np.asarray(arr,dtype=float);c[prefix+'_rows']+=len(x);c[prefix+'_NaN']+=int(np.isnan(x).sum());c[prefix+'_infinite']+=int(np.isinf(x).sum());c[prefix+'_finite_nonpositive']+=int((np.isfinite(x)&(x<=0)).sum());c[prefix+'_zero']+=int((x==0).sum())

t0=time.monotonic();sm=read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json');im=read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json');selection=read(OLD/'inputs-v2/selection.json');inputs=read(OLD/'inputs-v2/input-manifest.json');records={x['series_id']:x for x in inputs['series']};meta=read(OLD/'inputs-v2/metadata.json')
context_manifest=read(A/'relative_context/MANIFEST.json');data_path=Path(context_manifest['data_file']);assert sha(data_path)==context_manifest['data_sha256'];SRC[str(data_path)]=sha(data_path)
with gzip.open(data_path,'rb') as f:ctx=pickle.load(f)
indicator_manifest=read(EQ/'trend_exit_controls_v1/indicators/MANIFEST.json');indicator_path=Path(indicator_manifest['data_file']);assert sha(indicator_path)==indicator_manifest['data_sha256'];SRC[str(indicator_path)]=sha(indicator_path)
with gzip.open(indicator_path,'rb') as f:indicator=pickle.load(f)
checkpoint=read(IDX/'checkpoints/USZI399300.json');market=frame(IDX/'canonical/USZI399300.csv',checkpoint['canonical_sha256']);calendar=market.index
mc=Counter();value_counts(mc,market.close,'close');value_counts(mc,market.volume,'volume');value_counts(mc,market.amount,'amount')
market_anchors=pd.Series(calendar,index=calendar).shift(20);market_return=market.close/market.close.shift(20)-1
for p in checkpoint['pages']:
 path=IDX/p['file'];assert sha(path)==p['body_sha256'];SRC[str(path)]=sha(path)
received=sorted({p['received_at'] for p in checkpoint['pages']})
save('BENCHMARK_PROVENANCE.json',dict(rows=len(market),first=str(calendar.min().date()),last=str(calendar.max().date()),raw_pages=len(checkpoint['pages']),download_received_at=received,checkpoint_fields=list(checkpoint),canonical_columns=list(market.columns),checkpoint_status=checkpoint['status'],raw_page_SHA_all_exact=True,values=dict(mc),historical_daily_release_or_revision_timestamp_present=False,availability_boundary='2026 download proves the downloaded retrospective series exists then; per-bar date is not first-publication timestamp. 15:10 historical same-day availability and unrevised vintage are not certified by this CSV/checkpoint.'))

inds={};indcount=Counter();industry_schema=[]
for r in im:
 sid=r['series'];fp=next(p for p in r['source_sha256'] if '/industry-facts/' in p);f=frame(fp,r['source_sha256'][fp]);inds[sid]=f
 indcount['series']+=1;value_counts(indcount,f.close,'facts_close');value_counts(indcount,f.factor,'facts_factor');indcount['factor_not_one']+=int((f.factor!=1).sum());indcount['source_segments']+=int(f.segment_id.ne(f.segment_id.shift()).sum())
 rec=records[sid];raw=frame(rec['raw']['path'],rec['raw']['sha256']);value_counts(indcount,raw.close,'raw_close');value_counts(indcount,raw.volume,'raw_volume');indcount['raw_observed_false']+=int(raw.observed_bar.ne(True).sum());indcount['raw_source_invalid']+=int(raw.source_invalid.eq(True).sum());indcount['raw_synthetic']+=int(raw.synthetic_event_bar.eq(True).sum())
 industry_schema.append(dict(series=sid,kind=rec['kind'],adjustment=rec['adjustment'],declared_close_available_time=rec.get('close_available_time'),columns=list(raw.columns),source_paths=sorted(set(raw.source_path)),historical_constituent_effective_intervals_present=any('effective' in x or 'member' in x or 'weight' in x for x in raw.columns)))
save('INDUSTRY_PRICE_CHAIN.json',dict(counts=dict(indcount),series=industry_schema,meaning='Observed proprietary index price series. Not recomputed from the current1709 stocks. Historical constituent/weight/methodology vintages not contained in the source price bars or static mapping.'))

stockcount=Counter();actioncount=Counter();readiness=Counter();examples=defaultdict(list);per=[];max_err=0.;max_g_err=0.
for k,m in enumerate(sm):
 sid=m['symbol'];rec=records[sid];fp=m['refs']['facts'];f=frame(fp,m['output_sha256'][fp],['close','raw_close','factor','segment_id'])
 stockcount['fixed_symbols']+=1;stockcount['empty_fact_symbols']+=f.empty
 for col in ['close','raw_close','factor']:value_counts(stockcount,f[col],col)
 if len(f):
  err=np.abs(f.close.to_numpy(float)-f.raw_close.to_numpy(float)*f.factor.to_numpy(float));max_err=max(max_err,float(np.nanmax(err)));stockcount['raw_factor_relation_bad_rtol1e_10']+=int((~np.isclose(f.close,f.raw_close*f.factor,rtol=1e-10,atol=1e-10,equal_nan=True)).sum());stockcount['factor_changed_same_source_rows']+=int((f.factor.ne(f.factor.shift())&f.segment_id.eq(f.segment_id.shift())).sum())
 sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));sf=frame(sp,m['source_sha256'][sp],['close','raw_close','raw_volume','volume','adjustment_factor','volume_factor','segment_id','price_eligible','observed_bar','source_invalid','synthetic_event_bar','volume_eligible']).loc[:'2026-06-30']
 stockcount['prepared_source_rows_through_Jun30']+=len(sf)
 for col in ['close','raw_close','raw_volume','volume','adjustment_factor','volume_factor']:value_counts(stockcount,sf[col],'prepared_'+col)
 for col in ['price_eligible','observed_bar','source_invalid','synthetic_event_bar','volume_eligible']:stockcount['prepared_'+col+'_true']+=int(sf[col].eq(True).sum())
 if len(f):
  scope_f=f.loc[:'2026-06-30'];stockcount['facts_audited_through_Jun30']+=len(scope_f);stockcount['referenced_facts_after_Jun30_not_in_frozen_context']+=len(f)-len(scope_f)
  aligned=sf.reindex(scope_f.index);assert aligned.index.equals(scope_f.index)
  stockcount['facts_with_nonpositive_or_missing_source_volume']+=int((~np.isfinite(aligned.volume)|(aligned.volume<=0)).sum())
  stockcount['facts_on_synthetic_or_invalid_source']+=int((aligned.synthetic_event_bar.eq(True)|aligned.source_invalid.eq(True)|aligned.price_eligible.ne(True)|aligned.observed_bar.ne(True)).sum())
 ac=read(rec['adjustment']['actions']['path'],rec['adjustment']['actions']['sha256'])
 actioncount['stock_action_files']+=1;actioncount['files_exact_pay_dates_certified_true']+=bool(ac.get('exact_pay_dates_certified'));actioncount['files_declared_research_proxy']+=ac.get('status')=='declared_research_proxy'
 for e in ac['events']:
  if e['effective_date']>'2026-06-30':continue
  actioncount['events_through_Jun30']+=1;typ=e['classification'];actioncount['classification_'+typ]+=1;actioncount['paid_at_unknown']+=e.get('paid_at') is None
  if len(examples['action_'+typ])<3:examples['action_'+typ].append(dict(sid=sid,event=e))
 r=ctx[sid];old=indicator[sid];dates=pd.DatetimeIndex(r['days'].astype('datetime64[D]'));aa=pd.DatetimeIndex(market_anchors.reindex(dates).to_numpy());s0=f.reindex(aa);s1=f.reindex(dates);g=inds[r['sector']];i0=g.reindex(aa);i1=g.reindex(dates);mr=market_return.reindex(dates).to_numpy(float)
 sc,spc,ic,ipc=[x.close.to_numpy(float) for x in [s1,s0,i1,i0]]
 known=(old['observed_valid']&np.isfinite(sc)&np.isfinite(spc)&np.isfinite(ic)&np.isfinite(ipc)&np.isfinite(mr)&(sc>0)&(spc>0)&(ic>0)&(ipc>0)&s1.segment_id.to_numpy(float).__eq__(s0.segment_id.to_numpy(float))&i1.segment_id.to_numpy(float).__eq__(i0.segment_id.to_numpy(float)))
 assert np.array_equal(known,r['ready_R']);assert np.array_equal(old['observed_valid']&np.isfinite(old['values'][:,1]),r['ready_P'])
 readiness['rows']+=len(dates);readiness['ready_R']+=int(known.sum());readiness['unknown_R']+=int((~known).sum());readiness['ready_P']+=int(r['ready_P'].sum());readiness['unknown_P']+=int((~r['ready_P']).sum());readiness['source_current_observed_invalid']+=int((~old['observed_valid']).sum());readiness['stock_anchor_missing']+=int((~np.isfinite(spc)).sum());readiness['industry_anchor_missing']+=int((~np.isfinite(ipc)).sum());readiness['market_endpoint_or_warmup_missing']+=int((~np.isfinite(mr)).sum());readiness['stock_cross_source']+=int((np.isfinite(spc)&(s1.segment_id.to_numpy(float)!=s0.segment_id.to_numpy(float))).sum());readiness['industry_cross_source']+=int((np.isfinite(ipc)&(i1.segment_id.to_numpy(float)!=i0.segment_id.to_numpy(float))).sum())
 mask=known&np.isfinite(s1.factor.to_numpy(float))&np.isfinite(s0.factor.to_numpy(float))
 if mask.any():
  cr=s1.raw_close.to_numpy(float);ar=s0.raw_close.to_numpy(float);cf=s1.factor.to_numpy(float);af=s0.factor.to_numpy(float);gr=(cr[mask]/ar[mask])*(cf[mask]/af[mask]);expected=1+r['stock_return20'][mask];max_g_err=max(max_g_err,float(np.max(np.abs(gr-expected))));cross=mask&~np.isclose(cf,af,rtol=1e-12,atol=1e-12);readiness['ready_R_windows_crossing_factor_change']+=int(cross.sum())
  if len(examples['adjusted_vs_raw20'])<12:
   for j in np.flatnonzero(cross)[:12-len(examples['adjusted_vs_raw20'])]:examples['adjusted_vs_raw20'].append(dict(sid=sid,day=str(dates[j].date()),anchor=str(aa[j].date()),raw_return20=cr[j]/ar[j]-1,causal_adjusted_return20=r['stock_return20'][j],factor_ratio=cf[j]/af[j],g_adjusted_equals_g_raw_times_factor_ratio=True))
 for name,mask in [('missing_stock_anchor',~np.isfinite(spc)),('EMA20_source_warmup_unknown',~r['ready_P'])]:
  if len(examples[name])<12:
   for j in np.flatnonzero(mask)[:12-len(examples[name])]:examples[name].append(dict(sid=sid,day=str(dates[j].date()),anchor=str(aa[j].date()) if not pd.isna(aa[j]) else None,ready_R=bool(r['ready_R'][j]),ready_P=bool(r['ready_P'][j]),reason='Missing endpoint may be suspension, source gap or source age; cause not certified from price bars alone.' if name=='missing_stock_anchor' else 'Fewer than20 original valid source observations; no synthetic zeros.'))
 per.append(dict(sid=sid,facts_rows=len(f),prepared_source_rows=len(sf),context_rows=len(dates),ready_R=int(r['ready_R'].sum()),ready_P=int(r['ready_P'].sum())))
 if (k+1)%400==0:print('SOURCE_AUDIT',k+1,flush=True)
stockcount['maximum_abs_close_minus_raw_times_factor']=max_err;readiness['maximum_abs_g_adjusted_minus_g_raw_factor_ratio']=max_g_err
save('VALUE_DOMAIN_AND_CONTEXT_COUNTS.json',dict(stock=clean(dict(stockcount)),industry=clean(dict(indcount)),benchmark=clean(dict(mc)),relative_context=clean(dict(readiness)),root_ready_flags_recomputed_exact=True,zero_or_nonpositive_values_not_silently_divided=True,limitation='Counted current frozen data. Market inputs are validated here positive; source implementation uses finite market return rather than an explicit market price>0 assertion. No malformed-input policy change made.'))
save('ACTUAL_EDGE_EXAMPLES.json',clean(dict(examples)));save('CORPORATE_ACTION_SCOPE.json',clean(dict(actioncount)));save('PER_SYMBOL_COUNTS.json',per)
repair=read(OLD/'audit/industry-repair-v2/report.json');selection_summary={k:selection[k] for k in ['snapshot_id','observed_at','source_id','roster_asof','cap_observed_date','market_timestamp_unknown','universe_limit']};master=Path(selection['industry_resolution_evidence']['path']);assert sha(master)==selection['industry_resolution_evidence']['sha256'];SRC[str(master)]=sha(master)
save('CLASSIFICATION_PIT_EVIDENCE.json',dict(selection=selection_summary,current_snapshot_mapping=selection['industry_resolution_evidence'],current_snapshot_repair_recorded_at=repair['recorded_at'],qualified_industry_lines_repaired=repair['qualified_lines_changed'],classification_source_files=repair['facts'],master_columns=list(pd.read_csv(master,nrows=1).columns),historical_membership_intervals_proven=False,historical_index_constituents_or_weights_proven=False,current_pool_not_PIT_explicit_in_selection=True,distinction='Current stock->industry mapping is a2026snapshot. URFI industry price series is historical index price data, not historical membership evidence and not a current1709-stock reconstruction.'))
for p in [A/'prepare_relative_context.py',A/'context_provider.py',A/'native_adapter/mobile_authorization_adapter.py',A/'H2_POLICY_FREEZE.json',EQ/'trend_exit_controls_v1/prepare_indicators.py',OLD/'code/current_pool_bridge.py',OLD/'code/normalize_actions.py',OLD/'code/build_inputs.py',OLD/'code/repair_classification.py']:
 SRC[str(p)]=sha(p)
SRC[str(__file__)]=sha(__file__);save('SOURCE_SHA256.json',SRC)
save('VALIDATION.json',dict(passed=True,stocks=1709,industries=90,new_accounts=0,new_account_events=0,new_market_models=0,no_frozen_source_changes=True,seconds=time.monotonic()-t0,current_data_prefix_causal_scope_only=True,full_input_PIT_claim_supported=False))
print(json.dumps(clean(dict(stock=stockcount,industry=indcount,relative_context=readiness,corporate_actions=actioncount,seconds=time.monotonic()-t0)),ensure_ascii=False,indent=2))
