"""Two-session C history ENTRY PREPARATION. No account is constructed by prepare.

--execute is a future, explicit authorization-gated entry; it is NOT invoked by
readiness. The frozen native engine remains a separate immutable dependency.
"""
from pathlib import Path
from datetime import datetime,timedelta
from decimal import Decimal as D
from dataclasses import asdict
import sys,json,hashlib,pickle,copy,argparse,importlib

HERE=Path(__file__).resolve().parent;W=HERE.parent
ENGINE=W/'g-s-C-native-synthetic-v3-20261102'
sys.path.insert(0,str(ENGINE));import native_c as E
sys.path.insert(0,str(W/'g-s-historical-native-prefix-20261101'));import historical_binding as H
from policy import Scope
EXPECTED={'2022':['2022-01-04','2022-01-05'],'2025_26':['2025-07-01','2025-07-02']}
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(window):
 H.guards();x=H.LD.HistoricalInputs(H.INPUT/window/'MANIFEST.json');E.require(x.days==EXPECTED[window],'exact two-day original prefix required');return x
def engine_guard():
 b=read(HERE/'ENGINE_BINDING.json')
 for name,h in b['sources'].items():E.require(sha(ENGINE/name)==h,'engine revision requires new explicit binding: '+name)
 return b

class HistoricalAccount(E.Account):
 def __init__(self,owner,inputs):
  market=H.HistoricalMarket(inputs);facts=H.HistoricalFacts(inputs,market)
  E.N.CapitalAccount.__init__(self,'C_REAL_TWO_DAY_NEW_1M',market=market,facts=facts)
  self.policy=E.CPolicy();self.owner=owner;self.receipt_registry={};self.retained={}
  self.canonical_registry=H.registry(inputs);self.canonical_binding=E.digest(self.canonical_registry);self.share_ratio={s:E.ONE for s in inputs.ids}
 receipt_verified=H.HistoricalAccount.receipt_verified
 def request_buy_cancel(self,sid):
  super().request_buy_cancel(sid)
  if sid in self.buys:
   self.native_callbacks.append(dict(kind='original_historical_synchronous_ACK',sid=sid,at=self.last_cursor,order=self.buys[sid].order_id));self.ack_buy_cancel(sid)

