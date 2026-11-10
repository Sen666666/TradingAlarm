"""Save source-only contract evidence. Never import/run an economic consumer.

Outputs only to this new directory's design_facts/ child, refuses overwrite.
Run with the specified research Python, PYTHONDONTWRITEBYTECODE=1 and -B.
"""
from pathlib import Path
import ast
import hashlib
import json
import textwrap
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
R = O.parent
E = R / 'm3_stock_birth_during_sector_v1'
DEST = O / 'design_facts'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    (DEST / name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                      default=str, allow_nan=False) + '\n')


def main():
    if DEST.exists():
        raise RuntimeError('Completed/incomplete design evidence exists: do not overwrite')
    references = [
        R / 'independent_channel_probe_preflight_v1/core.py',
        R / 'independent_channel_probe_preflight_v1/PROTOCOL.md',
        R / 'independent_channel_full1709_preflight_v1/engine.py',
        R / 'independent_channel_full1709_preflight_v1/FINAL_MARKET_SEAL.json',
        R / 'independent_channel_full1709_preflight_v1/INDEPENDENT_FULL_AUDIT.json',
        R / 'independent_channel_full1709_preflight_v1/overlap/CONTRACT.json',
        R / 'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet',
        R / 'fast_entry_equity_2022_v1/NATIVE_CONTRACT_NOTES.md',
        R / 'fast_entry_equity_2022_v1/prepare_inputs.py',
        R / 'fast_entry_equity_2022_v1/lifecycle.py',
        E / 'relative_priority_v1/simulate.py',
    ]
    baselines = [
        ('2022', E / 'relative_priority_equity_run_2022_v1', 'dynamic'),
        ('2024_924', E / 'cash_equity_baseline_2024_v1', 'economic'),
    ]
    plan = []
    for window, base, leaf in baselines:
        for name in ['engine.py', 'run.py', 'READOUT.md', 'report/CORE_AND_FULL_ROUNDS.csv']:
            references.append(base / name)
        for name in ['ROUNDS.csv', 'ACTIONS.csv', 'DECISIONS.csv', 'RANKING_AUDIT.csv',
                     'END_STATES.csv']:
            p = base / leaf / name
            references.append(p)
            q = pd.read_csv(p, low_memory=False)
            if 'arm' in q:
                q = q[q.arm.eq('A_UNION_B')]
            plan.append(dict(window=window, file=str(p), expected_rows=len(q),
                             columns=list(q.columns), sha256=sha(p),
                             comparison='all original columns/actions; no tolerance widening',
                             regression_executed=False))
    source_hashes = {str(p): sha(p) for p in references}
    overlap = references[6]
    receipts = pd.read_parquet(overlap)
    fields = ['old_sector_known', 'old_sector_observed_today',
              'old_sector_rs_ready_fresh', 'old_sector_up']
    counts = []
    for window, rows in receipts.groupby('window'):
        for scope, q in [('BIRTH', rows[rows.born]), ('ALL_RECEIPTS', rows)]:
            t = q[fields].astype('boolean')
            ok = t.fillna(False).all(axis=1)
            unknown = t.isna().any(axis=1)
            known_false = (~t.fillna(True)).any(axis=1) & ~unknown
            known_pvr = q.old_PVR_known.fillna(False) & np.isfinite(q.old_PVR_score)
            result = dict(window=window, scope=scope, receipts=len(q),
                          industry_pass=int(ok.sum()), industry_unknown=int(unknown.sum()),
                          industry_false=int(known_false.sum()),
                          industry_pass_pvr_known=int((ok & known_pvr).sum()),
                          industry_pass_pvr_unknown=int((ok & ~known_pvr).sum()),
                          industry_pass_unstarted_close_size=int(
                              (ok & q.conditional_unstarted_target_feasible.fillna(False)).sum()))
            for c in fields:
                result[c + '_true'] = int(t[c].eq(True).sum())
                result[c + '_false'] = int(t[c].eq(False).sum())
                result[c + '_unknown'] = int(t[c].isna().sum())
            counts.append(result)
    cases = [('300085.SZ', '2024-09-19'), ('002583.SZ', '2024-09-20'),
             ('002583.SZ', '2024-09-23'), ('300666.SZ', '2022-06-06'),
             ('300666.SZ', '2024-09-27')]
    case_rows = []
    cols = ['window', 'sid', 'name', 'day', 'born', 'root_day', 'phase'] + fields + [
        'old_AB_event_id', 'old_AB_event_type', 'old_AB_I_qualified',
        'old_AB_PVR_known', 'old_ab_I_PVR_qualified_permit', 'old_PVR_score',
        'old_ab_baseline_stock_state_before', 'old_ab_baseline_decision',
        'old_ab_baseline_close_check', 'old_ab_baseline_selected',
        'old_ab_baseline_queue_rank', 'close_size_check']
    for sid, day in cases:
        q = receipts[receipts.sid.eq(sid) & receipts.day.eq(pd.Timestamp(day))]
        assert len(q) == 1
        case_rows.append(q[cols])
    # Exact original helpers and native Q setup, restricting bundle lines to this
    # one named source-only case. No signal model, order, account or lifecycle.
    p = R / 'fast_entry_equity_2022_v1/prepare_inputs.py'
    text = p.read_text()
    env = {'__file__': str(p)}
    exec(compile(text[:text.index('\ndef main():')], str(p) + ':helpers', 'exec'), env)
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)
                and n.name == 'main')
    body = textwrap.dedent('\n'.join(ast.get_source_segment(text, node).splitlines()[1:]))
    setup = body[:body.index('tpath=W/')]
    assert setup.count('keep=set(ids)') == 1
    setup = setup.replace('keep=set(ids)', 'keep={"300666.SZ"}')
    exec(compile(setup, str(p) + ':one_stock_native_facts_only', 'exec'), env)
    sid = '300666.SZ'
    fp = Path(env['manifest'][sid]['refs']['facts'])
    source_hashes[str(fp)] = sha(fp)
    facts = pd.read_parquet(fp).loc[:env['END']]
    env['f'].f[sid] = facts
    env['b'].series[sid].states = facts[['e0_ready', 'e0_target', 'segment_id']].rename(
        columns={'e0_ready': 'ready', 'e0_target': 'target'})
    startup = []
    for day in ['2025-12-15', '2025-12-17', '2025-12-23']:
        d = pd.Timestamp(day)
        clock, stocks, sectors = env['f'].packet(env['datetime'].combine(
            d.date(), env['time'](15, 10), env['TZ']), 'I')
        ss = {s.sector_id: s for s in sectors}
        stock = next(s for s in stocks if s.security_id == sid)
        e = env['native_elig'](stock, ss, clock, 'S0')
        reasons = set(e.reasons)
        row = dict(sid=sid, day=day, sector=e.sector_id, native_event_Q=e.q,
                   native_reasons='|'.join(e.reasons), source_only_not_economic=True)
        for c in ['sector_known', 'sector_observed_today', 'sector_rs_ready_fresh', 'sector_up']:
            row[c] = None if c + ':unknown' in reasons else False if c + ':false' in reasons else True
        sec = ss[e.sector_id]
        row.update(sector_trend_known_at=str(sec.trend_up.known_at),
                   sector_observed_at=str(sec.trend_up.observed_at),
                   sector_H1=sec.rank.read(clock), sector_H1_known_at=str(sec.rank.known_at))
        startup.append(row)
    source_hashes.update(env['SOURCES'])
    for p, h in source_hashes.items():
        assert sha(p) == h, (p, 'source changed during read-only verification')
    DEST.mkdir()
    pd.DataFrame(counts).to_csv(DEST / 'INDUSTRY_GATE_COUNTS.csv', index=False)
    pd.concat(case_rows, ignore_index=True).to_csv(DEST / 'NAMED_CASE_INDUSTRY.csv', index=False)
    pd.DataFrame(startup).to_csv(DEST / 'JIANGFENG_202512_NATIVE_INDUSTRY.csv', index=False)
    save('BASELINE_REGRESSION_PLAN.json', plan)
    save('SOURCE_HASHES.json', source_hashes)
    save('QA.json', dict(scope='DESIGN_FACTS_ONLY', script_sha256=sha(__file__),
                         protocol_sha256=sha(O / 'PROTOCOL_DRAFT.md'),
                         old_sources_unchanged=True, baseline_engines_imported=False,
                         no_new_market_formula=True, new_economic_runs=0,
                         baseline_regressions_executed=0, actual_orders=0, actual_fills=0,
                         native_startup_fact_days=len(startup), full_window_count_rows=len(counts)))
    save('OUTPUT_HASHES.json', {p.name: sha(p) for p in DEST.iterdir() if p.is_file()})
    print('DESIGN_FACTS_DONE: six count rows, five fixed-window cases, three native startup days; no economics.')


if __name__ == '__main__':
    main()
