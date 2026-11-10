"""Independent stdlib audit of saved completed-loss feedback classifications."""
from pathlib import Path
from decimal import Decimal, getcontext
from collections import defaultdict
from datetime import datetime
import json, gzip, hashlib
import pandas as pd

getcontext().prec = 70
D = Decimal
Z = D(0)
O = Path(__file__).resolve().parent
P = O.parent / 'online_feedback'
B = Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
M = B / 'risk_constraints/ma63_information_diagnostic_v1'
checks = defaultdict(int)

def read(p):
    p = Path(p)
    if p.suffix == '.gz':
        with gzip.open(p, 'rt') as f:
            return json.load(f)
    return json.loads(p.read_text())

def n(x):
    return D(str(x))

def dt(x):
    return datetime.fromisoformat(x)

def eq(a, b, name):
    assert abs(n(a) - n(b)) < D('1e-18'), (name, a, b)
    checks[name] += 1

def agg(rows):
    out = dict(layers=len(rows), stocks=len({x['sid'] for x in rows}))
    for k in ['cost', 'net', 'strict_realized', 'open_unrealized', 'recognized_dividend_AR', 'buy_fee', 'sell_fee']:
        out[k] = None if any(k not in x for x in rows) else sum((n(x[k]) for x in rows), Z)
    out.update(positive_net=sum((n(x['net']) for x in rows if n(x['net'])>0),Z),
               negative_net=sum((n(x['net']) for x in rows if n(x['net'])<0),Z),
               negative_layers=sum(n(x['net'])<0 for x in rows),open_layers=sum(bool(x['qty']) for x in rows))
    return out

def verify_agg(rows, result):
    expected = agg(rows)
    assert set(expected)==set(result)
    for k,v in expected.items():
        if v is None:
            assert result[k] is None
            checks['aggregate_NA'] += 1
        else:
            eq(v,result[k],'aggregate_'+k)

manifest = read(P/'SOURCE_MANIFEST.json')
for p,h in manifest['sources'].items():
    assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
    checks['source_sha256'] += 1
assert hashlib.sha256((P/'analyze.py').read_bytes()).hexdigest()==manifest['script_sha256']
checks['script_sha256'] += 1
result=read(P/'RESULTS.json')
fixed=read(M/'ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json')['members']
industry=read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')
industry={x['series']:x for x in industry}
industry_identity={}
def industry_probe(sector,decision):
    if sector not in industry_identity:
        f=pd.read_parquet(industry[sector]['refs']['state'],columns=['day','attempt_id','action'])
        probes={};timeline={}
        for r in f.itertuples(index=False):
            day=str(r.day)[:10]
            if pd.isna(r.attempt_id):timeline[day]=None;continue
            if r.action=='probe' and r.attempt_id not in probes:probes[r.attempt_id]=day
            timeline[day]=probes.get(r.attempt_id)
        industry_identity[sector]=timeline
    return industry_identity[sector].get(decision[:10])
