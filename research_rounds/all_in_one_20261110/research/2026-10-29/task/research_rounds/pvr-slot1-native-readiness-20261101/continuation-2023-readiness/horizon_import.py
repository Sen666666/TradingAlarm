"""Explicit authorized horizon/input identity transition, no new trading rule.

Original PVR_SLOT1 adapter remains byte-immutable. The old checkpoint is
checked under its ACTUAL generation class/provenance before any state copy.
No source guard is disabled, no old provenance is rewritten.
"""
from pathlib import Path
from datetime import datetime,time as dt
import sys,ast,copy,json,pickle,hashlib,inspect,textwrap,shutil
import pandas as pd

O=Path(__file__).resolve().parent;P=O.parent;W=P.parent
sys.path.insert(0,str(P));import native_rank as N
J,L,IO=N.J,N.L,N.IO
sys.path.insert(0,str(W/'q2-normal-continuation-20261031'))
import continuation as E
ADAPTER_SHA='5ec91c2323b2d3b8fa5c99df504139e2ac7af9b5b84359222c3d6353d0cd697c'
OLD_SCORE_SHA='22077458907e1989ca88cb8e3dcc72284cedf3f670abc5432f08198a262bf27f'
NEW_SCORE_SHA='4d764fb1c258110dd3d08c8e45c7e8aeabce88685b8f98b2a82577b25f8065bf'
PARENT_AT=J.M.N.iso('2022-12-30T15:10:00+08:00')
END='2023-12-29'
DEFAULT_BINDING=O/'AUTHORIZED_IMPORT_BINDING.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(path,value):IO.write_json(path,J.W.canon(value))

def inputs():
    """Extract ONLY the already audited original input function, no module writes."""
    source=W/'recovery-2023-readiness-20261101/continuation_2023.py'
    node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='inputs')
    env=dict(J=J,L=L,pd=pd,O=source.parent,START='2023-01-01',END=END,
             save=lambda path,value:save(O/'horizon-input-readiness'/Path(path).name,value))
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),env)
    # Internal event horizon starts at the parent cursor, strictly skipped by
    # resume_after; this includes Jan3 opening and any intervening original action.
    J.START='2022-12-30';J.END=END
    return env['inputs']()

def score_prefix_proof():
    old=read(P/'SCORES_MANIFEST.json');new=read(O/'SCORES_MANIFEST.json')
    assert sha(P/'SCORES_MANIFEST.json')==OLD_SCORE_SHA and sha(O/'SCORES_MANIFEST.json')==NEW_SCORE_SHA
    assert old['fixed_stock_ids']==new['fixed_stock_ids'] and len(old['entries'])==len(new['entries'])==1709
    dates=old['decision_calendars']['2022']['dates'];lookup={x['symbol']:x for x in new['entries']};cells=0
    for r in old['entries']:
        a=P/'scores'/f"{r['symbol']}.parquet";b=O/'scores'/a.name;nr=lookup[r['symbol']]
        assert sha(a)==r['output_sha256'] and sha(b)==nr['output_sha256']
        pd.testing.assert_frame_equal(pd.read_parquet(a).loc[dates],pd.read_parquet(b).loc[dates],check_exact=True,check_freq=False)
        assert r['source_sha256']==nr['source_sha256'] and r['formula_sha256']==nr['formula_sha256']
        cells+=len(dates)
    assert cells==413578
    return dict(passed=True,cells=cells,all1709_old_file_bytes_unchanged=True,
                old_manifest_sha256=OLD_SCORE_SHA,new_manifest_sha256=NEW_SCORE_SHA)

def source_freeze():
    paths=[Path(__file__),O/'preflight_import.py',DEFAULT_BINDING,O/'SCORES_MANIFEST.json',
           O/'CONTINUATION_CONTRACT_PROPOSAL.txt',O/'READINESS.json',
           W/'recovery-2023-readiness-20261101/continuation_2023.py',
           W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',
           W/'recovery-2023-readiness-20261101/inputs/COMPLETION.json',
           W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json',
           W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json',
           P/'runs/2022/checkpoint.pkl',P/'runs/2022/checkpoint.provenance.json',
           J.M.O/'recovery.csv',J.M.P/'h1.npz']
    result=N.source_freeze()
    for p in paths:result[str(p.resolve())]=sha(p)
    return result

