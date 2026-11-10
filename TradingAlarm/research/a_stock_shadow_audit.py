"""Independent cash reconciliation and tail attribution of shadow accounts."""
import json
import math
from collections import defaultdict
import pandas as pd
from build_stock_features import ROOT


def audit(directory):
    summaries=[]
    for result in json.loads((directory/'results.json').read_text()):
        case=result['case'];orders=json.loads((directory/f'{case}-orders.json').read_text())
        campaigns=json.loads((directory/f'{case}-campaigns.json').read_text())
        path=pd.read_csv(directory/f'{case}-path.csv').set_index('date')
        changes=defaultdict(float);fees=0.;quantities=defaultdict(float);small=0
        for order in orders:
            amount=order['quantity']*order['price'];fees+=order['fee']
            side=1 if order['side']=='buy' else -1
            changes[order['date']]-=side*amount+order['fee']
            quantities[order['symbol']]+=side*order['quantity']
            assert quantities[order['symbol']]>=-1e-7
            if side==1 and amount<1000:small+=1
        cash=1_000_000.;error=0.
        for date,row in path.iterrows():
            cash+=changes[date];error=max(error,abs(cash-row.cash))
        assert error<1e-6
        assert abs(fees-result['fees'])<1e-6
        assert {s for s,q in quantities.items() if q>1e-7}=={r['symbol'] for r in campaigns['open']}
        end=1_000_000.*path.nav.iloc[-1]
        assert abs(cash+sum(r['mark_value'] for r in campaigns['open'])-end)<1e-6
        closed=pd.DataFrame(campaigns['closed']);opened=pd.DataFrame(campaigns['open'])
        pnl=sum(r['pnl'] for r in campaigns['closed']+campaigns['open'])
        assert abs(pnl-(end-1_000_000.))<1e-6
        top=closed.nlargest(max(1,math.ceil(len(closed)*.1)),'pnl')
        summaries.append(dict(case=case,total_return=result['total_shadow_return'],drawdown=result['max_shadow_drawdown'],
            closed_pnl=float(closed.pnl.sum()),open_mark_pnl=float(opened.pnl.sum()) if len(opened) else 0.,
            closed_top10_pnl=float(top.pnl.sum()),closed_other90_pnl=float(closed.drop(top.index).pnl.sum()),
            largest_closed=closed.nlargest(3,'pnl').to_dict('records'),small_buy_tickets_under1000=small,
            maximum_cash_reconciliation_error=error,terminal_wealth_reconciliation_error=abs(pnl-(end-1_000_000.))))
    (directory/'audit.json').write_text(json.dumps(summaries,indent=2))
    return summaries


def main():
    partial=audit(ROOT/'results/a-stock-campaign-shadow')
    full=audit(ROOT/'results/a-stock-campaign-shadow-fullrisk')
    compared=[]
    for a,b in zip(partial,full):
        assert a['case']==b['case']
        compared.append(dict(case=a['case'],partial_return=a['total_return'],fullrisk_return=b['total_return'],
            partial_drawdown=a['drawdown'],fullrisk_drawdown=b['drawdown'],
            partial_small_tickets=a['small_buy_tickets_under1000'],fullrisk_small_tickets=b['small_buy_tickets_under1000'],
            partial_ordinary_closed=a['closed_other90_pnl'],fullrisk_ordinary_closed=b['closed_other90_pnl']))
    out=ROOT/'results/a-stock-campaign-shadow';(out/'sizing-comparison.json').write_text(json.dumps(compared,indent=2))
    print(json.dumps(compared,indent=2))


if __name__=='__main__':main()
