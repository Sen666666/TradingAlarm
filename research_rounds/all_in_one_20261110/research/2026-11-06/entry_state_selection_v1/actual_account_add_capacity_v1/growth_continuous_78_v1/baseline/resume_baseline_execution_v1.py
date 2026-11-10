"""Guarded original-account continuation; research only, no strategy changes.

Reusable API: boot = bootstrap_original(); with restored_original(boot, out) as
(last, audit): run_window(boot, last, ...). The restore occurs under the actual
original AtomicOutputs_ProfitRunner identity and unmodified source freeze.
Never install an alternate engine until this context has completed restore.
Do not attach two markets to the same facts object; boot owns its facts/market.
"""
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, time as dtime
from decimal import Decimal
import argparse, gzip, hashlib, json, sys, time, traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORIGINAL = ROOT / 'account_comparison_continuous_v1/no_loss_add_v1'
FULL = ORIGINAL / 'run_1200000'
CHECKPOINT = FULL / 'latest_checkpoint/checkpoint-2022-12-30.pkl'
CHECKPOINT_SHA256 = '848cc43a153aa609e67191504e8e835474ce46bb140d23733716f3aff759ef54'
EVENT_START, EVENT_END = '2023-01-03', '2023-04-28'
PYTHON = '/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python'
sys.path.insert(0, str(ORIGINAL))
import run_no_loss_add as S


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_source_identity():
    """Reconstruct, do not copy or spoof, the original main() source freeze."""
    result = S.A.source_freeze()
    result.update(S.N.SCORES.source_manifest_sha256)
    paths = [Path(S.__file__), S.O/'continuous_execution.py',
             S.O/'factors/continuous_factors.py', S.O/'factors/SUMMARY.json',
             S.O/'inputs/continuous_inputs.py', S.O/'inputs/H1_MANIFEST.json',
             S.O/'inputs/SOURCE_FREEZE.json', S.O/'run_continuous.py',
             ORIGINAL/'profit_gate.py', ORIGINAL/'test_profit_gate.py']
    for path in paths:
        result[str(path)] = sha(path)
    return result


def verify_frozen_sources(source_freeze):
    for path, expected in source_freeze.items():
        assert sha(path) == expected, ('source drift', path)


def bootstrap_original():
    """Fresh immutable inputs and exact original runner boot; no event replay."""
    begun = time.monotonic()
    assert S.C.END == '2026-05-15', 'Never shorten factor/input horizon'
    assert sha(CHECKPOINT) == CHECKPOINT_SHA256
    meta = S.read(CHECKPOINT.with_suffix('.json'))
    provenance = S.read(CHECKPOINT.with_suffix('.provenance.json'))
    assert meta['sha256'] == provenance['checkpoint_sha256'] == CHECKPOINT_SHA256
    assert sys.version == provenance['engine_identity']['python_version']
    verify_frozen_sources(meta['source_freeze'])
    assert S.read(S.O/'factors/SUMMARY.json')['passed']
    print('LOAD_CONTINUOUS_INPUTS', flush=True)
    shared, receipts, cp, states, ir, identity = S.C.inputs()
    print('INPUTS_READY', round(time.monotonic()-begun, 3), flush=True)
    bundle, original_market, original_facts = shared
    timelines = {}
    no_factor_source = []
    for sid, raw in original_market.raw.items():
        if raw.empty:
            no_factor_source.append(sid)
            continue
        timelines[sid] = S.OpenFactorTimeline(
            raw, original_market.actions.get(sid, []),
            method=bundle.series[sid].record['adjustment']['method'], end=S.C.END)
    factors = S.FactorSource(timelines)
    r = S.A.Runner(shared, receipts, stock_cp=cp, industry_states=states, industry_receipts=ir)
    base = r.accounts['B']
    assert not base.positions and not base.trades and not base.buys and not base.exits and not base.budget.lots and not base.budget.orders
    base.available = S.CAPITAL
    base.initial_cash = S.CAPITAL
    base.current_nav = S.CAPITAL
    base.minimum_available = S.CAPITAL
    base.budget.cash = float(S.CAPITAL)
    base.risk_state = dict(on=True, peak=S.CAPITAL, saw_off=False, previous_fast=False, episode=0)
    assert base.budget.exhausted_policy == 'record_only'
    assert base.available == base.initial_cash == base.current_nav == base.minimum_available == Decimal(str(base.budget.nav)) == S.CAPITAL
    base.label = 'PVR'
    r.accounts = {'PVR': base}
    assert r.rank_mode == 'PVR_SLOT1'
    assert base.risk_state['peak'] == S.CAPITAL and base.budget.cash == float(S.CAPITAL)
    S.install(r)
    market, facts = S.attach(original_market, original_facts, factors, S.J.C.L)
    r.market, r.facts = market, facts
    for account in r.accounts.values():
        account.market, account.facts = market, facts
    r.open_checks = []
    r.assert_native_wiring()
    r.source_freeze = frozen_source_identity()
    assert r.source_freeze == meta['source_freeze'], 'Original reconstructed source freeze mismatch'
    assert len(r.source_freeze) == 45
    # Preserve the entire original recovery series. Event end alone is bounded.
    S.J.M.E.risk_policy.RECOVERY = S.pd.read_csv(S.J.M.O/'recovery.csv', index_col=0, parse_dates=True).loc[:S.C.END]
    return dict(runner=r, market=market, factors=factors, input_identity=identity,
                no_factor_source=no_factor_source, checkpoint_meta=meta,
                checkpoint_provenance=provenance, boot_seconds=time.monotonic()-begun)


