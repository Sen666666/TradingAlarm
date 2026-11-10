"""Isolated real-input binding of frozen G/S R4. Only authorized two-day prefixes.

Original Decimal ledger, native windows, settlement, fees and corporate actions
remain authoritative. No synthetic receipt/source or generated fill fallback.
"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,time,timedelta
from dataclasses import asdict
from decimal import Decimal as D
import sys,json,hashlib,copy,importlib.util,pickle,inspect
import pandas as pd
import native_capital as N
from native_capital import HistoricalReceipt,CapitalAccount,SyntheticRunner,Z,ONE,digest
from imports_native import C,LR,F1,IO,O,W,COMPOSITE,RULES,T,sha
from policy import Scope,UnknownRisk
LOADER_PATH=W/'g-s-readonly-historical-loader-r2-20261101/loader.py'
spec=importlib.util.spec_from_file_location('gs_frozen_loader_r2',LOADER_PATH);LD=importlib.util.module_from_spec(spec);sys.modules[spec.name]=LD;spec.loader.exec_module(LD)
INPUT=W/'g-s-readonly-historical-loader-r2-20261101/input-v1'
BASE_R4=W/'g-broad-s-concentrated-native-r4-20261101'
FROZEN=dict(R4='1649a09c73dde15134148cade02da8f27d7102d38f8a1370609934204a669665',loader='7c1f0e66833682924faa3fd0b1ac8a69bf01f69803af428149f1daba3676cbbf',input='1fbcf3cfc4d0b022cf02c7b9becee45b656596e25f10f3080f802c376788d82b',bootstrap='693bcafee5236c69f37cb063e458ba47e4637ffefe013de787432ed08a34bcc9',contract='a26b1959379ed6c7e8d82e35f9d3fca9dd050caa5e824850a0d75543005bcc50')

def guards():
 assert sha(BASE_R4/'native_capital.py')==FROZEN['R4']
 assert sha(LOADER_PATH)==FROZEN['loader']
 assert sha(INPUT.parent/'INPUT_PACKAGE_SHA256.json')==FROZEN['input']
 for path,h in LD.read(BASE_R4/'SOURCE_FREEZE.json')['binding']['sources'].items():assert sha(path)==h,('reviewed R4 dependency changed',path)
 for rel,h in LD.read(INPUT.parent/'INPUT_PACKAGE_SHA256.json').items():assert sha(INPUT/rel)==h,('reviewed input changed',rel)
 assert COMPOSITE==FROZEN['contract']
 assert sha(LD.B/'g-s-market-bootstrap-v1/PACKAGE_SHA256.json')==FROZEN['bootstrap']

def iso(s):return datetime.fromisoformat(s)
def payload_json(r):return LD.canonical(r)
def structure_key(row):
 if row['structure'] is None:return None
 return (row['sid'],int(row['facts']['segment_id']),row['structure'],bool(row['facts']['i_target']))

def registry(inputs):
 return {r['receipt_id']:payload_json(r) for r in inputs.obj('receipts') if r['confirmed_day']<=inputs.days[-1]}

def make_receipt(row,reg,source_binding):
 r=row['canonical_receipt']
 if r is None:return None
 structure=structure_key(row)
 if structure is None:raise UnknownRisk('fresh receipt has no known original structure '+row['sid'])
 text=payload_json(r['canonical_original'])
 if reg.get(r['event_id'])!=text:raise ValueError('receipt not in frozen canonical registry')
 return HistoricalReceipt(event_id=r['event_id'],sid=row['sid'],start=iso(r['start']),end=iso(r['end']),confirmed=iso(r['confirmed']),structure=structure,
   source='original_canonical_CP1_trace',scale='21',payload_json=text,payload_sha256=hashlib.sha256(text.encode()).hexdigest(),source_binding=source_binding)

class HistoricalMarket:
 """Original FrozenMarket methods over the physically frozen raw frames.

 __new__ only injects immutable saved inputs, avoiding a second raw loader or
 relaxed source-origin validator. Marks/window/fees/quantity/lag are ORIGINAL.
 """
 def __init__(self,inputs):
  self.inputs=inputs;self.protocol=inputs.protocol;self.prices={};self.known={};self.factors={};self.sectors={};self.stars={}
  native=C.N.FrozenMarket.__new__(C.N.FrozenMarket)
  lines={s:SimpleNamespace(**inputs.lines[s]) for s in inputs.ids}
  series={s:SimpleNamespace(record=copy.deepcopy(inputs.meta[s]['runtime_record'])) for s in inputs.ids}
  native.bundle=SimpleNamespace(lines=tuple(lines.values()),series=series,manifest_path=inputs.path)
  native.lines=lines;native.rules=inputs.rules;native.protocol=inputs.protocol
  native.cutoffs=tuple(iso(x) for x in inputs.rules['decision_cutoffs']);native.sessions={m:tuple(iso(x) for x in v) for m,v in inputs.rules['calendars'].items()}
  native.fx={};native._fx_times={};native._fx_cache={};native.notices=[];native._notice_keys={};native.raw={};native.actions={}
  for sid,f in inputs.table('raw').groupby('sid',sort=False):
   f=f.drop(columns=['sid']).set_index('day');f.index=pd.DatetimeIndex(f.index,name='date');f=f.sort_index()
   f['valid_price']=f.index.isin(C.N.eligible_prices(f).index)
   native.raw[sid]=f
  for sid in inputs.ids:
   native.actions[sid]=[r for r in inputs.obj('actions') if r['sid']==sid]
   self.sectors[sid]=inputs.lines[sid]['sector_id'];self.stars[sid]=sid.startswith('688')
  self.native=native
 def refresh(self,at):
  day=at.date().isoformat()
  for sid in self.inputs.ids:
   f=self.inputs.rows('facts',sid,day)
   if f and LD.finite(f['factor']):self.factors[sid]=D(str(f['factor']))
   try:m=self.native.latest_mark(sid,at)
   except (C.N.RuleUnavailable,KeyError):continue
   self.prices[sid]=m.raw_price;self.known[sid]=m.known_at
 def set(self,sid,price,at,sector,star):
  # Planning's source close is checked against the actual native known mark.
  m=self.native.latest_mark(sid,at)
  if D(str(price))!=m.raw_price:raise ValueError('source close differs from native raw mark '+sid)
  self.prices[sid]=D(str(price));self.known[sid]=at
 def marks(self,at,positions):return self.native.marks(at,positions)
 def quote(self,sid,at):return self.native.quotes(at,[sid]).get(sid)
 def quantity(self,sid,at):return self.native.quantity(sid,at)
 def fees(self,sid,at):return self.native.fees(sid,at)
 def window(self,sid,at,side):return self.native.window(sid,at,side,ONE)
 def lag(self,at,count):return self.native.lag('A',at,count)

class HistoricalFacts:
 def __init__(self,inputs,market):
  self.inputs=inputs;self.market=market;self.floors={};self.structure_lookup={}
  for sid in inputs.ids:
   r=inputs.rows('facts',sid,inputs.m['warm_through'])
   if r and LD.finite(r['i_floor']):self.floors[sid]=D(str(r['i_floor']))
 def factor(self,sid,at):
  value=self.market.factors.get(sid)
  if value is None or value<=0:raise UnknownRisk('missing known price factor '+sid)
  return value
 def floor(self,sid,at,kind):return self.floors.get(sid)

class HistoricalAccount(CapitalAccount):
 def __init__(self,inputs):
  market=HistoricalMarket(inputs);facts=HistoricalFacts(inputs,market)
  super().__init__('G_S_R4_HISTORICAL',market=market,facts=facts)
  self.canonical_registry=registry(inputs);self.canonical_binding=digest(self.canonical_registry)
  self.share_ratio={sid:ONE for sid in inputs.ids}
 def receipt_verified(self,c):
  if not isinstance(c,HistoricalReceipt) or c.source!='original_canonical_CP1_trace' or c.source_binding!=self.canonical_binding:return False
  if not c.payload_json or hashlib.sha256(c.payload_json.encode()).hexdigest()!=c.payload_sha256:return False
  if self.canonical_registry.get(c.event_id)!=c.payload_json:return False
  r=json.loads(c.payload_json)
  return r['canonical_series']==c.sid and r['receipt_id']==c.event_id and r['confirmed_day']==c.confirmed.date().isoformat() and r['formation_start_exclusive']==c.start.date().isoformat() and r['formation_end_inclusive']==c.end.date().isoformat() and not r['trace_unknown'] and c.scale=='21'
 def request_buy_cancel(self,sid):
  # Original historical native cancellation is synchronous. Preserve request
  # then actual ACK, never release before that callback or donate a receipt.
  super().request_buy_cancel(sid)
  if sid in self.buys:
   self.native_callbacks.append(dict(kind='historical_synchronous_cancel_ack',sid=sid,order=self.buys[sid].order_id,at=self.last_cursor))
   self.ack_buy_cancel(sid)

class HistoricalRunner(SyntheticRunner):
 def __init__(self,window,manifest=None):
  guards();self.window=window;self.inputs=LD.HistoricalInputs(manifest or INPUT/window/'MANIFEST.json')
  self.account=HistoricalAccount(self.inputs);self.f1={};self.f1seq={};self.cursor=datetime.fromisoformat(self.inputs.m['warm_through']).date().toordinal()
  self.lifecycle=[];self.last_stock_state={};self.last_completed_event=None;self.events=[];self.mapping=[];self.action_log=[];self.last_phase=None
  a=self.account;a.policy.cursor=self.cursor
  for seed in self.inputs.seeds.values():
   scope=seed['policy_scope'];ctx=seed['market_context'];self.f1[scope]=F1.loads(json.dumps(seed['f1_checkpoint']));self.f1seq[scope]=seed['scope_observation_sequence']
   a.policy.scopes[scope]=Scope(**{k:ctx[k] for k in ('source','seq','context','permit','support','mature','events')})
   a.policy.proof_history.extend(copy.deepcopy(ctx['proof_history']))
  assert not a.positions and not a.pending and not a.buys and not a.policy.k and not a.policy.losses and not a.policy.consumed
 def next_open(self,at):return next(s for s in self.account.market.native.sessions['A'] if s.date()>at.date())
 def stock_packet(self,at):
  day=at.date().isoformat();a=self.account;packet={};domain=[];mapped=[]
  for sid in self.inputs.ids:
   r=self.inputs.stock(sid,day,'CLOSE');f=r['facts'];why=[]
   q=r['retained_stock_Q']['value'];core=r['retained_core_event_Q']['value'] is True
   canonical=r['canonical_receipt'];i_valid=r['retained_stock_Q']['checks']['stock_up']
   quote=a.market.quote(sid,at) if q is True else None
   eligible=bool(q is True and i_valid is True and (core or canonical))
   if q is not True:why.extend(r['retained_stock_Q']['reasons'])
   if not core and not canonical:why.append('no_original_I_entry_or_fresh_CP1')
   if eligible and (quote is None or not f or not LD.finite(f['i_floor']) or structure_key(r) is None):raise UnknownRisk('qualified stock missing quote/floor/structure '+sid)
   receipt=make_receipt(r,a.canonical_registry,a.canonical_binding) if canonical and eligible else None
   row=dict(known_at=iso(LD.known(f['observed_day'])) if f else at,close=f['raw_close'] if f and f['observed_day']==day else None,
    i_valid=i_valid,q=eligible,core_event=core,receipt=receipt,i_floor=D(str(f['i_floor'])) if f and LD.finite(f['i_floor']) else None,
    cp_floor=D(str(canonical['canonical_original']['original_candidate'])) if canonical else None,structure=structure_key(r),priority=(0,sid),score=r['H1'])
   packet[sid]=row
   if eligible:domain.append(sid)
   mapped.append(dict(at=at,sid=sid,stock_Q=q,core_event=core,CP1_id=canonical['event_id'] if canonical else None,preliminary=eligible,barriers=why,original_I_key=r['original_I_structural_key'],original_E0_structure=r['structure']))
  rank=self.inputs.priority(day,domain);by={r['sid']:r for r in rank}
  for sid in domain:
   row=packet[sid];r=by[sid];row['priority']=(r['priority_rank'],sid);row['original_H1_rank']=r['original_H1_rank'];row['PVR_score']=r['PVR'];row['priority_policy']='PVR_SLOT1'
  self.mapping.append(dict(at=at,stocks=mapped,priority=rank));return packet
 def observations(self,day):
  return {r['policy_scope']:F1.Observation(day,F1.Source(**r['source']),r['price_input'],r['breadth']) for r in self.inputs.market_observations(day)}
 def planning(self,at,observations,stock_packet=None,**kw):
  a=self.account;a.last_cursor=at
  if stock_packet is not None:
   for sid,row in stock_packet.items():
    c=row.get('receipt')
    if c is not None and (not a.receipt_verified(c) or c.structure!=tuple(row['structure']) or c.confirmed!=at):raise ValueError('unverified/misaligned historical receipt '+sid)
  # Original same-day buy expiry: original actual cancel acknowledgement before
  # new close planning. No delayed credit, receipt refund, or lifespan extension.
  for sid,o in tuple(a.buys.items()):
   if at>=a.supports[o.order_id]['deadline']:a.request_buy_cancel(sid)
  super().planning(at,observations,stock_packet,**kw)
  for i in a.pending:
   row=stock_packet[i['sid']]
   for k in ('original_H1_rank','PVR_score','priority_policy','score'):i[k]=row.get(k)
 def corporate_actions(self,day):
  actions=self.inputs.actions(day)
  if not actions:return
  a=self.account;at=iso(day+'T00:00:00+08:00');a.market.refresh(at-timedelta(microseconds=1));a.last_cursor=at
  # Preflight ALL source terms before any financial mutation at this cursor.
  for r in actions:
   self.inputs.check_action_support(r,[z['qty'] for z in a.live(r['sid'])])
   sid=r['sid'];ratio=D(r['split_ratio']);quantities=[lot.shares for lot in a.positions[sid].lots] if sid in a.positions else []
   quantities += [e.remaining for e in a.policy.locks.values() if e.sid==sid]
   if sid in a.buys:
    order=a.buys[sid];quantities += [order.target_shares,order.remaining_shares,order.filled_shares,order.submitted_remaining]
   if sid in a.exits:
    order=a.exits[sid];quantities += [order.submitted_remaining]+([] if order.remaining_target is None else [order.remaining_target])
   if any(D(q)*ratio!=int(D(q)*ratio) for q in quantities):raise N.UnsupportedOperation('fractional action responsibility: atomic pre-action rejection')
   if a.quantity(sid) or sid in a.buys or any(i['sid']==sid for i in a.pending):
    current=self.inputs.rows('facts',sid,day,True)
    if current is None or not LD.finite(current['factor']):raise UnknownRisk('action has no known current coordinate factor '+sid)
  a.settle_due(at)
  for r in actions:
   sid=r['sid'];old=a.quantity(sid);cash=D(r['cash_per_old_share']);ratio=D(r['split_ratio']);event_id='original-action|'+sid+'|'+day+'|'+r['source_id']
   if old and cash:a.accrue_dividend(event_id='dividend:'+sid+':'+day,sid=sid,currency='CNY',net_local=D(old)*cash*D(a.market.protocol['dividend_net_factor']['A']),ex_at=at,paid_at=iso(r['paid_at']) if r['paid_at'] else None,source_id=r['source_id'],entitlement_basis='protocol_previous_close_inventory_and_explicit_net_factor')
   if ratio!=ONE:a.split(event_id='split:'+sid+':'+day,sid=sid,ratio=ratio,at=at,new_shares_sellable_at=iso(r['new_shares_sellable_at']) if r['new_shares_sellable_at'] else a.market.lag(at,a.market.protocol['bonus_sellable_lag_sessions']['A']))
   a.audit_log.append(dict(kind='original_action_source_observed',at=at,event_id=event_id,source=r,old_shares=old,cash_entitlement_gross=D(old)*cash))
   self.action_log.append(dict(at=at,event_id=event_id,source=r,old_shares=old,ratio=ratio,cash_entitlement_gross=D(old)*cash,payment_unknown=r['paid_at'] is None))
  a.market.refresh(at);self.last_completed_event=at;self.events.append(dict(at=at,phase='ACTION',bridge=a.bridge(at)))
 def payments(self,at):
  a=self.account
  for eid,ent in tuple(a.dividends.items()):
   if ent.paid_at is not None and ent.paid_at<=at:a.pay_dividend(eid,at=at,fx=a.market.native.rate(ent.currency,at),payment_evidence_id=ent.source_id+':declared-payment-field',payment_known_at=ent.paid_at)
 def opening(self,intents,at,capacities=None,*,buy_windows=None):
  if buy_windows is None or capacities is not None:raise ValueError('generated historical fill fallback forbidden')
  return super().opening(intents,at,buy_windows=buy_windows)
 def event(self,at,**kw):
  if kw.get('is_open') and (kw.get('buy_windows') is None or kw.get('sell_windows') is None):raise ValueError('actual native windows required')
  return super().event(at,**kw)
 def step(self,day,phase):
  if day not in self.inputs.days:raise ValueError('outside authorized two-day finance prefix')
  at=iso(day+('T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00'));a=self.account
  if self.last_completed_event and at<=self.last_completed_event:raise ValueError('completed financial event must not be rerun')
  a.market.refresh(at);a.last_cursor=at;a.settle_due(at);self.payments(at)
  if phase=='OPEN':
   bridge=self.event(at,is_open=True,buy_windows=lambda s,t:a.market.window(s,t,'buy'),sell_windows=lambda s,t:a.market.window(s,t,'sell'))
  elif phase=='CLOSE':bridge=self.event(at,observations=self.observations(day),stocks=self.stock_packet(at))
  else:raise ValueError('unsupported financial phase')
  self.last_phase=phase;self.events.append(dict(at=at,phase=phase,bridge=bridge))
  return bridge
 def observable(self,at):
  base=super().observable(at)
  base.update(events=self.events,mapping=self.mapping,action_log=self.action_log,account_audit=self.account.audit_log,decisions=self.account.decisions,
    pending=self.account.pending,actual_current_NAV=self.account.nav(at),initial_account='new original 1m, no imported SC/PVR economic state')
  return base
 def binding(self):
  paths=list(O.glob('*.py'))+[LOADER_PATH,BASE_R4/'native_capital.py',BASE_R4/'SOURCE_FREEZE.json',self.inputs.path,INPUT.parent/'INPUT_PACKAGE_SHA256.json',LD.B/'g-s-market-bootstrap-v1/PACKAGE_SHA256.json']
  paths.extend(Path(inspect.getsourcefile(c)) for c in C.Account.__mro__ if c is not object)
  paths += [Path(C.N.__file__),Path(F1.__file__),O/'imports_native.py',LOADER_PATH.parent/'SOURCE_FREEZE.json']
  return dict(policy='G_S_V2_R4_REAL_INPUT_TWO_SESSION_ONLY',window=self.window,contract=COMPOSITE,frozen=FROZEN,
   sources={str(p.resolve()):sha(p) for p in set(paths)},input_files=self.inputs.m['files'],engine=IO.runner_identity(self),
   native_callbacks={k:IO._code_fingerprint(getattr(type(self.account),k).__code__) for k in ('submit','route','fill_buy','fill_exit','split','trim','revalidate','resources','migrate','funding_reductions')})
 def checkpoint(self,path):
  path=Path(path);IO.write_pickle(path,self);IO.write_json(path.with_suffix('.provenance.json'),dict(checkpoint_sha256=sha(path),engine_identity=IO.runner_identity(self),binding=self.binding()))
 @classmethod
 def restore(cls,path):
  side=json.loads(Path(path).with_suffix('.provenance.json').read_text());raw=Path(path).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=side['checkpoint_sha256']:raise ValueError('checkpoint hash mismatch')
  r=pickle.loads(raw)
  if type(r) is not cls or IO.runner_identity(r)!=side['engine_identity'] or r.binding()!=side['binding']:raise ValueError('historical policy/source/input identity mismatch')
  return r
