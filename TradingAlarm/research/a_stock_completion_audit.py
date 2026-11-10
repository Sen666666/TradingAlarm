"""Verify fixed campaign budget and compare all completion controls."""
import json
import pandas as pd
from a_stock_shadow_audit import audit
from build_stock_features import ROOT


def main():
    out=ROOT/'results/a-stock-campaign-shadow-completion'
    audit(out)
    rows=[]
    for r in json.loads((out/'results.json').read_text()):
        case=r['case'];orders=json.loads((out/f'{case}-orders.json').read_text())
        state={};adds=0;campaigns_with_adds=set()
        for order in orders:
            if order['side']!='buy':continue
            key=(order['symbol'],order['campaign_entry_date'])
            if order['kind']=='initial':
                assert key not in state
                state[key]=dict(stop=order['stop'],budget=order['risk_budget'],used=0.,last_price=order['price'])
            else:
                assert key in state and order['date']>key[1]
                assert order['price']>=state[key]['last_price']
                adds+=1;campaigns_with_adds.add(key)
            s=state[key]
            assert order['stop']==s['stop'] and order['risk_budget']==s['budget']
            s['used']+=order['quantity']*(order['price']-s['stop'])
            s['last_price']=order['price']
            assert s['used']<=s['budget']+1e-6
            assert abs(s['used']-order['committed_risk'])<1e-6
        row=dict(case=case,completion_orders=adds,campaigns_completed_in_parts=len(campaigns_with_adds))
        for variant,directory in [('partial','a-stock-campaign-shadow'),('full','a-stock-campaign-shadow-fullrisk'),('completion','a-stock-campaign-shadow-completion')]:
            folder=ROOT/'results'/directory
            metrics=next(x for x in json.loads((folder/'results.json').read_text()) if x['case']==case)
            campaigns=json.loads((folder/f'{case}-campaigns.json').read_text())
            closed=pd.DataFrame(campaigns['closed']);closed['R']=closed.pnl/closed.initial_risk
            ordinary=closed[closed.R.lt(3)]
            row[variant]=dict(total_return=metrics['total_shadow_return'],drawdown=metrics['max_shadow_drawdown'],
                best252=metrics['best252_shadow_return'],closed=len(closed),
                closed_win_rate=float(closed.pnl.gt(0).mean()),ordinary_closed_below3R_pnl=float(ordinary.pnl.sum()),
                closed_at_least3R_pnl=float(closed.loc[closed.R.ge(3),'pnl'].sum()),
                open_mark_pnl=sum(x['pnl'] for x in campaigns['open']))
        rows.append(row)
    result=dict(interpretation='All18cases are reused syntheticprice shadow accounts,not executable portfolio proof.3R tail threshold is descriptive accounting applied uniformly,not a trading parameter or search. R uses total committed fill-to-stop risk;openmarkedPnL kept separate. Fixedbudgetchecks do notguarantee stopfills.',cases=rows)
    (out/'comparison.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
