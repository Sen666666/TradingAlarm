"""Explicit NO60 own-state horizon transition, unchanged native strategy."""
from pathlib import Path
from datetime import datetime,time as dt
import ast,copy,gzip,hashlib,inspect,json,pickle,shutil,sys
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent
sys.path.insert(0,str(P));import native_adapter as A
N,J,L,IO,W=A.N,A.J,A.L,A.IO,A.W
OLD=W/'pvr-slot1-native-readiness-20261101';OLD2023=OLD/'continuation-2023-readiness'
# Reuse only audited pure equality/record helpers and logging-only event loop;
# this old importer is never invoked for the new parent.
H=J.W.load('original_pvr2023_horizon_pattern_readonly',OLD2023/'horizon_import.py')
E=H.E;PARENT=P/'runs/2022';PARENT_AT=J.M.N.iso('2022-12-30T15:10:00+08:00')
END='2023-12-29';SCORES=OLD2023/'SCORES_MANIFEST.json'
OLD_SCORE_SHA='22077458907e1989ca88cb8e3dcc72284cedf3f670abc5432f08198a262bf27f'
NEW_SCORE_SHA='4d764fb1c258110dd3d08c8e45c7e8aeabce88685b8f98b2a82577b25f8065bf'
BINDING=O/'AUTHORIZED_IMPORT_BINDING.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):IO.write_json(p,J.W.canon(x))

def inputs():
 source=W/'recovery-2023-readiness-20261101/continuation_2023.py'
 node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='inputs')
 env=dict(J=J,L=L,pd=pd,O=source.parent,START='2023-01-01',END=END,
  save=lambda path,value:save(O/'input-readiness'/Path(path).name,value))
 exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),env)
 J.START='2022-12-30';J.END=END
 return env['inputs']()

def source_freeze():
 result=A.source_freeze()
 paths=[Path(__file__),O/'preflight.py',O/'cross_process.py',O/'IMPORT_CARD.txt',BINDING,SCORES,
  OLD2023/'horizon_import.py',W/'recovery-2023-readiness-20261101/continuation_2023.py',
  W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',W/'recovery-2023-readiness-20261101/inputs/COMPLETION.json',
  W/'recovery-2023-readiness-20261101/RIGHTS_2023.json',PARENT/'checkpoint.pkl',PARENT/'checkpoint.json',
  PARENT/'checkpoint.provenance.json',PARENT/'DONE.json']
 for p in paths:result[str(p.resolve())]=sha(p)
 return result

def create_binding():
 path=PARENT/'checkpoint.pkl';done=read(PARENT/'DONE.json');assert done['completed']
 ids=[SCORES,OLD/'SCORES_MANIFEST.json',W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',
  W/'recovery-2023-readiness-20261101/inputs/COMPLETION.json',W/'recovery-2023-readiness-20261101/RIGHTS_2023.json',
  L.U/'STOCK_MANIFEST.json',L.U/'INDUSTRY_MANIFEST.json',L.U/'FREEZE.json',J.M.O/'recovery.csv',J.M.P/'h1.npz']
 value=dict(scope='NO60_own2022_to2023_technical_import_only',parent_checkpoint=str(path.resolve()),parent_checkpoint_sha256=sha(path),
  parent_metadata_sha256=sha(path.with_suffix('.json')),parent_provenance_sha256=sha(path.with_suffix('.provenance.json')),
  parent_done_sha256=sha(PARENT/'DONE.json'),parent_NAV=done['ending_NAV']['B'],parent_last_event=str(PARENT_AT),
  policy=A.POLICY,native_adapter_sha256=sha(A.__file__),horizon_adapter_sha256=sha(__file__),
  old_score_manifest_sha256=OLD_SCORE_SHA,new_score_manifest_sha256=NEW_SCORE_SHA,
  new_input_identities={str(p):sha(p)for p in ids},full_year_authorized=False,
  technical_authority='root explicit own-state0event import and Jan3 physical/cross-process prefix delegation')
 assert value['parent_NAV']=='704487.8470098769005'
 if BINDING.exists():assert read(BINDING)==value,'existing horizon binding changed'
 else:save(BINDING,value)
 return value

