"""Mobile authorization overlay. Factory only; no native imports/run.

The parent must settle provider/domain and freeze before a financial run.
BASE/R_ONLY/P_ONLY/JOINT share action scope; only the weak predicate changes.
"""
from pathlib import Path
import ast,copy,hashlib,inspect,math,pickle,textwrap

HERE=Path(__file__).resolve().parent
NATIVE_PLANNING=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py')
ARMS={'BASE':None,'R_ONLY':'R','P_ONLY':'P','JOINT':'J'}
VERSION='MOBILE_AUTHORIZATION_H2_V1'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def provider_value(provider,sid,at,native_row,expected_sector):
    """Final parent ContextProvider schema; provider owns exact endpoints.
    Unready predicates retain native behavior; identity/future data is an error.
    """
    q=copy.deepcopy(dict(provider.at(sid,at)))
    required={'day','ready_R','ready_P','close','EMA20','RS20','sector','source_segment','source_max_day','anchor_day','unknown_reason'}
    assert required<=q.keys(),('provider schema missing',required-q.keys())
    assert type(q['ready_R']) is bool and type(q['ready_P']) is bool
    day=str(at.date());assert q['day']==day,'wrong provider decision day'
    # Absent exact current source observations correctly return unready with
    # sector=None; these must retain the original policy rather than error.
    assert q['sector'] is None or q['sector']==expected_sector,'wrong sector identity'
    if q['source_max_day'] is not None:assert q['source_max_day']<=day,'future source'
    if q['ready_R'] or q['ready_P']:
        assert q['source_max_day']==day and q['sector']==expected_sector
        assert math.isfinite(float(q['close'])) and float(q['close'])>0
        assert math.isclose(float(q['close']),float(native_row.close),rel_tol=1e-11,abs_tol=1e-11),'provider/native stock price mismatch'
        assert float(q['source_segment'])==float(native_row.segment_id),'provider/native source-domain mismatch'
    if q['ready_R']:
        assert math.isfinite(float(q['RS20']))
        assert isinstance(q['anchor_day'],str) and q['anchor_day']<day
    if q['ready_P']:assert math.isfinite(float(q['EMA20'])) and float(q['EMA20'])>0
    return q

def predicate(q,arm):
    """Three-valued truth; only known True adds a restriction.

    JOINT requires both parent-ready flags. Any unready factor in the chosen
    predicate leaves original permission unchanged, without cancelling a sell.
    """
    assert arm in ARMS
    r=(float(q['RS20'])<=0) if q['ready_R'] else None
    p=(float(q['close'])<float(q['EMA20'])) if q['ready_P'] else None
    if arm=='BASE':state=False
    elif arm=='R_ONLY':state=r
    elif arm=='P_ONLY':state=p
    else:state=(r and p) if q['ready_R'] and q['ready_P'] else None
    return dict(R_weak=r,P_weak=p,predicate_state='UNKNOWN' if state is None else 'TRUE' if state else 'FALSE',
                denies_mobile=state is True,unknown_keeps_native=True)

def patched_planning_source(native_source=None):
    """Exactly two insertions: held-mobile exit and mobile-only role guard."""
    source=Path(native_source or NATIVE_PLANNING).read_text();tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Runner')
    node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='planning')
    raw='\n'.join(source.splitlines()[node.lineno-1:node.end_lineno])+'\n'
    held_anchor="      if cp is not None and bool(cp.receipt):x['floor']=max(x['floor'],D(str(cp.candidate)))\n   a.sync(at);self.industry(a,at)"
    role_anchor="    for role in roles:\n     fline="
    assert raw.count(held_anchor)==raw.count(role_anchor)==1,'native planning anchors drifted'
    held_hook="    self._mobile_authorization_exit(a,sid,at,row,clock,quote)\n"
    # Never use the stale row variable from the earlier holdings/stock loop.
    role_hook="     if role=='mobile' and not self._mobile_role_allowed(a,sid,at,self.facts.row(sid,at),cpr):continue\n"
    changed=raw.replace(held_anchor,held_anchor.replace('   a.sync(at)',held_hook+'   a.sync(at)'))
    changed=changed.replace(role_anchor,role_anchor.replace('     fline=',role_hook+'     fline='))
    assert changed.replace(held_hook,'').replace(role_hook,'')==raw,'incidental native policy change'
    return textwrap.dedent(raw),textwrap.dedent(changed)

