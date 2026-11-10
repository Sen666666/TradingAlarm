"""Reconcile all-six portfolio P&L to individual campaigns and sparse tails."""
import json
import pandas as pd
from build_stock_features import ROOT
from global_combined_transfer import load_all


def main():
    folder=ROOT/'results/global-combined-provisional';results=json.loads((folder/'results.json').read_text())
    assets=load_all();summaries=[];allrows=[]
    for result in results:
        case=result['case'];cs=json.loads((folder/f'{case}-campaigns.json').read_text());orders=json.loads((folder/f'{case}-orders.json').read_text());rows=[]
        states=[(s['symbol'],s) for s in cs['closed']]+list(cs['open'].items())
        for symbol,state in states:
            os=[o for o in orders if o['campaign_id']==state['id']];buys=[o for o in os if o['units']>0]
            units=sum(o['units'] for o in os);market=units*float(assets[symbol]['raw'].close.iloc[-1])
            pnl=state['sell_cash']+state['dividend_claims']+market-state['buy_cash']
            risk=state.get('committed_risk',buys[0]['units']*4*state['entry_atr'])
            rows.append(dict(case=case,symbol=symbol,id=state['id'],entry_date=state['entry_date'],exit_date=state.get('exit_date'),
                status='closed' if 'exit_date' in state else 'open',pnl=pnl,initial_committed_risk=risk,R=pnl/risk))
        assert abs(sum(r['pnl'] for r in rows)-result['total_return']*1e6)<1e-6
        summaries.append(dict(case=case,closed_pnl=sum(r['pnl'] for r in rows if r['status']=='closed'),
            open_pnl=sum(r['pnl'] for r in rows if r['status']=='open'),ordinary_below3R=sum(r['pnl'] for r in rows if r['R']<3),
            tail_atleast3R=sum(r['pnl'] for r in rows if r['R']>=3),tail_count=sum(r['R']>=3 for r in rows),
            largest_campaign_pnl=max(r['pnl'] for r in rows),asset_pnl={s:sum(r['pnl'] for r in rows if r['symbol']==s) for s in assets}))
        allrows+=rows
    (folder/'attribution.json').write_text(json.dumps(summaries,indent=2));pd.DataFrame(allrows).to_parquet(folder/'attribution.parquet',index=False)
    print(json.dumps([s for s in summaries if s['case'].endswith('-base')],indent=2))

if __name__=='__main__':main()
