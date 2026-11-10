"""Saved-output diagnosis only. No strategy imports, Data construction, pickle, or replay."""
from pathlib import Path
from collections import Counter
import ast, hashlib, json, sys
R=Path(__file__).resolve().parent.parent
O=Path(__file__).resolve().parent
V=R/'mainline_candidate_v12_winner_funding_cash_688200_v2'
B=R/'mainline_candidate_v12_winner_funding_competition/once_20250120'
C=V/'once_20250120'
END='2024-10-08'
def read(p): return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''): h.update(x)
 return h.hexdigest()
def canon(x): return json.dumps(x,sort_keys=True,ensure_ascii=False,default=str)
def digest(x): return hashlib.sha256(canon(x).encode()).hexdigest()
def save(p,x):
 with p.open('x') as f: json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
tree=ast.parse((V/'prefix_check.py').read_text())
DAILY=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DAILY' for t in n.targets)))
def diff(a,b,path=''):
 if type(a)!=type(b): return [dict(path=path,baseline=a,candidate=b)]
 if isinstance(a,dict):
  out=[]
  for k in sorted(a.keys()|b.keys()):
   if k not in a or k not in b: out.append(dict(path=path+'/'+str(k),baseline=a.get(k),candidate=b.get(k),missing_from='baseline' if k not in a else 'candidate'))
   else: out.extend(diff(a[k],b[k],path+'/'+str(k)))
  return out
 if isinstance(a,list):
  if len(a)!=len(b): return [dict(path=path,baseline_length=len(a),candidate_length=len(b))]
  return sum((diff(x,y,path+'/'+str(i)) for i,(x,y) in enumerate(zip(a,b))),[])
 return [] if a==b else [dict(path=path,baseline=a,candidate=b)]
