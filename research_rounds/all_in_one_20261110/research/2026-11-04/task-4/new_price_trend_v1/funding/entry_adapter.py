"""One frozen flat-entry AND gate over the original native No60 account.

OFF delegates the original PVR planning function. ON differs from J.planning
by exactly one inserted call after the original roles/barriers have passed.
No account, opening, route, sizing, protection, or execution method is replaced.
"""
from pathlib import Path
import hashlib, inspect, json, pickle, sys, textwrap
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
ROOT = O.parent
POOL = Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility')
sys.path.insert(0, str(POOL))
import native_adapter as A
N, J, L, S, IO = A.N, A.J, A.L, A.S, A.IO
POLICY = 'ENTRY_BB20_FLAT_CONFIRM'
FEATURES = None

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class FrozenFeatures:
    def __init__(self, path=ROOT/'PRICE_FEATURES.pkl', manifest=ROOT/'PRICE_FEATURE_MANIFEST.json', through=None):
        self.manifest_sha256 = sha(manifest)
        m = json.loads(Path(manifest).read_text())
        assert m['passed'] and m['stocks'] == 1709 and sha(path) == m['output_sha256']
        data = pd.read_pickle(path)
        assert len(data) == 1709
        self.values = {}
        for sid, f in data.items():
            assert f.index.is_unique and f.index.tz is None
            assert {'bb20_cross_known','bb20_cross','source_segment','close'} <= set(f.columns)
            if through is not None: f = f.loc[:through]
            rows = {}
            for day, known, cross, segment, close in zip(f.index, f.bb20_cross_known, f.bb20_cross, f.source_segment, f.close):
                assert isinstance(known, (bool, np.bool_))
                assert isinstance(cross, (bool, np.bool_))
                rows[day.date()] = (bool(known), bool(cross), segment, float(close))
            self.values[sid] = rows
        self.physical_through = through

    def at(self, sid, at):
        return self.values.get(sid, {}).get(at.date())

def configure_features(**kwargs):
    global FEATURES
    FEATURES = FrozenFeatures(**kwargs)
    return FEATURES

ORIGINAL_PLANNING_SOURCE = textwrap.dedent(inspect.getsource(J.Runner.planning))
NEEDLE = '   if why or not roles:continue\n'
INSERTION = '   if not self.entry_bb20_accept(a,sid,at,roles,held):continue\n'
assert ORIGINAL_PLANNING_SOURCE.count(NEEDLE) == 1
GATED_PLANNING_SOURCE = ORIGINAL_PLANNING_SOURCE.replace(NEEDLE, NEEDLE + INSERTION)
assert GATED_PLANNING_SOURCE.replace(INSERTION, '') == ORIGINAL_PLANNING_SOURCE
_env = dict(J.__dict__)
exec(compile(GATED_PLANNING_SOURCE, str(O/'generated_entry_planning.py'), 'exec'), _env)
GATED_PLANNING = _env['planning']

class Runner(A.Runner):
    def __init__(self, *args, entry_mode='OFF', **kwargs):
        assert entry_mode in ('OFF', 'BB20') and FEATURES is not None
        self.entry_mode = entry_mode
        self.entry_features_sha256 = FEATURES.manifest_sha256
        self.entry_gate = []
        self._entry_bootstrap = True
        super().__init__(*args, **kwargs)
        self._entry_bootstrap = False
        self.integration_policy = A.POLICY + ':' + self.rank_mode + ':' + POLICY + ':' + entry_mode
        self.assert_native_wiring()

    def assert_native_wiring(self):
        cap_bootstrap = getattr(self, '_cap_bootstrap', False)
        entry_bootstrap = getattr(self, '_entry_bootstrap', False)
        expected = (N.POLICY if cap_bootstrap else A.POLICY) + ':' + self.rank_mode
        if not entry_bootstrap: expected += ':' + POLICY + ':' + self.entry_mode
        assert self.integration_policy == expected
        assert self.rank_scores_manifest_sha256 == N.SCORES.manifest_sha256
        assert self.entry_features_sha256 == FEATURES.manifest_sha256
        assert self.opening.__func__ is J.Runner.opening
        assert self.planning.__func__ is Runner.planning
        assert self.route.__func__ is A.P.ROUTES[True]
        for a in self.accounts.values():
            assert type(a) is J.Account
            assert type(a.budget) is (N.BASE.NoAccountBudget if cap_bootstrap else A.NoConfirmed60Budget)
            if not cap_bootstrap:
                assert a.budget.request.__func__ is A.P.MOD.Contract.request
                assert a.budget.migrate.__func__ is A.NoConfirmed60Budget.migrate
            for name in ('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys'):
                assert getattr(a, name).__func__ is getattr(J.Account, name)

    def entry_bb20_accept(self, a, sid, at, roles, held):
        if held:
            self.entry_gate.append(dict(account=a.label,day=str(at.date()),sid=sid,roles=list(roles),held=True,
                                        known=None,cross=None,accepted=True,reason='held_ADD_unchanged'))
            return True
        row = FEATURES.at(sid, at)
        known = row is not None and row[0] is True
        if known:
            fact = self.facts.row(sid, at)
            assert fact is not None and float(fact.close) == row[3], ('feature close mismatch',sid,str(at))
            assert int(fact.segment_id) == int(row[2]), ('feature source segment mismatch',sid,str(at))
        accepted = known and row[1] is True
        self.entry_gate.append(dict(account=a.label,day=str(at.date()),sid=sid,roles=list(roles),held=False,
                                    known=known,cross=row[1] if known else None,accepted=accepted,
                                    source_segment=str(row[2]) if row is not None else None,
                                    feature_close=row[3] if row is not None else None,
                                    reason='BB20_cross' if accepted else 'BB20_no_cross' if known else 'BB20_unknown'))
        return accepted

    def planning(self, at):
        if self.entry_mode == 'OFF':
            return N.Runner.planning(self, at)
        GATED_PLANNING(self, at)
        if self.rank_mode == 'H1': return
        for a in self.accounts.values():
            log = N.apply_priority(a, N.SCORES.at, str(at.date()))
            self.rank_log.extend(dict(account=a.label, **r) for r in log)

    def restore(self, path):
        p = pickle.loads(Path(path).read_bytes())
        assert p['runner']['entry_mode'] == self.entry_mode
        assert p['runner']['entry_features_sha256'] == FEATURES.manifest_sha256
        return super().restore(path)

    def dump_joint(self, path):
        super().dump_joint(path)
        IO.write_gzip_jsonl(Path(path)/'entry-gate.jsonl.gz', self.entry_gate)

def source_freeze():
    result = A.source_freeze()
    for path in [Path(__file__), O/'input_loader.py', O/'run_entry.py', ROOT/'PROTOCOL.txt',
                 ROOT/'PRICE_FEATURE_MANIFEST.json', ROOT/'PRICE_FEATURES.pkl']:
        result[str(path.resolve())] = sha(path)
    return result

if __name__ == '__main__':
    raise SystemExit('Adapter only; explicit reviewed technical/full runner required.')
