"""M v2: explicit Q0 retained-ticket unavailable-quote semantics. No alpha change."""
from pathlib import Path
import sys,importlib.util,json,copy,hashlib,argparse,ast,inspect
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;ROOT=O.parent;V1=ROOT/'mainline_candidate_v1'
spec=importlib.util.spec_from_file_location('mainline_frozen_v1',V1/'engine.py');v1=importlib.util.module_from_spec(spec);sys.modules[spec.name]=v1;spec.loader.exec_module(v1)
D=v1.D;ZERO=v1.ZERO;pd=v1.pd;np=v1.np;dec=v1.dec;day=v1.day;finite=v1.finite;lineage=v1.lineage;sha=v1.sha;save=v1.save;read=v1.read;Blocked=v1.Blocked;truth=v1.truth;false=v1.false
assert sha(V1/'engine.py')=='df47ad28878f837b6204277a0d33781b2beed38b25439ac2445c371cf2f450e9'
BASE_FAMILIES=['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END','RETRY_TICKETS','INFORMATION_CONFIRMATIONS','TRANSFERS','FUNDING_REQUESTS','ADD_FLOOR_RISK','OPEN_SECTOR_EXPOSURE','TICKET_STATE','TRANSFER_PLAN_AT_END']

def known_origin(z):
 return all(z.get(c) is not None and pd.notna(z.get(c)) and str(z.get(c))!='' for c in ['source_kind','source_path','segment_id'])
def open_known(z):
 return known_origin(z) and all(finite(z.get(c)) and z[c]>0 for c in ['raw_open','adjustment_factor'])

class Data(v1.Data):
 def __init__(self,end='2024-10-31'):
  super().__init__(end)
  supplement=ROOT/'joint_equity_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_20240930_RETAINED_THREE_V1.json'
  assert sha(supplement)=='074a6b77b415b7d392eb2bba4d5943fdda14d97ce15aada267cc52ed6109cd1c'
  self.hashes[str(supplement)]=sha(supplement);events=read(supplement)
  def checked(p,h):
   assert sha(Path(p))==h,('SUPPLEMENT_INPUT_DRIFT',str(p));self.hashes[str(p)]=h
  for e in events:
   s=e['sid'];dt=pd.Timestamp(e['ex_date'])
   if s not in self.ids or not pd.Timestamp('2024-09-02')<=dt<=self.end:continue
   assert (s,dt) not in self.events,('DUPLICATE_EVENT',s,dt)
   for p,h in e.get('evidence_hashes',{}).items():checked(p,h)
   for stem in ['source_fact','local_action','signal']:
    if e.get(stem+'_path'):checked(e[stem+'_path'],e[stem+'_sha256'])
   notice=e.get('notice')
   if notice and notice.get('pdf_path'):checked(notice['pdf_path'],notice['pdf_sha256'])
   a=self.actions[s];terms=[x for x in a['events'] if x['effective_date']==e['ex_date']];assert len(terms)==1
   term=terms[0];assert dec(term['split_ratio'])==1 and dec(term['cash_per_old_share'])==dec(e['d_source'])
   z=self.raw[s];prev=z[z.index<dt].iloc[-1];cur=z.loc[dt];fo=dec(prev.adjustment_factor);fn=dec(cur.adjustment_factor);ds=dec(e['d_source']);pc=dec(prev.raw_close)
   assert lineage(prev)==lineage(cur) and abs(fo*pc/(pc-ds)/fn-1)<D('1e-11')
   assert pd.Timestamp(e['record_date'])==prev.name and pd.Timestamp(e['record_date'])<dt<=pd.Timestamp(e['pay_date'])
   if 'factor_old' in e:assert abs(fo/dec(e['factor_old'])-1)<D('1e-11') and abs(fn/dec(e['factor_new'])-1)<D('1e-11')
   assert dec(e['d_cash'])>=0
   e=dict(e,factor_old=str(fo),factor_new=str(fn));self.events[(s,dt)]=e;self.admission.append(dict(sid=s,sector51=self.sid_sector[s],ex_date=day(dt),event_id=e['economic_event_id_candidate'],status='BOUNDED_RESEARCH_NET80_ONLY',factor_bridge_verified=True,not_PIT=True,not_production_admission=True))
  for p in [O/'engine.py',O/'CONTRACT.md',O/'synthetic_pause.py']:self.hashes[str(p)]=sha(p)

