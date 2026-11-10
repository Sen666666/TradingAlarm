"""Exact asset-level PNL accounting, not causal identification."""
import json
from collections import defaultdict
from build_stock_features import ROOT
from global_combined_transfer import load_all


def pnl_by_asset(folder,case,assets):
    c=json.loads((folder/f'{case}-campaigns.json').read_text())
    orders=json.loads((folder/f'{case}-orders.json').read_text())
    pnl=defaultdict(float);qty=defaultdict(float)
    for o in orders:qty[o['symbol']]+=o['units']
    for row in c['closed']:pnl[row['symbol']]+=row['pnl']
    for s,row in c['open'].items():
        price=float(assets[s]['raw'].loc['2025-12-31','close'])
        pnl[s]+=row['sell_cash']+row['dividend_claims']+qty[s]*price-row['buy_cash']
    return dict(pnl)


def main():
    old=ROOT/'results/global-multihorizon';new=ROOT/'results/global-signal-change';assets=load_all()
    baseline={r['case']:r for r in json.loads((old/'results.json').read_text())}
    results=json.loads((new/'results.json').read_text());rows=[]
    for r in results:
        if not r['case'].startswith('full-'):continue
        case=r['case'];a=pnl_by_asset(old,case,assets);b=pnl_by_asset(new,case,assets)
        diff={s:b.get(s,0)-a.get(s,0) for s in assets}
        assert abs(sum(a.values())-baseline[case]['total_return']*1e6)<1e-6
        assert abs(sum(b.values())-r['total_return']*1e6)<1e-6
        assert abs(sum(diff.values())-r['return_difference']*1e6)<1e-6
        rows.append(dict(case=case,baseline=a,candidate=b,difference=diff))
    (new/'asset-attribution.json').write_text(json.dumps(rows,indent=2))
    for r in rows:
        if r['case'].endswith('-base'):print(r)
    decision=dict(adopted=False,status='All 24 frozen cases complete; limited long-horizon improvement, goal unmet',
        improved_by_mode={m:sum(r['return_difference']>0 for r in results if m in r['case']) for m in ('single252','ensemble')},
        evidence='24 exact baseline path/order reproductions;24 independent cash ledgers and campaign PNL reconciliations;all candidate fills verified against changed monthly scores;7 tests passed;6 full-period asset PNL reconciliations.',
        conclusion='Single252 gains are accompanied by greater concentration and losses outside the largest closed winners. Ensemble improvement is mixed and small. Neither is adopted as the requested portable strategy. Full-history cumulative return is not single-cycle performance.',
        next='Inspect asset concentration of long-horizon gains and quantify risk contribution before proposing more exposure. Stop iterating monthly ensemble rebalancing; no new score weights or nearby horizon sweep. Any A/HK transfer requires existing raw inventory/FX/action accounting.',
        limitations='Reused selected-survivor ETF sample;provisional VNQ payment dates;no investor tax or idle interest;no new broad A/HK or futures validation. Closed bottom90 is hindsight diagnostic, not an entry filter.')
    (new/'decision.json').write_text(json.dumps(decision,indent=2))
    p=ROOT/'progress.json';data=json.loads(p.read_text());data['multihorizon_trend_comparator']['signal_change_rebalance']={'results':'results/global-signal-change/results.json','decision':'results/global-signal-change/decision.json','status':decision['status']};p.write_text(json.dumps(data,indent=2))

if __name__=='__main__':main()
