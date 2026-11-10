"""Four early-exit plugins over the original No60 native account runner.

No native import/account initialization, indicator calculation, or execution
entrypoint. Root supplies the native module and independently frozen provider.
"""
from pathlib import Path
import ast
import hashlib
import inspect
import math
import pickle
import textwrap

HERE = Path(__file__).resolve().parent
NATIVE_PLANNING = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py')
INDICATORS = ('EMA20', 'EMA60', 'BOLL20_MID', 'BOLL20_LOWER')
ARMS = {'BASELINE': None, **{'EARLY_' + x: x for x in INDICATORS}}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provider_value(provider, sid, at, indicator, native_row):
    q = dict(provider.at(sid, at, indicator))
    required = {'status', 'day', 'causal_close', 'line', 'source_segment', 'source_max_day', 'unknown_reason'}
    assert required <= set(q), ('provider schema', required - set(q))
    day = str(at.date())
    assert q['day'] == day, ('stale provider day', sid, day, q['day'])
    assert q['status'] in ('READY', 'UNKNOWN')
    if q['status'] == 'UNKNOWN':
        return q  # no extra exit; original I/ACT/CP branches still operate
    assert q['source_max_day'] is not None and q['source_max_day'] <= day, 'future provider input'
    assert math.isfinite(float(q['causal_close'])) and float(q['causal_close']) > 0
    assert math.isfinite(float(q['line']))  # a valid Boll lower band can be <=0
    assert math.isclose(float(q['causal_close']), float(native_row.close), rel_tol=1e-11, abs_tol=1e-11), 'provider/native causal close mismatch'
    assert float(q['source_segment']) == float(native_row.segment_id), 'provider/native source segment mismatch'
    return q


def patched_planning_source(native_source=None):
    """One exact insertion after the unchanged per-stock native CP loop."""
    source = Path(native_source or NATIVE_PLANNING).read_text()
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Runner')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'planning')
    raw = '\n'.join(source.splitlines()[node.lineno - 1:node.end_lineno]) + '\n'
    anchor = "      if cp is not None and bool(cp.receipt):x['floor']=max(x['floor'],D(str(cp.candidate)))\n   a.sync(at);self.industry(a,at)"
    assert raw.count(anchor) == 1, 'native per-stock CP/planning boundary drift'
    hook = "    self._trend_early_exit(a,sid,at,row,clock,quote)\n"
    changed = raw.replace(anchor, anchor.replace("   a.sync(at)", hook + "   a.sync(at)"))
    assert changed.replace(hook, '') == raw, 'incidental native planning modification'
    return textwrap.dedent(raw), textwrap.dedent(changed)


class EarlyHooks:
    def _trend_early_exit(self, a, sid, at, row, clock, quote):
        # This is reached only after original ACT and I guards passed, then
        # every mobile's OLD floor was checked and original ratchets applied.
        assert a.risk_state['on'] and bool(row.i_target)
        q = provider_value(type(self).trend_exit_provider, sid, at, self.trend_exit_indicator, row)
        broken = q['status'] == 'READY' and float(q['causal_close']) < float(q['line'])
        pending = set(a.sell_layers.get(sid, set()))
        ids = [x['id'] for x in a.live(sid) if x['id'] not in pending] if broken else []
        log = dict(at=str(at), account=a.label, sid=sid, arm=self.trend_exit_arm,
                   native_ACT_on=True, native_I_target=True, indicator=q,
                   indicator_break=bool(broken), prior_pending_layer_ids=sorted(pending),
                   added_indicator_layer_ids=list(ids), request_reason=None)
        if ids:
            reason = 'trend_early_' + self.trend_exit_indicator
            a.sell(sid, clock, quote, ids, reason)
            log['request_reason'] = reason
        self.trend_exit_log.append(log)
        return bool(ids)


def build_runner_class(no60_module, provider, arm):
    """Build only; root separately freezes and launches any native run.

    One arm/class per fresh process. Recreate it with the same provider before
    restoring its OWN checkpoint; old-policy accounts are never imported.
    """
    assert arm in ARMS, 'Only baseline and four EARLY arms; grace has stopped'
    A = no60_module
    N, J, IO = A.N, A.J, A.IO
    assert A.Runner.route is A.P.ROUTES[True]
    assert inspect.getsourcefile(J.Runner.planning) == str(NATIVE_PLANNING)
    original, changed = patched_planning_source()
    assert textwrap.dedent(inspect.getsource(J.Runner.planning)) == original
    env = dict(J.__dict__)
    exec(compile(changed, str(HERE/'DERIVED_PLANNING.py'), 'exec'), env)
    changed_plan = env['planning']
    provider_sha = 'BASELINE_NO_PROVIDER' if arm == 'BASELINE' else provider.manifest_sha256
    if arm != 'BASELINE':
        assert isinstance(provider_sha, str) and len(provider_sha) == 64
    assert 'Runner' not in globals(), 'One candidate class per fresh process preserves checkpoint identity'

    class Runner(EarlyHooks, A.Runner):
        trend_exit_provider = provider  # immutable input, excluded from checkpoint state
        def __init__(self, *args, **kwargs):
            self._trend_bootstrap = True
            super().__init__(*args, **kwargs)
            self.trend_exit_arm = arm
            self.trend_exit_indicator = ARMS[arm]
            self.trend_exit_provider_sha256 = provider_sha
            self.trend_exit_log = []
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
                assert self.trend_exit_arm == arm and self.trend_exit_indicator == ARMS[arm]
                assert self.trend_exit_provider_sha256 == provider_sha

        def restore(self, path):
            payload = pickle.loads(Path(path).read_bytes())
            assert payload['runner']['integration_policy'] == self.integration_policy
            assert payload['runner']['trend_exit_arm'] == arm
            assert payload['runner']['trend_exit_provider_sha256'] == provider_sha
            return super().restore(path)  # native source/provenance gates stay

        def dump_joint(self, path):
            super().dump_joint(path)
            IO.write_gzip_jsonl(Path(path)/'trend-exit-policy.jsonl.gz', self.trend_exit_log)

    Runner.__module__ = __name__
    Runner.__qualname__ = 'Runner'
    globals()['Runner'] = Runner
    return Runner


def source_patch_diff():
    import difflib
    old, new = patched_planning_source()
    return ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile='original_joint_v3.planning', tofile='early_hook_after_original_CP.planning'))


def source_freeze(no60_module):
    result = dict(no60_module.source_freeze())
    for p in (Path(__file__), HERE/'CONTRACT.txt', HERE/'check_adapter.py'):
        result[str(p.resolve())] = sha(p)
    return result


if __name__ == '__main__':
    raise SystemExit('Adapter only; root must freeze inputs/scope before any financial execution.')
