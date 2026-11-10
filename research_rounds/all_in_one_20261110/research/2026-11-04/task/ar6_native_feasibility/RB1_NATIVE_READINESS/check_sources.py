"""Read-only evidence inventory and actual-layer input coverage; no Account/Runner imports."""
from pathlib import Path
import json,hashlib,csv,collections,time
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent
T=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
U=W/'universe-cp1-inputs-20261031'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2))
books={'2022_2024':T/'risk_constraints/continuation2024_finance/analysis/2022_2024/PVR_NO_CONFIRMED60/LAYERS.json','strong':T/'loss_correction/pvr_no60_2025_26/analysis/2025_26/PVR_NO60/LAYERS.json'}
ends={'2022_2024':'2024-12-31','strong':'2026-06-30'}
sources=[Path(__file__),U/'STOCK_MANIFEST.json',U/'prepare.py',W/'native-I-cache-interface-20261031/cache.py',W/'rearm-risk-boundary-design-20261030/risk_boundary_v2.py',W/'full-account-risk-reentry-20261030/wire.py',W/'full-account-risk-reentry-20261030/SUMMARY_12.csv',W/'full-account-risk-reentry-20261030/FINAL_REPORT.txt',W/'full-account-risk-reentry-20261030/COMPLETION.json',W/'rb1-act-finite-20261031/adapter.py',W/'rb1-act-finite-20261031/MATRIX_12.csv',W/'rb1-act-history-pressure-2019-2023-20261031/adapter.py',W/'rb1-act-history-pressure-2019-2023-20261031/MATRIX_12.csv',W/'case-stage-ledger-20261031/v3/joint_v3.py',*books.values()]
save('PROTOCOL_AND_SOURCE_FREEZE.json',dict(scope='read-only original evidence + existing input availability for actual layers, no new policy calculation or account',windows=ends,sources={str(p):sha(p) for p in sources}))
start=time.monotonic();manifest=read(U/'STOCK_MANIFEST.json');by={x['symbol']:x for x in manifest};bb={k:read(p) for k,p in books.items()};ids=sorted({r['sid'] for b in bb.values() for r in b});sources_map={};cache={};checks=[]
for sid in ids:
 r=by[sid];ps=r['source_sha256'];ep=next(p for p in ps if p.endswith('/events.parquet'));sp=next(p for p in ps if p.endswith('/signal.parquet'));fp=r['refs']['facts'];qp=r['refs']['CP1_input']
 for p,h in [(ep,ps[ep]),(sp,ps[sp]),(fp,r['output_sha256'][fp]),(qp,r['output_sha256'][qp])]:
  actual=sha(p);assert actual==h,(sid,p,'source hash changed');sources_map[p]=actual
 f=pd.read_parquet(fp).loc[:'2026-06-30'];q=pd.read_parquet(qp).loc[:'2026-06-30'];e=pd.read_parquet(ep,columns=['event','segment_id','confirmed_pivot_date']);s=pd.read_parquet(sp,columns=['close','volume','observed_bar','source_invalid','synthetic_event_bar','segment_id'])
 assert f.index.is_unique and q.index.equals(f.index)
 for c in ['close','segment_id','i_target','i_floor']:pd.testing.assert_series_equal(f[c],q[c],check_exact=True,check_dtype=False,check_freq=False)
 z=e.reindex(f.index);ss=s.reindex(f.index)
 known=z.event.notna();assert z.loc[known,'segment_id'].eq(f.loc[known,'segment_id']).all()
 assert q.e0_down.equals(z.event.eq(-1)),(sid,'CP1 negative-event same original source')
 valid=f.close.gt(0)&np.isfinite(f.close)&ss.volume.gt(0)&np.isfinite(ss.volume)
 prior={}
 for seg,g in f[valid].groupby('segment_id',sort=False):prior[int(seg)]=g.index
 cache[sid]=(f,z,ss,prior)
 checks.append(dict(sid=sid,source_event_path=ep,event_sha256=ps[ep],facts_path=fp,CP1_input_path=qp,negative_event_same_source_exact=True))
