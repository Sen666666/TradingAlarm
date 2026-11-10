"""Frozen winner-drift counterfactual with exact old controls and cash replay."""
import json
import math
import pandas as pd
from build_stock_features import ROOT
from global_combined_transfer import load_all,reconcile
from multihorizon_engine import run


def main():
    old=ROOT/'results/global-multihorizon';out=ROOT/'results/global-signal-change'
    assert (out/'protocol.json').exists()
    protocol=json.loads((old/'protocol.json').read_text());assets=load_all();results=[]
    baseline={r['case']:r for r in json.loads((old/'results.json').read_text())}
    for i,(start,end) in enumerate(protocol['periods']):
        label='full' if i==0 else start[:4]
        for mode in ('single252','ensemble'):
            for scenario,cost,delay in [('base',15,0),('cost2',30,0),('delay1',15,1)]:
                case=f'{label}-{mode}-{scenario}'
                control=run(assets,start,end,mode,cost,delay)
                pd.testing.assert_frame_equal(control[1],pd.read_parquet(old/f'{case}-path.parquet'),check_exact=True)
                assert control[2]==json.loads((old/f'{case}-orders.json').read_text())
                metrics,path,orders,closed,state,decisions=run(assets,start,end,mode,cost,delay,rebalance='score_change')
                check,ledger=reconcile(assets,path,orders,cost)
                final=pd.DataFrame(ledger).iloc[-1]
                openpnl=sum(c['sell_cash']+c['dividend_claims']+final['value_'+s]-c['buy_cash'] for s,c in state.items())
                cp=sorted(c['pnl'] for c in closed);n=max(1,math.ceil(len(cp)*.1)) if cp else 0
                assert abs(sum(cp)+openpnl-metrics['total_return']*1e6)<1e-6
                # Independently enforce no orders for unchanged monthly scores.
                ds={d['date']:j for j,d in enumerate(decisions)}
                for order in orders:
                    eligible=[d for d in decisions if order['signal_date']<d['date']<=order['date']]
                    assert len(eligible)==1
                    d=eligible[0];j=ds[d['date']];s=order['symbol']
                    assert j==0 or d['scores'][s]!=decisions[j-1]['scores'][s]
                result=dict(case=case,**metrics,closed_pnl=sum(cp),open_pnl=openpnl,
                    ordinary_closed_bottom90=sum(cp[:-n]) if n else 0,
                    tail_closed_top10=sum(cp[-n:]) if n else 0,
                    closed_win_rate=sum(v>0 for v in cp)/len(cp) if cp else None,
                    max_single_weight=float(path.filter(like='w_').max().max()),
                    max_gross_weight=float(path.filter(like='w_').sum(axis=1).max()),
                    return_difference=metrics['total_return']-baseline[case]['total_return'],
                    drawdown_difference=metrics['max_drawdown']-baseline[case]['max_drawdown'],ledger=check)
                path.to_parquet(out/f'{case}-path.parquet')
                for name,data in [('orders',orders),('campaigns',dict(closed=closed,open=state)),('decisions',decisions)]:
                    (out/f'{case}-{name}.json').write_text(json.dumps(data,indent=2))
                results.append(result);(out/'results.json').write_text(json.dumps(results,indent=2))
                print({k:result[k] for k in ('case','total_return','max_drawdown','return_difference','ordinary_closed_bottom90','max_single_weight')},flush=True)

if __name__=='__main__':main()
