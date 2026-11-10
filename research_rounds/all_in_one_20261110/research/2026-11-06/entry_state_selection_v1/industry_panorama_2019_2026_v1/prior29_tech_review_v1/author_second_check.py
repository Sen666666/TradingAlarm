# Separate read/recompute check: does not import the review builder or its helpers.
import pathlib,json,hashlib
import pandas as pd,numpy as np
O=pathlib.Path(__file__).parent;P=O.parent;U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');B=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
C=pd.read_csv(O/'MANUAL_CYCLES.csv');L=pd.read_csv(O/'AUXILIARY_REVIEW_LEDGER.csv');R=pd.read_csv(O/'OLD_MANUAL_RECONCILIATION.csv');M=pd.read_csv(O/'MEMBER_RETURNS.csv');old=pd.read_csv(P/'MANUAL_RECORDS.csv');aux=pd.read_csv(P/'AUXILIARY_20PCT_WAVES.csv');sources=json.loads((O/'SOURCE_HASHES.json').read_text())
assert all(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h for p,h in sources.items())
assert len(L)==87 and L.aux_id.is_unique and set(L.aux_id)==set(aux[aux.sector.isin(C.sector)].record_id)
assert len(R)==34 and R.old_id.is_unique and set(R.old_id)==set(old[old.sector.isin(C.sector)].record_id)
assert len(C)==69 and C.record_id.is_unique and C.boundary_rationale.notna().all()
meta=json.loads((B/'inputs-v2/metadata.json').read_text());mapping=json.loads((B/'audit/industry-repair-v2/mapping.json').read_text());im=json.loads((U/'INDUSTRY_MANIFEST.json').read_text());sm=json.loads((U/'STOCK_MANIFEST.json').read_text());S={};I={}
for m in im+sm:
 sid=m.get('series',m.get('symbol'));sec=sid if 'series' in m else meta[sid]['sector_id']
 if sec not in set(C.sector):continue
 p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p)
 d=pd.read_parquet(p);valid=d['observed_bar'].eq(True)&d['price_eligible'].eq(True)&d['source_invalid'].eq(False)&d['synthetic_event_bar'].eq(False)&d['close'].gt(0)&np.isfinite(d['close']);v=d.loc[valid,'close'];assert v.index.is_unique
 (I if 'series' in m else S)[sid]=v
errors=[]
for _,r in C.iterrows():
 p=I[r.sector];q=p.loc[r.start:r.end];a=q.iloc[0];b=q.iloc[-1];ret=100*(b/a-1);dd=100*(q.to_numpy()/np.maximum.accumulate(q.to_numpy())-1).min();assert abs(ret-r.industry_return_pct)<1e-8 and abs(dd-r.mdd_pct)<1e-8
 rows=M[M.record_id==r.record_id];syms={s for s in S if meta[s]['sector_id']==r.sector};assert set(rows.symbol)==syms and rows.symbol.is_unique
 vals=[];fp=0
 for _,m in rows.iterrows():
  s=S[m.symbol];known=pd.Timestamp(r.start) in s.index and pd.Timestamp(r.end) in s.index;assert known==bool(m.known)
  full=known and all(t in s.index for t in q.index);assert full==bool(m.full_path);fp+=full
  if known:
   v=100*(s.loc[r.end]/s.loc[r.start]-1);assert abs(v-m.return_pct)<1e-8;vals.append(v)
  else:assert pd.isna(m.return_pct)
 vals=np.array(vals);assert len(vals)==r.K==r.known_members;assert len(syms)==r.P==r.research_pool_members;assert sum(vals>0)==r.n==r.positive_members;assert fp==r.full_path==r.full_path_members;assert r.P-r.K==r.unknown==r.unknown_members;assert sum(x['index']==r.sector for x in mapping)==r.F
 assert abs(np.median(vals)-r.member_median_pct)<1e-8;pos=np.sort(np.maximum(vals,0));assert abs(100*pos[-3:].sum()/pos.sum()-r.top3_positive_share_pct)<1e-8
 oo=old[(old.sector==r.sector)&(old.start<r.end)&(old.end>r.start)];assert set(str(r.old_overlap_ids).split(';'))-{'nan'}==set(oo.record_id);assert bool(r.is_genuinely_new_priority)==(r.priority_code=='K' and len(oo)==0)
 errors.append(dict(record_id=r.record_id,industry_return_error=abs(ret-r.industry_return_pct),mdd_error=abs(dd-r.mdd_pct),independent_n=int(sum(vals>0)),independent_K=len(vals),independent_full_path=int(fp)))
assert C.is_genuinely_new_priority.sum()==10
for sec,d in C.groupby('sector'):
 d=d.sort_values('start');assert all(a<=b for a,b in zip(d.end.iloc[:-1],d.start.iloc[1:]))
# Source independently confirms two subtle old-boundary corrections.
p=I['URFI881125'];car_old_end_vs_true_peak=100*(p.loc['2021-12-13']/p.loc['2021-09-07']-1)
p=I['URFI881272'];software_july_vs_feb=100*(p.loc['2020-07-13']/p.loc['2020-02-25']-1)
result=dict(status='AUTHOR_SECOND_IMPLEMENTATION_CHECK_PASSED',reviewer_role='same author, separate computation implementation; not an independent reviewer',cycles_checked=len(C),member_rows_checked=len(M),original_sources_checked=len(sources),aux_unique_reconciled=len(L),old_manual_reconciled=len(R),genuinely_new_priority=10,member_and_industry_endpoints_recomputed=True,n_K_P_F_full_path_unknown_checked=True,old_overlap_classification_checked=True,no_intra_industry_positive_time_overlap=True,canonical_start_not_true_low=['TC019'],car_old_2021_12_end_vs_2021_09_peak_pct=car_old_end_vs_true_peak,software_2020_07_vs_2020_02_peak_pct=software_july_vs_feb,limitation='Numerical and accounting check only; not independent validation of subjective manual grades, historical PIT membership, strategy execution, or completeness below auxiliary threshold.')
pd.DataFrame(errors).to_csv(O/'AUTHOR_SECOND_PASS_DETAIL.csv',index=False);(O/'AUTHOR_SECOND_PASS_QA.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
seal={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.iterdir()) if p.is_file() and p.name!='OUTPUT_HASHES.json'};(O/'OUTPUT_HASHES.json').write_text(json.dumps(seal,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
