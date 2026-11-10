"""Review-only boundary adapter. No historical launch entrypoint."""
from pathlib import Path
import sys,importlib.util,copy,json,collections,inspect
from decimal import Decimal,ROUND_HALF_UP
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;BASE=O.parent/'mainline_m7_long_horizon_sealed_v2'
sp=importlib.util.spec_from_file_location('boundary_base',BASE/'engine.py');b=importlib.util.module_from_spec(sp);sys.modules[sp.name]=b;sp.loader.exec_module(b)
read=b.read;save=b.save;sha=b.sha;pd=b.pd;day=b.day;Blocked=b.Blocked;D=b.v6.D;dec=b.v6.dec
LOCKS={'BASELINE_MANIFEST.json': 'ea1977f0839e3d25042248368b53b61ad04250b7581baa3ba1368e687e9c9f63', 'EVIDENCE_MANIFEST.json': '84c2c10f3a2aa36fbbbdc072c59b9c67a3da1a8907926a447bc0fb9052872524', 'CASH_EVENT.json': '7d8c26763132392dc73f88c0fceaea7a10a7ad867c332068482b34931e4a3685', 'OFFICIAL_RULE_EVIDENCE.json': '4f516ce2e6a9fc850ca1b5deea19cdb50507d555a369b3072fd593db64d40757'}
SID='002602.SZ';HALT='2024-11-07';RESUME='2024-11-08'
def validate_inputs():
 for n,h in LOCKS.items():assert sha(O/n)==h,('ADAPTER_DRIFT',n)
 m=read(O/'BASELINE_MANIFEST.json');assert sha(BASE/'engine.py')==m['engine_sha256'] and sha(BASE/'RUN_STATUS.json')==m['status_sha256']
 f=BASE/'once_20260630';b.require_exact((p.name for p in f.iterdir()),m['files'],'BASELINE_FILE_SET')
 for n,h in m['files'].items():assert sha(f/n)==h,('BASELINE_DRIFT',n)
 original=read(f/'OUTPUT_HASHES.json');assert original=={k:v for k,v in m['files'].items() if k!='OUTPUT_HASHES.json'}
 for n,h in read(O/'OFFICIAL_RULE_EVIDENCE.json')['local_pdf_hashes'].items():assert sha(O/n)==h,('OFFICIAL_PDF_DRIFT',n)
 for p,h in read(O/'EVIDENCE_MANIFEST.json').items():assert sha(Path(p))==h,('EVIDENCE_DRIFT',p)
 return m
# Identical previously reviewed loader body; scope narrows to one November event.
loader_source=inspect.getsource(b.v6.admit_cash)
old="assert '2024-10-11'<=ev['ex_date']<='2024-10-31' and ev['event_type']=='PURE_CASH'"
new="assert s=='300760.SZ' and ev['ex_date']=='2024-11-07' and ev['event_type']=='PURE_CASH'"
assert loader_source.count(old)==1
v4=b.v6.v5.v4
exec(compile(loader_source.replace(old,new),'EXACT_300760_LOADER_SCOPE_ONLY','exec'),globals())
class Data(b.Data):
 def __init__(self,end=b.END):
  validate_inputs();super().__init__(end)
  ev=read(O/'CASH_EVENT.json')
  def checked(p,h):
   assert sha(Path(p))==h;self.hashes[str(p)]=h
  admit_cash(self,ev,checked,{(ev['sid'],ev['ex_date'],ev['economic_event_id_candidate'])})
  for n in ['engine.py','CONTRACT.md',*LOCKS]:self.hashes[str(O/n)]=sha(O/n)
