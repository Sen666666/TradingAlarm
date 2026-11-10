"""Frozen signal balance over fixed semiconductor saved CP facts. No Account."""
from pathlib import Path
import csv,hashlib,importlib.util,json,math
import pandas as pd

O=Path(__file__).resolve().parent;P=O.parent;Q=P.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,pd.Timestamp):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def enc(x):return json.dumps(clean(x),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

spec=importlib.util.spec_from_file_location('frozen_cp_effective_balance',P/'balance.py');B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
index=json.loads((O/'INPUT_INDEX.json').read_text());fixed=json.loads((O/'FIXED25_COHORT.json').read_text())['layers']
outcomes={r['layer']:r for r in json.loads((O/'ORIGINAL_OUTCOME_ANNOTATIONS_ONLY.json').read_text())}
sources={str(P/'balance.py'):sha(P/'balance.py'),str(P/'FREEZE.md'):sha(P/'FREEZE.md'),str(O/'INPUT_INDEX.json'):sha(O/'INPUT_INDEX.json'),str(O/'FIXED25_COHORT.json'):sha(O/'FIXED25_COHORT.json')}
daily=[];raw=[];signals=[];counts=[];prefix=None;full_results={}
for r in index:
 sid=r['sid'];cp_path=Path(r['source_paths']['CP1']);inp_path=Path(r['source_paths']['CP1_input'])
 for p in [cp_path,inp_path]:assert sha(p)==r['source_sha256'][str(p)];sources[str(p)]=sha(p)
 cp=pd.read_parquet(cp_path).loc[:'2026-06-30'];inp=pd.read_parquet(inp_path).loc[:'2026-06-30']
 z=B.calculate(cp,inp);full_results[sid]=(cp,inp,z)
 display=z.loc['2026-01-01':'2026-06-30'].copy()
 fields=['ready','r','m','delta_frontier','scale','receipt','reset_reason','candidate','anchor','frontier','credit','displacement','s','z','B','u','v','e0_valid']
 display=display.join(cp[fields].add_prefix('original__')).join(inp[['close','amount','segment_id','e0_down','e0_valid']].add_prefix('input__'))
 display.insert(0,'sid',sid)
 records=[]
 for day,row in display.iterrows():
  rec=dict(day=str(day.date()),**row.to_dict());records.append(rec);daily.append(rec)
  if bool(row['original__receipt']):raw.append(rec)
 display.to_parquet(O/(sid.replace('.','_')+'_BALANCE_2026H1.parquet'),index=True)
 counts.append(dict(sid=sid,name=r['name'],display_rows=len(display),raw_CP=int(display['original__receipt'].sum()),effective_CP=int(display['effective_advance'].sum()),rejected_CP=int((display['original__receipt']&~display['effective_advance']).sum())))
 for f in [x for x in fixed if x['sid']==sid]:
  day=f['decision_at'][:10];t=pd.Timestamp(day);c=cp.loc[t];b=z.loc[t];q=inp.loc[t]
  signals.append(dict(layer=f['layer'],sid=sid,name=f['name'],role=f['role'],decision_at=f['decision_at'],opened=f['opened'],original_receipt_id=f['receipt'],close_adjusted=q['close'],original_CP_receipt=bool(c.receipt),original_CP_candidate=c.candidate,original_used_scale=c.scale,original_r=c.r,original_m=c.m,original_delta_frontier=c.delta_frontier,original_reset_reason=c.reset_reason,**b.to_dict(),gate_scope='CONTINUOUS_MATURE_ADD_ONLY; CORE and first-UP probe not deleted by this gate',original_static_annotation_only=outcomes[f['layer']] ))
 if sid=='603061.SH':
  cut=pd.Timestamp('2026-01-30');short=B.calculate(cp.loc[:cut],inp.loc[:cut]);pd.testing.assert_frame_equal(short,z.loc[:cut],check_exact=True)
  prefix=dict(sid=sid,cutoff=str(cut.date()),full_rows=len(z),short_rows=len(short),physical_input_cut=True,exact=True)
save('ALL_2026H1_DAILY_BALANCES.json',daily);save('ALL238_RAW_CP_EVENTS.json',raw);save('FIXED25_SIGNAL_BALANCES.json',signals);save('PER_STOCK_COUNTS.json',counts);save('PREFIX_CHECK.json',prefix)
with (O/'ALL238_RAW_CP_EVENTS.csv').open('w') as f:
 rows=[{k:(enc(v) if isinstance(v,(dict,list)) else v) for k,v in clean(r).items()} for r in raw];w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with (O/'FIXED25_SIGNAL_BALANCES.csv').open('w') as f:
 rows=[{k:(enc(v) if isinstance(v,(dict,list)) else v) for k,v in clean(r).items()} for r in signals];w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

# Original buy/close annotations only: no decision threshold may read outcomes.
mobile=[r for r in signals if r['role']=='mobile'];rejected=[r for r in mobile if not r['effective_advance']]
summary=dict(status='FIXED_FROZEN_SIGNAL_ONLY_COMPLETE',stocks=len(index),fixed_layers=len(signals),fixed_CORE_layers=sum(r['role']=='core' for r in signals),fixed_MOBILE_layers=len(mobile),full_source_rows=sum(r['full_source_rows'] for r in index),display_rows=len(daily),raw_CP_events=len(raw),effective_CP_events=sum(r['effective_advance'] for r in raw),rejected_CP_events=sum(not r['effective_advance'] for r in raw),fixed_MOBILE_signals_accepted=sum(r['effective_advance'] for r in mobile),fixed_MOBILE_signals_rejected=len(rejected),rejected_original_MOBILE_layer_ids=[r['layer'] for r in rejected],gate_scope='MATURE_ADD only; rejected MOBILE rows may have been first-UP probes, whose original eligibility is retained and is not modeled here.',CORE636_unchanged='Gate does not delete original CORE entry; its CP balance row is only an annotation.',sample_limits=['18 stocks selected by original actually funded 2026H1 cohort; not all126 semiconductor stocks.','Original static annotations are not avoided loss, new trades or portfolio performance.','No live holdings/fill/probe status or new I_mature is inferred.'],source_sha256=sources,script_sha256=sha(__file__),new_accounts=0,new_CP_kernel_runs=0,new_E0_runs=0,new_quantities=0,new_returns=0,parameter_scan=False,lambda_fixed=B.LAMBDA)
save('SIGNAL_RUN_RECEIPT.json',summary)

# Separate fixed initial carry population; no candidate expansion or replacement.
context_path=Q/'structural_failure_v1/scale_concentration/results_v3/strong_ALL_LAYER_SCALE_CONTEXT.json';allrows=json.loads(context_path.read_text())
carry=[r for r in allrows if r['industry']=='半导体' and r['opened'][:10]<'2026-01-01' and (r['closed'] is None or r['closed'][:10]>='2026-01-01')]
carry_fields=['layer','sid','name','role','decision_at','opened','closed','stock_structure','receipt','actual_entry_action']
save('ORIGINAL_2026_INITIAL_CARRY_COHORT.json',dict(definition='Original semiconductor layer opened before2026Jan01 and not closed before2026Jan01; source endpoint row identity only.',classification_limit='Frozen current metadata, not historical PIT classification.',count=len(carry),stocks=sorted({r['sid'] for r in carry}),layers=[{k:r[k] for k in carry_fields} for r in carry],overlap_with_fixed18=sorted({r['sid'] for r in carry}&{r['sid'] for r in index}),candidate_run_for_carry=False,source_path=str(context_path),source_sha256=sha(context_path)))
print(enc({k:summary[k] for k in ['stocks','fixed_layers','raw_CP_events','effective_CP_events','rejected_CP_events','fixed_MOBILE_signals_accepted','fixed_MOBILE_signals_rejected','rejected_original_MOBILE_layer_ids']}))
print(enc(dict(initial_carry_layers=len(carry),initial_carry_stocks=sorted({r['sid'] for r in carry}),candidate_run_for_carry=False)))
print(enc([r for r in signals if r['layer'] in [636,674,677,684,702]]))