def identity_guard_for_original(path):
    """Invoke the unchanged guard using original generation class, not this subclass."""
    shell=N.Runner.__new__(N.Runner)
    with IO.atomic_runner_outputs(shell,L,O/'old-generation-identity-guard',canonicalize=J.W.canon):
        return IO.assert_checkpoint_identity(shell,path)

# Only exclude pure extended input lookup from checkpoint, as in the audited
# original 2023 continuation. All actual account/strategy state remains saved.
_OLD=textwrap.dedent(inspect.getsource(L.PreparedRunner.checkpoint))
assert _OLD.count("'actions_by_date'")==1
_NEW=_OLD.replace("'actions_by_date'","'actions_by_date','episode_starts'")
assert _NEW.replace("'actions_by_date','episode_starts'","'actions_by_date'")==_OLD
_env=dict(L.__dict__,save=lambda p,x:IO.write_json(p,J.W.canon(x)))
exec(compile(_NEW,str(Path(__file__))+'::checkpoint-input-lookup-exclusion','exec'),_env)
_save_checkpoint=_env['checkpoint']
_RUN_OLD=textwrap.dedent(inspect.getsource(L.PreparedRunner.run_prepared))
_LOG_OLD="if at in cutoffs and (pd.Timestamp(at.date())+pd.offsets.BDay()).month!=at.month:"
_LOG_NEW="if at in cutoffs and ((pd.Timestamp(at.date())+pd.offsets.BDay()).month!=at.month or str(at.date()) in {'2023-03-31','2023-06-30','2023-09-28','2023-12-29'}):"
assert _RUN_OLD.count(_LOG_OLD)==1
_RUN_NEW=_RUN_OLD.replace(_LOG_OLD,_LOG_NEW)
assert _RUN_NEW.replace(_LOG_NEW,_LOG_OLD)==_RUN_OLD
_runenv=dict(L.__dict__,save=lambda p,x:IO.write_json(p,J.W.canon(x)))
exec(compile(_RUN_NEW,str(Path(__file__))+'::quarter-checkpoint-only','exec'),_runenv)
_run_original=_runenv['run_prepared']

