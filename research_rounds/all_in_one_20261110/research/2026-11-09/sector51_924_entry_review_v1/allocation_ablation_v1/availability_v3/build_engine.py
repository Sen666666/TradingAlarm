from pathlib import Path
import sys,inspect,hashlib,json,shutil
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;OLD=O.parent;ROOT=OLD.parent
sys.path.insert(0,str(OLD));import ablation_engine as frozen
header='''"""New bounded availability/accounting semantics, not a fact-only revision."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import sys,json,copy,hashlib,importlib.util,argparse
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;OLD=O.parent;ROOT=OLD.parent
sys.path.insert(0,str(OLD));import ablation_engine as frozen
spec=importlib.util.spec_from_file_location('availability_core_v11',ROOT/'joint51_candidate_v11_suspension_accounting/engine.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
base=frozen.base;ZERO=base.ZERO;SLIP=base.SLIP;INITIAL=base.INITIAL
pd=base.pd;np=base.np;dec=base.dec;day=base.day;finite=base.finite;truth=base.truth;false=base.false;valid=base.valid;lineage=base.lineage;Blocked=core.Blocked
from allocation_rules import add_quantity_limit,arm_config,seed_capital_failure,ticket_from_seed,refresh_retained_ticket,m3_seed_exit
OLD_FAMILIES=frozen.FAMILIES+['RETRY_TICKETS','RETAINED_AT_END','ADDITIONAL_EXIT','ADD_QUANTITY_LIMITS','FULL_CAP_VIOLATIONS']

def known_origin(z):return all(z.get(k) is not None and pd.notna(z.get(k)) and str(z.get(k))!='' for k in ('source_kind','source_path','segment_id'))
def open_known(z):return known_origin(z) and all(finite(z.get(k)) and z[k]>0 for k in ('raw_open','adjustment_factor'))

class Data(base.Data):
 def __init__(self):
  base.O=O/'facts';super().__init__('2024-10-31')
  self.policies=base.read(O/'SUSPENSION_POLICY.json')['policies'];self.resume_sources={}
  for pol in self.policies:
   for stem in ['source','official_notice','official_text','fact_envelope']:
    p=pol[stem+'_path'];h=pol[stem+'_sha256'];assert base.sha(p)==h;self.hashes[p]=h
   anchor=self.z(pol['sid'],pd.Timestamp(pol['mark_source_day']));assert valid(anchor) and dec(anchor['raw_close'])==dec(pol['raw_mark']) and dec(anchor['adjustment_factor'])==dec(pol['factor']);pol['origin']=lineage(anchor)
   for ds in pol['covered_dates']:
    assert not len(self.z(pol['sid'],pd.Timestamp(ds)));assert self.stock.at[pd.Timestamp(ds),pol['sid']]==-1
   fact=base.read(pol['fact_envelope_path']);self.resume_sources[pol['sid']]=[x for x in fact.get('official_sources',[]) if x.get('role')=='RESUMPTION']
  for name in ['engine.py','CONTRACT.md','SUSPENSION_POLICY.json','synthetic_availability.py','SYNTHETIC_QA.json','build_engine.py']:self.hashes[str(O/name)]=base.sha(O/name)
 def suspension(self,s,d):
  return next((p for p in self.policies if p['sid']==s and day(d) in p['covered_dates']),None)
 def resume_notice_available(self,s,d):
  # Same-day publication without a historical pre-OPEN timestamp is insufficient.
  return any(x['publication_date']<day(d) for x in self.resume_sources.get(s,[]))

class Engine(frozen.AblationEngine):
 def __init__(self,data,arm):
  super().__init__(data,arm);self.quote_gaps={};self.held_gaps={};self.availability=[];self.suspension_log=[];self.preflight_log=[]
 suspension=core.Engine.suspension
 mark=core.Engine.mark
 qvalue=core.Engine.qvalue
 liquidation_value=core.Engine.liquidation_value
 suspension_preflight=core.Engine.suspension_preflight
 suspension_event=core.Engine.suspension_event
 net=core.Engine.net
 order=core.Engine.order
 exit_open=core.Engine.exit_open
 def avail(self,t,d,event,**kw):
  self.availability.append(dict(day=day(d),sid=t['sid'],ticket_id=t.get('ticket_id'),event=event,status=t.get('status'),original_signal_day=t.get('signal_day'),original_NAV=str(t['nav0']),last_verified_day=t.get('last_verified_day'),last_verified_factor=str(t.get('current_factor',t.get('factor'))),**kw))
 def pause(self,t,d,z):
  s=t['sid'];assert s not in self.active or self.quantity(self.active[s])==0
  if s not in self.quote_gaps:self.quote_gaps[s]=dict(start_day=day(d),last_verified_day=t['last_verified_day'],last_verified_factor=str(t['current_factor']),origin=t['origin'],days=[],action_inventory=[])
  gap=self.quote_gaps[s];gap['days'].append(day(d));gap['action_inventory'].extend(dict(day=day(d),action=a,reviewed_event=(s,d) in self.d.events) for a in self.d.action(s,d));t['status']='PAUSED_NO_QUOTE';t['plan']=None;t['reason']='CURRENT_OPEN_SOURCE_UNAVAILABLE'
  self.avail(t,d,'PAUSED_NO_QUOTE',source_identity_observed=known_origin(z),observed_open=z.get('raw_open') if finite(z.get('raw_open')) else None,pending_action_count=len(gap['action_inventory']))
 def verify_gap_chain(self,s,d,gap,held=False):
  expected=dec(gap['last_verified_factor']);origin=tuple(gap['origin']);start=pd.Timestamp(gap['last_verified_day']);dates=set(self.d.cal[(self.d.cal>start)&(self.d.cal<=d)])
  for event in self.d.actions[s]['events']:
   dt=pd.Timestamp(event['effective_date'])
   if start<dt<=d:dates.add(dt)
  dates|={dt for sid,dt in self.d.events if sid==s and start<dt<=d};checks=[]
  if hasattr(self.d,'manifest'):
   source=next(p for p in self.d.manifest[s]['source_sha256'] if p.endswith('/signal.parquet'));assert base.sha(source)==self.d.hashes[source]
  for when in sorted(dates):
   z=self.d.z(s,when);actions=self.d.action(s,when);ev=self.d.events.get((s,when))
   if known_origin(z) and lineage(z)!=origin:
    if held:raise Blocked(f'{day(d)} {s} HELD_GAP_SOURCE_CHANGED {day(when)}')
    return None,dict(changed_source_day=day(when))
   if actions and ev is None:raise Blocked(f'{day(d)} {s} GAP_UNADMITTED_EQUITY_EVENT {day(when)}')
   if ev:
    if abs(expected/dec(ev['factor_old'])-1)>D('1e-11'):raise Blocked(f'{day(d)} {s} GAP_FACTOR_CHAIN_OLD_MISMATCH {day(when)}')
    expected=dec(ev['factor_new'])
   observed=finite(z.get('adjustment_factor')) and z['adjustment_factor']>0
   if observed and abs(dec(z['adjustment_factor'])/expected-1)>D('1e-11'):raise Blocked(f'{day(d)} {s} GAP_UNADMITTED_FACTOR_CHANGE {day(when)}')
   checks.append(dict(day=day(when),event_id=ev.get('economic_event_id_candidate') if ev else None,factor_observed=bool(observed),verified_factor_chain=str(expected)))
  if not open_known(self.d.z(s,d)) or abs(dec(self.d.z(s,d)['adjustment_factor'])/expected-1)>D('1e-11'):raise Blocked(f'{day(d)} {s} GAP_FINAL_QUOTE_MISMATCH')
  return expected,checks
 def economic_preflight(self,d,pending):
  exclude=set();remove=set()
  if self.arm.retry_capital_seed:
   for s,t in list(self.retained.items()):
    if s in self.active and self.quantity(self.active[s])>0:raise Blocked(f'{day(d)} {s} RETAINED_TICKET_WITH_ACTUAL_HOLDING')
    z=self.d.z(s,d)
    if known_origin(z) and lineage(z)!=tuple(t['origin']):
     t['status']='CANCELLED';t['plan']=None;self.retry_record(t,d,'OPEN','SOURCE_CHANGED_CANCEL');self.avail(t,d,'KNOWN_SOURCE_CHANGED_CANCEL');self.retained.pop(s);self.quote_gaps.pop(s,None);remove.add(s);continue
    if not open_known(z):self.pause(t,d,z);exclude.add(s);remove.add(s)
    elif s in self.quote_gaps:
     factor,checks=self.verify_gap_chain(s,d,self.quote_gaps[s]);remove.add(s);exclude.add(s)
     if factor is None:
      t['status']='CANCELLED';t['plan']=None;self.avail(t,d,'GAP_SOURCE_CHANGED_CANCEL',**checks);self.retained.pop(s)
     else:
      t['current_factor']=factor;t['last_verified_day']=day(d);t['status']='RETAINED';t['plan']=None;t['reason']='GAP_REVERIFIED_WAIT_CLOSE';self.avail(t,d,'GAP_REVERIFIED_NO_OLD_OPEN_FILL',checks=checks)
     self.quote_gaps.pop(s,None)
  pending[:]=[r for r in pending if r['sid'] not in remove]
  all_pending=list(pending);queued={r['sid'] for r in all_pending}
  for s,t in self.retained.items():
   if s not in queued and s not in exclude:all_pending.append(dict(sid=s,origin=t['origin'],factor=t['current_factor'],ticket_id=t['ticket_id']))
  # Held policies do not supply a quote; capture original anchor and obligations.
  resumed=[]
  for s,a in self.active.items():
   pol=self.suspension(s,d)
   if pol and s not in self.held_gaps:self.held_gaps[s]=dict(last_verified_day=pol['mark_source_day'],last_verified_factor=str(a['factor']),origin=a['origin'],start_day=day(d))
   elif not pol and s in self.held_gaps and open_known(self.d.z(s,d)):
    if not self.d.resume_notice_available(s,d):raise Blocked(f'{day(d)} {s} HELD_RESUME_NOTICE_NOT_KNOWN_BEFORE_OPEN')
    factor,checks=self.verify_gap_chain(s,d,self.held_gaps[s],held=True);a['factor']=factor;resumed.append(s);self.suspension_event(a,d,'OPEN','HELD_RESUMPTION_VERIFIED',checks=checks);self.held_gaps.pop(s)
  # A resumed held chain has already been checked over its entire interval.
  held_saved={s:self.active.pop(s) for s in resumed}
  try:core.Engine.economic_preflight(self,d,all_pending)
  finally:self.active.update(held_saved)
  for s,t in self.retained.items():
   if s not in exclude:
    t['current_factor']=dec(self.d.z(s,d)['adjustment_factor']);t['last_verified_day']=day(d)
    if self.d.events.get((s,d)) is not None:self.retry_record(t,d,'OPEN','VERIFIED_PENDING_BRIDGE',record_qty=0,entitlement='0')
 def paused_close(self,s,t,d):
  sec=int(self.d.sectors[self.d.sid_sector[s]].at[d,'state']);st=int(self.d.stock.at[d,s]);i=self.d.f(s,d).get('i_target');reason='RETRY_SECTOR_FALSE' if sec==0 else 'RETRY_STOCK_M3_FALSE' if st==0 else 'RETRY_I_FALSE' if false(i) else None
  if reason:
   t['status']='CANCELLED';t['plan']=None;t['reason']=reason;self.avail(t,d,'KNOWN_FALSE_CANCEL_WHILE_NO_QUOTE',reason=reason);self.retained.pop(s);self.quote_gaps.pop(s,None)
  else:self.avail(t,d,'PAUSED_CLOSE_NO_PRICE_SIGNAL',sector_state=sec,stock_state=st)
'''
# Copy the already-frozen economic implementation, adding only explicit availability guards.
close=inspect.getsource(frozen.AblationEngine.close)
close=close.replace('pending=super().close(d,prev)','pending=core.Engine.close(self,d,prev)')
close=close.replace("   for s,t in list(self.retained.items()):\n    z=self.d.z(s,d)","   for s,t in list(self.retained.items()):\n    if s in self.quote_gaps:\n     self.paused_close(s,t,d);continue\n    z=self.d.z(s,d)")
alloc=inspect.getsource(frozen.AblationEngine.alloc_open)
old="   s=r['sid'];a=self.active.get(s);z=self.d.z(s,d);op=dec(z['raw_open']);p=op*(1+SLIP);fac=dec(z['adjustment_factor']);reason='PASS';net=None"
new="""   s=r['sid'];a=self.active.get(s)
   if self.suspension(s,d):
    self.candidates.append(dict(day=day(d),phase='OPEN',sid=s,round_id=a['id'] if a else None,event=r['kind'],signal_day=r['signal_day'],decision='SUSPENDED_NONTRADABLE',allocation_rank=rank+1,cp_id=r.get('cp_id'),planned_q=r['planned_q'],executed_q=0));continue
   z=self.d.z(s,d);op=dec(z['raw_open']);p=op*(1+SLIP);fac=dec(z['adjustment_factor']);reason='PASS';net=None"""