def main():
 stage=sys.argv[1] if len(sys.argv)>1 else 'snapshot'
 assert stage in ('snapshot','final')
 families=[];sources={};allrows={};pending=[]
 ref=read(V/'PREFIX_REFERENCE.json');refdays={x['day']:x for x in ref['days']}
 for n in DAILY:
  bp=B/(n+'.json');cp=C/(n+'.json')
  try:
   raw=cp.read_bytes();z=json.loads(raw);a=read(bp)
  except (OSError,json.JSONDecodeError) as ex:
   pending.append(dict(family=n,reason=str(ex)));continue
  sources[str(bp)]=sha(bp);sources[str(cp)]=hashlib.sha256(raw).hexdigest()
  a=[x for x in a if x['day']<=END];z=[x for x in z if x['day']<=END]
  allrows[n]=(a,z)
  days=sorted(set(x['day'] for x in a+z))
  daychecks=[]
  for day in days:
   aa=[x for x in a if x['day']==day];zz=[x for x in z if x['day']==day]
   daychecks.append(dict(day=day,baseline_count=len(aa),candidate_count=len(zz),ordered_equal=aa==zz,full_record_counter_equal=Counter(map(canon,aa))==Counter(map(canon,zz)),baseline_ordered_sha256=digest(aa),candidate_ordered_sha256=digest(zz),baseline_matches_frozen_reference=digest(aa)==refdays[day]['daily_hashes'][n]))
  families.append(dict(family=n,baseline_count=len(a),candidate_count=len(z),ordered_equal=a==z,full_record_counter_equal=Counter(map(canon,a))==Counter(map(canon,z)),days=daychecks,differences=diff(a,z)))
 a,z=allrows['AVAILABILITY_EVENTS'];ca,cz=Counter(map(canon,a)),Counter(map(canon,z))
 positions=[dict(index_zero_based=i,baseline=x,candidate=y) for i,(x,y) in enumerate(zip(a,z)) if x!=y]
 key=lambda x:(x['day'],x['sid'],x['event'],x['ticket_id'])
 aa={key(x):x for x in a};zz={key(x):x for x in z};assert len(aa)==len(a) and len(zz)==len(z)
 availability=dict(baseline_rows=a,candidate_rows=z,positional_differences=positions,missing_records=[json.loads(x) for x in (ca-cz).elements()],added_records=[json.loads(x) for x in (cz-ca).elements()],keyed_field_differences=[dict(key=k,changes=diff(aa[k],zz[k])) for k in aa.keys()&zz.keys() if aa[k]!=zz[k]],pure_order_permutation=ca==cz and a!=z)
 pq=read(V/'PREFIX_QA.json');latest=read(V/'runtime_checkpoint/LATEST.json')
 ledger=allrows['DAY_LEDGER'][1]
 report=dict(result='DIAGNOSED_AVAILABILITY_ORDER_ONLY_NOT_CERTIFICATION',cutoff=END,stage=stage,history_run=False,Data_constructed=False,strategy_or_gate_changed=False,
 certification=dict(raw_days=len(ledger),raw_last=ledger[-1],certified_days=len(pq['days']),certified_through=pq['days'][-1]['day'],prefix_result=pq['result'],prefix_error=pq['error'],latest_checkpoint=latest,usable_result=False),
 availability=availability,families=families,pending_families=pending,source_hashes=sources,
 code_findings=[
  dict(path=str(R/'mainline_candidate_v2_pending_quote_pause/engine.py'),lines='92-98',finding='PAUSED_CLOSE_NO_PRICE_SIGNAL appends while iterating a set of paused sids; this does not specify inter-symbol ordering. Actual hash seed was not captured, so set iteration is source-based explanation, not proven exact process seed.'),
  dict(path=str(R/'mainline_m7_cash_batch_design_v6/engine.py'),lines='68-73,84-89',finding='Existing M7 check_prefix/check_nov7 compares AVAILABILITY_EVENTS as Counter of full sorted-key JSON records, preserving multiplicity and every field.'),
  dict(path=str(V/'prefix_check.py'),lines='42-50',finding='V2 hashes ordered per-day lists including availability, asserts daily hashes before book verification. Failure is reproduced by exact saved rows. Only Oct10 permits book/scratch digest differences.'),
  dict(path=str(R/'mainline_candidate_v12_winner_funding_competition/engine.py'),lines='125-137,275-300,319-343',finding='state_fingerprint includes availability list; CLOSE scratch digests enter book_id, and next OPEN decision links book_id plus its own scratch fingerprint. Changing only AVAIL comparison is not proven sufficient.'),
  dict(path=str(V/'run_approved_once.py'),lines='61-92',finding='Prefix assertion occurs after successful atomic_step and before checkpoint; failed Oct8 remains raw exported state but was not committed or certified. Empty BLOCKERS/UNCERTIFIED_DAY does not certify it.')],
 pending_checks=['No Oct9 or later continuation exists; future decisions/branch propagation cannot be checked without a separately authorized run.','No change to frozen gate, inputs, economics, approval, or existing seals is authorized.'])
 for name in ['prefix_check.py','run_approved_once.py','PREFIX_REFERENCE.json','PREFIX_QA.json','SOURCE_HASHES.json','recovery_001/recover.py','recovery_001/RECOVERY_STDOUT.log','runtime_checkpoint/LATEST.json','CHECKPOINT_RECEIPTS.jsonl']:
  report['source_hashes'][str(V/name)]=sha(V/name)
 for p in [R/'mainline_m7_cash_batch_design_v6/engine.py',R/'mainline_candidate_v2_pending_quote_pause/engine.py',R/'mainline_candidate_v12_winner_funding_competition/engine.py']:
  report['source_hashes'][str(p)]=sha(p)
 if stage=='final':
  assert not pending,'EXPORT_FAMILIES_PENDING'
  assert (V/'RUN_STATUS.json').exists() and (C/'COMPRESSED_OUTPUTS.json').exists(),'EXPORT_NOT_COMMITTED'
  report['run_status']=read(V/'RUN_STATUS.json')
  report['source_hashes'][str(V/'RUN_STATUS.json')]=sha(V/'RUN_STATUS.json')
  report['source_hashes'][str(C/'COMPRESSED_OUTPUTS.json')]=sha(C/'COMPRESSED_OUTPUTS.json')
  report['next_verification']='Read-only compare complete branch books and all linked scratch/book/decision fields. Preserve economic fields and all full-record multiplicities. Do not silently ignore digests or mark certified.'
 path=O/('V12_RECOVERY_20241008_'+stage.upper()+'_DIAGNOSIS.json')
 save(path,report)
 print(json.dumps(dict(path=str(path),sha256=sha(path),families=len(families),pending=pending,raw_days=len(ledger),certified_days=len(pq['days']),availability_pure_order=availability['pure_order_permutation']),ensure_ascii=False))
if __name__=='__main__':main()
