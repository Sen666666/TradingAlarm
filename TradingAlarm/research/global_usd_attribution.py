"""Account-dollar attribution for no-add USD ledger diagnostics."""
import json
import pandas as pd
from build_stock_features import ROOT


def main():
    folder=ROOT/'results/global-usd-ledger';results=json.loads((folder/'results.json').read_text());summary=[];all_rows=[]
    for result in results:
        symbol=result['symbol'];campaigns=json.loads((folder/f'{symbol}-campaigns.json').read_text())
        orders=json.loads((folder/f'{symbol}-orders.json').read_text());ledger=pd.read_parquet(folder/f'{symbol}-ledger.parquet')
        rows=[]
        for state in campaigns['closed']+list(campaigns['open'].values()):
            first=next(o for o in orders if o['campaign_id']==state['id'] and o['type']=='entry')
            assert not any(o['type'] in ('add','complete') for o in orders)
            risk=first['units']*4*state['entry_atr']
            closed='exit_date' in state
            market=0. if closed else float(ledger.iloc[-1].market_value)
            pnl=state['sell_cash']+state['dividend_claims']+market-state['buy_cash']
            rows.append(dict(symbol=symbol,id=state['id'],entry_date=state['entry_date'],exit_date=state.get('exit_date'),
                status='closed' if closed else 'open',pnl=pnl,initial_risk=risk,R=pnl/risk))
        assert abs(sum(r['pnl'] for r in rows)-result['metrics']['total_return']*1e6)<1e-6
        summary.append(dict(symbol=symbol,account_total_return=result['metrics']['total_return'],
            closed_pnl=sum(r['pnl'] for r in rows if r['status']=='closed'),open_pnl=sum(r['pnl'] for r in rows if r['status']=='open'),
            ordinary_below3R_pnl=sum(r['pnl'] for r in rows if r['R']<3),tail_atleast3R_pnl=sum(r['pnl'] for r in rows if r['R']>=3),
            largest_campaign_pnl=max(r['pnl'] for r in rows),average_cash_weight=result['metrics']['average_cash_weight']))
        all_rows+=rows
    out=dict(summary=summary,interpretation='Dollar contributions under fixed small initial risk, no additions and single-asset accounts. Receivables count as equity but not spendable cash. This is not combined portfolio performance. High idle cash is measured, not a license to scale risk without re-testing portfolio drawdown, gaps and correlated losses.')
    (folder/'attribution.json').write_text(json.dumps(out,indent=2));pd.DataFrame(all_rows).to_parquet(folder/'attribution.parquet',index=False)
    print(json.dumps(out,indent=2))


if __name__=='__main__':main()
