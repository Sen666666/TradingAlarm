"""Explicit trend-exit plugins over the original No60 native runner.

Imports no native engine, creates no Account, and computes no indicator.
Root supplies the already loaded No60 module and a frozen causal provider.
Grace construction is disabled until its separate coverage/freeze decision.
"""
from __future__ import annotations
from pathlib import Path
from decimal import Decimal as D
import ast
import copy
import hashlib
import inspect
import math
import pickle
import textwrap

HERE = Path(__file__).resolve().parent
NATIVE_PLANNING = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py')
INDICATORS = ('EMA20', 'EMA60', 'BOLL20_MID', 'BOLL20_LOWER')
ARMS = {'BASELINE': ('baseline', None, None)}
ARMS.update({'EARLY_' + x: ('early', x, None) for x in INDICATORS})
ARMS.update({f'GRACE_{x}_H{h}': ('grace', x, h) for x in ('EMA20', 'EMA60') for h in (3, 5, 10)})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _same(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-11, abs_tol=1e-11)


def provider_value(provider, sid, at, indicator, native_row):
    """Strict current-date, same-coordinate receipt; UNKNOWN is not validity."""
    q = dict(provider.at(sid, at, indicator))
    required = {'status', 'day', 'causal_close', 'line', 'source_segment', 'source_max_day', 'unknown_reason'}
    assert required <= set(q), ('provider schema', required - set(q))
    day = str(at.date())
    assert q['day'] == day, ('stale provider day', sid, day, q['day'])
    assert q['status'] in ('READY', 'UNKNOWN')
    if q['status'] == 'UNKNOWN':
        # Unknown indicator is not an unknown original facts.close. Hard
        # reference guards still use that native, decision-known coordinate.
        if q['causal_close'] is not None:
            assert _same(q['causal_close'], native_row.close), 'unknown-provider/native close mismatch'
        q['causal_close'] = float(native_row.close)
        return q
    assert q['source_max_day'] is not None and q['source_max_day'] <= day, 'future provider input'
    assert all(math.isfinite(float(q[k])) and float(q[k]) > 0 for k in ('causal_close', 'line'))
    assert _same(q['causal_close'], native_row.close), 'provider/native causal close mismatch'
    assert _same(q['source_segment'], native_row.segment_id), 'provider/native source segment mismatch'
    return q


class ExitController:
    """Serializable policy state only; no execution, indicators or provider ref."""
    def __init__(self, arm, native_close_days):
        assert arm in ARMS
        self.arm = arm
        self.kind, self.indicator, self.horizon = ARMS[arm]
        self.calendar = tuple(sorted(set(native_close_days)))
        assert len(self.calendar) == len(native_close_days), 'native CLOSE dates must be unique'
        self.index = {d: i for i, d in enumerate(self.calendar)}
        self.state = {}
        self.log = []

    @staticmethod
    def key(account, sid):
        return account + '|' + sid

    def active(self, account, sid):
        return self.key(account, sid) in self.state

    def reconcile(self, account, held_sids, pending_buy_sids, pending_exit_sids, at):
        """Reset only after actual flat and no original outstanding obligation."""
        for key in list(self.state):
            a, sid = key.split('|', 1)
            if a == account and sid not in held_sids and sid not in pending_buy_sids and sid not in pending_exit_sids:
                old = self.state.pop(key)
                self.log.append(dict(at=str(at), account=account, sid=sid, kind='actual_flat_reset', previous=copy.deepcopy(old)))

    def decide(self, account, sid, at, native_I, quote, old_I_reference, core_references, exit_pending=False):
        """Return only a CLOSE request decision. No cancel of a locked exit."""
        day = str(at.date())
        assert day in self.index, 'decision outside native market CLOSE calendar'
        close = float(quote['causal_close']) if quote['causal_close'] is not None else None
        ready = quote['status'] == 'READY'
        broken = bool(ready and close < float(quote['line']))  # equality retains
        key = self.key(account, sid)
        state = self.state.get(key)
        out = dict(arm=self.arm, request_reason=None, hold_only=False, state=None,
                   indicator_ready=ready, indicator_broken=broken, native_I=bool(native_I),
                   provider_unknown_reason=quote.get('unknown_reason'))
        if self.kind == 'baseline':
            out['request_reason'] = None if native_I else 'I_structure_exit'
            return out
        if self.kind == 'early':
            out['request_reason'] = 'I_structure_exit' if not native_I else ('trend_early_' + self.indicator if broken else None)
            return out
        if state is None:
            if native_I:
                return out
            # Unknown indicator/reference never grants a grace permission.
            reference_known = old_I_reference is not None and math.isfinite(float(old_I_reference)) and float(old_I_reference) > 0
            if not ready or broken or not reference_known or close <= float(old_I_reference) or exit_pending:
                out['request_reason'] = 'I_structure_exit'
                return out
            state = dict(mode='HOLD_ONLY', start_day=day, start_native_close_index=self.index[day],
                         expiry_native_close_index=self.index[day] + self.horizon, horizon=self.horizon,
                         frozen_original_I_reference=float(old_I_reference),
                         frozen_core_references={str(k): float(v) for k, v in core_references.items()},
                         locked_exit_reason=None)
            self.state[key] = state
        out['hold_only'] = True
        elapsed = self.index[day] - state['start_native_close_index']
        out['elapsed_native_market_CLOSEs'] = elapsed
        if state['mode'] == 'EXIT_LOCKED':
            reason = state['locked_exit_reason']
        elif close is not None and close <= state['frozen_original_I_reference']:
            reason = 'grace_original_I_reference_breach'
        elif elapsed >= self.horizon:
            reason = 'grace_deadline_' + self.indicator + '_H' + str(self.horizon)
        elif broken:
            reason = 'grace_EMA_break_' + self.indicator
        elif not ready and not native_I:
            reason = 'I_structure_exit'  # explicit original-I fallback
        else:
            reason = None
        if reason:
            state['mode'] = 'EXIT_LOCKED'
            state['locked_exit_reason'] = reason
        out['request_reason'] = reason
        out['state'] = copy.deepcopy(state)
        return out


