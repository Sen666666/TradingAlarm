"""Explicit own2023-state->2024 identity transition; unchanged native policies."""
from pathlib import Path
import copy,gzip,json,pickle,sys,shutil
import loader_2024 as D
N,J,L,IO,W=D.N,D.J,D.L,D.IO,D.W
OLD=W/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness'
sys.path.insert(0,str(OLD));import horizon_import as H
POOL=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility')
sys.path.insert(0,str(POOL));import native_adapter as A
sys.path.insert(0,str(POOL/'continuation2023'));import horizon_adapter as V
E=H.E;O=D.O;sha,read=D.sha,D.read
PARENT_AT=J.M.N.iso('2023-12-29T15:10:00+08:00');END='2024-12-31'
OLD_SCORE=OLD/'SCORES_MANIFEST.json';NEW_SCORE=O/'SCORES_MANIFEST.json'
PARENTS={'original':OLD/'run-2023','no60':POOL/'continuation2023/run-2023'}
PARENT_CLASSES={'original':H.Continuation,'no60':V.Continuation}
POLICIES={'original':N.POLICY,'no60':A.POLICY}
def save(p,x):IO.write_json(p,J.W.canon(x))
def root(policy):return O/'cycle2024'/policy
def binding_path(policy):return root(policy)/'AUTHORIZED_IMPORT_BINDING.json'
def inputs():
 value=D.inputs();J.START='2023-12-29';J.END=END;return value

def create_binding(policy):
 assert policy in PARENTS;parent=PARENTS[policy];cp=parent/'checkpoint.pkl';done=read(parent/'DONE.json');meta=read(cp.with_suffix('.json'))
 assert done['completed']and meta['at']==str(PARENT_AT)
 assert sha(cp)==meta['sha256']==read(cp.with_suffix('.provenance.json'))['checkpoint_sha256']
 value=dict(scope='own2023_to2024_import_and_Jan2_technical_only',policy=policy,parent_checkpoint=str(cp),
  parent_checkpoint_sha256=sha(cp),parent_metadata_sha256=sha(cp.with_suffix('.json')),
  parent_provenance_sha256=sha(cp.with_suffix('.provenance.json')),parent_done_sha256=sha(parent/'DONE.json'),
  parent_last_event=str(PARENT_AT),parent_NAV=done['ending_NAV']['B'],parent_generation_class=read(cp.with_suffix('.provenance.json'))['engine_identity']['trading_class'],
  old_score_manifest_sha256=sha(OLD_SCORE),new_score_manifest_sha256=sha(NEW_SCORE),adapter_sha256=sha(__file__),
  data_gate_sha256=sha(O/'DATA_GATE.json'),loader_gate_sha256=sha(O/'LOADER_GATE.json'),
  technical_authority='root explicit own2023 zero-event import and Jan2 physical/separate-process prefix delegation',
  last_permitted_technical_event='2024-01-02 15:10:00+08:00',full_year_authorized=False)
 path=binding_path(policy)
 if path.exists():assert read(path)==value,'preserve existing binding; do not silently rebind'
 else:save(path,value)
 return value

def source_freeze(policy):
 result=D.S.freeze()if policy=='original'else A.source_freeze()
 parent=PARENTS[policy]
 paths=[Path(__file__),O/'cycle2024_preflight.py',O/'cycle2024_cross.py',O/'CYCLE2024_CARD.txt',
        Path(D.__file__),O/'SOURCE_FREEZE.json',O/'TECHNICAL_SOURCE_FREEZE.json',O/'DATA_GATE.json',O/'LOADER_GATE.json',
        NEW_SCORE,OLD_SCORE,O/'inputs/MANIFEST.json',O/'inputs/COMPLETION.json',binding_path(policy),
        Path(H.__file__),Path(V.__file__),parent/'checkpoint.pkl',parent/'checkpoint.json',parent/'checkpoint.provenance.json',parent/'DONE.json']
 for n in ['B.json.gz','daily.jsonl.gz','opportunities.jsonl.gz','funding.jsonl.gz','industry.jsonl.gz','balances.jsonl.gz','rank-policy.jsonl.gz']:
  paths.append(parent/'pair'/n)
 execution=parent/'EXECUTION_FREEZE.json'
 if execution.exists():
  paths.append(execution)
  for p,h in read(execution)['entry_sources'].items():assert sha(p)==h;result[p]=h
 for p in paths:result[str(p.resolve())]=sha(p)
 return result

