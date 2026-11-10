"""Original N1 account planning/execution, batched over common immutable market facts."""
from pathlib import Path
import sys,time,json,gzip,copy,hashlib,inspect,importlib.util,collections
from decimal import Decimal as D
from datetime import datetime,date,time as dt,timezone
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/n1-structural-finite-20261029';SRC=ROOT/'research_rounds/broad-stage-reentry-20261029';START=time.monotonic();stage=sys.argv[1];assert stage in ['bench','full']
sys.path.insert(0,str(SRC/'code'));sp=importlib.util.spec_from_file_location('finite_original_n1',SRC/'code/study.py');M=importlib.util.module_from_spec(sp);sys.modules[sp.name]=M;sp.loader.exec_module(M)
pp=importlib.util.spec_from_file_location('finite_structural_protection',O/'code/policy.py');P=importlib.util.module_from_spec(pp);pp.loader.exec_module(P)
L,N,A=M.L,M.N,M.A;orig_advance=M.advance;nc=sys.modules['policy'].new_candidates;CURRENT={};memo={};memo_at=None;cache_counts=collections.Counter();perturb=[];ZERO=D(0)
def save(p,x):Path(p).write_text(json.dumps(N.encoded(x),ensure_ascii=False,indent=2,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
original_elig=A.eligibility
# Full-input equality on every cache hit proves the narrow lookup key is adequate.
def cached_elig(s,sectors,clock,variant):
 global memo_at,memo
 if memo_at!=clock.decision_at:memo={};memo_at=clock.decision_at
 key=(s.security_id,s.buy_allowed,variant);sector_key=tuple(sectors.items())
 if key in memo:
  old_s,old_sec,old_clock,result=memo[key];assert old_s==s and old_sec==sector_key and old_clock==clock;cache_counts['hit']+=1;return result
 result=original_elig(s,sectors,clock,variant);memo[key]=(s,sector_key,clock,result);cache_counts['miss']+=1;return result
A.eligibility=cached_elig
VERIFY_LIVE=True
class Account(M.Account):
 def live(self,sid):
  if not hasattr(self,'_live_index'):self._live_index={};self._live_indexed=0
  for z in self.layers[self._live_indexed:]:self._live_index.setdefault(z['sid'],[]).append(z)
  self._live_indexed=len(self.layers);result=[z for z in self._live_index.get(sid,()) if z['qty']]
  if VERIFY_LIVE:assert result==M.BP.Account.live(self,sid)
  return result
 def fill_buy(self,sid,w):
  f=super().fill_buy(sid,w)
  if f and getattr(self,'structural',False):self.layers[-1]['structural_base']=True
  return f

def dispatch(layer,day,close,e,f,c):
 if layer.get('structural_base') and layer['kind']!='mobile':return P.structural_advance(layer,day,close,e,f,c,orig_advance,nc)
 return orig_advance(layer,day,close,e,f,c)
M.advance=dispatch
original_fees=M.LR.fees
M.LR.fees=lambda q,p,fs,side,par=None:sum(fs.incremental(side,D(q)*p,{}, {},D(CURRENT.get('cost',1)),shares=q,par_value=par).values(),ZERO) if q else ZERO
whole=M.LR.whole_orders
PAIR=('300857.SZ','603039.SH');AT='2024-03-14T09:30:00+08:00'
def order_hook(order,items,cash):
 if not CURRENT.get('swap') or CURRENT.get('at')!=AT or items[0]['i']['group']!=0:return order
 hit=dict(path=CURRENT['path'],at=AT,group=0,pair=list(PAIR),cash=str(cash),before=list(order),present=all(s in order for s in PAIR),applied=False)
 if hit['present'] and not all(x['i']['kind']=='trial' and x['i']['reason'].startswith('first_') and x['i'].get('prior_flat_exit') is None for x in items if x['sid'] in PAIR):
  hit['present']=False;hit['reason']='not_first_new_trial_in_this_path'
 if hit['present']:
  i,j=order.index(PAIR[0]),order.index(PAIR[1]);hit['indices']=[i,j]
  if abs(i-j)==1:order=list(order);order[i],order[j]=order[j],order[i];hit['applied']=True
  else:hit['reason']='not_adjacent_in_this_path'
 else:hit['reason']='object_not_in_legal_preview_list'
 hit['after']=list(order);perturb.append(hit);return order
src=inspect.getsource(whole).replace('def whole_orders(items,cash):','def swapped_whole_orders(items,cash):').replace('order=sorted(by,key=lambda s:(-ideal[s]/by[s][\'cost\'](by[s][\'minq\']),s));left=cash;selected=[];audit=[]','order=sorted(by,key=lambda s:(-ideal[s]/by[s][\'cost\'](by[s][\'minq\']),s));order=order_hook(order,items,cash);left=cash;selected=[];audit=[]')
assert 'order=order_hook' in src;env=dict(M.LR.__dict__);env['order_hook']=order_hook;exec(src,env);swap_whole=env['swapped_whole_orders']
M.LR.whole_orders=lambda items,cash:swap_whole(items,cash) if CURRENT.get('swap') else whole(items,cash)
base=M.Pilot(only=['N1']);initsec=time.monotonic()-START;window=base.market.window;base.market.window=lambda sid,at,side,cost:window(sid,at,side,D(CURRENT.get('cost',cost)))
old=json.loads((SRC/'results/N1.json').read_text())
with gzip.open(SRC/'results/daily.jsonl.gz','rt') as f:old_daily=[json.loads(l) for l in f if '"account": "N1"' in l]
# Validate the frozen pair using the original saved legal preview/intent and market rules.
prior=next(d for d in old['decisions'] if d['at'].startswith('2024-03-13'))
for sid in PAIR:
 i=next(i for i in prior['intents'] if i['sid']==sid);assert i['group']==0 and i['kind']=='trial' and i['reason']=='first_CP1' and i.get('prior_flat_exit') is None
 at=N.iso(AT);w=window(sid,at,'buy',D(1));assert w and w.buy_allowed and w.quantity.buy_floor(w.capacity_shares)>=w.quantity.buy_minimum
 assert w.raw_open*base.facts.factor(sid,at)>D(i['floor'])
assert json.loads((O/'PERTURBATION.json').read_text())['pair']==list(PAIR)
slots=[('R_base_orig',False,1,False),('R_base_swap',False,1,True),('R_cost2_orig',False,2,False),('R_cost2_swap',False,2,True),('S_base_orig',True,1,False),('S_base_swap',True,1,True),('S_cost2_orig',True,2,False),('S_cost2_swap',True,2,True)]
def clones(slotlist):
 runners={}
 for name,structural,cost,sw in slotlist:
  r=copy.copy(base);r.accounts={'N1':Account('N1',r.market,r.facts)};a=r.accounts['N1'];a.structural=structural;a.cost_multiplier=D(cost);r.last_epoch={};r.epoch=collections.Counter();r.global_watch={};r.b0=N.B0Controller();r.applied_actions=set();r.daily=[];r.label=name;r.cost=cost;r.sw=sw;r.structural=structural;runners[name]=r
 return runners

def activate(r,at):CURRENT.update(path=r.label,cost=r.cost,swap=r.sw,at=at.isoformat());M.LR.SLIP=D('.0005')*r.cost

def batch_run(runners,end,after=None):
 start=N.iso('2023-12-29T15:10:00+08:00');finish=N.iso(end+'T15:10:00+08:00');cutoffs={x for x in base.market.cutoffs if start<=x<=finish};opens={x for x in base.market.sessions['A'] if start<=x<=finish};acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,N.TZ) for d in base.actions_by_date};events=sorted(cutoffs|opens|{x for x in acts if start<=x<=finish})
 for at in events:
  if after is not None and at<=after:continue
  for r in runners.values():
   activate(r,at)
   for a in r.accounts.values():a.settle_due(at)
   r._actions(at)
   for a in r.accounts.values():r._payments(a,at)
   if at in opens:
    before=len(perturb)
    for a in r.accounts.values():r.opening(a,at)
    if r.sw and at.isoformat()==AT and not any(x['path']==r.label for x in perturb[before:]):perturb.append(dict(path=r.label,at=AT,pair=list(PAIR),applied=False,reason='no_group0_legal_funded_allocation_batch'))
   if at in cutoffs:r.planning(at)
  if at in cutoffs and at.month in (1,7) and at.day<=3:print(json.dumps(dict(stage=stage,day=str(at.date()),rows=len(next(iter(runners.values())).daily),seconds=time.monotonic()-START)),flush=True)
  if time.monotonic()-START+json.loads((O/'REMAINING_BUDGET_TRACKER.json').read_text())['failed_date_serialization_attempt_wall_seconds']>900:raise TimeoutError('900s remaining approved calculation budget')
 return runners