@contextmanager
def restored_original(boot, out):
    """Keep the true atomic class bound for guarded restore and all baseline I/O."""
    r = boot['runner']
    assert type(r).__module__ == 'profit_gate' and type(r).__name__ == 'ProfitRunner'
    with S.IO.atomic_runner_outputs(r, S.L, Path(out), canonicalize=S.canon):
        before_identity = S.IO.runner_identity(r)
        assert before_identity == boot['checkpoint_provenance']['engine_identity']
        last = r.restore(CHECKPOINT)  # Original guarded restore, no monkeypatch.
        after_identity = S.IO.runner_identity(r)
        assert before_identity == after_identity
        assert r.source_freeze == boot['checkpoint_meta']['source_freeze']
        r.assert_native_wiring()
        a = r.accounts['PVR']
        assert last.isoformat() == '2022-12-30T15:10:00+08:00'
        assert len(a.positions) == 69 and len(a.pending) == 82
        assert a.available == Decimal('84360.525699312823')
        assert a.current_nav == Decimal('844956.557699312823')
        assert r.cost_books['PVR'].journal_cursor == len(a.journal)
        audit = dict(passed=True, last_completed_event=last,
                     checkpoint=str(CHECKPOINT), checkpoint_sha256=sha(CHECKPOINT),
                     source_files=len(r.source_freeze), engine_identity=after_identity,
                     holdings_count=len(a.positions), pending_count=len(a.pending),
                     available=str(a.available), nav=str(a.current_nav),
                     payload_sha256=S.digest(S.payload(r)), original_guards_preserved=True)
        boot['restore_audit'] = audit
        yield last, audit


def event_window(boot, last, end=EVENT_END):
    """All original ACTION/OPEN/CLOSE events after checkpoint, strictly bounded."""
    r, m = boot['runner'], boot['market']
    hi = S.J.M.N.iso(end+'T15:10:00+08:00')
    opens = {at for at in m.sessions['A'] if last < at <= hi}
    closes = {at for at in m.cutoffs if last < at <= hi}
    actions = {datetime.combine(datetime.fromisoformat(day).date(), dtime.min, S.J.M.N.TZ)
               for day in r.actions_by_date}
    events = sorted(opens | closes | {at for at in actions if last < at <= hi})
    assert min(opens).date().isoformat() == EVENT_START
    assert len(opens) == len(closes) == 78 and max(closes) == hi
    assert sorted(x.date() for x in opens) == sorted(x.date() for x in closes)
    return events, opens, closes


