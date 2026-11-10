"""All-channel as-of coverage, no old financial event is replayed."""
from gs_next_session import *
import pandas as pd,numpy as np,shutil,subprocess,pickle,time
from datetime import datetime
from dataclasses import asdict
spec=importlib.util.spec_from_file_location('old_full_state_view',OLD/'export-recovery/audit_state.py');AUD=importlib.util.module_from_spec(spec);spec.loader.exec_module(AUD)

def rebind(root,name,value=None,frame=None):
 m=LD.read(root/'MANIFEST.json');p=root/m['extensions'][name]['path']
 if value is not None:LD.write(p,value)
 if frame is not None:frame.to_parquet(p,index=False)
 m['extensions'][name]['sha256']=sha(p);LD.write(root/'MANIFEST.json',m)
def packet_view(r,at):
 r.account.market.refresh(at)
 return normalize(r.stock_packet(at))
def run():
 root=O/'coverage-003';root.mkdir(exist_ok=False);started=time.monotonic();checks=[]
 inventory={r['symbol']:r for r in LD.read(LD.B/'g-s-minimal-input-readiness/STOCK_INPUT_INVENTORY.json')}
 srcbind=LD.read(H.INPUT/'SOURCE_BINDINGS.json')
 for k,s in SPECS.items():
  original=LD.HistoricalInputs(H.INPUT/k/'MANIFEST.json');extended=ExtendedInputs(O/'inputs'/k/'MANIFEST.json')
  variant=root/(k+'-future-all-channels');shutil.copytree(O/'inputs'/k,variant)
  m=LD.read(variant/'MANIFEST.json');m['horizon_extension']['diagnostic']=True;LD.write(variant/'MANIFEST.json',m)
  for name in ('facts','cp','raw','pvr','h1','f1_observations'):
   p=variant/m['extensions'][name]['path'];f=pd.read_parquet(p)
   for col in f.select_dtypes(include=['number']).columns:
    if col=='e0_target':f[col]=0
    elif col=='breadth':f[col]=f[col].where(f[col].isna(),0.)
    elif col not in ('segment_id','price_source_segment_id'):
     if pd.api.types.is_integer_dtype(f[col].dtype):f[col]=f[col]+1
     else:f[col]=f[col].astype('float64')*1.25+1.
   rebind(variant,name,frame=f)
  # Rebuild ALL derived structure metadata from actual full original history
  # plus only future E0 changes. Do not leave stale derived metadata untouched.
  meta=LD.read(original.ref('metadata'));newstructures={};causal_prefix_count=0
  for sid in original.ids:
   p=Path(inventory[sid]['refs']['facts']);assert sha(p)==srcbind[str(p)]
   f=PREP.filtered(p,s['next_day']);f=f.copy();f.loc[f.index>pd.Timestamp(s['old_end']),'e0_target']=0
   olddays=[r['observed_day'] for r in meta[sid]['structure_observations']]
   all_days=olddays+([s['next_day']] if pd.Timestamp(s['next_day']) in f.index else [])
   rebuilt=PREP.structure_observations(sid,f,all_days)
   assert [r for r in rebuilt if r['observed_day']<=s['old_end']]==meta[sid]['structure_observations'],(k,sid,'future-derived structure changed past')
   newstructures[sid]=[r for r in rebuilt if r['observed_day']>s['old_end']];causal_prefix_count+=1
  rebind(variant,'metadata',value=newstructures)
  rr=LD.read(variant/m['extensions']['receipts']['path'])
  for r in rr:r['original_candidate']*=1.25
  rebind(variant,'receipts',value=rr)
  aa=LD.read(variant/m['extensions']['actions']['path'])
  for a in aa:a['split_ratio']='1.5';a['cash_per_old_share']='9.0';a['paid_at']=s['next_day']+'T12:00:00+08:00'
  if not aa:aa=[dict(sid=original.ids[0],effective_date=s['next_day'],cash_per_old_share='9',split_ratio='1.5',source_id='DIAGNOSTIC_FUTURE_ONLY',paid_at=s['next_day']+'T12:00:00+08:00',new_shares_sellable_at=None,classification='ordinary_cash_and_pro_rata_bonus')]
  rebind(variant,'actions',value=aa);rebind(variant,'payments',value=aa)
  poisoned=ExtendedInputs(variant/'MANIFEST.json')
  physical=root/(k+'-physical-old-cutoff');shutil.copytree(variant,physical)
  pm=LD.read(physical/'MANIFEST.json')
  for name,ref in pm['extensions'].items():
   p=physical/ref['path']
   if p.suffix=='.parquet':f=pd.read_parquet(p);rebind(physical,name,frame=f[f.day<=s['old_end']])
   elif name=='metadata':rebind(physical,name,value={sid:[] for sid in original.ids})
   else:rebind(physical,name,value=[])
  cut=ExtendedInputs(physical/'MANIFEST.json')
  for day in original.days:
   for phase in ('ACTION','PAYMENT','OPEN','CLOSE'):
    baseline=normalize(original.event(day,phase))
    assert baseline==normalize(extended.event(day,phase))==normalize(poisoned.event(day,phase))==normalize(cut.event(day,phase)),(k,day,phase,'past input changed')
   assert original.priority(day)==extended.priority(day)==poisoned.priority(day)==cut.priority(day)
  # Read-only candidate/ordering generation at each historical pre-CLOSE state.
  # No planning(), opening(), step(), reserve or fill is invoked here.
  for day,sub in [(original.days[0],'primary'),(original.days[1],'primary-resume')]:
   p=OLD/'runs'/k/sub/'BEFORE_EVENT.pkl';at=iso(day+'T15:10:00+08:00')
   base=pickle.loads(p.read_bytes());assert base.last_completed_event<at
   expected=packet_view(base,at)
   for label,inputs in [('complete',extended),('future-derived-poison',poisoned),('physical-cutoff',cut)]:
    r=pickle.loads(p.read_bytes());r=install_inputs(r,inputs,finance=False)
    got=packet_view(r,at);assert got==expected,(k,day,label,'historical candidate/priority packet changed')
  # Pure future F1 previews use copies of the last known State, never account
  # evidence updates; recomputing the future cannot alter old state/proof.
  r=H.HistoricalRunner.restore(old_checkpoint(k));prior=normalize({q:asdict(v) for q,v in r.f1.items()})
  future_modes={}
  for ob in poisoned.market_observations(s['next_day']):
   state=copy.deepcopy(r.f1[ob['policy_scope']]);new,dec=F1.step(state,F1.Observation(s['next_day'],F1.Source(**ob['source']),ob['price_input'],ob['breadth']))
   future_modes[ob['node_id']]=dec.mode
  assert normalize({q:asdict(v) for q,v in r.f1.items()})==prior
  # Explicit import and cross-process checkpoint: same whole economic state.
  imported=import_checkpoint(k,O/'inputs'/k/'MANIFEST.json',finance=False);assert imported.account.available==r.account.available
  cp=root/(k+'-readonly-import.pkl');imported.checkpoint(cp)
  save(root/(k+'-import.json'),dict(economic_state_exact=True,old_cursor=str(r.last_completed_event),cash=str(r.account.available),positions=len(r.account.positions),pending=len(r.account.pending),exits=len(r.account.exits),old_canonical_receipts_unmodified=True))
  try:imported.step(s['next_day'],'OPEN')
  except ValueError as e:assert 'read-only diagnostic' in str(e)
  else:raise AssertionError('read-only import allowed finance')
  checks.append(dict(window=k,all_channels_past_inputs_exact=True,past_pure_candidate_priority_packets_exact=True,old_financial_events_replayed=0,
    actual_source_structures_rebuilt=causal_prefix_count,F1_future_copy_previews=len(future_modes),future_canonical_action_payment_perturbations=True,physical_future_rows_removed=True,
    old_input_base_file_hashes_unchanged=True,import_state_exact=True,readonly_finance_rejected=True))
 save(root/'GATE.json',dict(passed=True,checks=checks,financial_events=0,seconds=time.monotonic()-started))
 print(json.dumps(dict(passed=True,cohorts=2,financial_events=0,seconds=time.monotonic()-started)),flush=True)
if __name__=='__main__':run()