class CycleMixin:
 cycle_policy=None
 def __init__(self,*args,binding=None,**kwargs):
  self.cycle_policy=type(self).cycle_policy
  assert self.cycle_policy in PARENTS and N.SCORES.manifest_sha256==sha(NEW_SCORE)
  super().__init__(*args,**kwargs)
  path=Path(binding or binding_path(self.cycle_policy))
  self.cycle_binding_path=str(path.resolve());self.cycle_binding_sha256=sha(path)
  self.cycle_imported=False;self.cycle_generation=0;self.cycle_last_completed=None;self.cycle_claimed=False
 def assert_cycle_binding(self):
  b=read(self.cycle_binding_path);assert sha(self.cycle_binding_path)==self.cycle_binding_sha256
  assert b['policy']==self.cycle_policy and b['adapter_sha256']==sha(__file__)
  assert b['scope']=='own2023_to2024_import_and_Jan2_technical_only'
  assert b['old_score_manifest_sha256']==sha(OLD_SCORE)
  assert b['new_score_manifest_sha256']==sha(NEW_SCORE)==N.SCORES.manifest_sha256
  assert b['data_gate_sha256']==sha(O/'DATA_GATE.json')and b['loader_gate_sha256']==sha(O/'LOADER_GATE.json')
  assert b['parent_last_event']==str(PARENT_AT)
  return b
 def import_verified_parent(self):
  assert not self.cycle_imported and self.cycle_generation==0,'single-use2024 import'
  self.assert_native_wiring();b=self.assert_cycle_binding();parent=PARENTS[self.cycle_policy];path=parent/'checkpoint.pkl'
  assert Path(b['parent_checkpoint']).resolve()==path.resolve(),'wrong own-policy parent'
  assert b['parent_checkpoint_sha256']==sha(path)and b['parent_metadata_sha256']==sha(path.with_suffix('.json'))
  assert b['parent_provenance_sha256']==sha(path.with_suffix('.provenance.json'))and b['parent_done_sha256']==sha(parent/'DONE.json')
  shell=PARENT_CLASSES[self.cycle_policy].__new__(PARENT_CLASSES[self.cycle_policy])
  with IO.atomic_runner_outputs(shell,L,root(self.cycle_policy)/'parent-generation-guard',canonicalize=J.W.canon):identity=IO.assert_checkpoint_identity(shell,path)
  payload=pickle.loads(path.read_bytes());meta=read(path.with_suffix('.json'))
  assert payload['last_completed_event']==PARENT_AT and payload['source_freeze']==meta['source_freeze']
  for p,h in payload['source_freeze'].items():assert sha(p)==h,('old source drift',p)
  execution=parent/'EXECUTION_FREEZE.json';entry_sources=0
  if execution.exists():
   full=read(execution);assert full['checkpoint_source_freeze_preserved']==payload['source_freeze']
   for p,h in full['entry_sources'].items():assert sha(p)==h,('parent full entry source changed',p)
   entry_sources=len(full['entry_sources'])
  old=payload['accounts']['B'];oldrunner=payload['runner'];a=self.accounts['B']
  assert not a.positions and not a.trades and a.available==a.initial_cash==a.current_nav==J.D(1000000)
  expected_budget=N.BASE.NoAccountBudget if self.cycle_policy=='original'else A.NoConfirmed60Budget
  assert type(old['budget'])is expected_budget and oldrunner['integration_policy']==self.integration_policy==POLICIES[self.cycle_policy]+':PVR_SLOT1'
  assert oldrunner['rank_scores_manifest_sha256']==b['old_score_manifest_sha256']and oldrunner['rank_mode']=='PVR_SLOT1'
  if self.cycle_policy=='no60':assert oldrunner['remove_confirmed60']is True
  assert old['mode']=='ACT'and old['cost_multiplier']==1 and old['delay_events']==0 and not old['add_enabled']
  with gzip.open(parent/'pair/B.json.gz','rt')as f:book=json.load(f)
  fields={'trades':'trades','layers':'layers','jmeta':'metadata','journal':'journal','buys':'orders','exits':'exits','audit_log':'audit','decisions':'decisions','available':'ending_cash','current_nav':'ending_NAV'}
  bookchecks={k:J.W.canon(old[k])==book[v]for k,v in fields.items()};assert all(bookchecks.values())
  budget=old['budget'];assert J.W.canon(dict(sectors=budget.sectors,orders=budget.orders,losses={str(k):v for k,v in budget.losses.items()},consumed=sorted(budget.consumed)))==book['budget']
  streams={}
  for field,file in {'daily':'daily','opportunities':'opportunities','funding':'funding','stage_events':'industry','balance_audit':'balances','rank_log':'rank-policy'}.items():
   left=E.record_digest(oldrunner[field]);right=E.record_digest(E.file_rows(parent/'pair'/(file+'.jsonl.gz')));assert left==right;streams[field]=left
  assert self.sector_by_sid==oldrunner['sector_by_sid']==old['sector_by_sid']
  # The audited2023 serializer excludes episode_starts as a pure input lookup.
  # Reconstruct its exact immutable2023 view using the original constructor's
  # setdefault algorithm; source guards above and loader verify the90 state files.
  assert 'episode_starts'not in oldrunner
  extended=dict(self.episode_starts);past={}
  for sector in sorted(self.industry_rows):
   for row in self.industry_rows[sector].values():
    if row['day']<=str(PARENT_AT.date())and row['E0_valid']:
     past.setdefault(row['E0_episode'],J.ordinal(row['day']))
  assert len(past)==oldrunner['horizon_transition']['pure_lookup_new'],'original2023 derived lookup count changed'
  assert all(extended.get(k)==v for k,v in past.items()),'old episode lookup changed'
  added={k:v for k,v in extended.items()if k not in past};assert all(v>PARENT_AT.date().toordinal()for v in added.values())
  excluded={'source_freeze','run_seconds','episode_starts','rank_scores_manifest_sha256'}
  copied=set(oldrunner)-excluded
  assert not any(k.startswith('cycle_')for k in copied),'cannot import an already2024 parent'
  for k in copied:setattr(self,k,copy.deepcopy(oldrunner[k]))
  self.episode_starts=extended;self.rank_scores_manifest_sha256=b['new_score_manifest_sha256']
  market,facts=a.market,a.facts;a.__dict__.clear();a.__dict__.update(copy.deepcopy(old));a.market=market;a.facts=facts
  ac={k:E.equal(v,a.__dict__[k])for k,v in old.items()};rc={k:E.equal(oldrunner[k],getattr(self,k))for k in copied};assert all(ac.values())and all(rc.values())
  balance=a.balance(PARENT_AT,self.market.marks(PARENT_AT,a.positions))
  assert balance['nav']==a.current_nav==J.D(b['parent_NAV'])==J.D(book['ending_NAV'])
  assert abs(a.budget.nav-float(balance['nav']))<1e-6 and abs(a.budget.cash-a.budget.resources()[2]-float(a.available))<1e-6
  assert all(E.equal(v,a.__dict__[k])for k,v in old.items()),'read-only validation changed account'
  self.cycle_imported=True;self.cycle_generation=1;self.cycle_last_completed=PARENT_AT;self.cycle_claimed=False
  self.cycle_transition=dict(parent_checkpoint=str(path),parent_sha256=sha(path),old_score_manifest_sha256=b['old_score_manifest_sha256'],new_score_manifest_sha256=b['new_score_manifest_sha256'],
    lookup_old=len(past),lookup_new=len(extended),lookup_future=len(added),economic_reset=False,account_events=0)
  self.assert_native_wiring()
  return dict(passed=True,parent_generation_identity=identity,all_account_fields_equal=ac,all_strategy_fields_equal=rc,bookchecks=bookchecks,
   all6_old_streams_exact=streams,parent_additional_entry_source_count=entry_sources,
   future_lookup_entries=len(added),parent_lookup_reconstructed_from_immutable_state=True,
   parent_lookup_entries=len(past),parent_lookup_not_serialized=True,
   parent_NAV=str(a.current_nav),held_stocks=len(a.positions),pending_intents=len(a.pending),account_events=0)
 def claim_cursor(self,cursor):
  assert self.cycle_imported and not self.cycle_claimed,'cursor/import already claimed or missing'
  assert cursor==self.cycle_last_completed,'exact own saved cursor required'
  assert cursor<J.M.N.iso(END+'T15:10:00+08:00'),'completed2024 horizon cannot be claimed'
  self.cycle_claimed=True;return cursor
 def run_prepared(self,out,max_seconds,resume_after=None,end=None):
  authpath=root(self.cycle_policy)/'FULL_2024_RUN_AUTHORIZATION.json';assert authpath.exists(),'2024 full financial path not authorized'
  auth=read(authpath);assert auth['approved']is True and auth['policy']==self.cycle_policy
  assert auth['adapter_sha256']==sha(__file__)and auth['binding_sha256']==self.cycle_binding_sha256
  cursor=self.claim_cursor(resume_after)
  try:return L.PreparedRunner.run_prepared(self,out,max_seconds,resume_after=cursor,end=end or END)
  finally:self.cycle_claimed=False
 def checkpoint(self,out,last_event):
  assert self.cycle_imported and last_event>=self.cycle_last_completed
  self.cycle_last_completed=last_event;claimed=self.cycle_claimed;self.cycle_claimed=False
  try:H._save_checkpoint(self,out,last_event)
  finally:self.cycle_claimed=claimed
  if str(last_event.date())in {'2024-03-29','2024-06-28','2024-09-30','2024-12-31'}:
   for suffix in ['pkl','json']:shutil.copyfile(Path(out)/('checkpoint.'+suffix),Path(out)/('checkpoint-'+str(last_event.date())+'.'+suffix))
 def restore(self,path):
  p=pickle.loads(Path(path).read_bytes());r=p['runner']
  assert r['cycle_binding_sha256']==self.cycle_binding_sha256 and r['cycle_policy']==self.cycle_policy
  assert r['cycle_imported']and r['cycle_generation']==1 and not r['cycle_claimed']and r['cycle_last_completed']==p['last_completed_event']
  after=super().restore(path);assert self.cycle_last_completed==after;self.assert_cycle_binding();return after

class Original2024(CycleMixin,N.Runner):cycle_policy='original'
class No602024(CycleMixin,A.Runner):cycle_policy='no60'
CLASSES={'original':Original2024,'no60':No602024}

if __name__=='__main__':raise SystemExit('Identity adapter only; full finance requires separate root grant.')
