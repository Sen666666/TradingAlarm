"""Exact saved-source preparation only; no indicator, candidate or account run."""
from pathlib import Path
import hashlib,json,math
import pandas as pd

O=Path(__file__).resolve().parent
Q=O.parents[1]
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
FIXED=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4/trend_hold_v1/ALL25_PROFIT_PROGRESS_SCALE.json')
CONTEXT=Q/'structural_failure_v1/scale_concentration/results_v3/strong_ALL_LAYER_SCALE_CONTEXT.json'
COHORT=Q/'dec2022_authorization_v1/followup_robustness_v1/performance/SEMICONDUCTOR_COHORT_FREEZE.json'
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 SRC[str(p)]=sha(p)
 return json.loads(Path(p).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,pd.Timestamp):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

fixed=read(FIXED);context=read(CONTEXT);cohort=read(COHORT)
rows=[r for r in context if r['industry']=='半导体' and '2026-01-01'<=r['opened'][:10]<='2026-06-30']
assert len(rows)==25 and len({r['sid'] for r in rows})==18
assert {r['layer'] for r in rows}=={r['layer'] for r in fixed}
fixed_by={r['layer']:r for r in fixed}
fields=['layer','sid','name','role','decision_at','opened','closed','stock_structure','receipt','actual_entry_action']
frozen=[{k:r[k] for k in fields} for r in rows]
save('FIXED25_COHORT.json',dict(definition='Existing fixed task4 cohort: actual fills in 2026H1; industry==半导体 from frozen metadata. No PnL or R filter.',source_semiconductor_population=126,classification_limit=cohort['assignment_limit'],layers=frozen))
pd.DataFrame(frozen).to_csv(O/'FIXED25_COHORT.csv',index=False)
save('ORIGINAL_OUTCOME_ANNOTATIONS_ONLY.json',[dict(layer=r['layer'],sid=r['sid'],role=r['role'],original_lifecycle_net=r['original_lifecycle_net'],initial_nominal_price_floor_R=r['initial_nominal_price_floor_R'],maximum_quoted_close_advance_R=r['maximum_quoted_close_advance_R'],quoted_advance_at_least_1R=r['quoted_advance_at_least_1R'],scope='Saved original path annotation only; never a candidate input, avoided loss, or new account return.') for r in fixed])
manifest={r['symbol']:r for r in read(MANIFEST)};idx=[];signals=[]
for sid in sorted({r['sid'] for r in rows}):
 m=manifest[sid];paths={k:Path(m['refs'][k]) for k in ['CP1','CP1_input','facts']}
 fs={}
 for k,p in paths.items():
  actual=sha(p);assert actual==m['output_sha256'][str(p)],(sid,k,'source hash')
  SRC[str(p)]=actual;fs[k]=pd.read_parquet(p).loc[:'2026-06-30']
 cp,inp,facts=fs['CP1'],fs['CP1_input'],fs['facts']
 assert cp.index.is_unique and cp.index.is_monotonic_increasing and cp.index.equals(inp.index)
 assert cp['e0_valid'].equals(inp['e0_valid'])
 joined=cp.copy()
 joined=joined.join(inp[['close','amount','segment_id','e0_valid','e0_down','i_floor']].add_prefix('input__'))
 joined=joined.join(facts[['raw_close','factor','i_target','i_buy','g_grade','g_ready','e0_target']].add_prefix('native__'))
 out=O/(sid.replace('.','_')+'_ORIGINAL_CP_INPUTS.parquet');joined.to_parquet(out,index=True)
 this=[r for r in rows if r['sid']==sid]
 for r in this:
  day=r['decision_at'][:10];t=pd.Timestamp(day);assert t in joined.index
  z=joined.loc[t]
  if r['role']=='mobile':assert bool(z['receipt']) and r['receipt']
  signals.append(dict(layer=r['layer'],sid=sid,name=r['name'],role=r['role'],decision_at=r['decision_at'],original_CP_id=r['receipt'],original_opened=r['opened'],source_original_CP_row=z.to_dict(),annotation_scope='Decision-close market facts only; original fill identity, no new quantity or return.'))
 idx.append(dict(sid=sid,name=this[0]['name'],layers=[r['layer'] for r in this],source_paths={k:str(p) for k,p in paths.items()},source_sha256={str(p):SRC[str(p)] for p in paths.values()},prepared_path=str(out.resolve()),prepared_sha256=sha(out),full_source_first_day=str(joined.index[0].date()),full_source_last_day=str(joined.index[-1].date()),full_source_rows=len(joined),window_2026H1_rows=len(joined.loc['2026-01-01':'2026-06-30']),window_2026H1_raw_CP_receipts=int(joined.loc['2026-01-01':'2026-06-30','receipt'].sum()),original_funded_signal_count=len(this)))
save('INPUT_INDEX.json',idx);save('ORIGINAL25_SIGNAL_ROWS.json',signals)
save('PREPARATION_RECEIPT.json',dict(status='PASS_EXACT_ORIGINAL_PREPARATION_ONLY',stocks=len(idx),fixed_layers=len(rows),core_layers=sum(r['role']=='core' for r in rows),mobile_layers=sum(r['role']=='mobile' for r in rows),source_rows=sum(r['full_source_rows'] for r in idx),raw_CP_receipts_2026H1=sum(r['window_2026H1_raw_CP_receipts'] for r in idx),source_sha256=SRC,script_sha256=sha(__file__),candidate_runs=0,new_CP_runs=0,new_E0_runs=0,new_accounts=0,new_quantities=0,new_returns=0))
print(json.dumps(dict(stocks=len(idx),layers=len(rows),source_rows=sum(r['full_source_rows'] for r in idx),raw_CP_receipts_2026H1=sum(r['window_2026H1_raw_CP_receipts'] for r in idx),candidate_runs=0)))