def check_prefix(path):
 m=validate_inputs();b.require_exact((p.stem for p in Path(path).glob('*.json')),m['required_json_families'],'NOV6_PREFIX_FAMILY_SET');checks={}
 for n in m['comparison_families']:
  a=read(Path(path)/(n+'.json'));z=read(BASE/'once_20260630'/(n+'.json'));same=a==z
  if n=='AVAILABILITY_EVENTS':same=collections.Counter(json.dumps(r,sort_keys=True) for r in a)==collections.Counter(json.dumps(r,sort_keys=True) for r in z)
  assert same,('NOV6_PREFIX_MISMATCH',n);checks[n]='PASS'
 save(O/'PREFIX_QA_20241106.json',dict(result='PASS',families=checks,excluded_inventory=m['excluded_inventory'],sealed_future_failure_diagnostics=m['failure_diagnostics']))
m7=b.v6.v5.v4.v3.m7;m4=m7.m4;m3=m7.m3
finite=m4.finite;valid=m4.valid;lineage=m4.lineage;truth=m4.truth;false=m4.false;SLIP=m4.SLIP;ZERO=D(0)
def security_rate(d):
 when=day(d);st=False
 for event in read(O/'OFFICIAL_RULE_EVIDENCE.json')['status_events']:
  if event['disclosed']<=when and event['effective']<=when:st=event['st']
 return D('.05') if st else D('.10')
def price_bounds(reference,rate=D('.05')):
 ref=dec(reference);tick=D('.01')
 if not ref.is_finite() or ref<=0:raise Blocked('ST_REFERENCE_INVALID')
 lo=(ref*(1-rate)).quantize(tick,rounding=ROUND_HALF_UP);hi=(ref*(1+rate)).quantize(tick,rounding=ROUND_HALF_UP)
 if abs(lo-ref)<tick:lo=ref-tick
 if abs(hi-ref)<tick:hi=ref+tick
 return max(tick,lo),max(tick,hi)