OLD_EXIT_BLOCK = """    if not a.risk_state['on'] or not bool(row.i_target):
     if not bool(row.i_target):
      for x in a.live(sid):
       if x['kind']=='core':a.jmeta[x['id']]['pending_I_exit_reference']=True
     a.sell(sid,clock,quote,[x['id'] for x in a.live(sid)],'ACT_pause' if not a.risk_state['on'] else 'I_structure_exit');continue
"""


def patched_planning_source(native_source=None):
    """Three exact edits; immutable original I input and CP loop remain intact."""
    source = Path(native_source or NATIVE_PLANNING).read_text()
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Runner')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'planning')
    raw = '\n'.join(source.splitlines()[node.lineno - 1:node.end_lineno]) + '\n'
    assert raw.count(OLD_EXIT_BLOCK) == 1, 'native exit block drift'
    changed = raw.replace(OLD_EXIT_BLOCK, "    if self._trend_manage_position(a,sid,at,row,clock,quote):continue\n")
    before = "a.pending=[]\n   for sid in tuple(a.positions):"
    after = "a.pending=[];self._trend_reconcile(a,at)\n   for sid in tuple(a.positions):"
    assert changed.count(before) == 1
    changed = changed.replace(before, after)
    before2 = "    if sid in a.exits:why.append('exit_pending')\n"
    after2 = before2 + "    if self._trend_bans_new(a,sid):why.append('trend_grace_HOLD_ONLY')\n"
    assert changed.count(before2) == 1
    changed = changed.replace(before2, after2)
    # Round-trip proves no incidental entry/CP/ranking/ledger edits.
    assert changed.replace(after2, before2).replace(after, before).replace(
        "    if self._trend_manage_position(a,sid,at,row,clock,quote):continue\n", OLD_EXIT_BLOCK) == raw
    return textwrap.dedent(raw), textwrap.dedent(changed)


def _last_valid_I_reference(runner, sid, at, native_row):
    """Read original same-segment historical I values; no model recalculation."""
    frame = runner.facts.f[sid]
    prefix = frame.loc[:str(at.date())]
    for _, row in prefix.iloc[::-1].iterrows():
        if not _same(row.segment_id, native_row.segment_id):
            break
        if bool(row.i_target) and math.isfinite(float(row.i_floor)) and float(row.i_floor) > 0:
            return float(row.i_floor)
    return None