def run_window(boot, last, *, after_event=None):
    """Execute the unchanged original event helper; optional observation hook."""
    r, m = boot['runner'], boot['market']
    events, opens, closes = event_window(boot, last)
    begun = time.monotonic()
    log = []
    for at in events:
        S.event(r, m, at, opens, closes, None)
        last = at
        phase = 'OPEN' if at in opens else 'CLOSE' if at in closes else 'ACTION'
        log.append(dict(at=at, phase=phase))
        if after_event is not None:
            after_event(boot, at, phase)
        if at in closes and (S.pd.Timestamp(at.date())+S.pd.offsets.BDay()).month != at.month:
            print('MONTH', at.date(), 'elapsed', round(time.monotonic()-begun, 3), flush=True)
    return last, dict(event_rows=log, sessions=len(opens), events=len(events),
                      action_events=sum(x['phase']=='ACTION' for x in log),
                      run_seconds=time.monotonic()-begun)


def row_day(row):
    value = row.get('at', row.get('day'))
    assert value is not None, ('undated record', row)
    return str(value)[:10]


def first_difference(a, b, path='$'):
    if type(a) is not type(b):
        return dict(path=path, expected_type=type(a).__name__, actual_type=type(b).__name__, expected=repr(a)[:500], actual=repr(b)[:500])
    if isinstance(a, dict):
        if set(a) != set(b):
            return dict(path=path, expected_keys=sorted(a), actual_keys=sorted(b))
        for key in a:
            diff = first_difference(a[key], b[key], path+'.'+str(key))
            if diff:
                return diff
    elif isinstance(a, list):
        if len(a) != len(b):
            return dict(path=path, expected_length=len(a), actual_length=len(b))
        for i, (left, right) in enumerate(zip(a, b)):
            diff = first_difference(left, right, path+f'[{i}]')
            if diff:
                return diff
    elif a != b:
        return dict(path=path, expected=a, actual=b)
    return None


def jsonl(path):
    with gzip.open(path, 'rt') as handle:
        for line in handle:
            yield json.loads(line)


def compare_records(expected, actual):
    """All fields compared exactly, including unrounded Decimal strings."""
    expected = iter(x for x in expected if row_day(x) <= EVENT_END)
    actual = iter(actual)
    eh, ah = hashlib.sha256(), hashlib.sha256()
    count, continuation, first = 0, 0, None
    end = object()
    while True:
        left, right = next(expected, end), next(actual, end)
        if left is end and right is end:
            break
        if first is None:
            if left is end or right is end:
                first = dict(row=count, reason='record_count_mismatch', expected_missing=left is end, actual_missing=right is end)
            else:
                diff = first_difference(left, right)
                if diff:
                    first = dict(row=count, **diff)
        for value, hasher in ((left, eh), (right, ah)):
            if value is not end:
                hasher.update((json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))+'\n').encode())
        if left is not end and EVENT_START <= row_day(left) <= EVENT_END:
            continuation += 1
        count += 1
    return dict(passed=first is None, prefix_records=count, continuation_records=continuation,
                expected_sha256=eh.hexdigest(), actual_sha256=ah.hexdigest(), first_difference=first)