summary={};details=[]
for window,b in bb.items():
 agg=collections.Counter();role=collections.Counter()
 for x in b:
  sid=x['sid'];f,e,s,prior=cache[sid];begin=x['opened'][:10];end=x['closed'][:10] if x['closed'] else ends[window]
  # A layer sold at OPEN is absent from that day's CLOSE; endpoint open layers remain valued.
  m=(f.index>=begin)&(f.index<end if x['closed'] else f.index<=end);ff=f[m];ee=e[m];ss=s[m]
  known=ee.event.notna();observed=ss.observed_bar.fillna(False).astype(bool)&~ss.source_invalid.fillna(True).astype(bool)&~ss.synthetic_event_bar.fillna(True).astype(bool)
  units=(ff.raw_close.gt(0)&ff.factor.gt(0)&np.isfinite(ff.raw_close)&np.isfinite(ff.factor));unit_exact=np.isclose((ff.raw_close*ff.factor)[units],ff.close[units],rtol=64*np.finfo(float).eps,atol=0).all()
  negative=ee.index[ee.event.eq(-1)];warm=sum(prior[int(ff.loc[d,'segment_id'])].searchsorted(d)>=64 for d in negative)
  pivot_unknown=sum(pd.isna(ee.loc[d,'confirmed_pivot_date']) for d in negative);pivot_ok=sum(not pd.isna(ee.loc[d,'confirmed_pivot_date']) and pd.Timestamp(ee.loc[d,'confirmed_pivot_date'])<=d for d in negative)
  row=dict(window=window,layer=x['layer'],sid=sid,role=x['role'],pool_at_fill=x['pool_at_fill'],open=begin,end=end,held_fact_rows=len(ff),missing_event_rows=int((~known).sum()),observed_price_rows=int(observed.sum()),unknown_price_factor_rows=int((~units).sum()),causal_units_exact=bool(unit_exact),native_negative_events=len(negative),negative_with_64_prior_valid_prices=int(warm),negative_with_nonfuture_pivot=int(pivot_ok),negative_pivot_unknown=int(pivot_unknown),negative_with_I_floor_known=int(ff.loc[negative,'i_floor'].notna().sum()))
  details.append(row);role[x['role']]+=1
  for k in ['held_fact_rows','missing_event_rows','observed_price_rows','unknown_price_factor_rows','native_negative_events','negative_with_64_prior_valid_prices','negative_with_nonfuture_pivot','negative_pivot_unknown','negative_with_I_floor_known']:agg[k]+=row[k]
  agg['layers_with_negative_event']+=len(negative)>0;agg['layer_unit_failures']+=not unit_exact
 summary[window]=dict(layers=len(b),unique_stocks=len({x['sid']for x in b}),roles=dict(role),**dict(agg))
save('ACTUAL_LAYER_INPUT_COVERAGE.json',dict(passed=not any(x['missing_event_rows']or x['layer_unit_failures'] for x in summary.values()),scope='Input availability only; overlapping layers count the same event repeatedly. No boundary, controller, fills, profit or counterfactual computed. Original OPEN-close responsibility range, existing fact rows; not a full exchange-calendar completeness certificate.',summaries=summary,unique_stocks=len(ids),source_files_checked=len(sources_map),seconds=time.monotonic()-start,unknown_never_zero=True,new_account_events=0))
save('ACTUAL_LAYER_INPUT_DETAILS.json',details);save('STOCK_INPUT_BINDINGS.json',checks);save('ACTUAL_SOURCE_SHA256.json',sources_map)
with (W/'full-account-risk-reentry-20261030/SUMMARY_12.csv').open()as f:table=list(csv.DictReader(f))
save('FROZEN_BOUNDARY_12_CELLS.json',[{k:r[k]for k in ['sector','scenario','policy_label','final_nav','net_return','max_drawdown','mean_exposure','fees','closed','tail_profit','all_closed_losses','risk_requests','safe_handoffs','risk_exit_same_structure_actual_reentries','delta_net_cny']}for r in table])
print(json.dumps(read(O/'ACTUAL_LAYER_INPUT_COVERAGE.json'),ensure_ascii=False,indent=2))
