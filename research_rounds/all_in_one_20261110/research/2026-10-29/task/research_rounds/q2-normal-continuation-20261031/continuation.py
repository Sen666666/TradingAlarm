"""Original normal policies, explicit verified legacy import, Q2 input horizon."""
from pathlib import Path
import sys,inspect,textwrap,copy,pickle,json,gzip,hashlib,math
from dataclasses import is_dataclass,fields
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;END='2026-06-30';PARENT_END='2026-03-31'
sys.path.insert(0,str(O.parent/'execution-pressure-preflight-20261031'))
import pressure_runner as R
from initialization_guard import IO
J=R.J;L=R.L;BASE=R.BASE

INPUT_SOURCE=textwrap.dedent(inspect.getsource(L.inputs))
assert INPUT_SOURCE.count('J.END')==10
INPUT_SOURCE=INPUT_SOURCE.replace('J.END','END')
old="if old5.exists():assert states[sid]==read(old5),'Parquet state view differs from original case JSON'"
new="if old5.exists():\n   previous=read(old5);old_end=max(x['day'] for x in previous);assert [x for x in states[sid] if x['day']<=old_end]==previous,'Legacy case state prefix changed'"
assert INPUT_SOURCE.count(old)==1;INPUT_SOURCE=INPUT_SOURCE.replace(old,new)
env=dict(L.__dict__,END=END);exec(INPUT_SOURCE,env);inputs=env['inputs']
CHECKPOINT_SOURCE=textwrap.dedent(inspect.getsource(L.PreparedRunner.checkpoint))
assert CHECKPOINT_SOURCE.count("'actions_by_date'")==1
CHECKPOINT_SOURCE=CHECKPOINT_SOURCE.replace("'actions_by_date'","'actions_by_date','episode_starts'")
env2=dict(L.__dict__);exec(CHECKPOINT_SOURCE,env2)

def equal(a,b):
 if type(a) is not type(b):return False
 if isinstance(a,float) and math.isnan(a):return math.isnan(b)
 if isinstance(a,dict):
  if a.keys()!=b.keys():return False
  if hasattr(a,'default_factory') and a.default_factory!=b.default_factory:return False
  return all(equal(v,b[k]) for k,v in a.items())
 if isinstance(a,(list,tuple)):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
 if isinstance(a,(set,frozenset)):return a==b
 if isinstance(a,np.ndarray):return np.array_equal(a,b,equal_nan=True)
 if isinstance(a,(pd.DataFrame,pd.Series)):return a.equals(b)
 if is_dataclass(a):return all(equal(getattr(a,f.name),getattr(b,f.name)) for f in fields(a))
 if hasattr(a,'__dict__'):return equal(vars(a),vars(b))
 return bool(a==b)

def record_digest(rows):
 h=hashlib.sha256();count=0
 for x in rows:
  h.update(json.dumps(J.M.N.encoded(x),sort_keys=True,ensure_ascii=False,separators=(',',':'),default=J.C.encoded).encode());h.update(b'\n');count+=1
 return dict(records=count,sha256=h.hexdigest())
def file_rows(path):
 with gzip.open(path,'rt') as f:
  for line in f:
   x=json.loads(line)
   if x['account']=='B':yield x