class Continuation(A.Runner):
 def __init__(self,*args,binding=BINDING,**kwargs):
  assert sha(SCORES)==NEW_SCORE_SHA and type(N.SCORES)is N.FrozenScores
  assert N.SCORES.manifest_sha256==NEW_SCORE_SHA and Path(N.SCORES.path)==SCORES.resolve()
  super().__init__(*args,**kwargs)
  self.horizon_binding_path=str(Path(binding).resolve());self.horizon_binding_sha256=sha(binding)
  self.horizon_imported=False;self.horizon_import_generation=0;self.horizon_last_completed=None;self._cursor_claimed=False

 def assert_binding(self,path):
  assert sha(path)==self.horizon_binding_sha256,'horizon binding bytes mismatch'
  b=read(path);assert b['scope']=='NO60_own2022_to2023_technical_import_only'
  assert b['policy']==A.POLICY and b['native_adapter_sha256']==sha(A.__file__) and b['horizon_adapter_sha256']==sha(__file__)
  assert b['old_score_manifest_sha256']==OLD_SCORE_SHA==sha(OLD/'SCORES_MANIFEST.json')
  assert b['new_score_manifest_sha256']==NEW_SCORE_SHA==sha(SCORES)==N.SCORES.manifest_sha256
  assert b['parent_last_event']==str(PARENT_AT)
  for p,h in b['new_input_identities'].items():assert sha(p)==h,('new horizon input changed',p)
  return b

 def import_verified_parent(self,binding=BINDING):
  assert not self.horizon_imported and self.horizon_import_generation==0,'single-use parent import'
  self.assert_native_wiring();bind=self.assert_binding(binding)
  path=Path(bind['parent_checkpoint']);assert path.resolve()==(PARENT/'checkpoint.pkl').resolve(),'not own NO60 parent'
  assert bind['parent_done_sha256']==sha(PARENT/'DONE.json')and bind['parent_NAV']==read(PARENT/'DONE.json')['ending_NAV']['B']
  assert sha(path)==bind['parent_checkpoint_sha256']
  assert sha(path.with_suffix('.json'))==bind['parent_metadata_sha256']and sha(path.with_suffix('.provenance.json'))==bind['parent_provenance_sha256']
  shell=A.Runner.__new__(A.Runner)
  with IO.atomic_runner_outputs(shell,L,O/'parent-generation-guard',canonicalize=J.W.canon):
   identity=IO.assert_checkpoint_identity(shell,path)
  payload=pickle.loads(path.read_bytes());meta=read(path.with_suffix('.json'))
  assert payload['last_completed_event']==PARENT_AT and meta['sha256']==sha(path) and payload['source_freeze']==meta['source_freeze']
  for p,h in payload['source_freeze'].items():assert sha(p)==h,('parent frozen source changed',p)
  old=payload['accounts']['B'];oldrunner=payload['runner'];a=self.accounts['B']
  assert a.available==a.current_nav==a.initial_cash==J.D(1000000)and not a.positions and not a.trades
  assert type(old['budget'])is A.NoConfirmed60Budget and oldrunner['remove_confirmed60']is True
  assert oldrunner['integration_policy']==self.integration_policy==A.POLICY+':PVR_SLOT1'
  assert oldrunner['rank_mode']=='PVR_SLOT1'and oldrunner['rank_scores_manifest_sha256']==OLD_SCORE_SHA
  assert old['mode']=='ACT'and old['cost_multiplier']==1 and old['delay_events']==0 and not old['add_enabled']
  with gzip.open(PARENT/'pair/B.json.gz','rt')as f:book=json.load(f)
  fmap={'trades':'trades','layers':'layers','jmeta':'metadata','journal':'journal','buys':'orders','exits':'exits','audit_log':'audit','decisions':'decisions','available':'ending_cash','current_nav':'ending_NAV'}
  bookchecks={k:J.W.canon(old[k])==book[v]for k,v in fmap.items()};assert all(bookchecks.values()),bookchecks
  b=old['budget'];assert J.W.canon(dict(sectors=b.sectors,orders=b.orders,losses={str(k):v for k,v in b.losses.items()},consumed=sorted(b.consumed)))==book['budget']
  streams={}
  for field,file in {'daily':'daily','opportunities':'opportunities','funding':'funding','stage_events':'industry','balance_audit':'balances'}.items():
   left=E.record_digest(oldrunner[field]);right=E.record_digest(E.file_rows(PARENT/'pair'/(file+'.jsonl.gz')));assert left==right;streams[field]=left
  assert self.sector_by_sid==oldrunner['sector_by_sid']==old['sector_by_sid']
  extended=dict(self.episode_starts);past=oldrunner['episode_starts']
  assert all(extended.get(k)==v for k,v in past.items()),'old industry lookup changed'
  added={k:v for k,v in extended.items()if k not in past};assert all(v>PARENT_AT.date().toordinal()for v in added.values())
  excluded={'source_freeze','run_seconds','episode_starts','rank_scores_manifest_sha256'}
  copied=set(oldrunner)-excluded
  for k in copied:setattr(self,k,copy.deepcopy(oldrunner[k]))
  self.episode_starts=extended;self.rank_scores_manifest_sha256=NEW_SCORE_SHA
  market,facts=a.market,a.facts;a.__dict__.clear();a.__dict__.update(copy.deepcopy(old));a.market=market;a.facts=facts
  ac={k:E.equal(v,a.__dict__[k])for k,v in old.items()};rc={k:E.equal(oldrunner[k],getattr(self,k))for k in copied}
  assert all(ac.values())and all(rc.values())
  balance=a.balance(PARENT_AT,self.market.marks(PARENT_AT,a.positions))
  assert balance['nav']==a.current_nav==J.D(bind['parent_NAV'])==J.D(book['ending_NAV'])
  assert abs(a.budget.nav-float(balance['nav']))<1e-6 and abs(a.budget.cash-a.budget.resources()[2]-float(a.available))<1e-6
  assert all(E.equal(v,a.__dict__[k])for k,v in old.items()),'zero-event verification changed account'
  assert all(i['clock'].earliest_execution_at==J.M.N.iso('2023-01-03T09:30:00+08:00')for i in a.pending)
  self.horizon_imported=True;self.horizon_import_generation=1;self.horizon_last_completed=PARENT_AT;self._cursor_claimed=False
  self.horizon_transition=dict(parent_checkpoint=str(path),parent_sha256=sha(path),old_score_manifest_sha256=OLD_SCORE_SHA,new_score_manifest_sha256=NEW_SCORE_SHA,
   pure_lookup_old=len(past),pure_lookup_new=len(extended),future_entries=len(added),economic_state_reset=False,account_events=0)
  self.assert_native_wiring()
  return dict(passed=True,parent_generation_identity=identity,all_account_fields_equal=ac,all_strategy_fields_equal=rc,final_book_fields_equal=bookchecks,
   all5_old_event_streams_exact=streams,lookup_added_after_parent=added,transition=self.horizon_transition,
   actual_new_events=0,parent_NAV=str(a.current_nav),pending_intents=len(a.pending),held_stocks=len(a.positions),
   account_field_count=len(ac),strategy_field_count=len(rc),source_freeze_only_explicitly_extended=True)

 def next_event_inventory(self,through='2023-01-03'):
  assert self.horizon_imported
  finish=J.M.N.iso(through+'T15:10:00+08:00');cursor=self.horizon_last_completed
  closes={x for x in self.market.cutoffs if cursor<x<=finish};opens={x for x in self.market.sessions['A']if cursor<x<=finish}
  acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,J.M.N.TZ)for d in self.actions_by_date};acts={x for x in acts if cursor<x<=finish}
  return [dict(at=str(x),opening=x in opens,close=x in closes,action=x in acts)for x in sorted(closes|opens|acts)]

 def _claim_cursor(self,expected):
  assert self.horizon_imported and not self._cursor_claimed,'cursor already claimed or not imported'
  assert expected==self.horizon_last_completed,'exact saved last-completed cursor required'
  assert expected<J.M.N.iso(END+'T15:10:00+08:00')
  self._cursor_claimed=True;return expected

 def run_prepared(self,out,max_seconds,resume_after=None,end=None):
  authpath=O/'FULL_2023_RUN_AUTHORIZATION.json';assert authpath.exists(),'2023 full account path not authorized'
  auth=read(authpath);assert auth['approved']is True and auth['scope']=='ONE_NO60_own2022_2023_continuation'
  assert auth['horizon_adapter_sha256']==sha(__file__)and auth['binding_sha256']==self.horizon_binding_sha256
  assert auth['native_adapter_sha256']==sha(A.__file__)
  cursor=self._claim_cursor(resume_after)
  try:return H._run_original(self,out,max_seconds,resume_after=cursor,end=end or END)
  finally:self._cursor_claimed=False

 def checkpoint(self,out,last_event):
  assert self.horizon_imported and last_event>=self.horizon_last_completed
  self.horizon_last_completed=last_event;claimed=self._cursor_claimed;self._cursor_claimed=False
  try:H._save_checkpoint(self,out,last_event)
  finally:self._cursor_claimed=claimed
  if str(last_event.date())in {'2023-03-31','2023-06-30','2023-09-28','2023-12-29'}:
   for suffix in ['pkl','json']:shutil.copyfile(Path(out)/('checkpoint.'+suffix),Path(out)/('checkpoint-'+str(last_event.date())+'.'+suffix))

 def restore(self,path):
  payload=pickle.loads(Path(path).read_bytes())
  assert payload['runner']['horizon_binding_sha256']==self.horizon_binding_sha256
  assert payload['runner']['horizon_imported']and payload['runner']['horizon_import_generation']==1
  assert payload['runner']['horizon_last_completed']==payload['last_completed_event']and not payload['runner']['_cursor_claimed']
  after=super().restore(path);assert self.horizon_last_completed==after;return after