class HistoricalRunner(E.Runner):
 def __init__(self,mode,window):
  engine_guard();self.inputs=load(window);self.window=window;self.mode=mode
  E.require(mode in ('C10','C_BATCH20'),'mode binding');self.account=HistoricalAccount(self,self.inputs)
  self.f1={};self.f1seq={};self.cursor=datetime.fromisoformat(self.inputs.m['warm_through']).date().toordinal()
  self.lifecycle=[];self.last_stock_state={};self.last_completed_event=None;self.budget=None;self.authority=E.Authority();self.trusted={};self.active=None;self.transitions=[];self.binding_id=None
  self.windows={};self.event_ids={};self.action_ids={};self.results=[];self.coverage=E.GoalCoverage();self.goal_intents={};self.local_wait_sids={};self._busy_goals={};self.close_stages={};self._required_close_plan_at=None
  self.events=[];self.mapping=[];self.action_log=[];self.last_phase=None;self.rank_bindings=[]
  a=self.account;a.policy.cursor=self.cursor
  for seed in self.inputs.seeds.values():
   scope=seed['policy_scope'];ctx=seed['market_context'];self.f1[scope]=E.F1.loads(json.dumps(seed['f1_checkpoint']));self.f1seq[scope]=seed['scope_observation_sequence']
   a.policy.scopes[scope]=Scope(**{k:ctx[k] for k in ('source','seq','context','permit','support','mature','events')});a.policy.proof_history.extend(copy.deepcopy(ctx['proof_history']))
  E.require(a.available==D(1000000) and not any((a.positions,a.pending,a.buys,a.exits,a.policy.k,a.policy.losses,a.policy.consumed,a.policy.locks,self.coverage.goals)),'new 1m finance state required; no old A/SC/PVR import')
 next_open=H.HistoricalRunner.next_open
 stock_packet=H.HistoricalRunner.stock_packet
 observations=H.HistoricalRunner.observations
 payments=H.HistoricalRunner.payments
 def corporate_actions(self,day):
  # Frozen synthetic engine does not yet transform an UNSUBMITTED authority
  # Q through a split. Refuse before native mutation instead of under-sizing.
  for action in self.inputs.actions(day):
   if D(action['split_ratio'])==1:continue
   sid=action['sid']
   for c in self.authority.certificates.values():
    submitted=any(o['cid']==c['certificate_id'] and o['sid']==sid for o in self.authority.orders.values())
    if c['Q'].get(sid,0) and not submitted and E.iso(c['deadline'])>=E.iso(day+'T00:00:00+08:00'):raise E.N.UnsupportedOperation('unsubmitted C certificate split quantity conversion not wired; atomic pre-action stop '+sid)
  return H.HistoricalRunner.corporate_actions(self,day)
 def _current_priority(self,at,intents):
  a=self.account;domain=set()
  for z in a.layers:
   sid=z['sid'];m=a.capital_meta[z['id']]
   if z['qty'] and m['role']=='mobile' and self.last_stock_state.get(sid,{}).get('i_valid') is True and sid not in a.buys and sid not in a.exits and not any(e.lot==z['id'] and e.remaining for e in a.policy.locks.values()) and a._current_holding_support(m['sector'])['use'] is not None:domain.add(sid)
  for i in intents:
   c=i['receipt'];sid=i['sid'];sec=i['sector']
   if i['stock_q'] and i['i_valid'] and c and a.receipt_verified(c) and c.confirmed==at and c.event_id not in a.policy.consumed and (a.policy.allowed(sec,'S') or a.policy.allowed('G','G')) and sid not in a.buys and sid not in a.exits and not any(e.sid==sid and e.remaining for e in a.policy.locks.values()):
    floor=max(i['I_floor'],D(i['cp_floor']))/a.facts.factor(sid,at)
    if a.market.prices[sid]>floor:domain.add(sid)
  rank=self.inputs.priority(at.date().isoformat(),sorted(domain));keys={r['sid']:tuple(r['new_full_key']) for r in rank}
  for sid,key in keys.items():self.last_stock_state[sid]['priority']=key
  for i in intents:
   if i['sid'] in keys:i['priority']=keys[i['sid']]
  return dict(at=at,domain=sorted(domain),source_priority=rank,rule='actual legal held-mobile union fresh expansion, no actual A decisions; core-only initial keys retained')
 def provider(self,at,intents,evidence):
  cursor=E.iso(at) if isinstance(at,str) else at
  self._current_priority(cursor,intents)
  return super().provider(at,intents,evidence)
 def planning(self,at,observations,stock_packet=None,**kwargs):
  for sid,row in (stock_packet or {}).items():
   c=row.get('receipt')
   if c is not None:E.require(self.account.receipt_verified(c) and c.structure==tuple(row['structure']) and c.confirmed==at,'real canonical/source/structure mismatch '+sid)
  evidence=self.industry_input(at);passed=kwargs.pop('industry_evidence',None)
  E.require(passed is None or E.digest(passed)==E.digest(evidence),'source industry H1 packet mismatch')
  return super().planning(at,observations,stock_packet,industry_evidence=evidence,**kwargs)
 def industry_input(self,at):
  h1={sec:(r['score'] if r and H.LD.finite(r['score']) else None) for sec in self.inputs.m['sectors'] for r in [self.inputs.rows('h1',sec,at.date().isoformat(),True)]}
  return dict(day=at.date().isoformat(),known_at=H.LD.known(at.date().isoformat()),industry_H1=h1,source_path=str(self.inputs.ref('h1')),source_sha256=sha(self.inputs.ref('h1')))
 def opening(self,intents,at,capacities=None,*,buy_windows=None):
  E.require(buy_windows is not None and capacities is None,'actual source windows required; synthetic fallback forbidden')
  return super().opening(intents,at,buy_windows=buy_windows)
 def event(self,at,**kwargs):
  if kwargs.get('is_open'):E.require(kwargs.get('buy_windows') is not None and kwargs.get('sell_windows') is not None,'actual source buy/sell windows required')
  if kwargs.get('observations') is not None and kwargs.get('industry_evidence') is None:kwargs['industry_evidence']=self.industry_input(at)
  return super().event(at,**kwargs)
 def step(self,day,phase):
  E.require(day in EXPECTED[self.window],'outside exact authorized two-day prefix')
  return H.HistoricalRunner.step(self,day,phase)
 def source_binding(self):
  out=super().source_binding();out.update({str(p):sha(p) for p in [Path(__file__),Path(H.__file__),H.LOADER_PATH,self.inputs.path,H.INPUT.parent/'INPUT_PACKAGE_SHA256.json',HERE/'ENGINE_BINDING.json']})
  return out
 def binding(self):
  return dict(mode=self.mode,window=self.window,days=EXPECTED[self.window],source=self.source_binding(),input_files=self.inputs.m['files'],engine=E.IO.runner_identity(self),scope='explicitly authorized exact two-day NEW account only')
 def observable(self,at):
  x=super().observable(at);x.update(window=self.window,events=self.events,mapping=self.mapping,action_log=self.action_log,pending=self.account.pending,input_manifest=str(self.inputs.path),input_sha256=sha(self.inputs.path));return x
 @classmethod
 def restore(cls,path):
  side=read(Path(path).with_suffix('.provenance.json'));E.require(sha(path)==side['checkpoint_sha256'],'checkpoint bytes changed')
  with Path(path).open('rb') as f:r=pickle.load(f)
  E.require(type(r) is cls and r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'exact native/input/source/mode identity required')
  r.account.owner=r;r.assert_observers()
  for c in r.authority.certificates.values():r.verify_native(c)
  return r

