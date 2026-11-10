"""One causal completed-mobile feedback classification, saved books only."""
from pathlib import Path
from decimal import Decimal, getcontext
from collections import defaultdict
from bisect import bisect_left
from datetime import datetime
import gzip, hashlib, json
import pandas as pd

getcontext().prec = 60
D = Decimal
Z = D(0)
O = Path(__file__).resolve().parent
B = Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
M = B / 'risk_constraints/ma63_information_diagnostic_v1'
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
SOURCES = {}

def read(p):
    p = Path(p)
    SOURCES[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    if p.suffix == '.gz':
        with gzip.open(p, 'rt') as f:
            return json.load(f)
    return json.loads(p.read_text())

def save(name, value):
    with (O / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, default=str)
        f.write('\n')

def n(x):
    return D(str(x))

def at(s):
    return datetime.fromisoformat(s)

def agg(rows):
    out = dict(layers=len(rows), stocks=len({x['sid'] for x in rows}))
    for field in ['cost', 'net', 'strict_realized', 'open_unrealized', 'recognized_dividend_AR', 'buy_fee', 'sell_fee']:
        out[field] = None if any(field not in x for x in rows) else sum((n(x[field]) for x in rows), Z)
    out.update(positive_net=sum((n(x['net']) for x in rows if n(x['net']) > 0), Z),
               negative_net=sum((n(x['net']) for x in rows if n(x['net']) < 0), Z),
               negative_layers=sum(n(x['net']) < 0 for x in rows),
               open_layers=sum(bool(x['qty']) for x in rows))
    return out

def groups(rows, field):
    return {key: agg([x for x in rows if x[field] == key]) for key in sorted({x[field] for x in rows})}

def main():
    read(O / 'PROTOCOL.json')
    fixed = read(M / 'ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json')['members']
    industry_manifest = {x['series']: x for x in read(W / 'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
    states = {}

    def identity(sector, decision):
        if sector not in states:
            man = industry_manifest[sector]
            p = Path(man['refs']['state'])
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            assert h == man['output_sha256'][str(p)]
            SOURCES[str(p)] = h
            f = pd.read_parquet(p, columns=['day', 'attempt_id', 'action'])
            f['day'] = f.day.astype(str).str[:10]
            states[sector] = f.set_index('day', drop=False)
        f = states[sector]
        day = decision[:10]
        if day not in f.index:
            return None
        prefix = f.loc[:day]
        aid = prefix.iloc[-1].attempt_id
        if pd.isna(aid):
            return None
        probes = prefix[prefix.attempt_id.eq(aid) & prefix.action.eq('probe')]
        return None if probes.empty else str(probes.iloc[0].day)

    results = {}
    for ref, root in [
        ('2022_2024', B / 'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024'),
        ('strong', B / 'pvr_pool_feasibility/runs/2025_26'),
    ]:
        entries = read(M / (ref + '_ENTRIES.json'))
        book = read(root / 'pair/B.json.gz')
        assert len(entries) == (2265 if ref == '2022_2024' else 1171)
        buys = {x['layer']: x for x in book['trades'] if x['side'] == 'buy'}
        sells = defaultdict(list)
        for t in book['trades']:
            if t['side'] == 'sell':
                for part in t['parts']:
                    sells[part['layer']].append(dict(at=t['at'], net_cash=part['net_cash'], shares=part['shares'], reason=part['reason']))
        evidence = defaultdict(list)
        sector_evidence = defaultdict(list)
        native = {x['id']: x for x in book['layers']}
        for e in entries:
            assert identity(e['sector'], e['decision_at']) == e['probe_progress']['probe_day']
            if e['role'] != 'mobile' or e['qty']:
                continue
            lid = e['layer']
            sale = sells[lid]
            assert sale and max(at(t['at']) for t in sale) == at(e['closed'])
            cash = sum((n(t['net_cash']) for t in sale), Z) - n(e['cost'])
            assert abs(cash - n(e['strict_realized'])) < D('1e-18')
            assert abs(cash - n(native[lid]['cash'])) < D('1e-18')
            row = dict(layer=lid, sid=e['sid'], sector=e['sector'], probe_day=e['probe_progress']['probe_day'],
                       closed=e['closed'], trading_cash=cash, sale_parts=sale)
            evidence[(e['sector'], row['probe_day'])].append(row)
            sector_evidence[e['sector']].append(row)
        for value in list(evidence.values()) + list(sector_evidence.values()):
            value.sort(key=lambda x: (at(x['closed']), x['layer']))

        def classify(e):
            x = dict(e)
            probe_day = identity(x['sector'], x['decision_at'])
            clock = at(x['decision_at'])
            seq = evidence[(x['sector'], probe_day)]
            times = [at(t['closed']) for t in seq]
            prior = seq[:bisect_left(times, clock)]
            assert all(at(t['closed']) < clock for t in prior)
            balance = sum((t['trading_cash'] for t in prior), Z)
            old = [t for t in sector_evidence[x['sector']] if at(t['closed']) < clock and t['probe_day'] != probe_day]
            # Partial-only layers are excluded. Record availability, never use their later terminal value.
            partial = []
            for p in entries:
                if p['role'] != 'mobile' or p['sector'] != x['sector'] or p['probe_progress']['probe_day'] != probe_day or at(p['opened']) >= clock:
                    continue
                ps = [s for s in sells[p['layer']] if at(s['at']) < clock]
                if ps and (not p['closed'] or at(p['closed']) >= clock):
                    partial.append(p['layer'])
            label = 'unknown_original_industry_identity' if probe_day is None else 'no_completed_mobile' if not prior else 'negative_completed_net' if balance < 0 else 'nonnegative_completed_net'
            x['feedback'] = dict(label=label, probe_day=probe_day, completed_trading_cash=balance,
                prior_completed_layers=[t['layer'] for t in prior], prior_completed_stocks=sorted({t['sid'] for t in prior}),
                other_stock_completed_layers=[t['layer'] for t in prior if t['sid'] != x['sid']],
                latest_evidence_at=max((t['closed'] for t in prior), default=None),
                first_negative_evidence_at=next((t['closed'] for t in prior if t['trading_cash'] < 0), None),
                lag_calendar_days_since_latest=None if not prior else (clock - max(at(t['closed']) for t in prior)).total_seconds() / 86400,
                omitted_old_attempt_completed_layers=len(old), omitted_old_attempt_completed_trading_cash=sum((t['trading_cash'] for t in old), Z),
                partial_only_layer_ids=partial)
            x['feedback_label'] = label
            return x

        rows = [classify(e) for e in entries]
        scopes = {'ALL': rows}
        if ref == '2022_2024':
            scopes['2022_2023'] = [x for x in rows if x['opened'][:10] <= '2023-12-29']
            scopes['strict303_postOct8_newfills'] = [x for x in rows if '2024-10-08' < x['opened'][:10] <= '2024-12-31']
            assert len(scopes['strict303_postOct8_newfills']) == 303
        summary = {}
        for name, sr in scopes.items():
            summary[name] = dict(all=agg(sr), by_feedback=groups(sr, 'feedback_label'),
                by_action={a: groups([x for x in sr if x['action'] == a], 'feedback_label') for a in sorted({x['action'] for x in sr})},
                by_role={r: groups([x for x in sr if x['role'] == r], 'feedback_label') for r in ['mobile', 'core']},
                negative_with_other_stock_evidence=agg([x for x in sr if x['feedback_label'] == 'negative_completed_net' and x['feedback']['other_stock_completed_layers']]),
                no_completed_but_old_attempt_losses=agg([x for x in sr if x['feedback_label'] == 'no_completed_mobile' and x['feedback']['omitted_old_attempt_completed_trading_cash'] < 0]),
                partial_only_omitted_decisions=agg([x for x in sr if x['feedback']['partial_only_layer_ids']]))
            assert abs(sum((n(v['net']) for v in summary[name]['by_feedback'].values()), Z) - n(summary[name]['all']['net'])) < D('1e-18')

        controls = []
        oldcoverage = read(M / (ref + '_ORIGINAL_FIXED_TAIL_COVERAGE.json'))
        bylayer = {x['layer']: x for x in rows}
        for tail, coverage in zip(fixed[ref], oldcoverage):
            assert tail['budget_order'] == coverage['original']['budget_order'] and tail['layer'] == coverage['original']['layer']
            c = classify(tail)
            c['matched_actual_No60_layers'] = coverage['matched_No60_layers']
            c['matched_actual_No60_money'] = agg([bylayer[lid] for lid in c['matched_actual_No60_layers']])
            controls.append(c)
        assert len(controls) == (83 if ref == '2022_2024' else 94)
        tail_summary = dict(original_members=len(controls), original_by_feedback=groups(controls, 'feedback_label'),
            negative_original_members=[{k: x[k] for k in ['sid', 'name', 'layer', 'role', 'cost', 'net', 'decision_at', 'feedback', 'matched_actual_No60_layers', 'matched_actual_No60_money']} for x in controls if x['feedback_label'] == 'negative_completed_net'],
            actual_correspondence_members=sum(bool(x['matched_actual_No60_layers']) for x in controls),
            unmatched_members=sum(not x['matched_actual_No60_layers'] for x in controls))
        results[ref] = dict(scopes=summary, fixed_original_tail=tail_summary)
        save(ref + '_ROWS.json', rows)
        save(ref + '_FIXED_ORIGINAL_TAILS.json', controls)
        save(ref + '_COMPLETED_EVIDENCE.json', [x for seq in evidence.values() for x in seq])
        print(ref, json.dumps(results[ref], ensure_ascii=False, default=str), flush=True)
    save('RESULTS.json', results)
    save('SOURCE_MANIFEST.json', dict(sources=SOURCES, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        account_events=0, new_signal_events=0, quote_refresh=0,
        limitations=['endogenous baseline-funded feedback; policy changes future feedback and resource competition', 'completion-duration selection: short losers observed before long winners', 'omits partial-only realizations and dividend AR deliberately', 'attempt resets can forget previous-attempt losses', 'original fixed-tail unmatched observations retain baseline history only; no virtual trades', 'current surviving stock/industry snapshot historical development sample; daily execution proxy']))

if __name__ == '__main__':
    main()