class MobileHooks:
    def _mobile_context(self,sid,at,row):
        q=provider_value(type(self).mobile_overlay_provider,sid,at,row,self.sector_by_sid[sid])
        return q,predicate(q,self.mobile_overlay_arm)

    def _mobile_authorization_exit(self,a,sid,at,row,clock,quote):
        # Original ACT/I branches have already passed; all original mobile OLD
        # floors were checked and native ratchets applied before this hook.
        assert a.risk_state['on'] and bool(row.i_target)
        live=a.live(sid);mobile=[]
        for x in live:
            role=a.jmeta[x['id']]['role']
            assert (role=='mobile')==(x['kind']=='add'),'native role/kind mismatch'
            if role=='mobile':mobile.append(x)
        if not mobile:return False
        q,decision=self._mobile_context(sid,at,row);pending=set(a.sell_layers.get(sid,set()))
        ids=[x['id'] for x in mobile if x['id'] not in pending] if decision['denies_mobile'] else []
        log=dict(at=str(at),account=a.label,sid=sid,arm=self.mobile_overlay_arm,phase='held_mobile_after_native_hard_exits',
                 native_ACT_on=True,native_I_target=True,context=q,decision=decision,
                 live_mobile_layer_ids=[x['id'] for x in mobile],prior_pending_layer_ids=sorted(pending),
                 added_mobile_exit_layer_ids=list(ids),core_exit_ids_added=[],request_reason=None)
        if ids:
            reason='mobile_authorization_'+self.mobile_overlay_arm
            a.sell(sid,clock,quote,ids,reason);log['request_reason']=reason
        self.mobile_overlay_log.append(log)
        return bool(ids)

    def _mobile_role_allowed(self,a,sid,at,row,cpr):
        # Called only INSIDE original `for role in roles`, for role==mobile.
        # Original Q/fresh receipt/ACT/industry/exit/buy-pending guards remain.
        assert cpr and cpr.get('receipt_id'),'missing original fresh CP receipt'
        q,decision=self._mobile_context(sid,at,row);allowed=not decision['denies_mobile']
        log=dict(at=str(at),account=a.label,sid=sid,arm=self.mobile_overlay_arm,phase='new_mobile_role_before_pending',
                 role='mobile',CP1_id=cpr['receipt_id'],context=q,decision=decision,allowed=allowed,
                 original_receipt_mutated=False,original_core_permission_mutated=False,
                 result='native_permission_retained' if allowed else 'mobile_authorization_denied_'+self.mobile_overlay_arm)
        self.mobile_overlay_log.append(log)
        if not allowed:
            self.funding.append(dict(account=a.label,at=at,sid=sid,role='mobile',CP1_id=cpr['receipt_id'],
                                     result=log['result'],decision_phase='CLOSE_before_pending',overlay_arm=self.mobile_overlay_arm))
        return allowed

def build_runner_class(no60_module,provider,arm):
    """Class build only. Parent separately freezes inputs/scope before use."""
    assert arm in ARMS
    A=no60_module;N,J,IO=A.N,A.J,A.IO
    assert A.Runner.route is A.P.ROUTES[True]
    assert inspect.getsourcefile(J.Runner.planning)==str(NATIVE_PLANNING)
    old,new=patched_planning_source();assert textwrap.dedent(inspect.getsource(J.Runner.planning))==old
    env=dict(J.__dict__);exec(compile(new,str(HERE/'DERIVED_PLANNING_DRAFT.py'),'exec'),env);changed_plan=env['planning']
    provider_sha='BASE_NO_PROVIDER' if arm=='BASE' else provider.manifest_sha256
    if arm!='BASE':assert isinstance(provider_sha,str) and len(provider_sha)==64
    assert 'Runner' not in globals(),'one arm/class per fresh process for checkpoint identity'

    class Runner(MobileHooks,A.Runner):
        mobile_overlay_provider=provider
        def __init__(self,*args,**kwargs):
            self._mobile_bootstrap=True
            super().__init__(*args,**kwargs)
            self.mobile_overlay_arm=arm;self.mobile_overlay_provider_sha256=provider_sha;self.mobile_overlay_log=[]
            self.integration_policy=A.POLICY+':'+VERSION+':'+arm+':'+self.rank_mode
            self._mobile_bootstrap=False;self.assert_native_wiring()

        def planning(self,at):
            if arm=='BASE':return N.Runner.planning(self,at)
            changed_plan(self,at)
            if self.rank_mode!='H1':
                for a in self.accounts.values():self.rank_log.extend(dict(account=a.label,**r) for r in N.apply_priority(a,N.SCORES.at,str(at.date())))

        def assert_native_wiring(self):
            cap=getattr(self,'_cap_bootstrap',False);boot=getattr(self,'_mobile_bootstrap',False)
            prefix=N.POLICY if cap else A.POLICY if boot else A.POLICY+':'+VERSION+':'+arm
            assert self.integration_policy==prefix+':'+self.rank_mode
            assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
            assert self.opening.__func__ is J.Runner.opening
            assert self.route.__func__ is A.P.ROUTES[True]
            assert self.planning.__func__ is Runner.planning
            for a in self.accounts.values():
                assert type(a) is J.Account
                assert type(a.budget) is (N.BASE.NoAccountBudget if cap else A.NoConfirmed60Budget)
                if not boot:
                    assert a.budget.request.__func__ is A.P.MOD.Contract.request
                    assert a.budget.migrate.__func__ is A.NoConfirmed60Budget.migrate
                for name in ('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys'):
                    assert getattr(a,name).__func__ is getattr(J.Account,name)
            if not boot:
                assert self.mobile_overlay_arm==arm and self.mobile_overlay_provider_sha256==provider_sha

        def restore(self,path):
            payload=pickle.loads(Path(path).read_bytes());r=payload['runner']
            assert r['integration_policy']==self.integration_policy and r['mobile_overlay_arm']==arm
            assert r['mobile_overlay_provider_sha256']==provider_sha
            return super().restore(path)

        def dump_joint(self,path):
            super().dump_joint(path)
            IO.write_gzip_jsonl(Path(path)/'mobile-authorization-policy.jsonl.gz',self.mobile_overlay_log)

    Runner.__module__=__name__;Runner.__qualname__='Runner';globals()['Runner']=Runner
    return Runner

def source_patch_diff():
    import difflib
    old,new=patched_planning_source()
    return ''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='original_joint_v3.planning',tofile='draft_mobile_authorization_overlay.planning'))

def source_freeze(no60_module):
    result=dict(no60_module.source_freeze())
    for p in [Path(__file__),HERE/'DRAFT_CONTRACT.txt',HERE/'check_draft.py']:result[str(p.resolve())]=sha(p)
    return result

if __name__=='__main__':raise SystemExit('Draft adapter only. No financial execution; await parent domain/provider/policy freeze.')
