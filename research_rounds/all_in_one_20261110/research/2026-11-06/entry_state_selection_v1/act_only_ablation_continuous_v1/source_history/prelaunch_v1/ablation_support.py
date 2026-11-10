"""Engineering gates and output-only comparisons. Never changes trade eligibility."""
from pathlib import Path
from types import SimpleNamespace
import copy,gzip,hashlib,json,inspect
from decimal import Decimal as D
import pandas as pd,numpy as np
ORIGINAL_STEP=None
FIXED_DATES={'2022-04-21','2022-04-22','2022-06-17','2023-08-15','2024-05-06','2024-09-24','2025-01-03','2025-03-14'}

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(path):return json.loads(Path(path).read_text())
def verify_static_freeze(root):
 for p,h in read(root/'STATIC_FREEZE.json').items():assert sha(p)==h,('static source changed',p)
def risk_dispatch(a,at,mode):
 assert mode=='ACT20_BREAK',('unexpected risk mode',mode)
 assert a.label in ('PVR','NOACT'),('unknown arm',a.label)
 if a.label=='NOACT':
  assert a.risk_state['on'] is True
  return ORIGINAL_STEP(a,at,'CONTROL')
 return ORIGINAL_STEP(a,at,mode)
def install_dispatch(policy):
 global ORIGINAL_STEP
 assert ORIGINAL_STEP is None,'risk dispatch may only be installed once'
 ORIGINAL_STEP=policy.step;policy.step=risk_dispatch

def static_checks(J,root,save):
 policy=J.M.E.risk_policy
 assert policy.step is risk_dispatch
 at=J.M.N.iso('2022-04-21T15:10:00+08:00')
 class Fixture:
  def __init__(self,label):
   self.label=label;self.current_nav=D(960000);self.risk_state=dict(on=True,peak=D(1200000),saw_off=False,previous_fast=False,episode=0)
   self.positions={};self.exits={};self.buys={};self.audit=[]
  def log(self,*args,**kwargs):self.audit.append((args,kwargs))
 base=Fixture('PVR');ref=copy.deepcopy(base);no=Fixture('NOACT');before=copy.deepcopy(vars(no))
 ORIGINAL_STEP(ref,at,'ACT20_BREAK');policy.step(base,at,'ACT20_BREAK');policy.step(no,at,'ACT20_BREAK')
 assert vars(base)==vars(ref) and base.risk_state['on'] is False
 assert vars(no)==before and no.risk_state['on'] is True
 assert 'account_risk' not in J.__dict__.get('_unused','')
 save(root/'STATIC_PREFLIGHT.json',dict(passed=True,original_ACT_dispatch_exact=True,NOACT_original_CONTROL_exact_noop=True,synthetic_threshold='0.20',real_accounts_run=0,original_risk_source=str(Path(policy.__file__).resolve()),original_risk_sha256=sha(policy.__file__),dispatcher_source=str(Path(__file__).resolve()),label_ids_not_rewritten=True))

def assert_isolation(r):
 a,b=r.accounts['PVR'],r.accounts['NOACT'];assert a is not b and a.budget is not b.budget
 for key in set(vars(a))&set(vars(b)):
  if key in ('market','facts'):continue
  x,y=getattr(a,key),getattr(b,key)
  if isinstance(x,(dict,list,set)):assert x is not y,('shared mutable account field',key)
 for key in set(vars(a.budget))&set(vars(b.budget)):
  x,y=getattr(a.budget,key),getattr(b.budget,key)
  if isinstance(x,(dict,list,set)):assert x is not y,('shared mutable budget field',key)
 assert a.label=='PVR' and b.label=='NOACT'

def check_native_wiring(r,J,A):
 r.assert_native_wiring();assert r.opening.__func__ is J.Runner.opening
 assert r.planning.__func__ is A.N.Runner.planning
 assert r.route.__func__ is A.P.ROUTES[True]
 assert 'account_risk' not in A.P.NEW_ROUTE
 assert A.P.RG not in A.P.NEW_ROUTE and A.P.RN in A.P.NEW_ROUTE
 assert A.P.MG not in A.P.NEW_MODEL and A.P.PG not in A.P.NEW_MODEL and A.P.PN in A.P.NEW_MODEL
 assert all(a.budget.exhausted_policy=='record_only' for a in r.accounts.values())
 assert J.M.E.risk_policy.step is risk_dispatch
 assert_isolation(r)

def iter_arm(path,label='PVR'):
 with gzip.open(path,'rt') as f:
  for line in f:
   r=json.loads(line)
   if r.get('account')==label:yield r

def first_difference(a,b,path='$'):
 if type(a)!=type(b) and not (isinstance(a,(int,float)) and isinstance(b,(int,float))):return dict(path=path,actual_type=type(a).__name__,expected_type=type(b).__name__)
 if isinstance(a,dict):
  if a.keys()!=b.keys():return dict(path=path,actual_keys=list(a),expected_keys=list(b))
  for k in a:
   q=first_difference(a[k],b[k],path+'.'+str(k))
   if q:return q
 elif isinstance(a,list):
  if len(a)!=len(b):return dict(path=path,actual_length=len(a),expected_length=len(b))
  for i,(x,y) in enumerate(zip(a,b)):
   q=first_difference(x,y,path+'['+str(i)+']')
   if q:return q
 elif a!=b:return dict(path=path,actual=repr(a)[:1000],expected=repr(b)[:1000])
 return None

