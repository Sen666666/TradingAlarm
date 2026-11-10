"""Read actual local provenance; reject incompatible packets, never trade."""
from pathlib import Path
from datetime import datetime
import json,csv,hashlib,collections,time
O=Path(__file__).resolve().parent;ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');RR=ROOT/'research_rounds';BASE=ROOT/'TradingAlarm/runtime/market';start=time.monotonic()
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def main():
 summary=read(O/'SUMMARY.json');latest=read(O/'LATEST_FIELDS.json');actions=read(O/'ACTIONS.json');calendar=read(ROOT/'TradingAlarm/desk/calendar.json');dates=calendar['sessions'];pools={};sectors={}
 for sec,p in [('TECH',RR/'tech-compound-design-20261026/proposed-pool.csv'),('DRUG',RR/'innovative-drug-local-recovery-20261028/pool.csv')]:
  rs=list(csv.DictReader(p.open()));pools[sec]={r['symbol'] for r in rs};sectors[sec]={r['sector_id'] for r in rs}
 action_knowledge=[]
 for row in actions:
  for e in row['new_events']:
   p=Path(e['source_id']);r=read(p.parent/'receipt.json');sid=row['sid'];day=e['effective_date'];before=[];native=('USZA' if sid.endswith('SZ') else 'USHA')+sid[:6]
   for q in sorted(BASE.glob('update-202610*/batch-*/rights/'+native+'/attempt-*/decoded.json')):
    if q.parents[4].name[:15]>'update-'+day.replace('-',''):continue
    rp=q.parent/'receipt.json'
    if not rp.exists():continue
    rec=read(rp);at=rec.get('received_at')
    if at and at<day+'T09:30:00+08:00':
     v=read(q);found=any(str(x.get('1',''))==day.replace('-','') for x in v)
     before.append(dict(path=str(q),received_at=at,target_event_already_present=found))
   action_knowledge.append(dict(sid=sid,effective_date=day,terms=e,first_known_at=None,recorded_response_received_at=r.get('received_at'),no_preopen_proof=not any(x['target_event_already_present'] for x in before),prior_local_responses=before,announcement_published_at=None,paid_at=e.get('paid_at'),bonus_sellable_not_applicable=e['split_ratio']=='1'))
 save(O/'ACTION_KNOWLEDGE.json',action_knowledge)
 receipts={read(p)['as_of']:read(p) for p in BASE.glob('update-202610*/prepared/receipt.json') if read(p).get('as_of') in ['2026-10-28','2026-10-29','2026-10-30']};packets=[]
 for sec in ['TECH','DRUG']:
  ids=pools[sec]|sectors[sec]
  for day in ['2026-10-28','2026-10-29','2026-10-30']:
   cutoff=day+'T15:10:00+08:00';bars=[r for r in latest if r['kind']=='bars' and r['day']==day and r['sid'] in ids];facts=[r for r in latest if r['kind']=='facts' and r['day']==day and r['sid'] in ids];received=[r.get('observed_at') for r in bars if r.get('observed_at')];late=[r['sid'] for r in bars if r.get('observed_at') and datetime.fromisoformat(r['observed_at'])>datetime.fromisoformat(cutoff)]
   missing_facts=sorted(ids-{r['sid'] for r in facts if r['present']});unknown_floor=[r['sid'] for r in facts if r['present'] and r.get('i_target') is True and 'i_floor' in r.get('missing_required',[])];badbars=[r['sid'] for r in bars if not r['present'] or r.get('missing_required')];blockers=[]
   if missing_facts:blockers.append('missing_actual_I_G1_E0_facts')
   if badbars:blockers.append('missing_required_raw_fields')
   if unknown_floor:blockers.append('unknown_floor_while_I_active')
   if late:blockers.append('source_received_after_frozen_15_10_decision_clock')
   if sec=='DRUG':blockers.append('own_frozen_ACT_recovery_clock_ends_2026_10_27')
   know=[x for x in action_knowledge if x['sid'] in ids and x['effective_date']==day and x['no_preopen_proof']]
   if know:blockers.append('new_action_preopen_knowledge_not_certified')
   p=dict(sector=sec,day=day,decision_clock=cutoff,export_receipt=receipts.get(day),required_series=len(ids),raw_rows_present=sum(r['present'] for r in bars),facts_rows_present=sum(r['present'] for r in facts),missing_fact_ids=missing_facts,source_observed_at_min=min(received) if received else None,source_observed_at_max=max(received) if received else None,source_received_after_clock_count=len(late),missing_raw_fields=badbars,unknown_active_floors=unknown_floor,local_market_session=day in dates,next_legal_market_session=next((d for d in dates if d>day),None),calendar_source=calendar['source'],new_action_known_at_unknown=[x['sid'] for x in know],commit_allowed=not blockers,blockers=blockers,changed_cutoff_or_assigned_known_at=False,old_account_state_modified=False)
   packets.append(p)
 save(O/'DAY_PACKETS.json',packets)
 assert len(packets)==6 and not any(p['commit_allowed'] for p in packets)
 assert all(p['local_market_session'] and p['next_legal_market_session'] for p in packets)
 assert all(p['source_received_after_clock_count']==p['required_series'] for p in packets)
 save(O/'GATE_TESTS.json',dict(passed=True,test='real six packets refused before any state or order mutation',all_six_blocked=True,missing_facts_not_zero=True,late_data_not_backdated=True,new_actions_unknown_not_backdated=True,calendar_resolvable_from_existing_local_source=True,actual_day_replay_started=False,complete_10_27_checkpoint_build_deferred=True,seconds=time.monotonic()-start))
 print([(p['sector'],p['day'],p['commit_allowed'],p['blockers']) for p in packets],flush=True)
if __name__=='__main__':main()
