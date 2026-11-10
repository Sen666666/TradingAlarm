"""Research-only ORIGINAL SINGLEPASS integration; no execution rule overrides.

The only policy differences are the two reviewed migration/admission gates.
Budget is an authorization view of the original native ledger, not an executor.
"""
from pathlib import Path
import sys, hashlib, pickle, inspect

O = Path(__file__).resolve().parent
ROOT = O.parent
sys.path.insert(0, str(ROOT / 'account-risk-ablation-20261031'))
import adapter as BASE
J = BASE.J
sys.path.insert(0, str(ROOT / '_shared'))
import research_output_io as IO

OLD_MODEL = ROOT / 'account-risk-ablation-20261031/model_without_account_check.py'
OLD_ROUTE = ROOT / 'account-risk-ablation-20261031/route_without_account_check.py'
MODEL = O / 'sources/model_decoupled.py'
ROUTE = O / 'sources/route_decoupled.py'
MG = "        if pool == 'confirmed':\n            if not self.migrate(sector):\n                return 'confirmed_unfunded'\n"
MN = "        if pool == 'confirmed':\n            self.migrate(sector)  # Best effort; failure is not new-order ineligibility.\n"
RG = "   if b.migrate(sector):a.pools_from_model();routes.append('confirmed')"
RN = "   if b.migrate(sector):a.pools_from_model()\n   routes.append('confirmed')"
assert OLD_MODEL.read_text().count(MG) == OLD_ROUTE.read_text().count(RG) == 1
assert MODEL.read_text().replace(MN, MG) == OLD_MODEL.read_text()
assert ROUTE.read_text().replace(RN, RG) == OLD_ROUTE.read_text()
D = J.W.load('native_decoupled_admission_budget', MODEL)
env = dict(J.__dict__)
exec(compile(ROUTE.read_text(), str(ROUTE), 'exec'), env)
decoupled_route = env['route']

class DecoupledBudget(BASE.NoAccountBudget):
    request = D.Contract.request

def enable(account, *, decoupled):
    """Retain every native account/attempt/order/receipt/ledger object in place."""
    assert type(account.budget) in (J.Budget, BASE.NoAccountBudget, DecoupledBudget)
    account.budget.__class__ = DecoupledBudget if decoupled else BASE.NoAccountBudget
    return account

class CoupledRunner(BASE.Runner):
    """Original Bdiag policy, used only for the authorized short identity gate."""
    policy_mode = 'original_singlepass_coupled'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.integration_policy = self.policy_mode
        self.assert_native_wiring()

    def assert_native_wiring(self):
        expected = DecoupledBudget if self.policy_mode.endswith('_decoupled') else BASE.NoAccountBudget
        assert self.integration_policy == self.policy_mode
        for a in self.accounts.values():
            assert type(a) is J.Account and type(a.budget) is expected
            for name in ('reserve_quantity', 'fill_buy', 'fill_exit', 'cancel_buy', 'split', 'sync', 'assert_budget_view'):
                assert getattr(a, name).__func__ is getattr(J.Account, name)
        assert self.planning.__func__ is J.Runner.planning
        assert self.opening.__func__ is J.Runner.opening

    def restore(self, path):
        # Additional policy guard, not a replacement for source/provenance guards.
        p = pickle.loads(Path(path).read_bytes())
        assert p['runner']['integration_policy'] == self.policy_mode, 'checkpoint policy mode mismatch'
        value = super().restore(path)
        self.assert_native_wiring()
        return value

class DecoupledRunner(CoupledRunner):
    policy_mode = 'original_singlepass_decoupled'
    route = decoupled_route
    def __init__(self, *args, **kwargs):
        # BASE init warms native market states; do not reseed a fresh account.
        BASE.Runner.__init__(self, *args, **kwargs)
        for a in self.accounts.values():
            enable(a, decoupled=True)
        self.integration_policy = self.policy_mode
        self.assert_native_wiring()

def source_freeze():
    paths = [Path(__file__), MODEL, ROUTE, OLD_MODEL, OLD_ROUTE,
             Path(BASE.__file__), Path(J.__file__), Path(BASE.L.__file__),
             Path(IO.__file__), J.BASE/'wire.py', J.BASE/'budget_v3/model.py',
             Path(J.C.__file__), Path(J.LR.__file__), Path(J.BP.__file__)]
    return {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def static_contract():
    methods = {}
    for name in ('resources','valid','migrate','fill','sell','cancel','cancel_ack','loss','industry','invalidate'):
        methods[name] = inspect.getsource(getattr(D.Contract,name)) == inspect.getsource(getattr(BASE.N.Contract,name))
    assert all(methods.values())
    return dict(passed=True, unchanged_budget_methods=methods,
                native_execution_callbacks='all inherited verbatim; budget.fill/sell are never used by native callbacks',
                original_singlepass_opening=True, core_first_reservation_unchanged=True,
                economic_changes=['route considers confirmed after failed best-effort migration',
                                  'request repeats best-effort migration without requiring success'],
                source_freeze=source_freeze())