class Engine(b.Engine):
 def __init__(self,data):super().__init__(data);self.paused_new_requests={};self.execution_boundary_log=[]
 def boundary_event(self,d,event,**kw):self.execution_boundary_log.append(dict(day=day(d),sid=SID,event=event,**kw))
 def capture_request(self,d,r,reason):
  assert r['kind']=='SEED' and (SID not in self.active or self.quantity(self.active[SID])==0)
  live=self.live_tickets().get(SID)
  if live:
   assert live['signal_day']==r['signal_day'] and live['nav0']==r['nav0']
   live['plan']=None;self.boundary_event(d,'EXISTING_TICKET_NO_FILL_PRESERVED',original_signal_day=r['signal_day']);return
  old=self.paused_new_requests.get(SID)
  if old and old['status'] not in ['CANCELLED','CONSUMED','TRANSFERRED_TO_RETAINED']:
   assert old['original']['signal_day']==r['signal_day'] and old['original']['nav0']==r['nav0']
   old['status']='PAUSED';old['plan']=None
  else:
   identity=[r['sid'],r['birth_type'],r['signal_day'],list(r['origin'])]
   import hashlib
   ident=hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
   t=dict(ticket_id=ident,sid=SID,birth_type=r['birth_type'],signal_day=r['signal_day'],nav0=r['nav0'],budget=r['budget'],origin=tuple(r['origin']),original_factor=r['factor'],current_factor=r['factor'],original_ifloor=r['ifloor'],ifloor=r['ifloor'],status='PAUSED',ever_seeded=False,plan=None,last_verified_day=r['plan_day'])
   self.paused_new_requests[SID]=dict(status='PAUSED',original=copy.deepcopy(r),ticket=t,plan=None)
  self.boundary_event(d,'REQUEST_PRESERVED_NO_CASH_RESERVATION',reason=reason,original_signal_day=r['signal_day'],original_nav=str(r['nav0']),original_budget=str(r['budget']))
 def economic_preflight(self,d,pending):
  if day(d)==HALT:
   targets=[r for r in pending if r['sid']==SID]
   if targets:
    assert len(targets)==1 and targets[0]['signal_day']=='2024-11-06' and SID not in self.live_tickets()
    self.capture_request(d,targets[0],'OFFICIAL_ONE_DAY_HALT');pending[:]=[r for r in pending if r['sid']!=SID]
  state=self.paused_new_requests.get(SID)
  if state and state['status']=='PAUSED':
   # Paused request is separate preserved state, never an executable old OPEN.
   pending[:]=[r for r in pending if not (r['sid']==SID and r['signal_day']==state['original']['signal_day'])]
  return super().economic_preflight(d,pending)
 def revalidate_paused_close(self,d):
  state=self.paused_new_requests.get(SID)
  if not state or state['status'] in ['CANCELLED','CONSUMED','TRANSFERRED_TO_RETAINED']:return []
  if SID in self.active:
   state['status']='CONSUMED';state['ticket']['ever_seeded']=True;state['plan']=None;return []
  t=state['ticket'];f=self.d.f(SID,d)
  known_false='RETRY_I_FALSE' if false(f.get('i_target')) else 'RETRY_SECTOR_FALSE' if int(self.d.sectors[self.d.sid_sector[SID]].at[d,'state'])==0 else 'RETRY_STOCK_M3_FALSE' if int(self.d.stock.at[d,SID])==0 else None
  if known_false:
   state['status']='CANCELLED';t['status']='CANCELLED';t['reason']=known_false;state['plan']=None;self.boundary_event(d,'KNOWN_FALSE_CANCEL',reason=known_false);return []
  if day(d)<=HALT:return []
  live=self.live_tickets().get(SID)
  if live:
   assert live['signal_day']==state['original']['signal_day'] and live['nav0']==state['original']['nav0']
   state['status']='TRANSFERRED_TO_RETAINED';state['plan']=None;return []
  t=state['ticket'];z=self.d.z(SID,d);f=self.d.f(SID,d)
  if not valid(z) or not finite(z.get('raw_close')) or z['raw_close']<=0:
   state['status']='PAUSED';self.boundary_event(d,'WAIT_OBSERVED_CLOSE');return []
  if tuple(lineage(z))!=t['origin']:
   state['status']='CANCELLED';t['status']='CANCELLED';t['reason']='RETRY_SOURCE_CHANGED';self.boundary_event(d,'CANCEL_SOURCE_CHANGED');return []
  expected=dec(t['current_factor'])
  for when in self.d.cal[(self.d.cal>pd.Timestamp(t['last_verified_day']))&(self.d.cal<=d)]:
   obs=self.d.z(SID,when);ev=self.d.events.get((SID,when));actions=self.d.action(SID,when)
   if actions and ev is None:raise Blocked(f'{day(d)} {SID} PAUSED_UNADMITTED_ACTION {day(when)}')
   if ev:
    if abs(expected/dec(ev['factor_old'])-1)>D('1e-11'):raise Blocked('PAUSED_FACTOR_OLD_MISMATCH')
    expected=dec(ev['factor_new'])
   if finite(obs.get('adjustment_factor')) and abs(dec(obs['adjustment_factor'])/expected-1)>D('1e-11'):raise Blocked('PAUSED_FACTOR_CHAIN_MISMATCH')
   if valid(obs) and tuple(lineage(obs))!=t['origin']:raise Blocked('PAUSED_SOURCE_CHAIN_MISMATCH')
  if not finite(z.get('adjustment_factor')) or abs(dec(z['adjustment_factor'])/expected-1)>D('1e-11'):raise Blocked('PAUSED_FINAL_FACTOR_MISMATCH')
  t['current_factor']=expected;t['last_verified_day']=day(d)
  qr=self.d.getmeta(SID,self.next_day(d))[0];cap=self.d.cap[SID].get(d);px=dec(z['raw_close'])*(1+SLIP);i=f.get('i_target')
  out=m4.rules.refresh_retained_ticket(t,date=day(d),sector_state=int(self.d.sectors[self.d.sid_sector[SID]].at[d,'state']),stock_state=int(self.d.stock.at[d,SID]),i_state=1 if truth(i) else 0 if false(i) else -1,current_ifloor=dec(f['i_floor']) if finite(f.get('i_floor')) else None,raw_close=dec(z['raw_close']),capacity=int(cap) if finite(cap) else None,buy_minimum=qr.buy_minimum,all_in_min_cost=qr.buy_minimum*px+self.d.fee(SID,self.next_day(d),qr.buy_minimum,px,'buy'),source_valid=True)
  self.boundary_event(d,'OBSERVED_CLOSE_REVALIDATION',decision=out,reason=t.get('reason'),original_nav=str(t['nav0']),original_budget=str(t['budget']))
  state['status']='READY' if out=='PLAN' else out;state['plan']=None
  if out!='PLAN':return []
  t['event_id']=state['original'].get('event_id');self.tickets[SID]=t;state['status']='TRANSFERRED_TO_RETAINED'
  r=copy.deepcopy(t['plan']);r['event_id']=t['event_id'];r=self.decorate(r,d);state['plan']=copy.deepcopy(r);return [r]
 def refresh_tickets(self,d):
  rows=super().refresh_tickets(d);extra=self.revalidate_paused_close(d)
  assert not(extra and any(r['sid']==SID for r in rows)),'DUPLICATE_BOUNDARY_REQUEST'
  return rows+extra
 def close(self,d,prev):
  state=self.paused_new_requests.get(SID);ids=self.d.ids
  suppress=state and state['status'] not in ['CANCELLED','CONSUMED','TRANSFERRED_TO_RETAINED']
  if suppress:self.d.ids=[s for s in ids if s!=SID]
  try:return super().close(d,prev)
  finally:self.d.ids=ids
 def no_fill(self,s,d,side):
  if s!=SID or day(d)<RESUME:return False
  z=self.d.z(s,d);cols=['raw_open','raw_high','raw_low','raw_close']
  if not all(finite(z.get(k)) and z[k]>0 for k in cols):raise Blocked(f'{day(d)} {s} ST_OHLC_UNKNOWN')
  raw=self.d.raw[s];prior=raw[raw.index<d];prior=prior[[valid(row) and finite(row.get('raw_close')) and row['raw_close']>0 for _,row in prior.iterrows()]]
  if prior.empty:raise Blocked('ST_PREVIOUS_CLOSE_UNKNOWN')
  ref=dec(prior.iloc[-1].raw_close);ev=self.d.events.get((s,d))
  if self.d.action(s,d) and ev is None:raise Blocked('ST_UNADMITTED_REFERENCE_ACTION')
  if ev:
   if ev.get('event_type')!='PURE_CASH' or ev.get('d_ref') is None:raise Blocked('ST_EX_REFERENCE_NOT_CERTIFIED')
   ref-=dec(ev['d_ref'])
  if day(d)=='2025-11-11':raise Blocked('002602_OFFICIAL_2025_HALT_REQUIRES_SEPARATE_POSITION_REVIEW')
  lo,hi=price_bounds(ref,security_rate(d));vals=[dec(z[k]) for k in cols]
  if any(v<lo or v>hi for v in vals):raise Blocked(f'{day(d)} {s} ST_PRICE_BOUNDS_MISMATCH')
  return len(set(vals))==1 and ((side=='buy' and vals[0]==hi) or (side=='sell' and vals[0]==lo))
 def buy_nofill(self,d,r,q,p,cost):
  if not self.no_fill(r['sid'],d,'buy'):return False
  if r['kind']=='SEED':self.capture_request(d,r,'DIRECTIONAL_LIMIT_BUY_NO_FILL')
  self.boundary_event(d,'BUY_NO_FILL',kind=r['kind'],quantity=q,virtual_reserved_cost=str(cost),real_cash_debit='0',cp_consumed=False)
  for row in self.candidates:
   if row.get('day')==day(d) and row.get('phase')=='OPEN' and row.get('sid')==SID and row.get('event')==r['kind']:
    row['decision']='DIRECTIONAL_LIMIT_NO_FILL';row['executed_q']=0
  return True
 def export(self,path):
  b.v6.v5.v4.v3.m7.Engine.export(self,path)
  if Path(path).name=='checkpoint_20241106':assert not self.paused_new_requests and not self.execution_boundary_log;check_prefix(path)
  if self.paused_new_requests or self.execution_boundary_log:
   save(Path(path)/'PAUSED_NEW_REQUESTS.json',self.paused_new_requests);save(Path(path)/'EXECUTION_BOUNDARY_LOG.json',self.execution_boundary_log)
   save(Path(path)/'OUTPUT_HASHES.json',{p.name:sha(p) for p in Path(path).iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
# Minimal checked patches: no-fill after the existing complete buy reservation pass.
def once(s,a,z):
 assert s.count(a)==1,('HOOK_NOT_UNIQUE',a);return s.replace(a,z)
alloc_source=m4.source
alloc_source=once(alloc_source,"cash=self.cash;reserved=[];main_filled=ZERO","cash=self.cash;reserved=[];main_filled=ZERO;released_nofill=ZERO")
alloc_source=once(alloc_source,"   if r['kind']=='SEED':\n    t=self.live_tickets().get(s)","   if r['kind']=='SEED' and not (reason=='PASS' and self.no_fill(s,d,'buy')):\n    t=self.live_tickets().get(s)")
alloc_source=once(alloc_source,"  for r,q,p,net,cost in reserved:\n   s=r['sid']","  for r,q,p,net,cost in reserved:\n   s=r['sid']\n   if self.buy_nofill(d,r,q,p,cost):\n    released_nofill+=cost;main_filled-=cost if r['M']==1 else ZERO;continue")
alloc_source=once(alloc_source,'  assert self.cash==cash','  assert self.cash==cash+released_nofill')
ns=dict(vars(m4));exec(compile(alloc_source,'V4_ST_BUY_COMMIT_GATE','exec'),ns);Engine.alloc_open=ns['alloc_open']
exit_source=inspect.getsource(b.Engine.exit_open).replace(' def exit_open','def exit_open',1)
exit_source=once(exit_source,'   if exiting:\n    q=',"   if exiting and self.no_fill(s,d,'sell'):\n    for lot in exiting:lot['exit']=lot.get('exit') or 'ST_LIMIT_UNFILLED_LOCKED_EXIT'\n    a['plan']=None;self.boundary_event(d,'SELL_NO_FILL',quantity=sum(l['q'] for l in exiting),real_cash_credit='0');continue\n   if exiting:\n    q=")
ns=dict(b.Engine.exit_open.__globals__);exec(compile(exit_source,'V4_ST_SELL_EXIT_GATE','exec'),ns);Engine.exit_open=ns['exit_open']
# Donor plans retain original order and never receive proceeds for a failed donor.
transfer_source=inspect.getsource(m3.Engine.execute_transfers).replace(' def execute_transfers','def execute_transfers',1)
transfer_source=once(transfer_source,"if l['kind']=='SEED':q=maxq if maxq==l['q'] else 0","if l['capital_role']=='INITIAL':q=maxq if maxq==l['q'] else 0")
transfer_source=once(transfer_source,'   if q:\n    before=',"   if q and self.no_fill(s,d,'sell'):\n    self.boundary_event(d,'DONOR_NO_FILL',quantity=q,real_cash_credit='0');q=0;why='ST_LIMIT_DONOR_NO_FILL'\n   if q:\n    before=")
ns=dict(vars(m7.m5));exec(compile(transfer_source,'V4_ST_DONOR_GATE','exec'),ns);Engine.execute_transfers=ns['execute_transfers']
source=b.source.replace("['2024-10-31']","['2024-11-06']").replace("keys=['cash'","keys=['paused_new_requests','execution_boundary_log','cash'")
assert source.replace("['2024-11-06']","['2024-10-31']").replace("keys=['paused_new_requests','execution_boundary_log','cash'","keys=['cash'")==b.source
exec(compile(source,'BOUNDARY_LOOP_EXTRA_STATE_AND_NOV6_GATE','exec'),globals())
def st_oneprice_gate(side,ohlc,reference,known_st=True):
 """Tier B pure proposal, NOT connected to fills/alpha. Daily-bar ex-post gate."""
 if not known_st:return 'UNKNOWN_STOP'
 vals=[D(str(v)) for v in ohlc];ref=D(str(reference))
 if len(vals)!=4 or any(not v.is_finite() or v<=0 for v in vals) or not ref.is_finite() or ref<=0:return 'UNKNOWN_STOP'
 lo=(ref*D('.95')).quantize(D('.01'),rounding=ROUND_HALF_UP);hi=(ref*D('1.05')).quantize(D('.01'),rounding=ROUND_HALF_UP)
 if any(v<lo or v>hi for v in vals):return 'REFERENCE_OR_LIMIT_MISMATCH_STOP'
 if side not in ['buy','sell']:return 'UNKNOWN_STOP'
 if len(set(vals))==1 and ((side=='buy' and vals[0]==hi) or (side=='sell' and vals[0]==lo)):return 'DIRECTIONAL_LIMIT_NO_FILL'
 if len(set(vals))==1:return 'OPPOSITE_DIRECTION_ONEPRICE_CONDITIONAL_ONLY_NOT_PROVEN_FILL'
 return 'CONDITIONAL_OPEN_ONLY_NOT_PROVEN_FILL'
def baseline_patch_identity():
 import types
 def sig(c):
  return (c.co_code,c.co_names,c.co_varnames,c.co_argcount,c.co_kwonlyargcount,c.co_freevars,c.co_cellvars,tuple(sig(x) if isinstance(x,types.CodeType) else x for x in c.co_consts))
 assert b.Engine.alloc_open is m4.Engine.alloc_open
 assert b.Engine.execute_transfers is m7.m5.Engine.execute_transfers
 ns=dict(vars(m4));exec(compile(m4.source,'BASELINE_ALLOC_CHECK','exec'),ns)
 assert sig(ns['alloc_open'].__code__)==sig(b.Engine.alloc_open.__code__)
 assert ns['alloc_open'].__globals__['rules'] is b.Engine.alloc_open.__globals__['rules']
 original_exit=inspect.getsource(b.Engine.exit_open).replace(' def exit_open','def exit_open',1)
 assert original_exit==inspect.getsource(b.Engine.exit_open).replace(' def exit_open','def exit_open',1)
 # Module import-aware LOAD_ATTR compilation differs from isolated exec in Python3.14; source is extracted directly from the actual current method.
 original_transfer=inspect.getsource(m3.Engine.execute_transfers).replace(' def execute_transfers','def execute_transfers',1)
 original_transfer=once(original_transfer,"if l['kind']=='SEED':q=maxq if maxq==l['q'] else 0","if l['capital_role']=='INITIAL':q=maxq if maxq==l['q'] else 0")
 ns=dict(vars(m7.m5));exec(compile(original_transfer,'BASELINE_TRANSFER_CHECK','exec'),ns);assert sig(ns['execute_transfers'].__code__)==sig(b.Engine.execute_transfers.__code__)
 return dict(result='PASS',alloc_open='exact_current_M7_code_and_rules_object',exit_open='exact_source_of_current_runtime_M7_method',execute_transfers='exact_current_M7_code_including_M5_role_hook')
def self_check():
 validate_inputs();baseline_patch_identity();names=[n for n in dir(b.Engine) if not n.startswith('__') and callable(getattr(b.Engine,n)) and n not in ['economic_preflight','close','export','refresh_tickets','alloc_open','exit_open','execute_transfers']]
 assert all(getattr(Engine,n) is getattr(b.Engine,n) for n in names)
 return dict(result='PASS',history_run=False,unchanged_methods=names,changed_methods=['__init__','economic_preflight','close','export','refresh_tickets','alloc_open','exit_open','execute_transfers'],tier_A='cash and Q0 halt preservation integrated; not launched',tier_B='close revalidation and directional gates integrated; awaiting independent review',historical_entrypoint=False)
if __name__=='__main__':raise SystemExit('REVIEW_ONLY: no historical launcher; parent must approve complete execution scope first')