class Continuation(L.PreparedRunner):
 reference='B3'
 def __init__(self,*args,**kw):
  super().__init__(*args,policies=('B',),**kw)
  if self.reference=='B_diag':BASE.enable(self.accounts['B'])
  assert self.planning.__func__ is J.Runner.planning and self.opening.__func__ is J.Runner.opening
 def checkpoint(self,out,last_event):
  import shutil
  env2['checkpoint'](self,out,last_event);out=Path(out)
  if str(last_event.date())==END:
   for suffix in ('pkl','json'):shutil.copyfile(out/('checkpoint.'+suffix),out/('checkpoint-'+END+'.'+suffix))
 def import_verified_legacy(self,parent,expected):
  """One explicit import; never weakens restore or backfills old provenance."""
  assert not getattr(self,'legacy_imported',False);a=self.accounts['B']
  assert a.available==a.initial_cash==J.D(1000000) and not a.positions and not a.trades and not a.buys
  path=Path(parent)/'checkpoint.pkl';h=L.sha(path);meta=L.read(Path(parent)/'checkpoint.json')
  assert h==expected['sha256']==meta['sha256'],'Legacy checkpoint SHA not equal to generation and preapproval evidence'
  assert not path.with_suffix('.provenance.json').exists(),'This import is only for the explicitly approved legacy files'
  p=pickle.loads(path.read_bytes());assert p['last_completed_event']==J.M.N.iso(PARENT_END+'T15:10:00+08:00')
  assert p['source_freeze']==meta['source_freeze']
  changes=[k for k,v in p['source_freeze'].items() if not Path(k).is_file() or L.sha(k)!=v];assert not changes,('Legacy frozen sources changed',changes)
  old=p['accounts']['B'];assert old['cost_multiplier']==1 and old['delay_events']==0 and old['mode']=='ACT' and not old['add_enabled']
  assert type(old['budget']) is (J.Budget if self.reference=='B3' else BASE.NoAccountBudget)
  with gzip.open(Path(parent)/'pair/B.json.gz','rt') as f:book=json.load(f)
  fields_map={'trades':'trades','layers':'layers','jmeta':'metadata','journal':'journal','buys':'orders','exits':'exits','audit_log':'audit','decisions':'decisions','available':'ending_cash','current_nav':'ending_NAV'}
  saved_checks={k:J.W.canon(old[k])==book[v] for k,v in fields_map.items()};assert all(saved_checks.values()),saved_checks
  budget=old['budget'];budget_check=dict(sectors=budget.sectors,orders=budget.orders,losses={str(k):v for k,v in budget.losses.items()},consumed=sorted(budget.consumed))
  assert J.W.canon(budget_check)==book['budget']
  log_fields={'daily':'daily','opportunities':'opportunities','funding':'funding','stage_events':'industry','balance_audit':'balances'};event_checks={}
  for field,name in log_fields.items():
   selected=(x for x in p['runner'][field] if x['account']=='B');left=record_digest(selected);right=record_digest(file_rows(Path(parent)/'pair'/(name+'.jsonl.gz')))
   assert left==right,(field,left,right);event_checks[field]=left
  old_derived=p['runner']['episode_starts'];assert all(self.episode_starts.get(k)==v for k,v in old_derived.items()),'Past E0 start identities changed'
  assert self.sector_by_sid==p['runner']['sector_by_sid']==old['sector_by_sid']
  strategy_keys=set(p['runner'])-{'source_freeze','episode_starts'}
  for k in strategy_keys:
   value=p['runner'][k]
   if k in log_fields:value=[x for x in value if x['account']=='B']
   setattr(self,k,copy.deepcopy(value))
  market,facts=a.market,a.facts;a.__dict__.clear();a.__dict__.update(copy.deepcopy(old));a.market=market;a.facts=facts
  account_checks={k:equal(v,a.__dict__[k]) for k,v in old.items()};assert all(account_checks.values()),[k for k,v in account_checks.items() if not v]
  runner_checks={}
  for k in strategy_keys:
   value=p['runner'][k]
   if k in log_fields:value=[x for x in value if x['account']=='B']
   runner_checks[k]=equal(value,getattr(self,k))
  assert all(runner_checks.values()),[k for k,v in runner_checks.items() if not v]
  at=p['last_completed_event'];marks=market.marks(at,a.positions);balance=a.balance(at,marks)
  assert balance['nav']==J.D(book['ending_NAV']) and abs(a.budget.nav-float(balance['nav']))<1e-6
  assert abs(a.budget.cash-a.budget.resources()[2]-float(a.available))<1e-6
  assert all(sum(x.qty for x in budget.lots if x.stock==sid)==pos.shares for sid,pos in a.positions.items())
  assert all(float(marks[sid].cny_price(at))==a.budget.prices[sid] for sid in a.positions)
  assert all(equal(v,a.__dict__[k]) for k,v in old.items()),'Read-only boundary verification changed account state'
  self.legacy_imported=True;self.parent_legacy_checkpoint=dict(path=str(path),sha256=h,last_completed_event=str(at),generation_identity_unknown=True,verified_and_imported_now=True)
  proof=dict(passed=True,reference=self.reference,parent=self.parent_legacy_checkpoint,generation_and_preapproval_SHA_match=True,original_frozen_source_count=len(p['source_freeze']),source_changes=[],saved_final_book_fields=saved_checks,budget_book_exact=True,all_five_complete_event_streams=event_checks,all_account_state_fields=account_checks,all_runner_strategy_fields=runner_checks,
   retained_old_episode_start_keys=len(old_derived),extended_derived_episode_map_not_live_state=len(self.episode_starts),account_NAV=str(balance['nav']),current_engine_identity=IO.runner_identity(self),old_identity_not_backfilled=True,old_file_not_written=True,actual_new_events_executed=0)
  return at,proof
class B3(Continuation):reference='B3';route=J.Runner.route
class Bdiag(Continuation):reference='B_diag';route=BASE.Runner.route

def observable(r):
 return dict(accounts={k:{n:v for n,v in a.__dict__.items() if n not in ('market','facts')} for k,a in r.accounts.items()},runner={k:v for k,v in r.__dict__.items() if k not in {'bundle','market','facts','accounts','cp','pv','matrix','matrix_days','industry_rows','industry_cp','receipts','actions_by_date','episode_starts','run_seconds'}})
