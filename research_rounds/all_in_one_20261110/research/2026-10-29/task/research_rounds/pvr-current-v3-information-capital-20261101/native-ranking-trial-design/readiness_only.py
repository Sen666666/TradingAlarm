"""Read saved native intent domains and original PVR readiness, never scores/labels/PnL.

The original finite-window score is ready exactly after 85 consecutive valid
same-source observations. Cross-check that mask against every existing score
cache point. No score cache, account, signal, or historical order is modified.
"""
from pathlib import Path
from datetime import datetime, timezone
import collections, gzip, hashlib, json, time
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
P = O.parent
W = P.parent
ROOTS = {
    '2022': W/'2022-normal-reference-20261031/runs/B_diag/pair',
    '2025_26': W/'q2-normal-continuation-20261031/runs/B_diag/pair',
}
INPUT = {}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p):
    INPUT[str(p)] = sha(p)
    return json.loads(Path(p).read_text())

def stream(p):
    INPUT[str(p)] = sha(p)
    with gzip.open(p, 'rt') as f:
        for line in f:
            yield json.loads(line)

def save(name, x):
    p = O/name
    t = p.with_name(p.name+'.tmp')
    t.write_text(json.dumps(x, ensure_ascii=False, indent=2)+'\n')
    t.replace(p)

def main():
    started = time.monotonic()
    domains = {}
    points = collections.defaultdict(set)
    for win, root in ROOTS.items():
        INPUT[str(root/'B.json.gz')] = sha(root/'B.json.gz')
        with gzip.open(root/'B.json.gz', 'rt') as f:
            # Do not inspect trades, account contribution or any outcome labels.
            decisions = json.load(f)['decisions']
        planned = []
        for d in decisions:
            day = d['at'][:10]
            for i in d['intents']:
                planned.append(dict(day=day, sid=i['sid'], role=i['role'],
                                    H1=i['score'], original_rank=i['rank']))
                points[i['sid']].add(day)
        roles = []
        for x in stream(root/'opportunities.jsonl.gz'):
            for role in x['roles']:
                roles.append(dict(day=x['day'], sid=x['sid'], role=role,
                                  barriers=x['barriers']))
                points[x['sid']].add(x['day'])
        domains[win] = (planned, roles, len(decisions))

    manifest = read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
    sm = {x['symbol']: x for x in manifest}
    masks = {}
    checked = 0
    source_na = []
    for number, sid in enumerate(sorted(points), 1):
        candidates = [(Path(p), h) for p, h in sm[sid]['source_sha256'].items()
                      if p.endswith('/signal.parquet')]
        assert len(candidates) == 1, (sid, candidates)
        path, expected = candidates[0]
        assert sha(path) == expected, ('input changed', sid)
        INPUT[str(path)] = expected
        f = pd.read_parquet(path).loc[:'2026-06-30']
        valid = f.close.gt(0) & np.isfinite(f.close) & f.amount.gt(0) & np.isfinite(f.amount)
        for key in ['price_eligible', 'observed_bar', 'is_observed_bar']:
            if key in f:
                valid &= f[key].fillna(False).astype(bool)
        for key in ['source_invalid', 'synthetic_event_bar']:
            if key in f:
                valid &= ~f[key].fillna(True).astype(bool)
        seg = f.segment_id if 'segment_id' in f else pd.Series(0, index=f.index)
        block = ((~valid) | (~valid.shift(fill_value=False)) | seg.ne(seg.shift())).cumsum()
        ready = valid & (valid.groupby(block).cumsum() >= 85)
        mask = {str(t.date()): bool(v) for t, v in ready.items()}
        masks[sid] = mask
        cache = P/'pvr-cache'/f'{sid}.parquet'
        if cache.exists():
            meta = read(cache.with_suffix('.json'))
            assert meta['source_sha256'] == expected
            assert meta['output_sha256'] == sha(cache)
            INPUT[str(cache)] = sha(cache)
            c = pd.read_parquet(cache)
            for t, v in c.score.items():
                assert mask.get(str(t.date()), False) == bool(np.isfinite(v)), (sid, str(t), v)
                checked += 1
        for day in sorted(points[sid]):
            if not mask.get(day, False):
                source_na.append(dict(sid=sid, day=day,
                                      reason='source_day_absent' if day not in mask else
                                      'less_than_85_consecutive_original_valid_same_source_observations'))
        if number % 500 == 0:
            print('READINESS_ONLY', number, '/', len(points), round(time.monotonic()-started, 2), flush=True)

    detail = []
    def census(rows):
        result = {}
        for role in ['core', 'mobile']:
            rr = [x for x in rows if x['role'] == role]
            bad = [x for x in rr if not masks[x['sid']].get(x['day'], False)]
            result[role] = dict(events=len(rr), ready=len(rr)-len(bad), NA=len(bad),
                                NA_fraction=len(bad)/len(rr) if rr else None,
                                distinct_stocks=len({x['sid'] for x in rr}),
                                NA_stocks=len({x['sid'] for x in bad}))
        keys = {(x['sid'], x['day']) for x in rows}
        na = {(sid, day) for sid, day in keys if not masks[sid].get(day, False)}
        result['distinct_stock_day_slots'] = dict(total=len(keys), NA=len(na),
                                                   NA_fraction=len(na)/len(keys) if keys else None)
        return result

    out = {}
    for win, (planned, roles, days) in domains.items():
        for domain, rows in [('saved_original_planned_intents', planned),
                             ('all_original_role_eligible_before_account_barriers', roles)]:
            for x in rows:
                if not masks[x['sid']].get(x['day'], False):
                    detail.append(dict(window=win, domain=domain, **x))
        both = collections.defaultdict(set)
        for x in planned:
            both[x['sid'], x['day']].add(x['role'])
        perday = collections.Counter(day for sid, day in both)
        vals = np.array(list(perday.values()), dtype=float)
        out[win] = dict(
            decision_dates=days,
            saved_original_planned_intents=census(planned),
            all_original_role_eligible_before_account_barriers=census(roles),
            planned_same_stock_both_roles=sum(v == {'core', 'mobile'} for v in both.values()),
            planned_core_only_slots=sum(v == {'core'} for v in both.values()),
            nonempty_candidate_dates=len(perday),
            distinct_planned_stocks_per_nonempty_date=dict(min=float(vals.min()),
                median=float(np.median(vals)), max=float(vals.max())) if len(vals) else None,
        )
    # Saved PVR caches cover only receipt mother points, not every native intent.
    save('NATIVE_NA_READINESS.json', dict(at=datetime.now(timezone.utc).isoformat(),
        scope='original saved SC/Bdiag native role/intent domain only, not future changed-account domain',
        windows=out, original_PVR_cache_points_mask_exact=checked,
        source_stocks_read=len(points), source_missing_or_unready_stock_days=len(source_na),
        seconds=time.monotonic()-started, new_scores_generated=0, economic_paths=0,
        new_price_label_values_read=0, original_score_cache_unchanged=True,
        source_support_rule='exact original valid/segment restart mask; 85th valid observation first ready',
        caveat='Readiness mask checked against all existing cached score points. Actual off-mother score export/native wiring remains unimplemented.'))
    save('NA_NATIVE_EVENTS.json', detail)
    save('SOURCE_SUPPORT_NA.json', source_na)
    save('READINESS_INPUT_SHA256.json', INPUT)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print('DONE readiness only', round(time.monotonic()-started, 2), 'seconds; old PVR points exact', checked)

if __name__ == '__main__':
    main()
