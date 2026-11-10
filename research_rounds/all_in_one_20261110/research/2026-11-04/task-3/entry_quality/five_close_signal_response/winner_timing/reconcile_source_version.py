"""Thin v1 archive binding and v2 as-of-clock parity; no root/return recalculation."""
from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent;P=O.parent;A=P/'pre_calendar_tail_fix'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,z):Path(p).write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n')
manifest=read(O/'SOURCE_MANIFEST.json')
history=O/'SOURCE_MANIFEST_V1_HISTORICAL_PATH_RECORD.json'
if not history.exists():history.write_bytes((O/'SOURCE_MANIFEST.json').read_bytes())
original=read(history);rebound={};records=[]
for path,h in original['sources'].items():
 p=Path(path);arch=None
 if p.is_relative_to(P):arch=A/p.relative_to(P)
 if arch is not None and arch.exists() and sha(arch)==h:
  rebound[str(arch)]=h;records.append(dict(original_v1_path=path,actual_bound_path=str(arch),sha256=h,binding='archived_v1_exact_bytes'))
 else:
  assert p.exists() and sha(p)==h,(path,'no exact original v1 bytes found')
  rebound[str(p)]=h;records.append(dict(original_v1_path=path,actual_bound_path=str(p),sha256=h,binding='unchanged_original_input'))
views=['2022_weak','2024_recovery','strong'];v2events={};parity={};inputs={}
for view in views:
 old=A/view/'DAILY_FEEDBACK.json';new=P/view/'DAILY_FEEDBACK.json'
 d1=read(old);d2=read(new);assert d1==d2,('asof feedback changed',view)
 for p in [old,new,A/view/'EVENTS.json',P/view/'EVENTS.json']:inputs[str(p)]=sha(p)
 v2events[view]={e['signal_id']:e for e in read(P/view/'EVENTS.json')}
 parity[view]=dict(asof_rows=len(d1),all_feedback_fields_equal=True,v1_feedback_sha256=sha(old),v2_feedback_sha256=sha(new))
assert sum(x['asof_rows'] for x in parity.values())==542
memberchecks={};futurechanges=[]
for ref in ['2022_2024','strong']:
 rows=read(O/(ref+'_WINNER_TIMING.json'));checked=0;left=0
 for row in rows:
  c=row['own_first_signal_clock'];day=row['decision_day'];view=row['analysis_view']
  if view is not None:
   daily=next(x for x in read(P/view/'DAILY_FEEDBACK.json') if x['day']==day)
   fb='NO_DATA' if daily['feedback_state']=='NO_MATURE_DATA' else daily['feedback_state'];assert fb==row['market_feedback_state']
   assert all(daily[k]==v for k,v in row['market_feedback'].items())
  else:assert row['market_feedback_state']=='outsidewindow' and row['market_feedback'] is None
  if c['left_censored']:
   assert c['primary_first_signal_day'] is None and c['maturity_day_known_asof'] is None and c['valid_closes_known_asof'] is None;left+=1;checked+=1;continue
  if c['label_source_view'] is None:checked+=1;continue
  ev=v2events[c['label_source_view']][c['signal_id']]
  known=[d for d in ev['valid_close_days'] if d<=day];mature=ev['maturity_day'] is not None and ev['maturity_day']<=day;bad=ev['first_bad_day'] is not None and ev['first_bad_day']<=day
  state='MATURED_KNOWN_AT_DECISION' if mature else 'CLOCK_AMBIGUOUS_KNOWN_AT_DECISION' if bad else 'NOT_YET_FIVE_AT_DECISION'
  assert state==c['maturity_state_asof']
  assert len(known)==c['valid_closes_known_asof'] and known==c.get('valid_close_days_known_asof',[])
  assert (ev['maturity_day'] if mature else None)==c['maturity_day_known_asof']
  assert (0 if mature else None if bad else 5-len(known))==c['remaining_valid_closes_to_five']
  v1=next(e for e in read(A/c['label_source_view']/'EVENTS.json') if e['signal_id']==c['signal_id'])
  if v1['maturity_day']!=ev['maturity_day']:
   futurechanges.append(dict(window=ref,sid=row['original']['sid'],original_decision_day=day,signal_id=c['signal_id'],v1_future_maturity_day=v1['maturity_day'],v2_future_maturity_day=ev['maturity_day'],own_maturity_known_at_original_decision_unchanged=mature))
  checked+=1
 memberchecks[ref]=dict(original_members=len(rows),checked=checked,left_censored_historical_first_unknown_retained=left,feedback_state_exact=True,own_response_known_exact=True,known_valid_close_count_and_dates_exact=True,remaining_valid_closes_exact=True)
assert sum(x['checked'] for x in memberchecks.values())==177
binding=dict(row_files='Existing WINNER_TIMING JSON/CSV and summary monetary values remain unchanged.',copied_main_fields_version='v1 exact original bytes now bound to pre_calendar_tail_fix archive',copied_fields=['own_first_signal_clock.label_observation_end','own_first_signal_clock.label_source_view','own_first_signal_clock as-of valid-close and maturity fields','market_feedback'],v2_use='All542 market asof rows and all177 winner decision-clock states verified identical. Future maturity outside the old observation end may change and is not backdated.',historical_manifest_record_is_not_current_input_binding=str(history),active_binding_manifest=str(O/'SOURCE_MANIFEST.json'))
result=dict(status='PASS',scope='v2 only extends offline existing calendar price tail; no root/outcome/gate/account rerun',all542_asof_feedback_fields_unchanged=parity,all177_winner_clock_parity=memberchecks,future_maturity_metadata_changes=futurechanges,original_v1_hash_binding=records,copied_field_binding=binding,comparison_inputs_sha256=inputs,new_returns_computed=0,new_accounts=0,new_gates=0,script_sha256=sha(__file__))
write(O/'SOURCE_VERSION_RECONCILIATION.json',result)
manifest['sources']=rebound
manifest['parent_v1_manifest_actual_archive_path']=str(A/'SOURCE_MANIFEST.json')
manifest['parent_v1_manifest_sha256']=original['parent_main_manifest_sha256']
manifest.pop('parent_main_manifest_sha256',None)
manifest['source_version_reconciliation']=str(O/'SOURCE_VERSION_RECONCILIATION.json')
manifest['source_version_reconciliation_sha256']=sha(O/'SOURCE_VERSION_RECONCILIATION.json')
manifest['copied_main_fields_bound_to_version']='archived_v1; all relevant asof values verified unchanged in v2'
assert all(sha(k)==h for k,h in rebound.items())
write(O/'SOURCE_MANIFEST.json',manifest)
write(O/'COPIED_MAIN_FIELD_VERSION_BINDING.json',binding)
write(O/'DELIVERABLE_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
print('PASS:542 feedback rows;177 winner clocks;archive original hashes exact;future maturity changes',len(futurechanges))
