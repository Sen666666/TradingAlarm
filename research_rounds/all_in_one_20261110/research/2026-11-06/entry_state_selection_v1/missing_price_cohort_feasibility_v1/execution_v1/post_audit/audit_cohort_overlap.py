"""Read-only cross-cohort identity/dependence and final immutable-source audit."""
from pathlib import Path
from collections import defaultdict,Counter
import ast,csv,datetime,hashlib,itertools,json,concurrent.futures,time
O=Path(__file__).resolve().parent.parent;R=O.parent.parent;A=O/'post_audit'
T='ORIGINAL_2024_AB_PRICE_165_NET80_STRICT_UNKNOWN_V1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def csvrows(p):
 with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def day(x):return str(x)[:10] if x not in ('',None) else None
def save(p,x):
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def writecsv(p,rows,fields):
 with p.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
 start=time.monotonic();out=A/'INDEPENDENT_CROSS_COHORT_REVIEW.json';assert not out.exists()
 per_cohort_reports={}
 for w in ['2023','2024JanAug']:
  per_cohort_reports[w]=read(A/('INDEPENDENT_POST_'+w+'_FULL.json'))
  assert read(A/('INDEPENDENT_POST_'+w+'_FULL.json'))['result']=='PASS_SAVED_LEDGER_AND_LABEL_AUDIT'
  assert (O/('economic_'+w)/'COMPLETE.json').exists()
 ds=[
  ('2022',R/'independent_channel_joint_economic_v1/economic_2022','ORIGINAL_2022_AB_PRICE_436_COORDINATES_SEPARATE_TEMPLATE'),
  ('2023',O/'economic_2023',T),
  ('2024JanAug',O/'economic_2024JanAug',T),
  ('2024SepDec',R/'independent_channel_joint_economic_v1/economic_2024',T)]
 files={};data={};allrows=[];allclaims=[];rootgroups=defaultdict(list);sidgroups=defaultdict(list);decisions=defaultdict(list);fail=[]
 for cohort,p,template in ds:
  f=p/'joint/ROUNDS.csv';files[str(f)]=sha(f);rows=csvrows(f)
  f=p/'joint/CLAIMS.json';files[str(f)]=sha(f);claims=read(f)
  f=p/'joint/CLAIM_LEDGER.csv';files[str(f)]=sha(f);claimledger=csvrows(f)
  paydays=defaultdict(list);claim_end={}
  for entry in claimledger:
   if entry['event']=='PAY_CLOSE_TRANSFER':paydays[(entry['round_id'],entry['economic_event_id'])].append(day(entry['day']))
  for claim in claims:
   rid=claim['owner_round_id'];pd=paydays[(rid,claim['economic_event_id'])]
   endpoint=max(pd) if claim.get('settled') and len(pd)==1 else '2026-06-30'
   claim_end[rid]=max(claim_end.get(rid,endpoint),endpoint)
  cc=[]
  for r in rows:
   root=ast.literal_eval(r['price_root']) if r.get('price_root') else None
   z=dict(cohort_id=cohort,template_id=template,round_id=r['round_id'],sid=r['sid'],owner_lane=r['owner_lane'],
    signal_close=day(r['signal_day']),entered=bool(r.get('entry_day')),entry_day=day(r.get('entry_day')),
    last_liability_day=max(day(r.get('exit_day')),claim_end.get(r['round_id'],day(r.get('exit_day')))) if r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND' else '2026-06-30',
    status=r['status'],canonical_price_root=root)
   cc.append(z);allrows.append(z);sidgroups[z['sid']].append(z)
   key=(z['sid'],z['signal_close'],template);decisions[key].append(z)
   if root is not None:rootgroups[tuple(root)].append(z)
  for c in claims:allclaims.append(dict(cohort_id=cohort,template_id=template,round_id=c['owner_round_id'],sid=c['sid'],economic_event_id=c['economic_event_id']))
  data[cohort]=cc
 duplicates=[dict(sid=k[0],signal_close=k[1],template_id=k[2],count=len(v),cohorts=json.dumps(sorted({z['cohort_id'] for z in v})),round_ids=json.dumps([z['round_id'] for z in v])) for k,v in decisions.items() if len(v)>1]
 if duplicates:fail.append(dict(check='duplicate_decisions',rows=duplicates))
 if len({(z['cohort_id'],z['round_id']) for z in allrows})!=len(allrows):fail.append(dict(check='duplicate_cohort_round_identity'))
 if len({(c['cohort_id'],c['round_id'],c['economic_event_id']) for c in allclaims})!=len(allclaims):fail.append(dict(check='duplicate_claim_identity_within_cohort'))
 pairs=[]
 for left,right in itertools.combinations(data,2):
  x=data[left];y=data[right];xs={r['sid'] for r in x};ys={r['sid'] for r in y}
  xe=[r for r in x if r['entered']];ye=[r for r in y if r['entered']]
  xr={tuple(r['canonical_price_root']) for r in x if r['canonical_price_root']};yr={tuple(r['canonical_price_root']) for r in y if r['canonical_price_root']}
  by=defaultdict(list)
  for r in ye:by[r['sid']].append(r)
  overlaps=[]
  for a in xe:
   for b in by[a['sid']]:
    lo=max(a['entry_day'],b['entry_day']);hi=min(a['last_liability_day'],b['last_liability_day'])
    if lo<=hi:overlaps.append((a['sid'],a['round_id'],b['round_id'],lo,hi))
  e1={(c['sid'],c['economic_event_id']) for c in allclaims if c['cohort_id']==left};e2={(c['sid'],c['economic_event_id']) for c in allclaims if c['cohort_id']==right}
  pairs.append(dict(left=left,right=right,same_template=x[0]['template_id']==y[0]['template_id'],shared_registered_sids=len(xs&ys),
   shared_entered_sids=len({r['sid'] for r in xe}&{r['sid'] for r in ye}),shared_PRICE_canonical_roots=len(xr&yr),
   overlapping_entered_or_UNKNOWN_liability_round_pairs=len(overlaps),overlapping_liability_sids=len({z[0] for z in overlaps}),
   shared_claim_economic_events=len(e1&e2),overlap_examples=sorted(overlaps)[:5],independent_observations=False))
 roots=[dict(sid=k[0],canonical_price_root=json.dumps(k),cohorts=json.dumps(sorted({z['cohort_id'] for z in v})),template_ids=json.dumps(sorted({z['template_id'] for z in v})),round_count=len(v),round_ids=json.dumps([z['round_id'] for z in v])) for k,v in rootgroups.items() if len({z['cohort_id'] for z in v})>1]
 sids=[dict(sid=k,cohorts=json.dumps(sorted({z['cohort_id'] for z in v})),template_ids=json.dumps(sorted({z['template_id'] for z in v})),round_count=len(v),PRICE_round_count=sum(z['owner_lane']=='PRICE' for z in v),entered_round_count=sum(z['entered'] for z in v)) for k,v in sidgroups.items() if len({z['cohort_id'] for z in v})>1]
 # Do final source rehash only after both economic jobs and per-cohort audits finish.
 inputs=read(O/'FROZEN_INPUT_SHA256.json');code=read(O/'FROZEN_CODE_SHA256.json');old=read(O.parent/'OLD_TREE_SHA256_BEFORE.json')
 def chk(item):
  p,h=item
  return None if sha(p)==h else p
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:drift=[x for x in pool.map(chk,inputs.items()) if x]
 for n,h in code.items():
  if sha(O/n)!=h:drift.append(str(O/n))
 olddrift=[p for p,h in old.items() if sha(p)!=h]
 if drift:fail.append(dict(check='final_frozen_input_or_code_drift',files=drift))
 if olddrift:fail.append(dict(check='protected_old_files_changed',files=olddrift))
 for cohort,report in per_cohort_reports.items():
  for name,h in report['artifact_sha256'].items():
   p=O/('economic_'+cohort)/name
   if sha(p)!=h:fail.append(dict(check='cohort_artifact_changed_since_independent_audit',file=str(p)))
 for p,h in files.items():
  if sha(p)!=h:fail.append(dict(check='cross_read_artifact_changed',file=p))
 writecsv(A/'COHORT_ROOT_DEPENDENCE_GROUPS.csv',sorted(roots,key=lambda x:(x['sid'],x['canonical_price_root'])),['sid','canonical_price_root','cohorts','template_ids','round_count','round_ids'])
 writecsv(A/'COHORT_SID_DEPENDENCE_GROUPS.csv',sorted(sids,key=lambda x:x['sid']),['sid','cohorts','template_ids','round_count','PRICE_round_count','entered_round_count'])
 writecsv(A/'DUPLICATE_DECISIONS.csv',duplicates,['sid','signal_close','template_id','count','cohorts','round_ids'])
 report=dict(result='PASS_COHORT_IDENTITY_AND_FINAL_SOURCE_CLOSURE' if not fail else 'BLOCKED_COHORT_OR_SOURCE_AUDIT',
  failures=fail,cohorts={k:dict(rounds=len(v),PRICE_rounds=sum(z['owner_lane']=='PRICE' for z in v),sids=len({z['sid'] for z in v}),template_id=v[0]['template_id']) for k,v in data.items()},
  pairwise=pairs,duplicate_decision_count=len(duplicates),cross_cohort_PRICE_root_groups=len(roots),cross_cohort_sid_groups=len(sids),
  final_source_verification=dict(input_files=len(inputs),code_items=len(code),protected_old_files=len(old),changed_inputs_or_code=drift,changed_old_files=olddrift),
  rules=['Cohorts are independent FLAT counterfactual starts, not a continuous cash account. Do not sum holdings, returns or claims across cohorts.',
   'The original 2022 engine is a separate responsibility/rights template; not interchangeable with the 2024_165 template.',
   'The dedup key is (sid, signal_close, template_id). The storage identity includes cohort_id and round_id.',
   'Same canonical PRICE root, same sid and overlapping follow-up are dependent evidence. Group/cluster before any later split or weighting; no model is fitted here.',
   'Known claim liability runs through actual PAY_CLOSE_TRANSFER; pending claims and UNKNOWN responsibility are conservatively retained through the common terminal endpoint for overlap description; no sale or zero value is imputed.'],
  per_cohort_audit_sha256={w:sha(A/('INDEPENDENT_POST_'+w+'_FULL.json')) for w in per_cohort_reports},
  artifact_sha256=files,script_sha256=sha(__file__),audited_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),seconds=time.monotonic()-start,economic_loops_executed=0)
 report['output_sha256']={n:sha(A/n) for n in ['COHORT_ROOT_DEPENDENCE_GROUPS.csv','COHORT_SID_DEPENDENCE_GROUPS.csv','DUPLICATE_DECISIONS.csv']}
 save(out,report)
 print(json.dumps(dict(result=report['result'],pairs=pairs,root_groups=len(roots),sid_groups=len(sids),duplicates=len(duplicates),source_files=len(inputs),old_files=len(old),failures=fail,report=str(out),sha256=sha(out)),ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