class TrendHooks:
    """Native original methods perform all requests/cancels; no virtual fills."""
    def _trend_reconcile(self, a, at):
        c = self.trend_exit_controller
        if c.kind != 'grace':
            return
        c.reconcile(a.label, set(a.positions), set(a.buys), set(a.exits), at)
        for sid in list(a.buys):
            if c.active(a.label, sid):
                a.cancel_buy(sid)

    def _trend_bans_new(self, a, sid):
        return self.trend_exit_controller.active(a.label, sid)

    def _trend_manage_position(self, a, sid, at, row, clock, quote):
        c = self.trend_exit_controller
        native_I = bool(row.i_target)
        if not native_I:
            for x in a.live(sid):
                if x['kind'] == 'core':
                    a.jmeta[x['id']]['pending_I_exit_reference'] = True
        if not a.risk_state['on']:
            a.sell(sid, clock, quote, [x['id'] for x in a.live(sid)], 'ACT_pause')
            return True
        q = provider_value(type(self).trend_exit_provider, sid, at, c.indicator, row)
        old_ref = None
        if c.kind == 'grace' and not native_I and not c.active(a.label, sid):
            old_ref = _last_valid_I_reference(self, sid, at, row)
        core_refs = {x['id']: a.jmeta[x['id']]['last_core_line'] for x in a.live(sid) if x['kind'] == 'core'}
        plan = c.decide(a.label, sid, at, native_I, q, old_ref, core_refs, exit_pending=sid in a.exits)
        log = dict(at=str(at), account=a.label, sid=sid, kind='CLOSE_policy_check', input=q,
                   old_original_I_reference_for_new_grace=old_ref, decision=copy.deepcopy(plan), responsibilities=[])
        c.log.append(log)
        if c.kind == 'grace' and (not native_I or plan['hold_only']):
            a.cancel_buy(sid)  # original callback owns all reserve/ack timing
        if plan['hold_only']:
            # Original pending responsibilities stay locked. A new request may
            # extend that order, but never replaces its prior layer reasons.
            state = c.state[c.key(a.label, sid)]
            for x in a.live(sid):
                if x['id'] in a.sell_layers.get(sid, set()):
                    continue
                reason = None
                if x['kind'] == 'add' and D(str(row.close)) <= D(str(x['floor'])):
                    reason = 'CP1_add_protection'
                elif x['kind'] == 'core':
                    reference = state['frozen_core_references'].get(str(x['id']))
                    if reference is None:
                        raise AssertionError('New core in HOLD_ONLY lifecycle')
                    if D(str(row.close)) <= D(str(reference)):
                        reason = 'grace_core_reference_breach'
                if reason:
                    a.sell(sid, clock, quote, [x['id']], reason)
                    log['responsibilities'].append(dict(layer_ids=[x['id']], reason=reason))
            if plan['request_reason']:
                ids = [x['id'] for x in a.live(sid) if x['id'] not in a.sell_layers.get(sid, set())]
                if ids:
                    a.sell(sid, clock, quote, ids, plan['request_reason'])
                    log['responsibilities'].append(dict(layer_ids=ids, reason=plan['request_reason']))
                return True
            if all(x['id'] in a.sell_layers.get(sid, set()) for x in a.live(sid)):
                state['mode'] = 'EXIT_LOCKED'
                state['locked_exit_reason'] = 'grace_all_layers_already_hard_exit_pending'
                return True
            # Critical: continue into original CP loop even when native I=False.
            return False
        if plan['request_reason']:
            ids = [x['id'] for x in a.live(sid)]
            a.sell(sid, clock, quote, ids, plan['request_reason'])
            log['responsibilities'].append(dict(layer_ids=ids, reason=plan['request_reason']))
            return True
        return False