class Engine(v1.Engine):
 def __init__(self,data):
  super().__init__(data);self.quote_gaps={};self.availability=[];self._preflight_excluded=set()
 def live_tickets(self):
  return {s:t for s,t in super().live_tickets().items() if s not in self._preflight_excluded}
 def availability_event(self,s,d,event,**kw):
  t=self.tickets[s];self.availability.append(dict(day=day(d),sid=s,ticket_id=t['ticket_id'],event=event,status=t['status'],original_signal_day=t['signal_day'],original_NAV=str(t['nav0']),last_verified_day=t.get('last_verified_day'),last_verified_factor=str(t['current_factor']),actual_quantity=self.quantity(self.active[s]) if s in self.active else 0,**kw))
 def pause_ticket(self,s,t,d,z):
  assert s not in self.active or self.quantity(self.active[s])==0
  if s not in self.quote_gaps:
   self.quote_gaps[s]=dict(start_day=day(d),last_verified_day=t['last_verified_day'],last_verified_factor=str(t['current_factor']),origin=t['origin'],days=[],action_inventory=[])
  gap=self.quote_gaps[s];gap['days'].append(day(d));gap['action_inventory'].extend(dict(day=day(d),action=act,reviewed_event=(s,d) in self.d.events) for act in self.d.action(s,d));t['status']='PAUSED_NO_QUOTE';t['plan']=None;t['reason']='CURRENT_OPEN_SOURCE_UNAVAILABLE'
  self.availability_event(s,d,'PAUSED_NO_QUOTE',observed_open=z.get('raw_open') if finite(z.get('raw_open')) else None,observed_factor=z.get('adjustment_factor') if finite(z.get('adjustment_factor')) else None,missing_fields=[c for c in ['raw_open','adjustment_factor'] if not finite(z.get(c)) or z[c]<=0],source_identity_observed=known_origin(z),pending_action_count=len(gap['action_inventory']))
 def reverify_gap(self,s,t,d):
  gap=self.quote_gaps[s];expected=dec(gap['last_verified_factor']);origin=tuple(gap['origin']);checks=[]
  assert t['current_factor']==expected and tuple(t['origin'])==origin
  for when in self.d.cal[(self.d.cal>pd.Timestamp(gap['last_verified_day']))&(self.d.cal<=d)]:
   z=self.d.z(s,when);actions=self.d.action(s,when);ev=self.d.events.get((s,when))
   if known_origin(z) and lineage(z)!=origin:
    v1.rules.cancel(t,'RETRY_SOURCE_CHANGED');self.availability_event(s,d,'GAP_SOURCE_CHANGED_CANCEL',changed_day=day(when),gap_record=copy.deepcopy(gap));self.quote_gaps.pop(s,None);return False
   if actions and ev is None:raise Blocked(f'{day(d)} {s} GAP_UNADMITTED_EQUITY_EVENT {day(when)}')
   if ev:
    if abs(expected/dec(ev['factor_old'])-1)>D('1e-11'):raise Blocked(f'{day(d)} {s} GAP_FACTOR_CHAIN_OLD_MISMATCH {day(when)}')
    expected=dec(ev['factor_new'])
   observed=finite(z.get('adjustment_factor')) and z['adjustment_factor']>0
   if observed and abs(dec(z['adjustment_factor'])/expected-1)>D('1e-11'):raise Blocked(f'{day(d)} {s} GAP_UNADMITTED_FACTOR_CHANGE {day(when)}')
   checks.append(dict(day=day(when),event_id=ev.get('economic_event_id_candidate') if ev else None,factor_observed=bool(observed),expected_verified_chain_factor=str(expected)))
  z=self.d.z(s,d)
  if not open_known(z) or abs(dec(z['adjustment_factor'])/expected-1)>D('1e-11'):raise Blocked(f'{day(d)} {s} GAP_FINAL_OBSERVATION_MISMATCH')
  t['current_factor']=dec(z['adjustment_factor']);t['last_verified_day']=day(d);t['status']='RETAINED';t['plan']=None;t['reason']='GAP_REVERIFIED_WAIT_CLOSE'
  self.availability_event(s,d,'GAP_REVERIFIED_NO_OLD_OPEN_FILL',gap_start=gap['start_day'],observed_day=day(d),checks=checks)
  del self.quote_gaps[s];return True
 def economic_preflight(self,d,pending):
  excluded=set();remove=set()
  for s,t in list(self.live_tickets().items()):
   if s in self.active and self.quantity(self.active[s])>0:continue
   z=self.d.z(s,d)
   if known_origin(z) and lineage(z)!=tuple(t['origin']):
    v1.rules.cancel(t,'RETRY_SOURCE_CHANGED');self.ticket_event(t,d,'CANCEL_SOURCE_CHANGED');
    if s in self.quote_gaps:self.availability_event(s,d,'GAP_SOURCE_CHANGED_CANCEL',gap_record=copy.deepcopy(self.quote_gaps[s]));self.quote_gaps.pop(s,None)
    remove.add(s);continue
   if not open_known(z):
    self.pause_ticket(s,t,d,z);excluded.add(s);remove.add(s)
   elif s in self.quote_gaps:
    self.reverify_gap(s,t,d);excluded.add(s);remove.add(s)
  pending[:]=[r for r in pending if r['sid'] not in remove]
  self._preflight_excluded=excluded
  try:super().economic_preflight(d,pending)
  finally:self._preflight_excluded=set()
 def refresh_tickets(self,d):
  paused={s for s,t in self.live_tickets().items() if t['status']=='PAUSED_NO_QUOTE'}
  for s in paused:
   t=self.tickets[s];sec=int(self.d.sectors[self.d.sid_sector[s]].at[d,'state']);st=int(self.d.stock.at[d,s]);i=self.d.f(s,d).get('i_target');reason='RETRY_SECTOR_FALSE' if sec==0 else 'RETRY_STOCK_M3_FALSE' if st==0 else 'RETRY_I_FALSE' if false(i) else None
   if reason:
    v1.rules.cancel(t,reason);self.availability_event(s,d,'KNOWN_FALSE_CANCEL_WHILE_NO_QUOTE',reason=reason,gap_record=copy.deepcopy(self.quote_gaps[s]));self.quote_gaps.pop(s,None)
   else:self.availability_event(s,d,'PAUSED_CLOSE_NO_PRICE_SIGNAL',sector_state=sec,stock_state=st,i_observed_false=False)
  self._preflight_excluded=paused
  try:return super().refresh_tickets(d)
  finally:self._preflight_excluded=set()
 def scan_restored_targets(self,d,pending):
  rows=super().scan_targets(d,pending)
  live=self.live_tickets()
  for row in rows:
   s=row['sid'];t=live.get(s);z=self.d.z(s,d)
   if row['held_qty']==0 and t is not None and not open_known(z) and not (known_origin(z) and lineage(z)!=tuple(t['origin'])):
    row['availability_boundary']='EXISTING_Q0_TICKET_PAUSABLE_NO_QUOTE';row['deferred_quote_issues']=[x for x in row['issues'] if x.endswith('_MISSING_OR_INVALID')];row['issues']=[x for x in row['issues'] if x not in row['deferred_quote_issues']]
   if s in self.quote_gaps:row['quote_gap']=copy.deepcopy(self.quote_gaps[s])
  return rows
 def run(self,checkpoint=True,stop_at_prefix=False):
  pending=[];keys=['cash','receivable','active','archive','seq','claims','snapshots','tickets','transfer_plan','quote_gaps'];logs=['orders','candidates','cp_log','profit','ledger','holdings','equity','sector_daily','ticket_log','confirmations','transfers','request_details','floor_risk','open_exposure','availability']
  for d in self.d.days:
   prev=self.d.cal[self.d.cal.get_loc(d)-1];snap=copy.deepcopy({k:getattr(self,k) for k in keys});p0=copy.deepcopy(pending);lengths={k:len(getattr(self,k)) for k in logs}
   try:
    self.economic_preflight(d,pending);self.accrue(d);self.exit_open(d);self.alloc_open(d,pending);pending=self.close(d,prev)
    if day(d)=='2024-09-27':
     self.pending=pending;self.export(O/'replay_20240927');counts={}
     for name in BASE_FAMILIES:
      actual=read(O/'replay_20240927'/(name+'.json'));old=read(V1/'checkpoint_20240927'/(name+'.json'));assert actual==old,('PREFIX_MISMATCH',name);counts[name]=len(actual)
     assert not self.availability and not self.quote_gaps
     save(O/'PRIOR_PREFIX_REPLAY_QA.json',dict(result='PASS',days=18,certified_through='2024-09-27',exact_records=counts,availability_events=0,alpha_rule_changes=0));print('PREFIX_REPLAY_PASS '+json.dumps(counts),flush=True)
     if stop_at_prefix:break
    if checkpoint and day(d) in ['2024-09-30','2024-10-08','2024-10-25','2024-10-31']:
     self.pending=pending;self.export(O/('checkpoint_'+day(d).replace('-','')));print('CHECKPOINT '+json.dumps(self.ledger[-1]),flush=True)
   except Blocked as ex:
    self.uncertified_day=dict(day=day(d),reason=str(ex),partial_orders=self.orders[lengths['orders']:])
    for k,v in snap.items():setattr(self,k,v)
    for k,n in lengths.items():del getattr(self,k)[n:]
    pending=p0;self._preflight_excluded=set();self.all_blockers=self.scan_restored_targets(d,pending);self.blockers.append(str(ex));print('ATOMIC_BLOCK '+str(ex),flush=True);break
   print('DAY '+day(d)+' orders='+str(len(self.orders))+' tickets='+str(len(self.live_tickets()))+' NAV='+self.ledger[-1]['NAV'],flush=True)
  self.pending=pending;return self
 def export(self,path):
  super().export(path);save(path/'AVAILABILITY_EVENTS.json',self.availability);pd.DataFrame(self.availability).to_csv(path/'AVAILABILITY_EVENTS.csv',index=False);save(path/'QUOTE_GAPS.json',self.quote_gaps);save(path/'OUTPUT_HASHES.json',{p.name:sha(p) for p in path.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})

