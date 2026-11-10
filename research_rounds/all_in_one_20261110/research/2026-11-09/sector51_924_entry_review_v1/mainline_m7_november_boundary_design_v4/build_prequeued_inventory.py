"""Source-only inventory; never imports strategy or runs historical execution."""
import json,pathlib,hashlib,collections,csv
import pandas as pd
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1');O=R/'mainline_m7_november_boundary_design_v4';B=R/'mainline_m7_long_horizon_sealed_v2/once_20260630'
read=lambda p:json.loads(pathlib.Path(p).read_text())
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
hashes={};expected=read(B/'SOURCE_HASHES.json');drift=[]
def track(p):
 p=str(p); h=sha(p);hashes[p]=h
 if p in expected and h!=expected[p]:drift.append(p)
 return p
for n in ['SOURCE_HASHES','HOLDINGS','PENDING_AT_END','TICKET_STATE','ALL_TARGETS_BLOCKER_SCAN','EVENT_ADMISSION','UNCERTIFIED_DAY']:track(B/(n+'.json'))
held={x['sid'] for x in read(B/'HOLDINGS.json') if x['day']=='2024-11-06' and float(x['qty'])>0};pending={x['sid'] for x in read(B/'PENDING_AT_END.json')};retained={k for k,v in read(B/'TICKET_STATE.json').items() if v['status']=='RETAINED'};targets=held|pending|retained
assert targets=={x['sid'] for x in read(B/'ALL_TARGETS_BLOCKER_SCAN.json')}
admitted={(x['sid'],x['ex_date']) for x in read(B/'EVENT_ADMISSION.json')}
mp=next(p for p in expected if p.endswith('/STOCK_MANIFEST.json'));manifest={x['symbol']:x for x in read(track(mp))}
evidence=collections.defaultdict(list)
# Exact sid/date matches only; filename-only notices are not event evidence.
paths=set(R.rglob('*REVIEWED*EVENT*.json'))|{R/'november_cash_evidence_v1/MISSING_EVENT_INVENTORY.json',R/'november_300760_cash_evidence_v1/EVENT_FACT_PROPOSAL.json',O/'CASH_EVENT.json'}
def visit(v,p):
 if isinstance(v,dict):
  sid=v.get('sid',v.get('symbol'));dt=v.get('ex_date',v.get('target_ex_date'))
  if sid in targets and isinstance(dt,str) and '2024-11-06'<dt<='2026-06-30':
   evidence[(sid,dt)].append(dict(path=str(p),reviewed_named_list='REVIEWED' in p.name,notice_url=v.get('notice_url',v.get('primary_source_url')),source_type=v.get('source_type'),official_raw_paths=v.get('official_raw_paths'),existing_evidence_status=v.get('existing_evidence_status'),notice=v.get('notice')))
  for a in v.values():
   if isinstance(a,(dict,list)):visit(a,p)
 elif isinstance(v,list):
  for a in v:visit(a,p)
for p in sorted(paths):
 if p.exists():visit(read(track(p)),p)