assert old in alloc;alloc=alloc.replace(old,new)
footer=''' def scan_blocked_targets(self,d,pending):
  rows=super().scan_blocked_targets(d,pending)
  for r in rows:
   s=r['sid'];z=self.d.z(s,d);t=self.retained.get(s)
   if r['held_qty']==0 and t is not None and not open_known(z) and not (known_origin(z) and lineage(z)!=tuple(t['origin'])):
    r['availability_boundary']='EXISTING_Q0_RETAINED_TICKET_PAUSABLE';r['deferred_quote_issues']=[x for x in r['issues'] if x in ('OPEN_MISSING','FACTOR_MISSING_OR_INVALID')];r['issues']=[x for x in r['issues'] if x not in r['deferred_quote_issues']]
   if self.suspension(s,d):
    r['availability_boundary']='OFFICIAL_SUSPENSION_STALE_ACCOUNTING';r['issues']=[x for x in r['issues'] if x not in ('OPEN_MISSING','FACTOR_MISSING_OR_INVALID')]
  return rows
 def export_ablation(self,path):
  super().export_ablation(path)
  for name,value in [('SUSPENSION_EVENTS',self.suspension_log),('PREFLIGHT_CHECKS',self.preflight_log),('AVAILABILITY_EVENTS',self.availability),('QUOTE_GAPS',self.quote_gaps),('HELD_GAPS',self.held_gaps)]:base.save(path/(name+'.json'),value)
  base.save(path/'OUTPUT_HASHES.json',{p.name:base.sha(p) for p in path.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
 def run_new(self,out,end,prefix_only=False):
  pending=[];prior=OLD/f'run_{self.arm.name}_fact2';old_end=base.read(prior/'RUN_STATUS.json')['certified_through'];passed=False
  keys=['cash','receivable','active','archive','seq','claims','snapshots','retained','quote_gaps','held_gaps'];logs=['orders','candidates','cp_log','profit','ledger','holdings','equity','sector_daily','retry_log','extra_exits','add_quantity_log','cap_violations','availability','suspension_log','preflight_log']
  for d in self.d.days[self.d.days<=pd.Timestamp(end)]:
   prev=self.d.cal[self.d.cal.get_loc(d)-1];snap=copy.deepcopy({k:getattr(self,k) for k in keys});p0=copy.deepcopy(pending);lengths={k:len(getattr(self,k)) for k in logs}
   try:
    self.economic_preflight(d,pending);self.accrue(d);self.exit_open(d);self.alloc_open(d,pending);pending=self.close(d,prev)
    if day(d)==old_end:
     self.pending=pending;p=out/'prior_prefix_replay';self.export_ablation(p);counts={}
     for name in OLD_FAMILIES:
      got=base.read(p/(name+'.json'));old=base.read(prior/'full_prefix'/(name+'.json'));assert got==old,('OLD_SEMANTIC_PREFIX_MISMATCH',self.arm.name,name);counts[name]=len(got)
     assert not self.availability and not self.suspension_log and not self.preflight_log and not self.quote_gaps and not self.held_gaps
     base.save(out/'PRIOR_PREFIX_REPLAY_QA.json',dict(result='PASS',through=old_end,exact_records=counts,new_logs_empty=True));passed=True;print('NEW_SEMANTIC_PREFIX_PASS '+self.arm.name+' '+old_end,flush=True)
     if prefix_only:break
    if day(d) in ('2024-09-30','2024-10-08'):
     self.pending=pending;self.export_ablation(out/('checkpoint_'+day(d)));print('CHECKPOINT '+self.arm.name+' '+json.dumps(self.ledger[-1]),flush=True)
   except Blocked as ex:
    self.uncertified_day=dict(day=day(d),reason=str(ex),partial_orders=self.orders[lengths['orders']:])
    for k,v in snap.items():setattr(self,k,v)
    for k,n in lengths.items():del getattr(self,k)[n:]
    pending=p0;self.blockers.append(str(ex));self.blocked_targets=self.scan_blocked_targets(d,pending);break
  self.pending=pending;self.export_ablation(out/'full_prefix');base.save(out/'RUN_STATUS.json',dict(arm=self.arm.name,new_semantics=True,not_fact_only=True,prior_prefix_exact=passed,days=len(self.ledger),orders=len(self.orders),last=self.ledger[-1] if self.ledger else None,blockers=self.blockers));return self

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['freeze','run'],required=True);ap.add_argument('--arms',default='A,E,F,B,D');ap.add_argument('--prefix-only',action='store_true');args=ap.parse_args()
 assert base.read(O/'SYNTHETIC_QA.json')['result']=='PASS'
 data=Data()
 if args.mode=='freeze':
  assert not (O/'FREEZE.json').exists();base.save(O/'FREEZE.json',dict(hashes=data.hashes,explicit_new_accounting_availability_semantics=True,old_implementation_hashes=base.read(OLD/'EXECUTION_FREEZE.json')['implementation_hashes']));print('FROZEN',len(data.hashes),flush=True)
 else:
  f=base.read(O/'FREEZE.json');assert data.hashes==f['hashes'];assert all(base.sha(p)==h for p,h in f['old_implementation_hashes'].items());assert base.read(O/'APPROVAL.json')['approved']
  for arm in args.arms.split(','):
   end='2024-10-08' if arm in ('B','D') else '2024-10-25';out=O/f'run_{arm}';out.mkdir(exist_ok=False);e=Engine(data,arm).run_new(out,end,prefix_only=args.prefix_only);print('RESULT '+json.dumps(base.read(out/'RUN_STATUS.json')),flush=True)
'''
(O/'engine.py').write_text(header+close+alloc+footer)
# Independent facts root: keep previous source/economic metadata immutable.
facts=O/'facts';facts.mkdir(exist_ok=False);oldfacts=OLD/'facts_revision_2'
for name in ['CLASSIFICATION_ALL1709.csv','MAPPING_SOURCE_HASHES.json','FROZEN_CONTRACT.md','engine.py','SYNTHETIC_QA.json','synthetic_joint.py','FACT_REVISION.json']:shutil.copyfile(oldfacts/name,facts/name)
p=ROOT/'joint_equity_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_20240930_RETAINED_THREE_V1.json';assert frozen.base.sha(p)=='074a6b77b415b7d392eb2bba4d5943fdda14d97ce15aada267cc52ed6109cd1c'
events=frozen.base.read(oldfacts/'ADDITIONAL_REVIEWED_EVENTS.json')+frozen.base.read(p);assert len(events)==len({(e['sid'],e['ex_date']) for e in events});frozen.base.save(facts/'ADDITIONAL_REVIEWED_EVENTS.json',events)
registry=frozen.base.read(ROOT/'joint51_candidate_v11_suspension_accounting/SUSPENSION_POLICY.json')
fp=ROOT/'joint_equity_evidence_v1/300489_suspension_v1/SUSPENSION_FACT_300489_V1.json';assert frozen.base.sha(fp)=='c92ba2699d23ff7cbe7bd8f82125554586641c5c9fe521bd62ce5779da4d4879';fact=frozen.base.read(fp);notice=next(x for x in fact['official_sources'] if x['role']=='INITIAL_SUSPENSION');source=next(p for p in fact['evidence_hashes'] if p.endswith('/signal.parquet'))
registry['policies'].append(dict(schema='explicit_suspension_accounting_v1',sid='300489.SZ',known_from_date='2024-09-30',covered_dates=['2024-09-30','2024-10-08'],mark_source_day='2024-09-27',raw_mark='22.78',factor='3.0113855556013487',source_path=source,source_sha256=fact['evidence_hashes'][source],notice_number=notice['notice_number'],official_notice_path=notice['path'],official_notice_sha256=notice['sha256'],official_text_path=notice['text_path'],official_text_sha256=notice['text_sha256'],fact_envelope_path=str(fp),fact_envelope_sha256=frozen.base.sha(fp),future_notices_or_resume_date_used_for_decisions=False))
frozen.base.save(O/'SUSPENSION_POLICY.json',registry)
print('BUILT_NEW_SEMANTICS_ENGINE')
