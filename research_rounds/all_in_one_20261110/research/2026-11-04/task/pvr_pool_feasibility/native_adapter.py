"""Minimal native PVR one-mechanism adapter; no implicit execution entrypoint."""
from pathlib import Path
import sys,pickle,hashlib
import component as P
W=P.W;O=P.O
sys.path.insert(0,str(W/'pvr-slot1-native-readiness-20261101'))
import execution_support as S
N,J,L,IO=S.N,S.J,S.L,S.IO
POLICY='PVR_SLOT1_NO_CONFIRMED60_ONLY'

class NoConfirmed60Budget(N.BASE.NoAccountBudget):
    request=P.MOD.Contract.request
    def migrate(self,sector):
        return P.MOD.Contract.migrate(self,sector) if self.expand else False

class Runner(N.Runner):
    route=P.ROUTES[True]
    def __init__(self,*args,**kwargs):
        self._cap_bootstrap=True
        super().__init__(*args,**kwargs)
        self.remove_confirmed60=True
        for a in self.accounts.values():a.budget.__class__=NoConfirmed60Budget
        self.integration_policy=POLICY+':'+self.rank_mode
        self._cap_bootstrap=False
        self.assert_native_wiring()

    def assert_native_wiring(self):
        bootstrap=getattr(self,'_cap_bootstrap',False)
        assert self.integration_policy==(N.POLICY if bootstrap else POLICY)+':'+self.rank_mode
        assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
        assert self.opening.__func__ is J.Runner.opening
        assert self.planning.__func__ is N.Runner.planning
        assert self.route.__func__ is P.ROUTES[True]
        for a in self.accounts.values():
            assert type(a)is J.Account and type(a.budget)is (N.BASE.NoAccountBudget if bootstrap else NoConfirmed60Budget)
            if not bootstrap:
                assert a.budget.request.__func__ is P.MOD.Contract.request
                assert a.budget.migrate.__func__ is NoConfirmed60Budget.migrate
            for name in ('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys'):
                assert getattr(a,name).__func__ is getattr(J.Account,name)

    def restore(self,path):
        # Original source freeze check still happens in PreparedRunner.restore;
        # atomic_runner_outputs adds the original exact engine-provenance gate.
        p=pickle.loads(Path(path).read_bytes())
        assert p['runner']['integration_policy']==self.integration_policy,'checkpoint cap policy mismatch'
        assert p['runner']['rank_scores_manifest_sha256']==N.SCORES.manifest_sha256
        assert p['runner']['remove_confirmed60']==self.remove_confirmed60
        result=L.PreparedRunner.restore(self,path)
        self.assert_native_wiring()
        return result

def source_freeze():
    result=S.freeze()
    result.update(P.source_hashes())
    for p in [Path(__file__),O/'NATIVE_WIRING_CARD.txt']:
        result[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result

if __name__=='__main__':raise SystemExit('Adapter only; economic execution needs root grant and a separate frozen card.')
