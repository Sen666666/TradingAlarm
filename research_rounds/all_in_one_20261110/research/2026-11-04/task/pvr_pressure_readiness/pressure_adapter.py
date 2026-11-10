"""Minimal PVR cost2 / D1v2 composition; no implicit economic entrypoint."""
from pathlib import Path
import copy, inspect, pickle, sys, textwrap
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
sys.path.insert(0,str(W/'pvr-slot1-d1-v2-composition-preflight-20261101'))
import composition as A
sys.path.insert(0,str(O.parent/'pvr_pool_feasibility'))
import native_adapter as B
E,N,J,L,IO,S,Q=A.E,A.N,A.J,A.L,A.IO,A.S,A.Q
assert B.N is N and B.J is J
P=B.P

AMEND_OLD="  if pc-oldcap+cap>(.10 if bo.pool=='probe' else .60)*nav+1e-8:out.append('pool_capital')"
AMEND_NEW="  if bo.pool=='probe' and pc-oldcap+cap>.10*nav+1e-8:out.append('pool_capital')"
AMEND_SOURCE=textwrap.dedent(inspect.getsource(E.Account.amend_d1))
assert AMEND_SOURCE.count(AMEND_OLD)==1
AMEND_NO60=AMEND_SOURCE.replace(AMEND_OLD,AMEND_NEW)
assert AMEND_NO60.replace(AMEND_NEW,AMEND_OLD)==AMEND_SOURCE
env=dict(E.__dict__)
exec(compile(AMEND_NO60,str(O/'derived_amend_d1_no60.py'),'exec'),env)
class No60D1Account(E.Account):
    amend_d1=env['amend_d1']

def source_freeze():
    value=A.source_freeze();value.update(B.source_freeze())
    for p in (Path(__file__),O/'PRESSURE_EXPERIMENT_CARD.txt',Path(E.R.__file__)):
        value[str(p.resolve())]=N.sha(p)
    return value

def read_inputs(window):
    previous=S.O
    try:
        S.O=O
        return S.inputs(window)
    finally:S.O=previous

class CostRunner(N.Runner):
    """PVR planner; existing cost-window opening; original native Account."""
    remove60=False
    opening=E.R.PressureBase.opening
    route=N.BASE.Runner.route
    def __init__(self,*args,cost=2,**kw):
        assert cost in (1,2)
        self._pressure_bootstrap=True;self.pressure_cost=cost
        super().__init__(*args,**kw)
        self.remove_confirmed60=self.remove60
        for a in self.accounts.values():
            a.cost_multiplier=cost
            if self.remove60:a.budget.__class__=B.NoConfirmed60Budget
        self.pressure_binding=dict(contract='original_cost_multiplier',cost=cost,D1=False,
            remove_confirmed60=self.remove60,rank=self.rank_mode,scores=N.SCORES.manifest_sha256)
        self.integration_policy='PVR_PRESSURE:'+str(self.pressure_binding)
        self._pressure_bootstrap=False;self.assert_native_wiring()
    def assert_native_wiring(self):
        bootstrap=getattr(self,'_pressure_bootstrap',False)
        assert self.opening.__func__ is E.R.PressureBase.opening
        assert self.planning.__func__ is N.Runner.planning
        assert self.route.__func__ is (P.ROUTES[True] if self.remove60 else N.BASE.Runner.route)
        assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
        for a in self.accounts.values():
            assert type(a) is J.Account
            assert type(a.budget) is (B.NoConfirmed60Budget if self.remove60 and not bootstrap else N.BASE.NoAccountBudget)
            for name in ('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys'):
                assert getattr(a,name).__func__ is getattr(J.Account,name)
            if not bootstrap:assert a.cost_multiplier==self.pressure_cost and a.delay_events==0
    def restore(self,path):
        p=pickle.loads(Path(path).read_bytes())
        assert p['runner']['pressure_binding']==self.pressure_binding,'pressure policy/cost binding mismatch'
        at=L.PreparedRunner.restore(self,path);self.assert_native_wiring();return at
class No60CostRunner(CostRunner):
    remove60=True
    route=P.ROUTES[True]

class D1Runner(A.Composition):
    """Original Composition with explicit pressure identity and checked MRO."""
    remove60=False
    route=E.BASE.Runner.route
    def __init__(self,*args,**kw):
        self._pressure_bootstrap=True
        super().__init__(*args,enabled=True,**kw)
        self.remove_confirmed60=self.remove60
        for a in self.accounts.values():
            if self.remove60:
                a.__class__=No60D1Account;a.budget.__class__=B.NoConfirmed60Budget
        self.composition_binding['policy']='PVR_PRESSURE_D1v2_NO60' if self.remove60 else 'PVR_PRESSURE_D1v2_CONTROL'
        self.composition_binding['remove_confirmed60']=self.remove60
        self._pressure_bootstrap=False;self.assert_composition()
    def assert_composition(self):
        boot=getattr(self,'_pressure_bootstrap',False);b=self.composition_binding
        assert b['policy']==(A.POLICY if boot else ('PVR_PRESSURE_D1v2_NO60' if self.remove60 else 'PVR_PRESSURE_D1v2_CONTROL'))
        assert b['rank_mode']==self.rank_mode=='PVR_SLOT1'
        assert b['D1_enabled']==self.d1_enabled is True and self.reference=='B_diag'
        assert b['PVR_source_sha256']==N.sha(A.P/'native_rank.py')==A.PVR_SHA
        assert b['D1_source_sha256']==N.sha(A.D1/'d1_runner.py')==A.D1_SHA
        assert b['PVR_scores_manifest_sha256']==N.SCORES.manifest_sha256
        assert self.planning.__func__ is A.Composition.planning
        assert self.opening.__func__ is E.Pair.opening
        assert self.route.__func__ is (P.ROUTES[True] if self.remove60 else E.BASE.Runner.route)
        assert self.prepare_carried.__func__ is E.Pair.prepare_carried
        assert self.revalidate_carried_buys.__func__ is E.Pair.revalidate_carried_buys
        for a in self.accounts.values():
            changed=self.remove60 and not boot
            assert type(a) is (No60D1Account if changed else E.Account)
            assert type(a.budget) is (B.NoConfirmed60Budget if changed else E.BASE.NoAccountBudget)
            assert a.d1_enabled and a.delay_events==1 and a.d1_account_cap is False and a.cost_multiplier==1
            assert a.amend_d1.__func__ is (No60D1Account.amend_d1 if changed else E.Account.amend_d1)
            for name in ('reserve_quantity','fill_buy','expire_day_buys'):
                assert getattr(a,name).__func__ is getattr(E.Account,name)
            for name in ('fill_exit','cancel_buy','split','sync','assert_budget_view'):
                assert getattr(a,name).__func__ is getattr(J.Account,name)
class No60D1Runner(D1Runner):
    remove60=True
    route=P.ROUTES[True]

if __name__=='__main__':raise SystemExit('Readiness adapter only; full economic execution needs separate root grant.')