def prepare(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);binding=engine_guard();rows=[]
 for window in EXPECTED:
  x=load(window)
  for key in x.m['files']:x.ref(key)
  counts=[]
  for day in x.days:
   packets=[x.stock(s,day,'CLOSE') for s in x.ids]
   domain=[r['sid'] for r in packets if r['retained_stock_Q']['value'] is True and (r['retained_core_event_Q']['value'] is True or r['canonical_receipt'])]
   source_rank=x.priority(day,domain)
   h1={s:x.rows('h1',s,day,True) for s in x.m['sectors']}
   for action in x.actions(day):x.check_action_support(action,[])
   counts.append(dict(day=day,original_input_candidates=len(domain),canonical_all=sum(r['canonical_receipt'] is not None for r in packets),source_priority_rows=len(source_rank),industry_H1_unknown=[s for s,r in h1.items() if not r or not H.LD.finite(r['score'])],actions=x.actions(day)))
  rows.append(dict(window=window,days=x.days,manifest=str(x.path),manifest_sha256=sha(x.path),files=x.m['files'],fixed_stocks=len(x.ids),industries=len(x.m['sectors']),bootstrap_nodes=len(x.seeds),warm_through=x.m['warm_through'],initial_finance_spec=x.initial_financial_state_spec(),source_counts=counts,
   bootstrap_contexts=dict(active=sum(v['market_context']['support'] for v in x.seeds.values()),mature=sum(v['market_context']['mature'] for v in x.seeds.values())),eligibility_mapping=x.m['eligibility_mapping']))
 # Source-only adversarial key check; no Account or order object is needed.
 # C prepends industry to an original stock key, while core-only retains it.
 mixed_key_failure=False
 try:sorted([(0,0,0,'C-mobile'),(0,'T-core')])
 except TypeError:mixed_key_failure=True
 result=dict(status='READ_ONLY_PREPARED_NOT_FINANCIALLY_EXECUTED',engine=binding,entry_sha256=sha(__file__),windows=rows,account_factory_invoked=False,account_events=0,new_intents=0,old_accounts_imported=0,financial_gate='requires final engine independent PASS and explicit parent authorization file; entry native finance untested',native_dispatch_ready=False,
  source_only_dispatch_blocker=dict(confirmed_mixed_key_typeerror=mixed_key_failure,source='native_c.Runner.opening sorted(funded, supports.priority)',reason='industry-prefixed C expansion keys versus original core-only stock keys have heterogeneous shape; requires affected native mixed-role gate before release, not an ad-hoc new order priority'),
  unsubmitted_split_note='688608 has no core/fresh CP1 on Jul1, so exact initial two-day path cannot submit it before Jul2 action; source event still processed; general live-authority split explicitly blocked')
 E.IO.write_json(out/'READINESS.json',result);print(json.dumps({k:result[k] for k in ['status','account_factory_invoked','account_events','new_intents','old_accounts_imported']},indent=2))
