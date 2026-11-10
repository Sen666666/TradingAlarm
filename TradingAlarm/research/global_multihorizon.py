"""Execute frozen monthly trend comparator and independently replay cash."""
import json
import pandas as pd
from build_stock_features import ROOT
from global_combined_transfer import load_all,reconcile
from multihorizon_engine import run


def main():
    out=ROOT/'results/global-multihorizon';protocol=json.loads((out/'protocol.json').read_text());assets=load_all();results=[]
    for i,(start,end) in enumerate(protocol['periods']):
        label='full' if i==0 else start[:4]
        for mode in ('single252','ensemble'):
            for scenario,cost,delay in [('base',15,0),('cost2',30,0),('delay1',15,1)]:
                metrics,path,orders,closed,state,decisions=run(assets,start,end,mode,cost,delay)
                check,ledger=reconcile(assets,path,orders,cost);case=f'{label}-{mode}-{scenario}'
                final=pd.DataFrame(ledger).iloc[-1]
                pnlrows=[dict(symbol=c['symbol'],status='closed',pnl=c['pnl']) for c in closed]
                pnlrows += [dict(symbol=s,status='open',pnl=c['sell_cash']+c['dividend_claims']+final['value_'+s]-c['buy_cash']) for s,c in state.items()]
                assert abs(sum(r['pnl'] for r in pnlrows)-metrics['total_return']*1e6)<1e-6
                closed_pnl=sorted(c['pnl'] for c in closed);n_tail=max(1,__import__('math').ceil(len(closed_pnl)*.1)) if closed_pnl else 0
                result=dict(case=case,**metrics,closed_pnl=sum(closed_pnl),open_pnl=sum(r['pnl'] for r in pnlrows if r['status']=='open'),
                    ordinary_closed_bottom90=sum(closed_pnl[:-n_tail]) if n_tail else 0.,tail_closed_top10=sum(closed_pnl[-n_tail:]) if n_tail else 0.,
                    closed_win_rate=sum(v>0 for v in closed_pnl)/len(closed_pnl) if closed_pnl else None,ledger=check)
                path.to_parquet(out/f'{case}-path.parquet')
                for name,data in [('orders',orders),('campaigns',dict(closed=closed,open=state)),('decisions',decisions)]:
                    (out/f'{case}-{name}.json').write_text(json.dumps(data,indent=2))
                results.append(result);(out/'results.json').write_text(json.dumps(results,indent=2))
                print({k:result[k] for k in ('case','total_return','max_drawdown','ordinary_closed_bottom90','average_cash_weight')},flush=True)

if __name__=='__main__':main()
