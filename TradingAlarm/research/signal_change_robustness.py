"""Leave-each-sleeve-in-cash tests with all six exclusions reported."""
import json
import pandas as pd
from build_stock_features import ROOT
from global_combined_transfer import load_all,reconcile
from multihorizon_engine import run


def main():
    out=ROOT/'results/signal-change-robustness';assert (out/'protocol.json').exists()
    periods=json.loads((ROOT/'results/global-multihorizon/protocol.json').read_text())['periods']
    original=load_all();rows=[]
    for excluded in sorted(original):
        assets={s:dict(a) for s,a in original.items()}
        assets[excluded]['signal']=assets[excluded]['signal'].copy()
        assets[excluded]['signal']['close']=1.
        for i,(start,end) in enumerate(periods):
            scenarios=[('base',15,0),('cost2',30,0),('delay1',15,1)] if i==0 else [('base',15,0)]
            for scenario,cost,delay in scenarios:
                for policy in ('monthly','score_change'):
                    case=f'{excluded}-{i}-{scenario}-{policy}'
                    metrics,path,orders,closed,state,decisions=run(assets,start,end,'single252',cost,delay,rebalance=policy)
                    assert not any(o['symbol']==excluded for o in orders)
                    assert path['w_'+excluded].eq(0).all()
                    check,ledger=reconcile(assets,path,orders,cost)
                    final=ledger[-1]
                    pnl=sum(c['pnl'] for c in closed)+sum(c['sell_cash']+c['dividend_claims']+final['value_'+s]-c['buy_cash'] for s,c in state.items())
                    assert abs(pnl-metrics['total_return']*1e6)<1e-6
                    r=dict(case=case,excluded=excluded,period=i,scenario=scenario,policy=policy,**metrics,ledger=check)
                    rows.append(r)
                    path.to_parquet(out/f'{case}-path.parquet')
                    (out/f'{case}-orders.json').write_text(json.dumps(orders))
                a,b=rows[-2:];print(dict(excluded=excluded,period=i,scenario=scenario,monthly=a['total_return'],drift=b['total_return'],difference=b['total_return']-a['total_return']),flush=True)
                (out/'results.json').write_text(json.dumps(rows,indent=2))

if __name__=='__main__':main()