class Continuation(N.Runner):
    def __init__(self,*args,binding=DEFAULT_BINDING,**kwargs):
        assert sha(N.__file__)==ADAPTER_SHA
        assert type(N.SCORES) is N.FrozenScores and N.SCORES.manifest_sha256==NEW_SCORE_SHA
        assert Path(N.SCORES.path)==(O/'SCORES_MANIFEST.json').resolve()
        super().__init__(*args,**kwargs)
        self.horizon_binding_sha256=sha(binding)
        self.horizon_binding_path=str(Path(binding).resolve())
        self.horizon_imported=False;self.horizon_import_generation=0
        self.horizon_last_completed=None;self._cursor_claimed=False

    def assert_binding(self,path):
        assert sha(path)==self.horizon_binding_sha256,'unauthorized horizon binding bytes'
        b=read(path)
        assert b['scope']=='PVR_SLOT1_2023_import_preflight_only'
        assert b['native_adapter_sha256']==ADAPTER_SHA==sha(N.__file__)
        assert b['old_score_manifest_sha256']==OLD_SCORE_SHA==sha(P/'SCORES_MANIFEST.json')
        assert b['new_score_manifest_sha256']==NEW_SCORE_SHA==sha(O/'SCORES_MANIFEST.json')
        assert N.SCORES.manifest_sha256==NEW_SCORE_SHA
        assert b['horizon_import_sha256']==sha(Path(__file__))
        for p,h in b['new_input_identities'].items():assert sha(p)==h,('new input identity drift',p)
        assert b['parent_last_event']==str(PARENT_AT)
        return b

    def import_verified_parent(self,binding=DEFAULT_BINDING):
        assert not self.horizon_imported and self.horizon_import_generation==0,'parent import is single-use'
        self.assert_native_wiring();bind=self.assert_binding(binding)
        path=Path(bind['parent_checkpoint']);assert path.resolve()==(P/'runs/2022/checkpoint.pkl').resolve()
        assert sha(path)==bind['parent_checkpoint_sha256']
        assert sha(path.with_suffix('.provenance.json'))==bind['parent_provenance_sha256']
        original_identity=identity_guard_for_original(path)
        meta=read(path.with_suffix('.json'));payload=pickle.loads(path.read_bytes())
        assert meta['sha256']==sha(path) and payload['last_completed_event']==PARENT_AT
        assert payload['source_freeze']==meta['source_freeze']
        for p,h in payload['source_freeze'].items():assert sha(p)==h,('old source identity drift',p)
        old=payload['accounts']['B'];oldrunner=payload['runner'];a=self.accounts['B']
        assert a.available==a.initial_cash==a.current_nav==J.D(1000000) and not a.positions and not a.trades
        assert type(old['budget']) is N.BASE.NoAccountBudget
        assert oldrunner['rank_mode']=='PVR_SLOT1' and oldrunner['integration_policy']==self.integration_policy
        assert oldrunner['rank_scores_manifest_sha256']==OLD_SCORE_SHA
        assert old['cost_multiplier']==1 and old['delay_events']==0 and not old['add_enabled'] and old['mode']=='ACT'
        with __import__('gzip').open(P/'runs/2022/pair/B.json.gz','rt') as f:book=__import__('json').load(f)
        fmap={'trades':'trades','layers':'layers','jmeta':'metadata','journal':'journal','buys':'orders','exits':'exits',
              'audit_log':'audit','decisions':'decisions','available':'ending_cash','current_nav':'ending_NAV'}
        book_checks={k:J.W.canon(old[k])==book[v] for k,v in fmap.items()};assert all(book_checks.values())
        budget=old['budget']
        assert J.W.canon(dict(sectors=budget.sectors,orders=budget.orders,
            losses={str(k):v for k,v in budget.losses.items()},consumed=sorted(budget.consumed)))==book['budget']
        streams={}
        for field,file in {'daily':'daily','opportunities':'opportunities','funding':'funding','stage_events':'industry','balance_audit':'balances'}.items():
            left=E.record_digest(oldrunner[field]);right=E.record_digest(E.file_rows(P/'runs/2022/pair'/(file+'.jsonl.gz')))
            assert left==right;streams[field]=left
        assert self.sector_by_sid==oldrunner['sector_by_sid']==old['sector_by_sid']
        extended=dict(self.episode_starts);past=oldrunner['episode_starts']
        assert all(extended.get(k)==v for k,v in past.items()),'past industry lookup changed'
        added={k:v for k,v in extended.items() if k not in past}
        assert all(v>PARENT_AT.date().toordinal() for v in added.values()),'new lookup fabricated a past start'
        # Economic/strategy state copy is complete. Only named metadata and pure
        # immutable input extension are retained from the new horizon view.
        excluded={'source_freeze','run_seconds','episode_starts','rank_scores_manifest_sha256'}
        copied=set(oldrunner)-excluded
        for k in copied:setattr(self,k,copy.deepcopy(oldrunner[k]))
        self.episode_starts=extended;self.rank_scores_manifest_sha256=NEW_SCORE_SHA
        market,facts=a.market,a.facts
        a.__dict__.clear();a.__dict__.update(copy.deepcopy(old));a.market=market;a.facts=facts
        account_checks={k:E.equal(v,a.__dict__[k]) for k,v in old.items()}
        strategy_checks={k:E.equal(oldrunner[k],getattr(self,k)) for k in copied}
        assert all(account_checks.values()) and all(strategy_checks.values())
        bal=a.balance(PARENT_AT,self.market.marks(PARENT_AT,a.positions))
        assert bal['nav']==a.current_nav==J.D('715009.3354426633890')
        assert abs(a.budget.nav-float(bal['nav']))<1e-6
        assert all(E.equal(v,a.__dict__[k]) for k,v in old.items()),'read-only import validation mutated account'
        assert len(a.positions)==60 and sum(x['qty']>0 for x in a.layers)==70 and len(a.pending)==79
        assert all(i['clock'].earliest_execution_at==J.M.N.iso('2023-01-03T09:30:00+08:00') for i in a.pending)
        self.horizon_imported=True;self.horizon_import_generation=1
        self.horizon_last_completed=PARENT_AT;self._cursor_claimed=False
        self.horizon_transition=dict(parent_checkpoint=str(path),parent_sha256=sha(path),
            old_score_manifest_sha256=OLD_SCORE_SHA,new_score_manifest_sha256=NEW_SCORE_SHA,
            pure_lookup_old=len(past),pure_lookup_new=len(extended),future_entries=len(added),
            economic_state_reset=False,account_events=0)
        self.assert_native_wiring()
        return dict(passed=True,old_generation_identity_verified_by_unchanged_guard=original_identity,
            all_account_fields_equal=account_checks,all_strategy_fields_equal=strategy_checks,
            final_book_fields_equal=book_checks,all5_old_event_streams_exact=streams,
            lookup_added_entries_after_parent_only=added,parent_cursor=str(PARENT_AT),
            named_metadata_changes={'rank_scores_manifest_sha256':[OLD_SCORE_SHA,NEW_SCORE_SHA],
                                    'source_freeze':'explicit authorized new horizon binding'},
            original_checkpoint_and_provenance_unchanged=True,transition=self.horizon_transition,
            known_original_generation_not_backfilled=True,new_generation_identity=IO.runner_identity(self),actual_new_events=0)

    def next_event_inventory(self,through='2023-01-03'):
        assert self.horizon_imported and self.horizon_last_completed==PARENT_AT
        finish=J.M.N.iso(through+'T15:10:00+08:00')
        closes={x for x in self.market.cutoffs if PARENT_AT<x<=finish}
        opens={x for x in self.market.sessions['A'] if PARENT_AT<x<=finish}
        actions={datetime.combine(datetime.fromisoformat(d).date(),dt.min,J.M.N.TZ) for d in self.actions_by_date}
        actions={x for x in actions if PARENT_AT<x<=finish}
        return [dict(at=str(x),opening=x in opens,close=x in closes,action=x in actions)
                for x in sorted(closes|opens|actions)]

    def _claim_cursor(self,expected):
        assert self.horizon_imported and not self._cursor_claimed,'cursor already claimed or not imported'
        assert expected==self.horizon_last_completed,'resume cursor must be exact saved last-completed event'
        assert expected<J.M.N.iso(END+'T15:10:00+08:00'),'horizon already complete'
        self._cursor_claimed=True
        return expected

    def run_prepared(self,out,max_seconds,resume_after=None,end=None):
        # No finance authorization file is created by this preflight task.
        authorization=O/'FULL_2023_RUN_AUTHORIZATION.json'
        assert authorization.exists(),'2023 account events not authorized'
        auth=read(authorization)
        assert auth['scope']=='ONE_PVR_SLOT1_2023_financial_continuation'
        assert auth['horizon_import_sha256']==sha(Path(__file__)) and auth['binding_sha256']==self.horizon_binding_sha256
        assert auth['native_adapter_sha256']==ADAPTER_SHA
        after=self._claim_cursor(resume_after)
        try:return _run_original(self,out,max_seconds,resume_after=after,end=end or END)
        finally:self._cursor_claimed=False

    def checkpoint(self,out,last_event):
        assert self.horizon_imported and last_event>=self.horizon_last_completed
        self.horizon_last_completed=last_event
        # Checkpoint serializes a resumable boundary, not an in-flight lock.
        claimed=self._cursor_claimed;self._cursor_claimed=False
        try:_save_checkpoint(self,out,last_event)
        finally:self._cursor_claimed=claimed
        if str(last_event.date()) in {'2023-03-31','2023-06-30','2023-09-28','2023-12-29'}:
            for suffix in ('pkl','json'):shutil.copyfile(Path(out)/('checkpoint.'+suffix),Path(out)/('checkpoint-'+str(last_event.date())+'.'+suffix))

    def restore(self,path):
        payload=pickle.loads(Path(path).read_bytes())
        assert payload['runner']['horizon_binding_sha256']==self.horizon_binding_sha256,'checkpoint horizon binding differs'
        assert payload['runner']['horizon_imported'] and payload['runner']['horizon_import_generation']==1
        assert payload['runner']['horizon_last_completed']==payload['last_completed_event']
        assert not payload['runner']['_cursor_claimed'],'in-flight lock cannot be resumed'
        after=super().restore(path)
        assert self.horizon_last_completed==after
        return after
