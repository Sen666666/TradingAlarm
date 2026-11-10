"""Review-only M7 + structural maturity entry adapter. NO historical launcher.

The frozen base is imported, never edited. Data is an alias (never instantiated here).
All new state is kept on Engine and atomically included by atomic_step.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import inspect
import json
import sys

sys.dont_write_bytecode = True
O = Path(__file__).resolve().parent
ROOT = O.parent
BASE = ROOT / 'mainline_m7_cash_batch_design_v6'
DESIGN = ROOT / 'mainline_structural_maturity_design_v1' / 'DESIGN.md'
DESIGN_SHA = '79ebeb73457914656eb70e4ecb59a58008e57d7cb92dd1296dd86d3577efbe12'
BASE_SHA = 'ad0f77fb92d47af4046bf5ab7ef3b4f9b51451d4fe6a6b86a62163f35076a056'
MODEL = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')
MODEL_SHA = '85f21ad1622863645618f570b5f2e832558ebaca218ff2c71d0b4a0b545dd0bf'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert sha(DESIGN) == DESIGN_SHA and sha(BASE / 'engine.py') == BASE_SHA
assert sha(MODEL) == MODEL_SHA, 'ACTUAL_CP_MODEL_VERSION_DRIFT'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


base = module('structural_maturity_frozen_cash_v6', BASE / 'engine.py')
sh = module('structural_maturity_entry_shadow', O / 'shadow.py')
m4 = base.v.m4
m3 = base.v.m3
m2 = m3.m2
rules = m4.rules
D, ZERO, SLIP = base.D, m4.ZERO, m4.SLIP
pd, dec, day, finite, valid, lineage = base.pd, base.dec, base.day, m4.finite, m4.valid, m4.lineage
truth, false, Blocked, Data = m4.truth, m4.false, base.Blocked, base.Data


def origin(z):
    raw = tuple(z.get(k) for k in ('source_kind', 'source_path', 'segment_id'))
    return tuple(lineage(z)) if sh.known_origin(raw) else raw


def known_source(z):
    return sh.known_origin(origin(z))


def once(source, old, new):
    assert source.count(old) == 1, ('HOOK_NOT_UNIQUE', old)
    return source.replace(old, new)


class Engine(base.Engine):
    def __init__(self, data, *, enabled=True):
        super().__init__(data)
        self.entry_enabled = enabled
        self.entry_shadows = {}
        self.entry_archive = []
        self.entry_log = []
        self.entry_decisions = []
        self._entry_preflight_excluded = set()

    def live_tickets(self):
        rows = super().live_tickets()
        return {s: t for s, t in rows.items() if s not in getattr(self, '_entry_preflight_excluded', set())}

    def provenance(self, s):
        manifest = getattr(self.d, 'manifest', {}).get(s, {})
        path = manifest.get('refs', {}).get('CP1')
        hashes = getattr(self.d, 'hashes', {})
        return dict(cp_path=path, cp_file_sha256=hashes.get(path), model_path=str(MODEL), model_sha256=MODEL_SHA)

    def ensure_shadow(self, r):
        s = r['sid']
        old = self.entry_shadows.get(s)
        if old is not None:
            assert old['identity']['ticket_id'] == sh.ticket_id(r), 'DUPLICATE_LIVE_SEED_IDENTITY'
            return old
        assert s not in self.active, 'HELD_CANNOT_CREATE_ENTRY_SHADOW'
        result = sh.new_shadow(r, MODEL_SHA, self.provenance(s))
        self.entry_shadows[s] = result
        self.entry_log.append(sh.event(result, r['signal_day'], 'CLOSE', 'BORN_WITH_ORIGINAL_A_B'))
        return result

    def finish_shadow(self, s, d, status, reason):
        shadow = self.entry_shadows.pop(s, None)
        if shadow is not None:
            sh.finish(shadow, day(d), status, reason, self.entry_log)
            self.entry_archive.append(shadow)

    def sync_terminal(self, d):
        for s in list(self.entry_shadows):
            t = self.tickets.get(s)
            if (t and t['status'] in sh.TERMINAL
                    and t['ticket_id'] == self.entry_shadows[s]['identity']['ticket_id']):
                self.finish_shadow(s, d, t['status'], t.get('reason'))

    def create_structure_wait(self, r, d, gate):
        shadow = self.ensure_shadow(r)
        s = r['sid']
        t = self.live_tickets().get(s)
        if t is None:
            t = sh.structure_ticket(shadow['identity'] | dict(plan_day=r['plan_day'],
                                    factor=shadow['identity']['original_factor'],
                                    ifloor=shadow['identity']['original_ifloor']))
            # Retain original birth fields, but verified factor/I can have advanced.
            t['current_factor'] = shadow['current_factor']
            t['ifloor'] = r['ifloor']
            t['last_verified_day'] = day(d)
            t['event_id'] = r.get('event_id')
            self.tickets[s] = t
            self.ticket_event(t, d, 'STRUCTURE_WAIT_CREATED', fake_capital_rejection=False)
        assert t['ticket_id'] == shadow['identity']['ticket_id']
        if t.get('event_id'):
            assert t['event_id'] == r.get('event_id')
        else:
            t['event_id'] = r.get('event_id')
        t['status'] = 'STRUCTURE_WAIT' if gate == sh.F else 'STRUCTURE_PAUSED_UNKNOWN'
        t['reason'] = t['status']
        t['plan'] = None
        r['ticket_id'] = t['ticket_id']
        return t

    def economic_preflight(self, d, pending):
        if not self.entry_enabled:
            return super().economic_preflight(d, pending)
        removed = set()
        # A stale same-identity plan is not a new A/B birth, including on a halt day.
        for r in pending:
            t = self.tickets.get(r['sid'])
            if (r['kind'] == 'SEED' and t and t['status'] in sh.TERMINAL
                    and t['ticket_id'] == sh.ticket_id(r)):
                removed.add(r['sid'])
        pending[:] = [r for r in pending if r['sid'] not in removed]
        # The frozen one-day ST adapter's new-request assertion predates STRUCTURE_WAIT.
        # An already-live ticket uses its original capture/Q0 path, never an OPEN attempt.
        if day(d) == base.v.HALT:
            live = self.live_tickets()
            for r in pending:
                if r['sid'] == base.v.SID and r['sid'] in live:
                    assert live[r['sid']]['ticket_id'] == sh.ticket_id(r), 'HALT_LIVE_TICKET_IDENTITY_MISMATCH'
                    self.capture_request(d, r, 'OFFICIAL_ONE_DAY_HALT')
                    removed.add(r['sid'])
        # Explicit known changes cancel; unknown strings are not new source identities.
        for s, shadow in list(self.entry_shadows.items()):
            z = self.d.z(s, d)
            if known_source(z) and tuple(lineage(z)) != shadow['identity']['origin']:
                t = self.live_tickets().get(s)
                if t:
                    rules.cancel(t, 'RETRY_SOURCE_CHANGED')
                    self.ticket_event(t, d, 'CANCEL_SOURCE_CHANGED')
                    self.quote_gaps.pop(s, None)
                self.finish_shadow(s, d, 'CANCELLED', 'RETRY_SOURCE_CHANGED')
                removed.add(s)
        pending[:] = [r for r in pending if r['sid'] not in removed]
        # The frozen Q0 code recognizes None/NaN, but not text sentinel "unknown".
        # Route only such waiting tickets through its existing pause branch.
        excluded = set()
        for s, t in list(self.live_tickets().items()):
            z = self.d.z(s, d)
            if not known_source(z) and m2.known_origin(z):
                self.pause_ticket(s, t, d, z)
                excluded.add(s)
        pending[:] = [r for r in pending if r['sid'] not in excluded]
        self._entry_preflight_excluded = excluded
        try:
            result = super().economic_preflight(d, pending)
        finally:
            self._entry_preflight_excluded = set()
        self.sync_terminal(d)
        pending_sids = {r['sid'] for r in pending}
        for s, shadow in self.entry_shadows.items():
            z = self.d.z(s, d)
            t = self.live_tickets().get(s)
            verified = ((t and t.get('last_verified_day') == day(d)
                         and t['status'] != 'PAUSED_NO_QUOTE') or s in pending_sids)
            if verified:
                # Original preflight has validated the same-source 1e-11 bridge.
                shadow['current_factor'] = t['current_factor'] if t else dec(z['adjustment_factor'])
            sh.observe_open(shadow, day(d), raw=z.get('raw_open'),
                            factor=shadow['current_factor'] if verified else None,
                            origin=origin(z), source_valid=bool(verified and valid(z) and known_source(z)),
                            log=self.entry_log)
        return result

    def reverify_gap(self, s, t, d):
        if not self.entry_enabled:
            return super().reverify_gap(s, t, d)
        return entry_reverify_gap(self, s, t, d)

    def observe_shadow_close(self, s, d):
        shadow = self.entry_shadows.get(s)
        if shadow is None:
            return
        z, f = self.d.z(s, d), self.d.f(s, d)
        sector = int(self.d.sectors[self.d.sid_sector[s]].at[d, 'state'])
        stock = int(self.d.stock.at[d, s])
        reason = ('RETRY_I_FALSE' if false(f.get('i_target')) else
                  'RETRY_SECTOR_FALSE' if sector == 0 else
                  'RETRY_STOCK_M3_FALSE' if stock == 0 else
                  'RETRY_SOURCE_CHANGED' if known_source(z) and tuple(lineage(z)) != shadow['identity']['origin'] else None)
        t = self.live_tickets().get(s)
        # The original refresh already performs the I ratchet/known-price protection check.
        if reason:
            if t:
                rules.cancel(t, reason)
            self.finish_shadow(s, d, 'CANCELLED', reason)
            return
        if (t and t['ticket_id'] == shadow['identity']['ticket_id']
                and t.get('last_verified_day') == day(d) and t['status'] != 'PAUSED_NO_QUOTE'):
            shadow['current_factor'] = t['current_factor']
        c = self.d.c(s, d)
        sh.observe_close(shadow, day(d), raw_open=z.get('raw_open'), raw_close=z.get('raw_close'),
                         factor=shadow['current_factor'] if positive_factor(z, shadow) else None,
                         origin=origin(z), receipt=c.get('receipt'), candidate=c.get('candidate'),
                         source_valid=valid(z) and known_source(z), log=self.entry_log)

    def refresh_tickets(self, d):
        result = super().refresh_tickets(d)
        if not self.entry_enabled:
            return result
        self.sync_terminal(d)
        for s in list(self.entry_shadows):
            self.observe_shadow_close(s, d)
        return result

    def prepare_requests(self, d, reqs):
        if not self.entry_enabled:
            return super().prepare_requests(d, reqs)
        # Birth observation happens regardless of EVENT/MATURE/RESIDUAL allocation.
        for r in reqs:
            if r['kind'] == 'SEED':
                self.ensure_shadow(r)
                self.observe_shadow_close(r['sid'], d)
        rows = super().prepare_requests(d, reqs)
        nav = self.nav(d, 'raw_close')
        sv = {s: self.qvalue(a, d, 'raw_close') for s, a in self.active.items()}
        for r in rows:
            if r['kind'] != 'SEED':
                continue
            shadow = self.entry_shadows.get(r['sid'])
            if shadow is None:
                raise AssertionError('ORIGINAL_REQUEST_SURVIVED_KNOWN_FALSE_OR_SOURCE_CANCEL')
            shadow['identity']['event_id'] = shadow['identity'].get('event_id') or r.get('event_id')
            fast = int(self.d.m(r['sid'], d).F)
            cpstate = sh.state(shadow)
            ev = self.events.get(r.get('event_id'))
            g = sh.gate(r['allocation_phase'], r['kind'], r['M'], r['E'],
                        bool(ev and ev['status'] == 'ACTIVE'), not r.get('_event_identity_mismatch'), fast, cpstate)
            r.update(_entry_frozen_F=fast, _entry_close_cp_state=cpstate, _entry_gate_close=g,
                     _entry_plan_cp_id=shadow['slot']['id'] if shadow['slot'] else None,
                     _entry_gate_plan_day=day(d))
            shadow['last_phase'] = r['allocation_phase']
            old = super().noncash(r, d, 'raw_close', nav, sv)
            # Explicit waiting is introduced only for an otherwise executable original request.
            if r['allocation_phase'] == 'MATURE' and g != sh.T and old['reason'] == 'PASS' and r.get('score_known'):
                self.create_structure_wait(r, d, g)
            self.entry_decisions.append(dict(day=day(d), phase='CLOSE', sid=r['sid'],
                 ticket_id=shadow['identity']['ticket_id'], original_signal_day=r['signal_day'],
                 allocation_phase=r['allocation_phase'], F=fast, CP_state=cpstate, G=g,
                 entry_evidence_id=r['_entry_plan_cp_id'], original_decision=old['reason'],
                 result='BYPASS' if r['allocation_phase'] != 'MATURE' else
                        'READY' if g == sh.T else 'STRUCTURE_WAIT' if g == sh.F else 'STRUCTURE_PAUSED_UNKNOWN'))
        formed = {r['sid'] for r in rows if r['kind'] == 'SEED'}
        for s, shadow in self.entry_shadows.items():
            if s in formed:
                continue
            t = self.live_tickets().get(s)
            m = self.d.m(s, d)
            eid = (t or shadow['identity']).get('event_id')
            ev = self.events.get(eid)
            active = ev and ev['status'] == 'ACTIVE' and eid == self.current_event.get(self.d.sid_sector[s])
            priority = active and not ev['priority_attempted'] and not ev['priority_expired']
            phase = ('EVENT' if priority and m.M != -1 and (m.M == 0 or sh.positive(m.E)) else
                     'MATURE' if active and m.M == 1 and sh.positive(m.E) else
                     'RESIDUAL' if active and m.M == 0 else 'PAUSED')
            shadow['last_phase'] = phase
            self.entry_decisions.append(dict(day=day(d), phase='CLOSE', sid=s,
                 ticket_id=shadow['identity']['ticket_id'], original_signal_day=shadow['identity']['signal_day'],
                 allocation_phase=phase, F=int(m.F), CP_state=sh.state(shadow), G=None,
                 result='ORIGINAL_REQUEST_PAUSED', original_reason=t.get('reason') if t else 'BOUNDARY_PAUSED',
                 original_request_formed=False, q=0, cost='0'))
        # All requests retain original phase and rank; noncash zeros illegal q before M7 D.
        return rows

    def entry_gate_open(self, r, d):
        if r['kind'] != 'SEED' or r.get('allocation_phase') != 'MATURE':
            return sh.T
        assert r['_entry_gate_plan_day'] < day(d), 'CLOSE_EVIDENCE_CANNOT_FILL_SAME_OPEN'
        if r['_entry_frozen_F'] == sh.T:
            return sh.T
        shadow = self.entry_shadows.get(r['sid'])
        cpstate = sh.state(shadow) if shadow else sh.F
        slot = shadow['slot'] if shadow else None
        if cpstate == sh.T and (slot['id'] != r['_entry_plan_cp_id'] or slot['receipt_day'] >= day(d)):
            cpstate = sh.F
        return sh.tri_or(r['_entry_frozen_F'], cpstate)

    def noncash(self, r, d, field, nav, sv):
        x = super().noncash(r, d, field, nav, sv)
        if not self.entry_enabled or r['kind'] != 'SEED' or r.get('allocation_phase') != 'MATURE':
            return x
        # I breach, original dated lot/capacity and other hard failures take precedence.
        if x['reason'] != 'PASS':
            return x
        if field == 'raw_open':
            shadow = self.entry_shadows.get(r['sid'])
            if shadow:
                z = self.d.z(r['sid'], d)
                sh.observe_open(shadow, day(d), raw=z.get('raw_open'), factor=shadow['current_factor'],
                                origin=origin(z), source_valid=valid(z) and known_source(z), log=self.entry_log)
            g = self.entry_gate_open(r, d)
        else:
            g = r['_entry_gate_close']
        if g != sh.T:
            return dict(x, q=0, structural=False,
                        reason='ENTRY_STRUCTURE_WAIT' if g == sh.F else 'ENTRY_STRUCTURE_PAUSED_UNKNOWN')
        return x

    def entry_open_outcome(self, t, r, d, reason, x, rawcost, caps):
        if reason in ('ENTRY_STRUCTURE_WAIT', 'ENTRY_STRUCTURE_PAUSED_UNKNOWN'):
            g = sh.F if reason == 'ENTRY_STRUCTURE_WAIT' else sh.U
            self.create_structure_wait(r, d, g)
            self.entry_decisions.append(dict(day=day(d), phase='OPEN', sid=r['sid'],
                    allocation_phase=r['allocation_phase'], F=r['_entry_frozen_F'], G=g,
                    entry_evidence_id=r['_entry_plan_cp_id'], result=reason, q=0, cost='0'))
            return
        rules.retry_open_outcome(t, filled=reason == 'PASS', structural_pass=x['structural'],
                                 all_in_cost=rawcost, caps=caps)

    def alloc_open(self, d, pending):
        if not self.entry_enabled:
            return super().alloc_open(d, pending)
        # A previously READY fresh signal may break its CP at OPEN before any ticket existed.
        for r in pending:
            if r['kind'] == 'SEED' and r.get('allocation_phase') == 'MATURE':
                shadow = self.entry_shadows.get(r['sid'])
                if shadow:
                    z = self.d.z(r['sid'], d)
                    sh.observe_open(shadow, day(d), raw=z.get('raw_open'), factor=shadow['current_factor'],
                                    origin=origin(z), source_valid=valid(z) and known_source(z), log=self.entry_log)
                g = self.entry_gate_open(r, d)
                original = super().noncash(r, d, 'raw_open', self.nav(d, 'raw_open'),
                                           {s: self.qvalue(a, d, 'raw_open') for s, a in self.active.items()})
                if g != sh.T and original['reason'] == 'PASS' and r['sid'] not in self.live_tickets():
                    self.create_structure_wait(r, d, g)
        result = entry_alloc_open(self, d, pending)
        self.sync_terminal(d)
        for s in list(self.entry_shadows):
            if s in self.active:
                continue  # order() has already archived successful seeds.
            boundary = self.paused_new_requests.get(s)
            still_boundary = boundary and boundary['status'] not in ('CANCELLED', 'CONSUMED', 'TRANSFERRED_TO_RETAINED')
            if s not in self.live_tickets() and not still_boundary:
                self.finish_shadow(s, d, 'CANCELLED', 'ORIGINAL_NON_CAPITAL_OPEN_REJECTION')
        return result

    def order(self, a, d, side, q, p, reason, **kw):
        result = super().order(a, d, side, q, p, reason, **kw)
        if self.entry_enabled and side == 'BUY_SEED':
            r = self._execution_requests[a['sid']]
            self.orders[-1]['entry_evidence_id'] = r.get('_entry_plan_cp_id')
            assert a['cp'] is None and a['confirmed_history'] is False and a['add_count'] == 0
            self.finish_shadow(a['sid'], d, 'CONSUMED', 'SEED_ACTUALLY_FILLED_NO_ACTIVE_CP_INHERITANCE')
        return result

    def atomic_step(self, d, pending, prev):
        """One externally supplied day, with complete old/new state and log rollback.

        This is not a history runner or approval. Tests pass artificial in-memory days.
        """
        snapshot = copy.deepcopy({k: v for k, v in vars(self).items() if k != 'd'})
        p0 = copy.deepcopy(pending)
        try:
            self.economic_preflight(d, pending)
            self.accrue(d)
            self.exit_open(d)
            self.alloc_open(d, pending)
            return self.close(d, prev)
        except BaseException:
            for k in list(vars(self)):
                if k != 'd':
                    delattr(self, k)
            vars(self).update(snapshot)
            pending[:] = p0
            raise

    def run(self, *args, **kwargs):
        raise RuntimeError('REVIEW_ONLY_NO_HISTORICAL_LAUNCH_APPROVAL')

    def export(self, path):
        # Explicit exports may target only this new candidate directory.
        path = Path(path).resolve()
        assert path.is_relative_to(O), 'CANDIDATE_OUTPUT_ONLY'
        super().export(path)
        for name, value in [('ENTRY_SHADOWS', self.entry_shadows), ('ENTRY_ARCHIVE', self.entry_archive),
                            ('ENTRY_CP_EVENTS', self.entry_log), ('ENTRY_GATE_DECISIONS', self.entry_decisions)]:
            base.save(path / (name + '.json'), value)
        base.save(path / 'OUTPUT_HASHES.json', {p.name: sha(p) for p in path.iterdir()
                                               if p.is_file() and p.name != 'OUTPUT_HASHES.json'})


def positive_factor(z, shadow):
    return sh.positive(z.get('adjustment_factor')) and abs(dec(z['adjustment_factor']) / shadow['current_factor'] - 1) <= sh.TOL


# This is the *current v6* allocator including the original ST no-fill commit hooks.
# Only the retained-ticket outcome call changes; every money/quantity/priority line is unchanged.
ALLOC_OLD = "rules.retry_open_outcome(t,filled=reason=='PASS',structural_pass=x['structural'],all_in_cost=rawcost,caps=caps)"
ALLOC_NEW = 'self.entry_open_outcome(t,r,d,reason,x,rawcost,caps)'
ALLOC_SOURCE = once(base.v.alloc_source, ALLOC_OLD, ALLOC_NEW)
ns = dict(base.Engine.alloc_open.__globals__)
exec(compile(ALLOC_SOURCE, 'ENTRY_STRUCTURE_OUTCOME_ONLY', 'exec'), ns)
entry_alloc_open = ns['alloc_open']

# Same frozen gap loop and 1e-11 economic bridge checks; only knowledge predicates
# distinguish an unknown text sentinel from a genuinely different source identity.
GAP_SOURCE = inspect.getsource(m2.Engine.reverify_gap).replace(' def reverify_gap', 'def reverify_gap', 1)
gap_ns = dict(m2.Engine.reverify_gap.__globals__)
gap_ns['known_origin'] = known_source
gap_ns['open_known'] = lambda z: known_source(z) and all(finite(z.get(k)) and z[k] > 0 for k in ['raw_open', 'adjustment_factor'])
exec(compile(GAP_SOURCE, 'ENTRY_Q0_KNOWLEDGE_ONLY', 'exec'), gap_ns)
entry_reverify_gap = gap_ns['reverify_gap']



def self_check():
    assert sha(DESIGN) == DESIGN_SHA and sha(BASE / 'engine.py') == BASE_SHA and sha(MODEL) == MODEL_SHA
    assert ALLOC_SOURCE.replace(ALLOC_NEW, ALLOC_OLD) == base.v.alloc_source
    assert GAP_SOURCE == inspect.getsource(m2.Engine.reverify_gap).replace(' def reverify_gap', 'def reverify_gap', 1)
    unchanged = ['accrue', 'register_pay', 'exit_open', 'execute_transfers', 'info_open', 'info_close',
                 'cpvalid', 'invalidate_cp', 'current_trial_seed', 'economic_q', 'surcharge',
                 'stock_key', 'request_key_groups', 'plan_transfers', 'plan_requests',
                 'independent_mature_demand', 'finalize_reference', 'classify_reference',
                 'reference_cap', 'event_cap', 'reserve_phase_cash', 'sell_quantity', 'net',
                 'no_fill', 'buy_nofill', 'capture_request', 'revalidate_paused_close', 'close']
    assert all(getattr(Engine, k) is getattr(base.Engine, k) for k in unchanged)
    assert Data is base.Data
    return dict(result='PASS', history_run=False, model_sha256=MODEL_SHA, design_sha256=DESIGN_SHA,
                baseline_sha256=BASE_SHA, unchanged_methods=unchanged,
                allocator_patch='single_structure_outcome_dispatch_only', data_loader='exact_baseline_alias',
                certified_baseline_through='2025-01-20', external_sources_accessed=False,
                historical_launcher=False, production_or_PIT_certification=False)


if __name__ == '__main__':
    print(json.dumps(self_check(), ensure_ascii=False))
