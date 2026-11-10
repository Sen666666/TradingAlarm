"""Thin frozen PVR_SLOT1 priority x frozen DiagD1-v2 execution composition.

Research preflight only. Neither the source components nor old archives are
changed. PVR touches new pending intents after the original D1 close planner;
retained native orders are managed solely by the original D1 lifecycle.
"""
from pathlib import Path
import copy, gzip, hashlib, importlib.util, json, pickle, shutil, sys

O = Path(__file__).resolve().parent
W = O.parent
P = W/'pvr-slot1-native-readiness-20261101'
D1 = W/'d1-delay-contract-v2-20261031'
PVR_SHA = '5ec91c2323b2d3b8fa5c99df504139e2ac7af9b5b84359222c3d6353d0cd697c'
D1_SHA = '4256f369439cea44e8283a7f5717befa08af6b0d5ab95a7250982d608f74f5c6'
SC_SHA = '5939c4be8195319d8e60ada801430a3cd82d289ece7e5964f84f59ebe0d1a08e'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(name, path):
    if name in sys.modules:
        m = sys.modules[name]
        assert Path(m.__file__).resolve() == Path(path).resolve()
        return m
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

assert sha(D1/'d1_runner.py') == D1_SHA
assert sha(P/'native_rank.py') == PVR_SHA
E = load('frozen_D1_reference_engines', D1/'d1_runner.py')
sys.path.insert(0, str(P))
import native_rank as N
import execution_support as S
sys.path.insert(0, str(W/'q2-normal-continuation-20261031'))
import continuation as Q
J, L, IO, OLD_IO = E.J, E.L, N.IO, E.R.P.IO
assert N.J is J and N.BASE is E.BASE and N.L is L
POLICY = 'PVR_SLOT1_x_D1_v2_original_singlepass_coupled'

def source_freeze():
    result = N.source_freeze()
    paths = [Path(__file__), O/'CONTRACT.txt', O/'test_composition.py',
             O/'preflight.py', D1/'d1_runner.py', D1/'CONTRACT.txt',
             D1/'test_real_pair.py', Path(E.R.__file__), Path(Q.__file__),
             P/'execution_support.py', L.U/'STOCK_MANIFEST.json',
             L.U/'INDUSTRY_MANIFEST.json', L.U/'FREEZE.json',
             J.M.O/'recovery.csv', J.M.P/'h1.npz']
    for p in paths: result[str(p.resolve())] = sha(p)
    return result

class Composition(E.DiagD1):
    """Same D1 opening/route/callbacks; the only trading override is planning."""
    def __init__(self, *args, rank_mode='PVR_SLOT1', horizon_binding=None, **kw):
        super().__init__(*args, **kw)
        self.bind_composition(rank_mode, horizon_binding or {})

    def bind_composition(self, rank_mode, horizon_binding):
        assert rank_mode in ('H1', 'PVR_SLOT1') and N.SCORES is not None
        self.rank_mode = rank_mode
        self.rank_log = []
        self.composition_binding = dict(policy=POLICY, rank_mode=rank_mode,
            D1_enabled=self.d1_enabled, reference=self.reference,
            PVR_source_sha256=PVR_SHA, D1_source_sha256=D1_SHA,
            PVR_scores_manifest_sha256=N.SCORES.manifest_sha256,
            horizon=copy.deepcopy(horizon_binding))
        self.assert_composition()

    def assert_composition(self):
        b = self.composition_binding
        assert b['policy'] == POLICY and b['rank_mode'] == self.rank_mode
        assert b['D1_enabled'] == self.d1_enabled and b['reference'] == self.reference == 'B_diag'
        assert b['PVR_source_sha256'] == sha(P/'native_rank.py') == PVR_SHA
        assert b['D1_source_sha256'] == sha(D1/'d1_runner.py') == D1_SHA
        assert N.SCORES is not None and b['PVR_scores_manifest_sha256'] == N.SCORES.manifest_sha256
        assert self.planning.__func__ is Composition.planning
        assert self.opening.__func__ is E.Pair.opening
        assert self.route.__func__ is E.BASE.Runner.route
        assert self.prepare_carried.__func__ is E.Pair.prepare_carried
        assert self.revalidate_carried_buys.__func__ is E.Pair.revalidate_carried_buys
        for a in self.accounts.values():
            assert type(a) is E.Account and type(a.budget) is E.BASE.NoAccountBudget
            assert a.d1_enabled == self.d1_enabled and a.delay_events == int(self.d1_enabled)
            assert a.d1_account_cap is False
            for name in ('reserve_quantity', 'fill_buy', 'expire_day_buys', 'amend_d1'):
                assert getattr(a, name).__func__ is getattr(E.Account, name)
            for name in ('fill_exit', 'cancel_buy', 'split', 'sync', 'assert_budget_view'):
                assert getattr(a, name).__func__ is getattr(J.Account, name)

    def apply_new_priority(self, at):
        if self.rank_mode == 'H1': return
        for a in self.accounts.values():
            self.rank_log.extend(dict(account=a.label, **r)
                for r in N.apply_priority(a, N.SCORES.at, str(at.date())))

    def planning(self, at):
        E.Pair.planning(self, at)
        self.apply_new_priority(at)

    def restore(self, path):
        self.assert_composition()
        p = pickle.loads(Path(path).read_bytes())
        assert p['runner']['composition_binding'] == self.composition_binding, 'composition/source/horizon binding mismatch'
        result = super().restore(path)
        self.assert_composition()
        return result

    def checkpoint(self, out, last_event):
        # Audited horizon-safe I/O only: keep future lookup on construction,
        # rather than replacing it with a short physical-prefix lookup.
        Q.env2['checkpoint'](self, out, last_event)
        if str(last_event.date()) in {'2025-09-30','2025-12-31','2026-03-31','2026-06-30'}:
            for suffix in ('pkl','json'):
                shutil.copyfile(Path(out)/('checkpoint.'+suffix),
                    Path(out)/('checkpoint-'+str(last_event.date())+'.'+suffix))

    def dump_joint(self, path):
        E.Pair.dump_joint(self, path)
        IO.write_gzip_jsonl(Path(path)/'rank-policy.jsonl.gz', self.rank_log)