summary={}
for ref,root in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024'),('strong',B/'pvr_pool_feasibility/runs/2025_26')]:
    original=read(M/(ref+'_ENTRIES.json'))
    entries={x['layer']:x for x in original}
    rows=read(P/(ref+'_ROWS.json'))
    book=read(root/'pair/B.json.gz')
    buys=defaultdict(list);sales=defaultdict(list)
    for t in book['trades']:
        if t['side']=='buy':buys[t['layer']].append(t)
        else:
            for p in t['parts']:sales[p['layer']].append((dt(t['at']),p))
    completed=[]
    for lid,e in entries.items():
        assert len(buys[lid])==1
        b=buys[lid][0]
        eq(e['cost'],n(b['gross_cny'])+n(b['fees_cny']),'actual_buy_cash')
        if e['role']!='mobile' or e['qty']:
            continue
        assert sales[lid] and max(t for t,p in sales[lid])==dt(e['closed'])
        cash=sum((n(p['net_cash']) for t,p in sales[lid]),Z)-n(b['gross_cny'])-n(b['fees_cny'])
        eq(cash,e['strict_realized'],'completed_cash_vs_realized')
        completed.append(dict(layer=lid,sid=e['sid'],sector=e['sector'],probe_day=e['probe_progress']['probe_day'],closed=dt(e['closed']),cash=cash))
    out_evidence=read(P/(ref+'_COMPLETED_EVIDENCE.json'))
    assert len(out_evidence)==len(completed)
    cem={x['layer']:x for x in completed}
    for c in out_evidence:
        expected=cem[c['layer']]
        assert (c['sid'],c['sector'],c['probe_day'],dt(c['closed']))==(expected['sid'],expected['sector'],expected['probe_day'],expected['closed'])
        eq(c['trading_cash'],expected['cash'],'evidence_cash')

    def verify_feedback(row,probe_day):
        clock=dt(row['decision_at']);f=row['feedback']
        assert industry_probe(row['sector'],row['decision_at'])==probe_day
        checks['original_industry_attempt_identity']+=1
        seq=sorted([c for c in completed if c['sector']==row['sector'] and c['probe_day']==probe_day and c['closed']<clock],key=lambda c:(c['closed'],c['layer']))
        cash=sum((c['cash'] for c in seq),Z)
        expected='no_completed_mobile' if not seq else 'negative_completed_net' if cash<0 else 'nonnegative_completed_net'
        assert expected==f['label']==row['feedback_label']
        assert [c['layer'] for c in seq]==f['prior_completed_layers']
        assert sorted({c['sid'] for c in seq})==f['prior_completed_stocks']
        assert [c['layer'] for c in seq if c['sid']!=row['sid']]==f['other_stock_completed_layers']
        eq(cash,f['completed_trading_cash'],'past_feedback_cash')
        old=[c for c in completed if c['sector']==row['sector'] and c['probe_day']!=probe_day and c['closed']<clock]
        assert len(old)==f['omitted_old_attempt_completed_layers']
        eq(sum((c['cash'] for c in old),Z),f['omitted_old_attempt_completed_trading_cash'],'old_attempt_cash')
        if seq:
            assert dt(f['latest_evidence_at'])==max(c['closed'] for c in seq)<clock
            eq((clock-max(c['closed'] for c in seq)).total_seconds()/86400,f['lag_calendar_days_since_latest'],'lag')
        else:assert f['latest_evidence_at'] is None
        partial=[]
        for e in original:
            if e['role']!='mobile' or e['sector']!=row['sector'] or e['probe_progress']['probe_day']!=probe_day or dt(e['opened'])>=clock:continue
            pastparts=[p for t,p in sales[e['layer']] if t<clock]
            if pastparts and (e['closed'] is None or dt(e['closed'])>=clock):partial.append(e['layer'])
        assert partial==f['partial_only_layer_ids']
        checks['partial_only_layer_ids']+=1
        checks['causal_row_classification']+=1
    for row in rows:
        e=entries[row['layer']]
        assert all(row[k]==v for k,v in e.items())
        verify_feedback(row,e['probe_progress']['probe_day'])
    scopes={'ALL':rows}
    if ref=='2022_2024':
        scopes['2022_2023']=[x for x in rows if x['opened'][:10]<='2023-12-29']
        scopes['strict303_postOct8_newfills']=[x for x in rows if '2024-10-08'<x['opened'][:10]<='2024-12-31']
    for name,sr in scopes.items():
        z=result[ref]['scopes'][name]
        verify_agg(sr,z['all'])
        for label,g in z['by_feedback'].items():verify_agg([x for x in sr if x['feedback_label']==label],g)
        for field,key in [('action','by_action'),('role','by_role')]:
            for value,groups in z[key].items():
                for label,g in groups.items():verify_agg([x for x in sr if x[field]==value and x['feedback_label']==label],g)
        verify_agg([x for x in sr if x['feedback_label']=='negative_completed_net' and x['feedback']['other_stock_completed_layers']],z['negative_with_other_stock_evidence'])
        verify_agg([x for x in sr if x['feedback_label']=='no_completed_mobile' and n(x['feedback']['omitted_old_attempt_completed_trading_cash'])<0],z['no_completed_but_old_attempt_losses'])
        verify_agg([x for x in sr if x['feedback']['partial_only_layer_ids']],z['partial_only_omitted_decisions'])
    controls=read(P/(ref+'_FIXED_ORIGINAL_TAILS.json'))
    oldcoverage=read(M/(ref+'_ORIGINAL_FIXED_TAIL_COVERAGE.json'))
    rb={x['layer']:x for x in rows}
    for c,originaltail,coverage in zip(controls,fixed[ref],oldcoverage):
        assert all(c[k]==v for k,v in originaltail.items())
        assert c['matched_actual_No60_layers']==coverage['matched_No60_layers']
        verify_feedback(c,c['feedback']['probe_day'])
        verify_agg([rb[lid] for lid in c['matched_actual_No60_layers']],c['matched_actual_No60_money'])
        checks['fixed_tail_identity']+=1
    for label,g in result[ref]['fixed_original_tail']['original_by_feedback'].items():verify_agg([x for x in controls if x['feedback_label']==label],g)
    negative=[x for x in rows if x['feedback_label']=='negative_completed_net']
    matches=[rb[lid] for c in controls if c['feedback_label']=='negative_completed_net' for lid in c['matched_actual_No60_layers']]
    lags=sorted(x['feedback']['lag_calendar_days_since_latest'] for x in negative)
    winner_counterexamples=sorted([x for x in negative if n(x['net'])>0],key=lambda x:n(x['net']),reverse=True)[:6]
    summary[ref]=dict(negative_feedback=agg(negative),negative_exact_matched_fixed_tail=agg(matches),
        negative_fixed_tail_members=sum(x['feedback_label']=='negative_completed_net' for x in controls),
        negative_exact_matched_fixed_tail_members=sum(x['feedback_label']=='negative_completed_net' and bool(x['matched_actual_No60_layers']) for x in controls),
        negative_feedback_lag_median_calendar_days=lags[len(lags)//2],
        one_or_two_completed_layers=sum(len(x['feedback']['prior_completed_layers'])<=2 for x in negative),
        winner_counterexamples=[{k:x[k] for k in ['sid','name','layer','role','action','decision_at','cost','net','qty','feedback']} for x in winner_counterexamples])

out=dict(status='PASS_WITH_SCOPE_LIMITS',checks=dict(checks),summary=summary,
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    scope='Independent original trade cash, completed-layer timing, original industry state attempt/probe identity, partial-only IDs, grouping money and full frozen-tail/cross-arm identity checks.',
    decision='Stop simple completed-net-loss industry admission gate before financial engineering. Coverage misses most adverse net loss and negative group includes substantial strong-window tail contribution.',
    limitations=['No policy counterfactual: fewer trades change endogenous feedback and capital competition.',
        'Completed-only evidence is duration-selected: failed short attempts can close before current winners; positive active marks deliberately absent.',
        'Industry-attempt reset can hide earlier negative trading cash; old losses are not recovered or forgotten in account equity.',
        'Partial-only realized cash, dividend AR and open marks intentionally excluded, so this is not total economic PnL feedback.',
        'Post hoc tail labels are audit controls only; unmatched fixed tails have baseline history but no hypothetical No60 fill.',
        'No new account, signal, policy sizing, market data refresh or live action.'])
(O/'AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps(dict(status=out['status'],checks=checks,negative_tail_match={k:v['negative_exact_matched_fixed_tail'] for k,v in summary.items()}),ensure_ascii=False,default=str,indent=2))
