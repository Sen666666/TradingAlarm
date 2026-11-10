"""Original N1 account planning/execution, batched over common immutable market facts."""
from pathlib import Path
import sys,time,json,gzip,copy,hashlib,inspect,importlib.util,collections
from decimal import Decimal as D
from datetime import datetime,time as dt,timezone
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
class Account(M.Account):
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
PAIR=('688728.SH','688002.SH');AT='2024-02-08T09:30:00+08:00'
def order_hook(order,items,cash):
 if not CURRENT.get('swap') or CURRENT.get('at')!=AT or items[0]['i']['group']!=0:return order
 hit=dict(path=CURRENT['path'],at=AT,group=0,pair=list(PAIR),cash=str(cash),before=list(order),present=all(s in order for s in PAIR),applied=False)
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
prior=next(d for d in old['decisions'] if d['at'].startswith('2024-02-07'))
for sid in PAIR:
 i=next(i for i in prior['intents'] if i['sid']==sid);assert i['group']==0 and i['kind']=='mobile' and i['reason']=='CP1_mobile'
 at=N.iso(AT);w=window(sid,at,'buy',D(1));assert w and w.buy_allowed and w.quantity.buy_floor(w.capacity_shares)>=w.quantity.buy_minimum
 assert w.raw_open*base.facts.factor(sid,at)>D(i['floor'])
assert all(any(z['sid']==sid and z['kind']=='core' for z in next(d for d in old_daily if d['at'].startswith('2024-02-07'))['layers']) for sid in PAIR)
source_events=[x for x in old['audit'] if x['kind']=='lot_allocation' and x['at'].startswith('2024-02-08') and x['sid'] in PAIR];assert len(source_events)==2 and source_events[0]['minimum_selected'] and not source_events[1]['minimum_selected']
freeze=dict(at=AT,signal_at=prior['at'],priority_group=0,pair=list(PAIR),original_order=list(PAIR),source_allocation=source_events,both_legal_previews=True,both_existing_core_mobile=True,not_claimed_initial_stock_selection=True,rule='swap only if both currently legal and adjacent, else unexposed; once only')
if stage=='bench':save(O/'PERTURBATION.json',freeze)
else:assert json.loads((O/'PERTURBATION.json').read_text())==N.encoded(freeze)
slots=[('R_base_orig',False,1,False),('R_base_swap',False,1,True),('R_cost2_orig',False,2,False),('R_cost2_swap',False,2,True),('S_base_orig',True,1,False),('S_base_swap',True,1,True),('S_cost2_orig',True,2,False),('S_cost2_swap',True,2,True)]
def clones(slotlist):
 runners={}
 for name,structural,cost,sw in slotlist:
  r=copy.copy(base);r.accounts={'N1':Account('N1',r.market,r.facts)};a=r.accounts['N1'];a.structural=structural;a.cost_multiplier=D(cost);r.last_epoch={};r.epoch=collections.Counter();r.global_watch={};r.b0=N.B0Controller();r.applied_actions=set();r.daily=[];r.label=name;r.cost=cost;r.sw=sw;r.structural=structural;runners[name]=r
 return runners

def activate(r,at):CURRENT.update(path=r.label,cost=r.cost,swap=r.sw,at=at.isoformat());M.LR.SLIP=D('.0005')*r.cost

def batch_run(runners,end):
 start=N.iso('2023-12-29T15:10:00+08:00');finish=N.iso(end+'T15:10:00+08:00');cutoffs={x for x in base.market.cutoffs if start<=x<=finish};opens={x for x in base.market.sessions['A'] if start<=x<=finish};acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,N.TZ) for d in base.actions_by_date};events=sorted(cutoffs|opens|{x for x in acts if start<=x<=finish})
 for at in events:
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
  prior_budget=json.loads((O/'PREFLIGHT.json').read_text())['total_preflight_seconds']
  if time.monotonic()-START+prior_budget>300:raise TimeoutError('300s cumulative preflight+batch budget')
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
 pre=json.loads((O/'BATCH_PREFLIGHT.json').read_text());assert pre['passed'] and pre['estimated_total_budget_seconds']<=300,'estimated budget exceeds300s; stop before economic'
 files=[O/'PROTOCOL.txt',O/'POLICY_DIFF.txt',O/'PERTURBATION.json',Path(__file__),O/'code/policy.py',SRC/'FREEZE-v2.json',SRC/'VERIFICATION.json',SRC/'results/N1.json',SRC/'results/daily.jsonl.gz']
 inherited=json.loads((SRC/'FREEZE-v2.json').read_text())['sha256'];identity={str(ROOT/k):v for k,v in inherited.items()}
 for p in files:identity[str(p)]=sha(p)
 for p,h in identity.items():assert sha(Path(p))==h,p
 save(O/'INPUT_IDENTITY.json',dict(sha256=identity,slots=slots,reused=['R_base_orig'],new_full_paths=7,recorded_utc=datetime.now(timezone.utc).isoformat()))
 runners=clones(slots[1:]);t1=time.monotonic()
 try:batch_run(runners,'2026-10-27')
 finally:
  dest=O/'full';dest.mkdir(exist_ok=False)
  with gzip.open(dest/'daily.jsonl.gz','wt',compresslevel=1) as f:
   for name,r in runners.items():
    for row in r.daily:f.write(json.dumps(dict(path=name,**N.encoded(row)),ensure_ascii=False)+'\n')
    save(dest/(name+'.json'),obj(r))
  save(dest/'RUN_META.json',dict(paths=list(runners),reused_path='R_base_orig',run_seconds=time.monotonic()-t1,total_process_seconds=time.monotonic()-START,prior_preflight_and_bench_seconds=pre['preflight_and_bench_seconds'],perturbation=perturb,cache_counts=cache_counts,completed_closes={k:len(r.daily) for k,r in runners.items()}))
 assert all(len(r.daily)==681 for r in runners.values())
 for p,h in identity.items():assert sha(Path(p))==h,p
 print(json.dumps(dict(stage=stage,completed=True,new_paths=7,total_seconds=time.monotonic()-START)),flush=True)
