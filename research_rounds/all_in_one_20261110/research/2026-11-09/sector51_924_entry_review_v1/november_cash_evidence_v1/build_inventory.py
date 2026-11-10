import json,csv,pathlib,hashlib,collections
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
O=R/'november_cash_evidence_v1'
run=R/'mainline_m7_downturn_cash_batch_v6/once_20241031'
A=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions')
C=R/'joint51_candidate_v11_suspension_accounting/CLASSIFICATION_ALL1709.csv'
classes=list(csv.DictReader(C.open())); ad={(x['sid'],x['ex_date']) for x in json.load((run/'EVENT_ADMISSION.json').open())}
tickets=json.load((run/'TICKET_STATE.json').open()); holdings=json.load((run/'HOLDINGS.json').open())
held={x['sid'] for x in holdings if x['day']=='2024-10-31' and float(x['qty'])>0}
rows=[]
for c in classes:
 if c['eligible']!='True': continue
 sid=c['symbol']; path=A/(sid+'.json')
 for e in json.load(path.open())['events']:
  dt=e['effective_date']
  if '2024-11-01'<=dt<='2024-11-30' and float(e['split_ratio'])==1 and float(e['cash_per_old_share'])>0 and (sid,dt) not in ad:
   rows.append(dict(sid=sid,name=c['name'],ex_date=dt,d_source=e['cash_per_old_share'],state_at_20241031='held' if sid in held else 'retained' if tickets.get(sid,{}).get('status')=='RETAINED' else 'none',ticket_status=tickets.get(sid,{}).get('status'),local_action_path=str(path),official_raw_matches=[],adapter_matches=[],notice_paths=[]))
rows.sort(key=lambda x:(x['ex_date'],x['sid']))
by_sid={x['sid']:x for x in rows}
scanroots=[R,pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')]
files=[]
for base in scanroots:
 for p in base.rglob('*'):
  if not p.is_file() or O in p.parents:continue
  low=str(p).lower()
  if not any(w in low for w in ('cash','equity_evidence','share_action','fact','notice')):continue
  if p.suffix.lower() not in ('.json','.pdf','.txt'):continue
  files.append(p)
for p in files:
 if p.suffix.lower() in ('.pdf','.txt'):
  for sid,x in by_sid.items():
   if sid[:6] in p.name and ('official' in p.name.lower() or 'notice' in str(p).lower() or p.suffix=='.pdf'):x['notice_paths'].append(str(p))
  continue
 if p.stat().st_size>20_000_000:continue
 try: obj=json.load(p.open())
 except:continue
 sid=obj.get('sid') if isinstance(obj,dict) else None
 if sid in by_sid and isinstance(obj.get('raw'),dict) and 'cninfo' in str(obj.get('endpoint','')):
  for rec in obj['raw'].get('records',[]):
   if rec.get('F020D')==by_sid[sid]['ex_date']:
    by_sid[sid]['official_raw_matches'].append(dict(path=str(p),endpoint=obj.get('endpoint'),record=rec))
 def visit(o):
  if isinstance(o,dict):
   sid=o.get('sid',o.get('symbol'));dt=o.get('ex_date',o.get('target_ex_date'))
   if sid in by_sid and dt==by_sid[sid]['ex_date'] and any(k in o for k in ('d_source','pay_date','notice','record_date')):
    by_sid[sid]['adapter_matches'].append(dict(path=str(p),classification='reviewed_named_artifact' if 'EXTRA_REVIEWED' in p.name else 'candidate_or_fact_requires_scope_review',record=o))
   for v in o.values():
    if isinstance(v,(list,dict)):visit(v)
  elif isinstance(o,list):
   for v in o:visit(v)
 visit(obj)
for x in rows:
 x['existing_evidence_status']='reviewed_named_adapter_found' if any(a['classification']=='reviewed_named_artifact' for a in x['adapter_matches']) else 'adapter_candidate_found' if x['adapter_matches'] else 'official_raw_only_needs_review' if x['official_raw_matches'] else 'missing_official_fact'
 x['official_raw_paths']=';'.join(dict.fromkeys(m['path'] for m in x['official_raw_matches']))
 x['reusable_reviewed_adapter_paths']=';'.join(dict.fromkeys(m['path'] for m in x['adapter_matches'] if m['classification']=='reviewed_named_artifact'))
 x['candidate_adapter_paths']=';'.join(dict.fromkeys(m['path'] for m in x['adapter_matches'] if m['classification']!='reviewed_named_artifact'))
 x['notice_paths']=sorted(set(x['notice_paths']))
json.dump(rows,(O/'MISSING_EVENT_INVENTORY.json').open('w'),ensure_ascii=False,indent=2)
columns=['sid','name','ex_date','d_source','state_at_20241031','ticket_status','existing_evidence_status','official_raw_paths','reusable_reviewed_adapter_paths','candidate_adapter_paths','notice_paths','local_action_path']
with (O/'MISSING_EVENT_INVENTORY.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)
summary=dict(eligible_tickers=sum(c['eligible']=='True' for c in classes),unadmitted_ordinary_cash_events=len(rows),state_counts=dict(collections.Counter(x['state_at_20241031'] for x in rows)),evidence_counts=dict(collections.Counter(x['existing_evidence_status'] for x in rows)),daily_counts=dict(collections.Counter(x['ex_date'] for x in rows)),files_scanned=len(files),scan_roots=list(map(str,scanroots)),frozen_asof='2024-10-31',run=str(run),not_engine_admission=True,limitations='Raw CNINFO facts and candidate adapters are not reviewed event admission. Filename-only notices require exact-date verification. None state does not remove a future event requirement. No pay dates inferred.')
json.dump(summary,(O/'SUMMARY.json').open('w'),ensure_ascii=False,indent=2)
sources=[C,run/'EVENT_ADMISSION.json',run/'TICKET_STATE.json',run/'HOLDINGS.json']+list({pathlib.Path(x['local_action_path']) for x in rows})+list({pathlib.Path(m['path']) for x in rows for m in x['official_raw_matches']+x['adapter_matches']})
json.dump({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},(O/'SOURCE_HASHES.json').open('w'),indent=2)
print(json.dumps(summary,ensure_ascii=False,indent=2))
print('10/11',[(x['sid'],x['existing_evidence_status'],len(x['official_raw_matches'])) for x in rows if x['ex_date']=='2024-10-11'])
