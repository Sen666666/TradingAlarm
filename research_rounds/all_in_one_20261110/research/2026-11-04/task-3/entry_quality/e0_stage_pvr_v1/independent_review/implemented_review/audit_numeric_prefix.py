"""Only original numeric-event causal-prefix check on four fixed stocks.
No stock_signal, G1/E0 policy, research replay, Account or Runner execution.
"""
from pathlib import Path
import sys,json,hashlib,ast
import numpy as np,pandas as pd
import pyarrow.dataset as ds
O=Path(__file__).resolve().parent;R=O.parents[1]
CORE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code')
sys.path.insert(0,str(CORE))
import numeric,data_utils
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
freeze=json.loads((R/'FREEZE.json').read_text());binding=json.loads((R/'SOURCE_BINDING.json').read_text())
assert Path(numeric.__file__).resolve()==(CORE/'numeric.py').resolve() and Path(data_utils.__file__).resolve()==(CORE/'data_utils.py').resolve()
for p in [CORE/'numeric.py',CORE/'data_utils.py']:assert sha(p)==binding['files'][str(p)]
# E0 policy arithmetic's two reused operations are the same bodies (ignoring docs).
a=ast.parse((CORE/'numeric.py').read_text());bpath=CORE.parent.parent/'pv-strength-b5-20261025/code/arithmetic.py';b=ast.parse(bpath.read_text())
for name in ['compare','higher']:
 def body(tree):
  f=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name==name);return ast.dump(ast.Module(body=[n for n in f.body if not(isinstance(n,ast.Expr)and isinstance(n.value,ast.Constant)and isinstance(n.value.value,str))],type_ignores=[]),include_attributes=False)
 assert body(a)==body(b)
sids=['000620.SZ','300666.SZ','300085.SZ','002583.SZ'];day='2024-09-24';end='2024-10-08';source=Path(freeze['source']);st=source.stat();assert st.st_size==binding['source_size'] and st.st_mtime_ns==binding['source_mtime_ns']
columns=['symbol','trade_date','open','high','low','close','volume','source'];dataset=ds.dataset(source)
cut=dataset.to_table(columns=columns,filter=ds.field('symbol').isin(sids)&(ds.field('trade_date')<=pd.Timestamp(day))).to_pandas()
extended=dataset.to_table(columns=columns,filter=ds.field('symbol').isin(sids)&(ds.field('trade_date')<=pd.Timestamp(end))).to_pandas()
parts={}
for p in (R/'parts').glob('*.jsonl'):
 for line in p.open():
  z=json.loads(line)
  if z['day']==day and z['sid']in sids:parts[z['sid']]=z
assert set(parts)==set(sids)
checks=[]
for sid in sids:
 frames=[];events=[]
 for data,target in [(cut,day),(extended,end)]:
  g=data[data.symbol.eq(sid)].sort_values('trade_date');assert g.trade_date.le(target).all() and g.source.nunique(dropna=False)==1 and g.source.notna().all()
  f=g.set_index('trade_date')[['open','high','low','close','volume']].copy();f['segment_id']=0;f=data_utils.eligible_prices(f)
  frames.append(f);events.append(numeric.event_frame_numeric(f.close,f.volume,joint=True,event_exit=False))
 f,e=frames[0],events[0];assert str(f.index[-1].date())==day and len(frames[1])>len(f)
 pd.testing.assert_frame_equal(e,events[1].loc[e.index],check_exact=True,check_dtype=True,check_freq=False)
 snap=parts[sid];row=e.loc[pd.Timestamp(day)]
 assert np.float64(row.event).view(np.uint64)==np.float64(snap['numeric_event']).view(np.uint64)
 assert np.float64(row.leg_direction).view(np.uint64)==np.float64(snap['numeric_leg_direction']).view(np.uint64)
 old=e[e.event.ne(0)]
 for event in snap['last_six_confirmed_events']:
  z=old.loc[pd.Timestamp(event['confirmed'])]
  assert str(z.confirmed_pivot_date)==event['occurred'] and int(z.pivot_age)==event['pivot_age']
  assert np.float64(z.confirmed_pivot_price).view(np.uint64)==np.float64(event['price']).view(np.uint64)
  assert np.float64(z.confirmation).view(np.uint64)==np.float64(event['confirmation']).view(np.uint64)
  assert event['kind']==('PEAK'if z.event==-1 else'TROUGH')
 for event,field,datefield in [(-1,'last_confirmed_peak','last_peak_confirmed'),(1,'last_confirmed_trough','last_trough_confirmed')]:
  z=old[old.event.eq(event)].iloc[-1];assert np.float64(z.confirmed_pivot_price).view(np.uint64)==np.float64(snap[field]).view(np.uint64)
  assert str(old[old.event.eq(event)].index[-1].date())==snap[datefield]
 if snap['reference_peak'] is not None:
  t=pd.Timestamp(snap['reference_peak_confirmed']);z=old.loc[t];assert z.event==-1 and str(t.date())<=snap['start_date']<=day
  assert str(z.confirmed_pivot_date)==snap['reference_peak_occurred'] and np.float64(z.confirmed_pivot_price).view(np.uint64)==np.float64(snap['reference_peak']).view(np.uint64)
 checks.append({'sid':sid,'target_day':day,'physical_prefix_end':str(f.index[-1].date()),'extended_test_only_end':str(frames[1].index[-1].date()),'prefix_eligible_rows':len(f),'extended_eligible_rows':len(frames[1]),'all_numeric_output_columns':list(e.columns),'all_prefix_fields_exact_after_future_append':True,'saved_event_and_provenance_exact':True,'phase_from_saved_not_replayed':snap['phase'],'reference_peak_from_saved':snap['reference_peak'],'reference_confirmed_from_saved':snap['reference_peak_confirmed']})
out={'status':'PASS_BOUNDED_FOUR_STOCK_ORIGINAL_NUMERIC_PHYSICAL_PREFIX_CAUSALITY','remaining_blocks':[],'checks':checks,'numeric_only_calls':8,'physical_prefix_tests':4,'new_full_signal_model_calls':0,'new_policy_replays':0,'new_accounts':0,'limits':['Extended input is a causality test only; its future rows never create official decision signals.','Only four predetermined stocks at2024Sep24 tested; not universal proof for every missing/invalid/source branch.','Exact prefix output establishes calculation causality, not historical publication or PIT availability.','Saved E0 target/floor checks in separate OUTPUT audit; no original E0/G1/I policy run here.'],'source_sha256':{str(p.resolve()):sha(p)for p in [CORE/'numeric.py',CORE/'data_utils.py',bpath,R/'FREEZE.json',R/'SOURCE_BINDING.json',R/'STAGED_PRIOR_RANKS.parquet',Path(__file__)]}}
p=O/'NUMERIC_PREFIX_AUDIT.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({'status':out['status'],'sha256':sha(p),'stocks':sids,'numeric_only_calls':8,'full_models':0},ensure_ascii=False))