rows=[];coverage=[]
A=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions')
for sid in sorted(targets):
 m=manifest[sid];sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));track(sp);ap=A/(sid+'.json');events=read(track(ap))['events'];z=pd.read_parquet(sp);z=z.sort_index();f=z['adjustment_factor'];prev=f.shift();changes=z[(f/prev-1).abs()>1e-11];actions=collections.defaultdict(list)
 for e in events:
  dt=e['effective_date']
  if '2024-11-06'<dt<='2026-06-30':actions[dt].append(e)
 dates=set(actions)|{str(d.date()) for d in changes.index if '2024-11-06'<str(d.date())<='2026-06-30'}
 coverage.append(dict(sid=sid,signal_first=str(z.index.min().date()),signal_last=str(z.index.max().date()),signal_path=sp,action_path=str(ap),held=sid in held,pending=sid in pending,retained=sid in retained))
 for dt in sorted(dates):
  t=pd.Timestamp(dt);before=z[z.index<t];cur=z.loc[t] if t in z.index else None;old=float(before.iloc[-1].adjustment_factor) if len(before) else None;new=float(cur.adjustment_factor) if cur is not None else None;es=evidence[(sid,dt)]
  rows.append(dict(sid=sid,date=dt,held=sid in held,pending=sid in pending,retained=sid in retained,actions=actions[dt],action_types=';'.join(sorted(set('CASH_AND_SPLIT' if float(e['cash_per_old_share'])>0 and float(e['split_ratio'])!=1 else 'SPLIT' if float(e['split_ratio'])!=1 else 'CASH' if float(e['cash_per_old_share'])>0 else e.get('classification','OTHER').upper() for e in actions[dt]))) or 'FACTOR_ONLY',factor_before=old,factor_after=new,previous_observation=str(before.index[-1].date()) if len(before) else None,factor_changed=old is not None and new is not None and abs(new/old-1)>1e-11,in_baseline_admission=(sid,dt) in admitted,exact_date_existing_evidence=es,evidence_status='REVIEWED_NAMED_ARTIFACT_REQUIRES_SCOPE_REVIEW' if any(e['reviewed_named_list'] for e in es) else 'EXISTING_CANDIDATE_OR_RAW_REQUIRES_REVIEW' if any(e.get('official_raw_paths') or e.get('notice') or e.get('notice_url') or e.get('existing_evidence_status') not in (None,'missing_official_fact') for e in es) else 'NO_EXACT_EVENT_OFFICIAL_EVIDENCE_IN_SCANNED_ARTIFACTS',signal_path=sp,action_path=str(ap)))
for p in [O/'build_prequeued_inventory.py',R/'november_300760_cash_evidence_v1/300760_2024-049_cninfo.pdf',R/'november_300760_cash_evidence_v1/300760_2024-049_cninfo.txt']:track(p)
rows.sort(key=lambda x:(x['date'],x['sid']));un=[x for x in rows if not x['in_baseline_admission']]
summary=dict(scope='FIXED_EXISTING_TARGET_SOURCE_FACT_INVENTORY_ONLY_NOT_ACTUAL_FUTURE_PORTFOLIO',asof='2024-11-06',through='2026-06-30',target_count=len(targets),held_count=len(held),pending_count=len(pending),retained_count=len(retained),target_counts_overlap=True,boundary_count=len(rows),factor_change_count=sum(x['factor_changed'] for x in rows),unadmitted_factor_change_count=sum(x['factor_changed'] for x in un),unadmitted_count=len(un),unadmitted_sid_count=len({x['sid'] for x in un}),unadmitted_months=dict(collections.Counter(x['date'][:7] for x in un)),unadmitted_types=dict(collections.Counter(x['action_types'] for x in un)),evidence_status_counts=dict(collections.Counter(x['evidence_status'] for x in un)),source_hash_mismatches=drift,source_files_hashed=len(hashes),earliest_unadmitted=[{k:x[k] for k in ['sid','date','action_types','factor_before','factor_after','evidence_status']} for x in un[:20]],history_run=False,new_admissions=0,limitations=['Frozen targets only; no future holding, entry, exit, entitlement, or payoff forecast.','Factor threshold relative 1e-11, matching existing boundary tolerance.','Evidence search restricted to existing reviewed-named event lists and November evidence inventory/proposal; absence is not global proof of no official notice.','Local action paid_at/new-share sellability may be null; no dates inferred.','No engine instantiated and no source or baseline output changed.'])
assert not drift,drift
payload=dict(summary=summary,targets=coverage,boundaries=rows,source_hashes=hashes)
(O/'PREQUEUED_TARGET_FACT_INVENTORY.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+'\n')
cols=['sid','date','held','pending','retained','action_types','actions','factor_before','factor_after','previous_observation','factor_changed','in_baseline_admission','evidence_status','exact_date_existing_evidence','signal_path','action_path']
with (O/'PREQUEUED_TARGET_FACT_INVENTORY.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,list) else v for k,v in r.items()} for r in rows)
(O/'PREQUEUED_TARGET_FACT_READOUT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