def obj(r):
 a=r.accounts['N1'];return N.encoded(dict(trades=a.trades,layers=a.layers,audit=a.audit_log,counts=dict(a.counts),decisions=a.decisions,minimum_available=a.minimum_available))
def record_day(x):return (x.get('at') or x.get('receipt',{}).get('at') or x.get('receivable',{}).get('ex_at') or '')[:10]
if stage=='bench':
 runners=clones(slots);t1=time.monotonic();batch_run(runners,'2024-02-08');sim=time.monotonic()-t1;r=runners['R_base_orig'];actual=obj(r)
 for k in ['trades','audit','decisions']:assert actual[k]==[x for x in old[k] if record_day(x)<='2024-02-08'],k
 assert N.encoded(r.daily)==[x for x in old_daily if x['at'][:10]<='2024-02-08']
 n=len(r.daily);estimate=sim/n*681*7/8;oldtime=json.loads((O/'PREFLIGHT.json').read_text())['total_preflight_seconds'];result=dict(passed=True,baseline_prefix_exact=True,paths=8,closes=n,initialization_seconds=initsec,batch_simulation_seconds=sim,estimated_7_full_simulation_seconds=estimate,conservative_7_full_with_init_and_serialization_seconds=estimate*1.2+initsec+15,preflight_and_bench_seconds=oldtime+time.monotonic()-START,estimated_total_budget_seconds=oldtime+time.monotonic()-START+estimate*1.2+initsec+15,cache_counts=cache_counts,perturbation=perturb)
 save(O/'BATCH_PREFLIGHT.json',result);print(json.dumps(N.encoded(result),ensure_ascii=False),flush=True)