def build_runner_class(no60_module, provider, arm, *, grace_coverage_frozen=False):
    """Build the class only. Caller must separately freeze/authorize any run.

    Call once per fresh process; re-create this same class/provider before
    restoring its own candidate checkpoint. Never import an old policy account.
    """
    assert arm in ARMS
    if ARMS[arm][0] == 'grace':
        assert grace_coverage_frozen, 'Grace disabled pending original-Ioff coverage/freeze decision'
    A = no60_module
    N, J, L, IO = A.N, A.J, A.L, A.IO
    assert A.Runner.route is A.P.ROUTES[True]
    assert inspect.getsourcefile(J.Runner.planning) == str(NATIVE_PLANNING)
    original, changed = patched_planning_source()
    assert textwrap.dedent(inspect.getsource(J.Runner.planning)) == original
    env = dict(J.__dict__)
    exec(compile(changed, str(HERE/'derived_planning.py'), 'exec'), env)
    changed_plan = env['planning']
    provider_sha = 'BASELINE_NO_PROVIDER' if arm == 'BASELINE' else provider.manifest_sha256
    if arm != 'BASELINE':
        assert isinstance(provider_sha, str) and len(provider_sha) == 64
    assert 'Runner' not in globals(), 'One candidate class per fresh process; preserve checkpoint identity'

    class Runner(TrendHooks, A.Runner):
        trend_exit_provider = provider
        def __init__(self, *args, **kwargs):
            self._trend_bootstrap = True
            super().__init__(*args, **kwargs)
            self.trend_exit_arm = arm
            self.trend_exit_provider_sha256 = provider_sha
            days = sorted({str(t.date()) for t in self.market.cutoffs})
            self.trend_exit_controller = ExitController(arm, days)
            self.integration_policy = A.POLICY + ':TREND_EXIT_CONTROLS_V1:' + arm + ':' + self.rank_mode
            self._trend_bootstrap = False
            self.assert_native_wiring()

        def planning(self, at):
            if arm == 'BASELINE':
                return N.Runner.planning(self, at)
            changed_plan(self, at)
            if self.rank_mode != 'H1':
                for a in self.accounts.values():
                    self.rank_log.extend(dict(account=a.label, **r) for r in N.apply_priority(a, N.SCORES.at, str(at.date())))

        def assert_native_wiring(self):
            cap_bootstrap = getattr(self, '_cap_bootstrap', False)
            trend_bootstrap = getattr(self, '_trend_bootstrap', False)
            prefix = N.POLICY if cap_bootstrap else A.POLICY if trend_bootstrap else A.POLICY + ':TREND_EXIT_CONTROLS_V1:' + arm
            assert self.integration_policy == prefix + ':' + self.rank_mode
            assert self.rank_scores_manifest_sha256 == N.SCORES.manifest_sha256
            assert self.opening.__func__ is J.Runner.opening
            assert self.route.__func__ is A.P.ROUTES[True]
            assert self.planning.__func__ is Runner.planning
            for a in self.accounts.values():
                assert type(a) is J.Account
                assert type(a.budget) is (N.BASE.NoAccountBudget if cap_bootstrap else A.NoConfirmed60Budget)
                for name in ('reserve_quantity', 'fill_buy', 'fill_exit', 'cancel_buy', 'split', 'sync', 'assert_budget_view', 'expire_day_buys'):
                    assert getattr(a, name).__func__ is getattr(J.Account, name)
            if not trend_bootstrap:
                assert self.trend_exit_arm == self.trend_exit_controller.arm == arm
                assert self.trend_exit_provider_sha256 == provider_sha

        def restore(self, path):
            payload = pickle.loads(Path(path).read_bytes())
            assert payload['runner']['integration_policy'] == self.integration_policy
            assert payload['runner']['trend_exit_arm'] == arm
            assert payload['runner']['trend_exit_provider_sha256'] == provider_sha
            return super().restore(path)  # retains native source/provenance gates

        def dump_joint(self, path):
            super().dump_joint(path)
            IO.write_gzip_jsonl(Path(path)/'trend-exit-policy.jsonl.gz', self.trend_exit_controller.log)
            IO.write_json(Path(path)/'trend-exit-state.json', self.trend_exit_controller.state)

    Runner.__module__ = __name__
    Runner.__qualname__ = 'Runner'
    globals()['Runner'] = Runner
    return Runner


def source_patch_diff():
    import difflib
    old, new = patched_planning_source()
    return ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile='original_joint_v3.planning', tofile='candidate_exit_hooks_only.planning'))


def source_freeze(no60_module):
    result = dict(no60_module.source_freeze())
    for p in (Path(__file__), HERE/'CONTRACT.txt', HERE/'check_adapter.py'):
        result[str(p.resolve())] = sha(p)
    return result


if __name__ == '__main__':
    raise SystemExit('Adapter only; no financial execution entrypoint. Root must freeze inputs and candidate scope first.')