def verify_old_sc(shared, receipts, kw, path):
    """Verify old generation identity FIRST, with its actual frozen class."""
    path = Path(path)
    assert sha(path) == SC_SHA, 'SC parent checkpoint SHA mismatch'
    p = pickle.loads(path.read_bytes())
    meta = json.loads(path.with_suffix('.json').read_text())
    assert meta['sha256'] == SC_SHA and meta['source_freeze'] == p['source_freeze']
    for name, h in p['source_freeze'].items():
        assert Path(name).is_file() and sha(name) == h, ('old SC source changed', name)
    stager = E.DiagD1(shared, receipts, enabled=True, **kw)
    stager.source_freeze = copy.deepcopy(p['source_freeze'])
    with OLD_IO.atomic_runner_outputs(stager, L, O/'SC-old-identity-only', canonicalize=J.W.canon):
        at = stager.restore(path)
    assert at == J.M.N.iso('2026-03-31T15:10:00+08:00')
    assert all(Q.equal(v, stager.accounts[k].__dict__[f])
               for k, d in p['accounts'].items() for f, v in d.items())
    root = path.parent
    with gzip.open(root/'pair/B.json.gz', 'rt') as f: book = json.load(f)
    fields = {'trades':'trades','layers':'layers','jmeta':'metadata','journal':'journal',
              'buys':'orders','exits':'exits','audit_log':'audit','decisions':'decisions',
              'available':'ending_cash','current_nav':'ending_NAV'}
    a = stager.accounts['B']
    book_checks = {n:J.W.canon(getattr(a,n)) == book[s] for n,s in fields.items()}
    assert all(book_checks.values()), book_checks
    stream_checks = {}
    for field, name in [('daily','daily'),('funding','funding'),('opportunities','opportunities'),
                        ('stage_events','industry'),('balance_audit','balances')]:
        left = Q.record_digest(getattr(stager, field))
        right = Q.record_digest(Q.file_rows(root/'pair'/(name+'.jsonl.gz')))
        assert left == right, field
        stream_checks[field] = left
    return stager, p, dict(passed=True, parent_checkpoint=str(path),
        parent_sha256=SC_SHA, parent_provenance_sha256=sha(path.with_suffix('.provenance.json')),
        old_generation_identity_verified_before_import=True, frozen_sources=len(p['source_freeze']),
        saved_book_checks=book_checks, five_complete_streams=stream_checks,
        actual_new_events_executed=0)

def import_sc_horizon(target, verified, payload, verification, horizon_binding):
    """One explicit no-event horizon transition; not a general restore bypass."""
    assert target.rank_mode == 'H1' and target.d1_enabled
    assert target.composition_binding['horizon'] == horizon_binding
    assert not getattr(target, 'sc_horizon_imported', False)
    a = target.accounts['B']; old = verified.accounts['B']
    assert a.available == a.initial_cash == J.D(1000000) and not a.trades and not a.positions
    old_map = payload['runner']['episode_starts']
    assert all(target.episode_starts.get(k) == v for k,v in old_map.items())
    extra = {k:v for k,v in target.episode_starts.items() if k not in old_map}
    assert all(v > J.ordinal('2026-03-31') for v in extra.values()), 'lookup extension rewrote past'
    runner_keys = set(payload['runner']) - {'source_freeze','episode_starts'}
    for k in runner_keys: setattr(target, k, copy.deepcopy(getattr(verified,k)))
    market, facts = a.market, a.facts
    a.__dict__.clear()
    a.__dict__.update(copy.deepcopy({k:v for k,v in old.__dict__.items() if k not in ('market','facts')}))
    a.market, a.facts = market, facts
    # Never call configure_d1 here: its reset would erase actual order history.
    assert all(Q.equal(v,a.__dict__[k]) for k,v in old.__dict__.items() if k not in ('market','facts'))
    assert all(Q.equal(getattr(verified,k),getattr(target,k)) for k in runner_keys)
    assert len(a.positions)==36 and len(a.pending)==119 and len(a.exits)==16 and not a.buys
    consumed = sum(x.delay_remaining == 0 for x in a.exits.values())
    assert consumed == 6 and len(a.exits)-consumed == 10
    assert a.current_nav == J.D('1256586.6197900841060')
    target.assert_composition()
    target.sc_horizon_imported = True
    at = payload['last_completed_event']
    proof = dict(verification, new_engine_identity=IO.runner_identity(target),
        explicit_new_horizon_binding=copy.deepcopy(horizon_binding),
        all_account_fields_exact=len(old.__dict__)-2, all_old_runner_fields_exact=len(runner_keys),
        old_episode_entries=len(old_map), new_future_episode_entries=len(extra),
        pending_intents=len(a.pending), pending_key_digest=Q.record_digest(a.pending),
        exits=len(a.exits), delay_consumed=consumed, delay_not_consumed=10,
        active_buys=0, preserved_cancelled_orders=sum(o.status=='cancelled' for o in a.budget.orders.values()),
        NAV=str(a.current_nav), cursor=str(at), old_checkpoint_not_modified=True,
        first_April_session_executed=False)
    return at, proof