else:
 files=[O/'PROTOCOL.txt',O/'POLICY_DIFF.txt',O/'PERTURBATION.json',Path(__file__),O/'code/policy.py',SRC/'FREEZE-v2.json',SRC/'VERIFICATION.json',SRC/'results/N1.json',SRC/'results/daily.jsonl.gz']
 inherited=json.loads((SRC/'FREEZE-v2.json').read_text())['sha256'];identity={str(ROOT/k):v for k,v in inherited.items()}
 for p in files:identity[str(p)]=sha(p)
 for p,h in identity.items():assert sha(Path(p))==h,p
 save(O/'INPUT_IDENTITY.json',dict(sha256=identity,slots=slots,reused=['R_base_orig'],new_full_paths_max=7,remaining_budget_seconds=900,recorded_utc=datetime.now(timezone.utc).isoformat()))
 runners=clones(slots);t1=time.monotonic();batch_run(runners,'2024-03-14');prefix_seconds=time.monotonic()-t1
 validation=obj(runners['R_base_orig'])
 for k in ['trades','audit','decisions']:assert validation[k]==[x for x in old[k] if record_day(x)<='2024-03-14'],k
 assert N.encoded(runners['R_base_orig'].daily)==[x for x in old_daily if x['at'][:10]<='2024-03-14']
 import dataclasses
 def canonical(v):
  if dataclasses.is_dataclass(v):return {f.name:canonical(getattr(v,f.name)) for f in dataclasses.fields(v)}
  if isinstance(v,dict):return {str(k):canonical(a) for k,a in v.items()}
  if isinstance(v,set):return sorted((canonical(a) for a in v),key=lambda z:json.dumps(z,sort_keys=True))
  if isinstance(v,(tuple,list)):return [canonical(a) for a in v]
  if isinstance(v,(datetime,date,D,Path)):return str(v)
  return v
 def state(r):
  a=r.accounts['N1'];return dict(account={k:v for k,v in a.__dict__.items() if k not in {'audit_log','market','facts'}},market_memory={k:getattr(r,k) for k in ['last_epoch','epoch','global_watch','applied_actions']},b0=r.b0.__dict__)
 proofs=[];aliases={};active={k:r for k,r in runners.items() if k!='R_base_orig'}
 for prefix in ['R_base','R_cost2','S_base','S_cost2']:
  r,sr=runners[prefix+'_orig'],runners[prefix+'_swap'];aa,bb=state(r),state(sr);same=aa==bb
  ha=hashlib.sha256(json.dumps(canonical(aa),sort_keys=True,separators=(',',':')).encode()).hexdigest();hb=hashlib.sha256(json.dumps(canonical(bb),sort_keys=True,separators=(',',':')).encode()).hexdigest();assert same==(ha==hb)
  proofs.append(dict(paths=[prefix+'_orig',prefix+'_swap'],complete_transition_state_equal=same,original_state_sha256=ha,swapped_state_sha256=hb,account_keys=sorted(aa['account']),checkpoint_at='2024-03-14T15:10:00+08:00',random_state='none_deterministic',audit_is_output_not_transition_state=True))
  if same:active.pop(prefix+'_swap');aliases[prefix+'_swap']=dict(economic_source=prefix+'_orig',reuse_reason='full_transition_state_hash_equal_after_only_swap',prefix_audit_retained=True)
 save(O/'PREFIX_GATE.json',dict(passed=True,prefix_closes=len(runners['R_base_orig'].daily),baseline_daily_decisions_trades_audit_exact=True,index_cache_each_call_equal_original=True,original_prefix_source=SRC.as_posix(),prefix_seconds=prefix_seconds,initialization_seconds=initsec,active_suffixes=list(active),reuse_aliases=aliases,proofs=proofs,perturbation=perturb))
 VERIFY_LIVE=False
 # Cached list membership does not alter source executor state transitions.
 estimate=initsec+prefix_seconds+0.65*len(active)/3*(681-len(runners['R_base_orig'].daily))+35
 save(O/'RUN_PLAN.json',dict(remaining_budget_seconds=900,estimated_total_seconds=estimate,estimated_from_previous_late_three_account_seconds_per_close=.65,live_index_only_performance_cache=True,active_full_paths=list(active),baseline_reused='R_base_orig',aliases=aliases))
 print(json.dumps(dict(stage=stage,prefix_gate_passed=True,active_suffixes=list(active),aliases=aliases,estimated_total_seconds=estimate,seconds=time.monotonic()-START)),flush=True)
 assert estimate<=900,('remaining estimate exceeds900',estimate,list(active))
 dest=O/'full'
 try:batch_run(active,'2026-10-27',after=N.iso('2024-03-14T15:10:00+08:00'))
 finally:
  dest.mkdir(exist_ok=False)
  with gzip.open(dest/'daily.jsonl.gz','wt',compresslevel=1) as f:
   for name,r in active.items():
    for row in r.daily:f.write(json.dumps(dict(path=name,**N.encoded(row)),ensure_ascii=False)+'\n')
    save(dest/(name+'.json'),obj(r))
  save(dest/'RUN_META.json',dict(paths=list(active),reused_path='R_base_orig',run_seconds=time.monotonic()-t1,total_process_seconds=time.monotonic()-START,remaining_budget_seconds=900,perturbation=perturb,cache_counts=cache_counts,completed_closes={k:len(r.daily) for k,r in active.items()}))
 assert all(len(r.daily)==681 for r in active.values())
 for name,record in aliases.items():
  source=record['economic_source'];original=old if source=='R_base_orig' else obj(active[source]);copy_obj=copy.deepcopy(original);copy_obj['audit']=obj(runners[name])['audit']+[x for x in original['audit'] if record_day(x)>'2024-03-14'];save(dest/(name+'.json'),copy_obj)
 save(dest/'ALIASES.json',aliases)
 for p,h in identity.items():assert sha(Path(p))==h,p
 print(json.dumps(dict(stage=stage,completed=True,new_full_paths=len(active),aliases=len(aliases),total_seconds=time.monotonic()-START)),flush=True)