def freeze_diff():
 unchanged=['info_open','info_close','request_key_groups','decorate','noncash','demand','sell_quantity','plan_transfers','execute_transfers','alloc_open','close','attribute','order','exit_open','net','cpvalid','accrue','register_pay']
 checks={name:getattr(Engine,name) is getattr(v1.Engine,name) for name in unchanged};assert all(checks.values())
 return dict(result='PASS',v1_engine_sha256=sha(V1/'engine.py'),unchanged_economic_methods=checks,overrides=['__init__','live_tickets:temporary_preflight_filter_only','economic_preflight:Q0_existing_ticket_quote_pause_gap_reverify','refresh_tickets:paused_known_false_cancel_only','run:exact_prefix_gate_and_complete_state_rollback_scan','export:added_availability_logs'],new_methods=['availability_event','pause_ticket','reverify_gap','scan_restored_targets'])

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['synthetic','run'],required=True);args=ap.parse_args()
 if args.mode=='synthetic':
  from synthetic_pause import run
  v=run();save(O/'SYNTHETIC_QA.json',v);save(O/'ECONOMIC_METHOD_IDENTITY_QA.json',freeze_diff());print(json.dumps(v))
 else:
  assert read(O/'CONTRACT_APPROVAL.json')['approved'];assert read(O/'SYNTHETIC_QA.json')['result']=='PASS';assert not (O/'RUN_STARTED.json').exists()
  data=Data();save(O/'FREEZE.json',dict(hashes=data.hashes,engine_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md'),explicit_pending_quote_semantics_extension=True,no_outcome_run=True));save(O/'RUN_STARTED.json',dict(time=str(pd.Timestamp.now(tz='UTC'))));e=Engine(data).run();e.export(O/'full_20241031_once');save(O/'RUN_STATUS.json',dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None));print(json.dumps(read(O/'RUN_STATUS.json')))