class Baseline:
 def __init__(self,root,canon,save,out):
  self.root=root;self.canon=canon;self.save=save;self.out=out;self.days=0;self.trades_checked=0
  self.daily=iter_arm(root/'pair/daily.jsonl.gz')
  with gzip.open(root/'pair/PVR.json.gz','rt') as f:old=json.load(f)
  self.trades=old['trades'];self.risk={x['at'][:10]:x for x in old['audit'] if x.get('kind')=='risk_checkpoint'}
  self.old_source=read(root/'PREDECLARED.json')['source_freeze']
 def verify_frozen_original_sources(self):
  for p,h in self.old_source.items():assert sha(p)==h,('old baseline source drift',p)
  self.save(self.out/'ORIGINAL_SOURCE_REGRESSION.json',dict(passed=True,source_files=len(self.old_source),checks=self.old_source))
 def check_close(self,r,at):
  current=self.canon(next(x for x in reversed(r.daily) if x['account']=='PVR'));old=next(self.daily)
  difference=first_difference(current,old)
  if difference:self.save(self.out/'BASELINE_MISMATCH.json',dict(at=str(at),scope='daily',difference=difference));raise AssertionError(('PVR daily mismatch',at,difference))
  trades=r.accounts['PVR'].trades
  new=self.canon(trades[self.trades_checked:]);oldtr=self.trades[self.trades_checked:len(trades)]
  difference=first_difference(new,oldtr)
  if difference:self.save(self.out/'BASELINE_MISMATCH.json',dict(at=str(at),scope='incremental_trades',difference=difference));raise AssertionError(('PVR trade mismatch',at,difference))
  self.trades_checked=len(trades);self.days+=1
  if str(at.date()) in ('2022-01-31','2022-04-22'):
   self.save(self.out/('BASELINE_PREFIX_GATE_'+str(at.date())+'.json'),dict(passed=True,through=at,days=self.days,trades=self.trades_checked,daily_and_trades_exact=True))
 def finish_daily(self,r):
  assert next(self.daily,None) is None and self.days==1054 and self.trades_checked==len(self.trades)==len(r.accounts['PVR'].trades)
  self.save(self.out/'BASELINE_DAILY_EXACT.json',dict(passed=True,days=self.days,trades=self.trades_checked,numeric_tolerance=0,IDs_not_rewritten=True))

def order_invariant_payload(p):
 # Account ordering can only reorder account-attributed log chunks. Preserve
 # within-arm row order and every row/number/ID; never normalize economic state.
 p=dict(p);rr=dict(p['runner'])
 for k,v in rr.items():
  if isinstance(v,list) and v and all(isinstance(x,dict) and 'account' in x for x in v):rr[k]=sorted(v,key=lambda x:x['account'])
 p['runner']=rr;return p

def replay_open_gate(r,m,at,last,opens,closes,e3,event,payload,digest,poison,unpoison,out,save,initial):
 assert last is not None
 path=out/('restart_gate_initial' if initial else 'restart_gate_divergent')
 r.checkpoint(path,last);cpfile=path/'checkpoint.pkl';execn=len(m.exec_rows);counts=copy.copy(m.exec_counts);labels=list(r.accounts)
 needed=set().union(*(set(a.positions)|set(a.exits)|{i['sid']for i in a.pending} for a in r.accounts.values()))
 assert needed
 def restore():
  r.restore(cpfile);r.accounts={k:r.accounts[k] for k in labels};m.exec_rows=m.exec_rows[:execn];m.exec_counts=copy.copy(counts);assert_isolation(r)
 def snap():return digest(order_invariant_payload(payload(r)))
 event(r,m,at,opens,closes,e3);expected=snap()
 # Verify public OPEN access contract after native execution.
 sid=sorted(needed)[0];assert list(m.raw[sid].columns)==['open']
 blocked=[]
 for name,args in [('row',(sid,at)),('floor',(sid,at,'I')),('packet',(at,'I'))]:
  try:getattr(r.facts,name)(*args)
  except AssertionError:blocked.append(name)
  else:raise AssertionError(('future signal API allowed at OPEN',name))
 assert len(blocked)==3
 restore();r.accounts={k:r.accounts[k] for k in reversed(labels)};event(r,m,at,opens,closes,e3);reversed_digest=snap();assert reversed_digest==expected,('arm order mismatch',at)
 restore();backup=poison(m,at,needed)
 # Rebuild/remove future derived masks as well as poisoning raw/array HLCV.
 day=pd.Timestamp(at.date()).value//86400000000000
 for sid in needed:
  ar=m.arr[sid];k=np.searchsorted(ar['days'],day)
  for field in ('positive','good'):
   old=ar[field];backup.append(('array',ar,field,old));ar[field]=old[old<k].copy()
 try:
  event(r,m,at,opens,closes,e3);actual=snap();assert actual==expected,('restart/future perturb mismatch',at)
 finally:unpoison(backup)
 assert list(r.accounts)==labels
 result=dict(passed=True,at=at,previous_event=last,stocks_perturbed=len(needed),normal_sha256=expected,reversed_arms_sha256=reversed_digest,restored_future_poison_sha256=actual,checkpoint_guard_preserved=True,OPEN_only_columns=['open'],OPEN_blocked_apis=blocked,poisoned=['raw high low close volume current+future','array high low close volume valid current+future','positive good indices current+future removed'],original_inputs_written=False,scope='Full account state and runner logs exact; inter-arm log chunk order only normalized. Same pre-event checkpoint replay. Research-only event replay, no live orders.')
 save(out/('RESTART_OPEN_ORDER_GATE_'+str(at.date())+'.json'),result)
 return result