def validate_exports(out):
    checks = {}
    with gzip.open(FULL/'pair/PVR.json.gz', 'rt') as handle:
        original = json.load(handle)
    with gzip.open(out/'pair/PVR.json.gz', 'rt') as handle:
        continued = json.load(handle)
    for key in ('journal', 'trades', 'decisions', 'audit'):
        checks[key] = compare_records(original[key], continued[key])
    del original, continued
    for key in ('funding', 'daily', 'balances', 'opportunities', 'industry', 'rank-policy'):
        checks[key] = compare_records(jsonl(FULL/f'pair/{key}.jsonl.gz'), jsonl(out/f'pair/{key}.jsonl.gz'))
    for key in ('PROFIT_GATE_EVENTS', 'OPEN_CASH_CHECKS'):
        checks[key] = compare_records(jsonl(FULL/f'{key}.jsonl.gz'), jsonl(out/f'{key}.jsonl.gz'))
    # Market execution cache is intentionally not checkpointed; compare new events only.
    checks['SHARED_WINDOW_AUDIT'] = compare_records(
        (row for row in jsonl(FULL/'SHARED_WINDOW_AUDIT.jsonl.gz') if row_day(row) >= EVENT_START),
        jsonl(out/'SHARED_WINDOW_AUDIT.jsonl.gz'))
    return dict(passed=all(x['passed'] for x in checks.values()), checks=checks,
                first_difference=next((dict(check=key, **value['first_difference']) for key, value in checks.items() if not value['passed']), None),
                comparison='Every field and sequence compared exactly, including Decimal monetary strings, holdings, cash, orders, decisions and execution records; no tolerance and no NAV-only gate.',
                source_full_run=str(FULL), event_start=EVENT_START, event_end=EVENT_END)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='run')
    args = parser.parse_args()
    out = (HERE / args.out).resolve()
    assert out.is_relative_to(HERE) and out != HERE
    assert not out.exists(), 'Never overwrite an existing experiment'
    out.mkdir(parents=True)
    started = time.monotonic()
    last = None
    boot = None
    try:
        boot = bootstrap_original()
        r, m = boot['runner'], boot['market']
        S.save(out/'PREDECLARED.json', dict(
            mode='STRICT_ORIGINAL_ACCOUNT_CONTINUATION_BASELINE', checkpoint=str(CHECKPOINT),
            checkpoint_sha256=CHECKPOINT_SHA256, event_start=EVENT_START, event_end=EVENT_END,
            trading_sessions=78, immutable_input_end=S.C.END, annual_resets=False,
            account_reset=False, real_orders=False, source_freeze=r.source_freeze,
            driver_sha256=sha(__file__), python_version=sys.version,
            study_label='FIXED_FUTURE_1709_POOL_CAUSAL_OPEN_PROXY_NOT_PIT_TRADABLE'))
        with restored_original(boot, out) as (last, audit):
            S.save(out/'RESTORE_AUDIT.json', audit)
            print('STRICT_RESTORE_PASS', flush=True)
            last, run = run_window(boot, last)
            S.IO.write_gzip_jsonl(out/'EVENT_CLOCK.jsonl.gz', run.pop('event_rows'), encoder=S.J.C.encoded)
            r.checkpoint(out/'latest_checkpoint', last)
            r.dump_joint(out/'pair')
        verify_frozen_sources(r.source_freeze)
        assert sha(CHECKPOINT) == CHECKPOINT_SHA256
        S.IO.write_gzip_jsonl(out/'PROFIT_GATE_EVENTS.jsonl.gz', r.profit_gate_events, encoder=S.J.C.encoded)
        S.IO.write_gzip_jsonl(out/'OPEN_CASH_CHECKS.jsonl.gz', r.open_checks, encoder=S.J.C.encoded)
        S.IO.write_gzip_jsonl(out/'SHARED_WINDOW_AUDIT.jsonl.gz', m.exec_rows, encoder=S.J.C.encoded)
        S.save(out/'REMAINING_COST_BOOK.json', r.cost_books['PVR'].states)
        print('COMPARE_ORIGINAL_PREFIX', flush=True)
        validation = validate_exports(out)
        S.save(out/'BASELINE_VALIDATION.json', validation)
        assert validation['passed'], validation['first_difference']
        result = dict(completed=True, validation_passed=True, last_event=last,
                      seconds=time.monotonic()-started, boot_seconds=boot['boot_seconds'], **run,
                      holdings_count=len(r.accounts['PVR'].positions), pending_count=len(r.accounts['PVR'].pending),
                      ending_cash=str(r.accounts['PVR'].available), ending_nav=str(r.accounts['PVR'].current_nav),
                      original_sources_unchanged=True, original_checkpoint_unchanged=True,
                      original_engine_guards_preserved=True, real_orders=False)
        S.save(out/'DONE.json', result)
        S.save(out/'OUTPUT_HASHES.json', {str(path.relative_to(out)): sha(path) for path in sorted(out.rglob('*')) if path.is_file()})
        print('DONE', json.dumps(S.canon(result)), flush=True)
    except BaseException as exc:
        S.save(out/'FAILURE.json', dict(error=str(exc), traceback=traceback.format_exc(), last_complete_event=last,
                                      partial_event_not_resumable=True, auto_retry=False))
        raise


if __name__ == '__main__':
    main()
