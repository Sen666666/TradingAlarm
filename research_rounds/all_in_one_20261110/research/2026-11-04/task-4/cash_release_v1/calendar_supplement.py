"""Complete original market-OPEN denominator and preserve F1 input unknowns.
Read-only original books; no financial or strategy simulation.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
import bisect, gzip, hashlib, json, statistics, time
import pandas as pd

O = Path(__file__).resolve().parent
T = O.parent.parent / 'task'
F = Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101')
ROOTS = {
    'long': T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair',
    'strong': T/'pvr_pool_feasibility/runs/2025_26/pair',
}
SOURCES = {}

def source(p):
    p = Path(p)
    SOURCES[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p

def read(p):
    return json.loads(source(p).read_text())

def gz(p, lines=False):
    with gzip.open(source(p), 'rt') as h:
        return list(map(json.loads, h)) if lines else json.load(h)

def table(p):
    a = pd.read_parquet(source(p), columns=['permit_next_open', 'unknown', 'effective_status'])
    return {str(k)[:10]: {'permit': bool(v.permit_next_open), 'unknown': list(v.unknown),
                         'effective_status': v.effective_status} for k, v in a.iterrows()}

def stats(a):
    return dict(n=len(a), minimum=min(a) if a else None, median=statistics.median(a) if a else None,
                mean=statistics.mean(a) if a else None, maximum=max(a) if a else None)

def write(n, x):
    (O/n).write_text(json.dumps(x, ensure_ascii=False, indent=2, default=str)+'\n')

def main():
    start=time.monotonic(); source(__file__)
    glob=table(F/'historical-shadow/run-v1/NATIVE1709_global_daily.parquet')
    nodes={n['sector']: n for n in read(F/'industry-coverage/run-v1/NODE_CATALOGUE.json') if n['domain']=='NATIVE1709'}
    industries={k:table(n['daily_result_path']) for k,n in nodes.items()}
    old={(r['window'],r['OPEN']):r for r in read(O/'ORIGINAL_DAILY_LIQUIDITY_STOCKS.json')}
    rows=[]
    for w,root in ROOTS.items():
        b=gz(root/'B.json.gz'); dd=gz(root/'daily.jsonl.gz',True)
        daily={r['at'][:10]:r for r in dd}; dates=sorted(daily)
        decisions={r['at'][:10]:r for r in b['decisions']}; dc=sorted(decisions)
        buys=defaultdict(lambda:D(0)); sells=defaultdict(lambda:D(0)); buyfee=defaultdict(lambda:D(0)); sellfee=defaultdict(lambda:D(0))
        for t in b['trades']:
            d=t['at'][:10]
            if t['side']=='buy': buys[d]+=D(t['gross_cny'])+D(t['fees_cny']); buyfee[d]+=D(t['fees_cny'])
            else: sells[d]+=D(t['gross_cny'])-D(t['fees_cny']); sellfee[d]+=D(t['fees_cny'])
        fs=gz(root/'funding.jsonl.gz',True)
        attempts=Counter(r['at'][:10] for r in fs if '09:30:00' in r['at'])
        for d in dates:
            j=bisect.bisect_left(dc,d)-1
            if j<0:
                assert d==dates[0] and not attempts[d] and buys[d]==0 and sells[d]==0
                continue
            sd=dc[j]; dec=decisions[sd]; nav=D(dec['nav']); a=D(daily[d]['available'])+buys[d]; reserve=nav*D('.1')
            f=glob.get(sd); unk=f is None or bool(f['unknown'])
            row=dict(window=w,OPEN=d,signal_day=sd,year=d[:4],quarter=f'{d[:4]}Q{(int(d[5:7])-1)//3+1}',
                     has_original_OPEN_attempts=bool(attempts[d]),original_OPEN_role_events=attempts[d],
                     ACT_on=bool(dec['on']),F1_global_permit=f['permit'] if f else None,
                     F1_global_input_unknown=unk,F1_global_unknown_reasons=f['unknown'] if f else ['missing_date'],
                     F1_global_status=f['effective_status'] if f else None,
                     S0_available=a,decision_NAV=nav,original_extra10_buffer=reserve,
                     maximum_discussable_release_cash=min(a,reserve),
                     maximum_discussable_release_pct_decisionNAV=float(min(a,reserve)/nav*100),
                     S0_cash_pct_decisionNAV=float(a/nav*100),
                     original_final_cash=daily[d]['available'],original_final_cash_pct_same_CLOSE_NAV=float(D(daily[d]['available'])/D(daily[d]['nav'])*100),
                     actual_protection_sale_net=sells[d],actual_original_buy_cash=buys[d],
                     original_buy_fees=buyfee[d],original_sell_fees=sellfee[d],
                     original_previous_CLOSE_inventory=daily[sd]['inventory'],
                     prior_existing_submitted_order_reserve=0,known_extra_unreserved_liability_U=0)
            if (w,d) in old:
                for k in ['S0_available','decision_NAV','original_extra10_buffer','maximum_discussable_release_cash']:
                    assert D(str(row[k]))==D(str(old[w,d][k])),(w,d,k)
            rows.append(row)
    assert Counter(r['window'] for r in rows)=={'long':725,'strong':241}
    write('ALL_MARKET_OPEN_LIQUIDITY_STOCKS.json',rows)
    summary=[]
    for w,y in sorted({(r['window'],r['year']) for r in rows}):
        a=[r for r in rows if (r['window'],r['year'])==(w,y)]
        summary.append(dict(window=w,year=y,market_OPEN_days=len(a),with_original_attempts=sum(r['has_original_OPEN_attempts'] for r in a),
                            ACT_on_days=sum(r['ACT_on'] for r in a),F1_global_unknown_days=sum(r['F1_global_input_unknown'] for r in a),
                            S0_cash_pct=stats([r['S0_cash_pct_decisionNAV'] for r in a]),
                            maximum_discussable_release_pct=stats([r['maximum_discussable_release_pct_decisionNAV'] for r in a]),
                            original_cash_below_extra10_days=sum(r['S0_available']<r['original_extra10_buffer'] for r in a),
                            original_final_cash_pct=stats([r['original_final_cash_pct_same_CLOSE_NAV'] for r in a]),
                            original_buy_fees=stats([float(r['original_buy_fees']) for r in a]),
                            original_sell_fees=stats([float(r['original_sell_fees']) for r in a])))
    write('ALL_MARKET_OPEN_LIQUIDITY_SUMMARY.json',summary)
    buckets=defaultdict(Counter); stocksets=defaultdict(set)
    with gzip.open(source(O/'ALL_ORIGINAL_CASH_REJECTS.jsonl.gz'),'rt') as h:
        for line in h:
            r=json.loads(line); g=glob.get(r['signal_day']); i=industries[r['sector']].get(r['signal_day'])
            gu=g is None or bool(g['unknown']); iu=i is None or bool(i['unknown']); u=gu or iu
            assert r['F1_global_permit']==(g['permit'] if g else None)
            assert r['F1_industry_permit']==(i['permit'] if i else None)
            for role in [r['role'],'all']:
                k=(r['window'],r['OPEN'][:4],role)
                buckets[k]['role_events']+=1
                buckets[k]['mature_release_criterion']+=int(r['original_permission_eligible'])
                buckets[k]['F1_global_input_unknown']+=gu; buckets[k]['F1_industry_input_unknown']+=iu
                buckets[k]['F1_any_input_unknown']+=u
                buckets[k]['F1_known_both_permit']+=not u and r['F1_joint_permit'] is True
                buckets[k]['F1_known_joint_cold']+=not u and r['F1_joint_permit'] is False
                buckets[k]['mature_and_F1_unknown']+=r['original_permission_eligible'] and u
                stocksets[k].add((r['OPEN'],r['sid']))
    write('F1_UNKNOWN_PRESERVATION_STRATA.json',[dict(window=k[0],year=k[1],role=k[2],unique_stock_OPENs=len(stocksets[k]),**v) for k,v in sorted(buckets.items())])
    write('SUPPLEMENT_SCOPE.json',dict(
        full_OPEN_denominator=966,excluded_initial_CLOSE_snapshots=2,
        original_permission_eligible_field_alias='mature_release_criterion_ACT_on_AND_original_CP1_industry_confirmed_or_expanded',
        other_original_CP1_stages='Not declared illegal: retain original purchasing and cash10 rules when release criterion false',
        F1='Stratification only; preserve bool permit and unknown flags separately; false with input unknown is not classified known cold',
        liquidity='Original independent daily cash stocks, not additive capital or released-policy losses, returns, drawdown, or liquidity success',
        known_U='Zero only under these audited original books; after release decisions all actual reservations and dated fees must still be funded',
        market_calendar='All original daily market snapshots with prior completed CLOSE decision; includes ACT paused and no attempted order dates',
        initial_snapshots='Initial seed CLOSE has no previous decision/OPEN plan, excluded rather than inventing exposure'))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in SOURCES.items())
    write('SUPPLEMENT_SOURCE_SHA256.json',SOURCES)
    write('SUPPLEMENT_COMPLETION.json',dict(seconds=time.monotonic()-start,new_accounts=0,new_restores=0,new_pricing_labels=0))
    print(json.dumps(summary,ensure_ascii=False,default=str));print('completed full calendar and F1 unknown strata')

if __name__=='__main__':main()