def execute(args):
 # This gate is before ANY Account construction or checkpoint unpickling.
 E.require(args.authorization is not None,'no historical authorization supplied')
 auth=read(args.authorization);x=load(args.window);review=engine_guard()
 E.require(review['status']=='INDEPENDENT_REVIEW_PASS','entry/engine pending independent dispatch review; no account construction')
 expected=dict(scope='C_TWO_DAY_PREFIX_ONLY',parent_approved=True,historical_financial_events_authorized=True,mode=args.mode,window=args.window,days=EXPECTED[args.window],initial_cash_cny='1000000',entry_sha256=sha(__file__),engine_sources=read(HERE/'ENGINE_BINDING.json')['sources'],input_manifest_sha256=sha(x.path))
 E.require(all(auth.get(k)==v for k,v in expected.items()),'explicit current root scope/source/input authorization mismatch')
 args.out.mkdir(parents=True,exist_ok=False)
 r=HistoricalRunner.restore(args.resume) if args.resume else HistoricalRunner(args.mode,args.window)
 E.require(r.mode==args.mode and r.window==args.window,'resume account/mode/window mismatch')
 for day in EXPECTED[args.window]:
  action_at=E.iso(day+'T00:00:00+08:00')
  try:
   if r.inputs.actions(day) and (r.last_completed_event is None or action_at>r.last_completed_event):r.corporate_actions(day);r.checkpoint(args.out/(day+'-ACTION.pkl'))
   for phase in ('OPEN','CLOSE'):
    at=E.iso(day+('T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00'))
    if r.last_completed_event is not None and at<=r.last_completed_event:continue
    r.step(day,phase);r.checkpoint(args.out/(day+'-'+phase+'.pkl'));E.IO.write_json(args.out/(day+'-'+phase+'.json'),r.observable(at),encoder=E.encode)
    if phase=='CLOSE' and r.close_stages[at.isoformat()]['optional_status']!='succeeded':raise ValueError('required CLOSE saved; optional planning blocked: inspect checkpoint and retry explicitly')
  except Exception as exc:
   E.IO.write_json(args.out/'ERROR.json',dict(day=day,cursor=r.last_completed_event,error=type(exc).__name__+': '+str(exc),scope='stop, never delete source event/stock'),encoder=E.encode)
   r.checkpoint(args.out/'failure-state.pkl');raise
 E.IO.write_json(args.out/'COMPLETED.json',dict(window=args.window,mode=args.mode,cursor=r.last_completed_event,source=r.binding(),authorization_sha256=sha(args.authorization)),encoder=E.encode)
def cli():
 p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--window',choices=EXPECTED);p.add_argument('--mode',choices=['C10','C_BATCH20']);p.add_argument('--authorization',type=Path);p.add_argument('--resume',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 E.require(a.prepare!=a.execute,'choose preparation or explicitly authorized execution')
 if a.prepare:prepare(a.out)
 else:E.require(a.window and a.mode,'exact mode/window required');execute(a)
if __name__=='__main__':importlib.import_module(Path(__file__).stem).cli()
