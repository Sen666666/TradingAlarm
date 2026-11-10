"""Independent accounting and S-only admission/exit contracts.

This module never starts an account replay.  It reads existing replay outputs
and delegates raw-price/cash/share/action/fee reconstruction to the unchanged
independent analyzer from the earlier finite-capital study.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal as D
from pathlib import Path
import sys

from sa_common import O, PRIOR, PREPS, OLD_TABLES, OLD_ACCOUNTS, read, rows, save, pd

sys.path.insert(0, str(PRIOR / 'code'))
import experiment as P


def contract_checker(strict_dir: Path):
    cache = {}

    def strict_at(sid, day):
        if sid not in cache:
            frame = pd.read_parquet(strict_dir / f'{sid}.parquet')
            assert frame.index.is_unique and frame.index.is_monotonic_increasing, sid
            assert pd.api.types.is_bool_dtype(frame.strict_target), sid
            assert not frame.strict_target.isna().any(), sid
            cache[sid] = frame
        frame = cache[sid]
        day = pd.Timestamp(day)
        assert day in frame.index, (sid, day, 'missing strict observation')
        return bool(frame.loc[day, 'strict_target'])

    def check(aid, obj, ds, facts, records):
        assert aid.startswith('S__'), ('unexpected policy', aid)
        intents, classes = {}, {}
        counts = Counter()
        risk = {r['at']: r for r in obj['audit_log'] if r['kind'] == 'risk_checkpoint'}
        forbidden = {'intent_create', 'intent_end', 'waiting_support_raise',
                     'waiting_support_inherited', 'fast_support_raise',
                     'fast_support_exit', 'rotation_started', 'rotation_buy_reserved',
                     'rotation_finished', 'risk_fill_bound'}
        for r in obj['audit_log']:
            kind = r['kind']
            assert kind not in forbidden, (aid, 'unexpected extra mechanism', kind)
            if kind == 'risk_checkpoint':
                assert r['policy'] == 'ACT20_BREAK', (aid, r)
                counts['unchanged_act_policy'] += 1
            elif kind == 'entry_contract':
                assert r['mode'] == 'S'
                sid, day = r['sid'], pd.Timestamp(r['decision_at'][:10])
                assert day in facts[sid].index
                original = facts[sid].loc[day]
                assert bool(original.i_buy), (aid, sid, day, 'not original I event')
                assert strict_at(sid, day), (aid, sid, day, 'strict gate false')
                assert D(r['floor_signal']) == D(str(original.i_floor)), (
                    aid, sid, day, 'actual entry support differs from original I')
                assert D(r['budget']) <= D('.15') * D(r['nav']) + D('.01')
                assert D(r['risk_budget']) == D('.01') * D(r['nav'])
                assert risk[r['at']]['on'], (aid, r['at'], 'entry while ACT paused')
                assert r['order_id'] not in intents
                intents[r['order_id']] = r
                counts['original_i_and_strict_gate'] += 1
                counts['original_i_floor_exact'] += 1
                counts['unchanged_budget'] += 1
            elif kind == 'intent_entry_class':
                assert r['original'] is True and r['origin'] is None and r['window'] == 0, (aid, r)
                assert r.get('waiting_floor') is None, (aid, r)
                assert r['order_id'] in intents
                classes[r['order_id']] = r
                counts['no_waiting_extension'] += 1
            elif kind == 'fill' and r['receipt']['side'] == 'buy':
                fill = r['receipt']
                order = intents[r['order_id']]
                assert r['order_id'] in classes
                assert order['decision_at'][:10] < fill['at'][:10]
                assert fill['at'][11:19] == '09:30:00', (aid, fill)
                factor = D(str(facts[fill['security_id']].loc[:fill['at'][:10]].iloc[-1].factor))
                assert D(r['raw_open']) > D(order['floor_signal']) / factor
                multiplier = D(2) if aid.endswith('cost2') else D(1)
                assert D(r['price']) == D(r['raw_open']) * (1 + D('.0005') * multiplier)
                counts['next_open_original_support'] += 1
            elif kind == 'fill' and r['receipt']['side'] == 'sell':
                fill = r['receipt']
                assert fill['at'][11:19] == '09:30:00', (aid, fill)
                multiplier = D(2) if aid.endswith('cost2') else D(1)
                assert D(r['price']) == D(r['raw_open']) * (1 - D('.0005') * multiplier)
                counts['unchanged_sell_price'] += 1
            elif kind == 'exit_request':
                sid, day = r['sid'], r['at'][:10]
                original = facts[sid].loc[:day].iloc[-1]
                assert not bool(original.i_target) or not risk[r['at']]['on'], (
                    aid, sid, day, 'exit not explained by original I or ACT pause')
                counts['original_structure_or_account_exit'] += 1
        assert set(intents) == set(classes), (aid, 'unclassified original buy orders')
        return {'passed': True, 'checks': dict(counts)}
    return check


def audit(run_root, core, prep, strict_dir, stage='economic'):
    run_root, core, prep, strict_dir = map(Path, (run_root, core, prep, strict_dir))
    assert stage in ('short', 'economic')
    analyzer = P.A
    analyzer.CORE, analyzer.PREP, analyzer.HERE = core, prep, run_root
    analyzer.check_contract = contract_checker(strict_dir)
    analyzer.main(stage)


def control(run_root, ref_dir, stage='economic'):
    run_root, ref_dir = Path(run_root), Path(ref_dir)
    assert stage in ('short', 'economic')
    source = run_root / ('technical/short-v2' if stage == 'short' else 'accounts-v2')
    current = rows(source / 'daily.jsonl.gz')
    assert current
    reference = {(r['account'], r['at']): r for r in rows(ref_dir / 'daily.jsonl.gz')}
    for row in current:
        assert row == reference[row['account'], row['at']], (row['account'], row['at'], 'daily control differs')
    end = max(r['at'] for r in current)
    ids = {r['account'] for r in current}
    for aid in sorted(ids):
        obj, ref = read(source / f'{aid}.json'), read(ref_dir / f'{aid}.json')
        assert obj['fills'] == [r for r in ref['fills'] if r['at'] <= end], (aid, 'fill control differs')
    receipt = dict(passed=True, accounts=len(ids), daily_rows=len(current),
                   complete_daily_rows_exact=True, fills_exact=True,
                   final_timestamp=end, reference=str(ref_dir))
    save(run_root / ('control-short.json' if stage == 'short' else 'control-full.json'), receipt)
    return receipt


def prefix(run_root):
    run_root = Path(run_root)
    full, cut = run_root / 'accounts-v2', run_root / 'technical/prefix'
    counts = {}
    for name in ('daily', 'decisions'):
        reference = {(r['account'], r['at']): r for r in rows(full / f'{name}.jsonl.gz')}
        current = rows(cut / f'{name}.jsonl.gz')
        assert current
        for row in current:
            assert row['at'][:10] <= '2026-06-30'
            assert row == reference[row['account'], row['at']], (name, row['account'], row['at'])
        counts[name] = len(current)
    accounts = sorted({r['account'] for r in rows(cut / 'daily.jsonl.gz')})
    for aid in accounts:
        current, reference = read(cut / f'{aid}.json'), read(full / f'{aid}.json')
        assert current['fills'] == [r for r in reference['fills'] if r['at'][:10] <= '2026-06-30'], aid
    receipt = dict(passed=True, accounts=len(accounts), cutoff='2026-06-30', fills_exact=True, **counts)
    save(run_root / 'prefix-verification.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['audit', 'control', 'prefix'])
    parser.add_argument('sector', choices=['TECH', 'DRUG'])
    parser.add_argument('version', choices=['OLD', 'AMT'])
    parser.add_argument('stage', nargs='?', default='economic', choices=['short', 'economic'])
    args = parser.parse_args()
    root = O / args.sector / args.version
    if args.action == 'audit':
        core = PRIOR / 'input' if args.sector == 'TECH' else PREPS['DRUG']
        strict_dir = OLD_TABLES[args.sector] if args.version == 'OLD' else O / 'signals' / args.sector
        audit(root, core, PREPS[args.sector], strict_dir, args.stage)
    elif args.action == 'control':
        assert args.version == 'OLD', 'Only original S is an identity control'
        control(root, OLD_ACCOUNTS[args.sector], args.stage)
    else:
        prefix(root)
