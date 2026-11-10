"""PVR_SLOT1: one stock-priority substitution over original coupled SC/Bdiag.

No native opening, route, sizing, protection, eligibility or ledger override.
The original planning body completes before the frozen pending priority keys
are substituted. Missing scores retain their original unique-stock slots.
"""
from pathlib import Path
from types import MappingProxyType
import sys, hashlib, json, math, pickle, shutil
import pandas as pd

O = Path(__file__).resolve().parent
W = O.parent
sys.path.insert(0, str(W/'account-risk-ablation-20261031'))
import adapter as BASE
J, L = BASE.J, BASE.L
sys.path.insert(0, str(W/'_shared'))
import research_output_io as IO

POLICY = 'PVR_SLOT1_original_singlepass_coupled'
SCORES = None

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

class FrozenScores:
    def __init__(self, path):
        self.path = str(Path(path).resolve()); self.manifest_sha256 = sha(path)
        m = json.loads(Path(path).read_text())
        assert m['stocks'] == len(set(m['fixed_stock_ids'])) == 1709
        self.values = {}
        for r in m['entries']:
            p = Path(path).parent/'scores'/f"{r['symbol']}.parquet"
            assert sha(p) == r['output_sha256']
            f = pd.read_parquet(p)
            assert f.index.is_unique
            self.values[r['symbol']] = MappingProxyType({str(t.date()): float(v) for t, v in f.score.items()})
        self.values = MappingProxyType(self.values)
    def at(self, sid, day):
        v = self.values.get(sid, {}).get(day)
        return v if v is not None and math.isfinite(v) else None

def configure_scores(path=None):
    global SCORES
    SCORES = FrozenScores(path or O/'SCORES_MANIFEST.json')
    return SCORES

def priority_plan(intents, score_at, day):
    """Pure planning: preserve unique-stock original slots, not role slots."""
    ordered = sorted(intents, key=lambda i: (i['rank'], i['role'] != 'core'))
    original = []; rank = {}; roles = {}
    for i in ordered:
        sid = i['sid']
        if sid not in rank:
            original.append(sid); rank[sid] = i['rank']; roles[sid] = []
        assert rank[sid] == i['rank'], ('inconsistent same-stock original key', sid)
        assert i['role'] not in roles[sid], ('duplicate native role', sid)
        roles[sid].append(i['role'])
    assert len(set(rank.values())) == len(rank), 'original stock priority keys must be unique'
    values = {s: score_at(s, day) for s in original}
    values = {s: float(v) if v is not None and math.isfinite(v) else None for s, v in values.items()}
    ready = [s for s in original if values[s] is not None]
    oldpos = {s: n for n, s in enumerate(original)}
    ready.sort(key=lambda s: (-round(values[s], 12), oldpos[s]))
    ready_iter = iter(ready)
    final = [s if values[s] is None else next(ready_iter) for s in original]
    assert set(final) == set(original) and len(final) == len(original)
    assert all(final[n] == s for n, s in enumerate(original) if values[s] is None)
    # Retain original numeric slot keys (including full-universe rank gaps).
    slots = [rank[s] for s in original]
    keys = {s: slots[n] for n, s in enumerate(final)}
    return keys, [dict(sid=s, day=day, original_H1_rank=rank[s], priority_rank=keys[s],
                      original_slot=oldpos[s], final_slot=final.index(s), PVR=values[s],
                      PVR_ready=values[s] is not None, roles=roles[s]) for s in original]

def apply_priority(account, score_at, day):
    """Only rank keys change; original target/price/floor/role/receipt stay exact."""
    keys, log = priority_plan(account.pending, score_at, day)
    before = [{k: v for k, v in i.items() if k != 'rank'} for i in account.pending]
    d = account.decisions[-1]
    assert str(d['at'])[:10] == day
    for i in account.pending: i['rank'] = keys[i['sid']]
    for i in d['intents']: i['rank'] = keys[i['sid']]
    assert before == [{k: v for k, v in i.items() if k != 'rank'} for i in account.pending]
    return log

class Runner(BASE.Runner):
    def __init__(self, *args, rank_mode='PVR_SLOT1', **kw):
        assert rank_mode in ('H1', 'PVR_SLOT1') and SCORES is not None
        super().__init__(*args, **kw)
        self.rank_mode = rank_mode
        self.integration_policy = POLICY+':'+rank_mode
        self.rank_scores_manifest_sha256 = SCORES.manifest_sha256
        self.rank_log = []
        self.assert_native_wiring()

    def assert_native_wiring(self):
        assert self.integration_policy == POLICY+':'+self.rank_mode
        assert SCORES is not None and self.rank_scores_manifest_sha256 == SCORES.manifest_sha256
        assert self.opening.__func__ is J.Runner.opening
        assert self.route.__func__ is BASE.Runner.route
        assert self.planning.__func__ is Runner.planning
        for a in self.accounts.values():
            assert type(a) is J.Account and type(a.budget) is BASE.NoAccountBudget
            for name in ('reserve_quantity', 'fill_buy', 'fill_exit', 'cancel_buy', 'split', 'sync', 'assert_budget_view'):
                assert getattr(a, name).__func__ is getattr(J.Account, name)

    def planning(self, at):
        J.Runner.planning(self, at)
        if self.rank_mode == 'H1': return
        for a in self.accounts.values():
            log = apply_priority(a, SCORES.at, str(at.date()))
            self.rank_log.extend(dict(account=a.label, **r) for r in log)

    def restore(self, path):
        p = pickle.loads(Path(path).read_bytes())
        assert p['runner']['integration_policy'] == self.integration_policy, 'checkpoint rank policy mode mismatch'
        assert p['runner']['rank_scores_manifest_sha256'] == SCORES.manifest_sha256, 'checkpoint PVR source mismatch'
        result = super().restore(path)
        self.assert_native_wiring()
        return result

    def checkpoint(self, out, last_event):
        super().checkpoint(out, last_event)
        day = str(last_event.date())
        if day in {'2022-03-31','2022-06-30','2022-09-30','2022-12-30',
                   '2025-09-30','2025-12-31','2026-03-31','2026-06-30'}:
            for suffix in ('pkl', 'json'):
                shutil.copyfile(Path(out)/('checkpoint.'+suffix), Path(out)/('checkpoint-'+day+'.'+suffix))

    def dump_joint(self, path):
        super().dump_joint(path)
        IO.write_gzip_jsonl(Path(path)/'rank-policy.jsonl.gz', self.rank_log)

def source_freeze():
    paths = [Path(__file__), Path(BASE.__file__), Path(J.__file__), Path(L.__file__),
             W/'account-risk-ablation-20261031/model_without_account_check.py',
             W/'account-risk-ablation-20261031/route_without_account_check.py',
             Path(IO.__file__), J.BASE/'wire.py', J.BASE/'budget_v3/model.py',
             Path(J.C.__file__), Path(J.LR.__file__), Path(J.BP.__file__),
             O/'SCORES_MANIFEST.json']
    return {str(p.resolve()): sha(p) for p in paths}

if __name__ == '__main__':
    raise SystemExit('Adapter only. Full financial paths require separate authorization.')