def fixed_event_check(r,at,baseline,out,save):
 day=str(at.date());p=r.accounts['PVR'];n=r.accounts['NOACT'];old=baseline.risk[day]
 assert baseline.canon(p.risk_state)=={k:old[k] for k in p.risk_state}
 assert n.risk_state['on'] and n.risk_state['episode']==0
 if day=='2022-04-21':assert not p.risk_state['on'] and p.exits
 if day=='2022-04-22':assert any(x['side']=='sell' and str(x['at'].date())==day and any(y.get('reason')=='ACT_pause' for y in x.get('parts',[])) for x in p.trades)
 save(out/('FIXED_EVENT_'+day+'.json'),dict(passed=True,at=at,PVR_risk=p.risk_state,NOACT_risk=n.risk_state,PVR_NAV=p.current_nav,NOACT_NAV=n.current_nav,PVR_stocks=len(p.positions),NOACT_stocks=len(n.positions),original_risk_event=old.get('event'),fixed_dates_used_only_for_verification=True))

def final_exact_regression(out,baseline,save):
 counts={};hashes={}
 with gzip.open(out/'pair/PVR.json.gz','rt') as f:actual=json.load(f)
 with gzip.open(baseline/'pair/PVR.json.gz','rt') as f:expected=json.load(f)
 diff=first_difference(actual,expected)
 if diff:save(out/'FINAL_BASELINE_MISMATCH.json',dict(scope='PVR account',difference=diff));raise AssertionError(('full PVR mismatch',diff))
 counts['PVR_account_fields']=list(actual);counts['PVR_trades']=len(actual['trades'])
 del actual,expected
 for name in ('daily','opportunities','funding','industry','balances','rank-policy'):
  a=iter_arm(out/'pair'/f'{name}.jsonl.gz');b=iter_arm(baseline/'pair'/f'{name}.jsonl.gz');count=0;h=hashlib.sha256()
  while True:
   x=next(a,None);y=next(b,None)
   if x is None or y is None:assert x is None and y is None,('stream length mismatch',name,count);break
   diff=first_difference(x,y)
   if diff:save(out/'FINAL_BASELINE_MISMATCH.json',dict(scope=name,row=count,difference=diff));raise AssertionError(('PVR stream mismatch',name,count,diff))
   h.update(json.dumps(x,sort_keys=True,separators=(',',':')).encode()+b'\n');count+=1
  counts[name]=count;hashes[name]=h.hexdigest()
 save(out/'FINAL_PVR_EXACT_REGRESSION.json',dict(passed=True,numeric_tolerance=0,IDs_not_rewritten=True,account_all_fields_exact=True,stream_counts=counts,canonical_stream_sha256=hashes))

def finish_metrics_and_hashes(out,save):
 annual=read(out/'ANNUAL_METRICS.json');old=read(out.parent.parent/'account_comparison_continuous_v1/run_1200000/ANNUAL_METRICS.json')
 assert [x for x in annual if x['account']=='PVR']==[x for x in old if x['account']=='PVR']
 rows={a:[] for a in ('PVR','NOACT')}
 with gzip.open(out/'pair/daily.jsonl.gz','rt') as f:
  for l in f:
   x=json.loads(l);rows[x['account']].append(x)
 summary=[]
 for arm,rr in rows.items():
  nav=np.array([1200000.]+[float(x['nav']) for x in rr]);dd=nav/np.maximum.accumulate(nav)-1
  summary.append(dict(account=arm,initial_NAV='1200000',end_NAV=rr[-1]['nav'],return_fraction=float(D(rr[-1]['nav'])/D(1200000)-1),max_drawdown_fraction=float(dd.min()),mean_inventory_fraction=float(np.mean([float(x['inventory'])/float(x['nav']) for x in rr])),mean_stock_count=float(np.mean([len(x['positions']) for x in rr])),paused_closes=sum(not x['on'] for x in rr)))
 save(out/'FULL_PERIOD_METRICS.json',summary)
 save(out/'OUTPUT_HASHES.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='OUTPUT_HASHES.json'})
