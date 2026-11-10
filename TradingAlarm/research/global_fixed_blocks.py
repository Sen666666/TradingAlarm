"""Previously specified fixed calendar blocks; no best-start selection."""
import json
import pandas as pd
from build_stock_features import ROOT
from campaign_engine import run_campaign
from global_combined_transfer import load_all,reconcile
from portfolio_data import total_return_frame


def main():
    out=ROOT/'results/global-combined-blocks';out.mkdir(exist_ok=True)
    blocks=[('2007-01-01','2012-12-31'),('2013-01-01','2018-12-31'),('2019-01-01','2025-12-31')]
    (out/'protocol.json').write_text(json.dumps(dict(blocks=blocks,selection='Blocks fixed before global price download; restart with1m cash, keep prior warmupprices, no inherited holdings.',
        cases='Noadd/completion each with15bpsbase,30bpscost2,one-sessiondelay. Same frozen rule/caps/sectors as whole-history experiment.',
        limitation='Same historical sample, not independent holdout; VNQ provisional payment dates, grossbeforetax. Completion remains unadopted.'),indent=2))
    rows=[]
    for start,end in blocks:
        assets=load_all()
        for a in assets.values():
            a['raw']=a['raw'].loc[:end].copy();a['dividends']=[e for e in a['dividends'] if e['ex_date']<=end]
            a['signal']=total_return_frame(a['raw'],a['dividends'],[])
        for completion in (False,True):
            for scenario,cost,delay in [('base',15,0),('cost2',30,0),('delay1',15,1)]:
                case=start[:4]+'-'+('completion' if completion else 'noadd')+'-'+scenario
                metrics,path,orders,closed,state=run_campaign(assets,start=start,pyramid=False,exit_mode='trend',ranking='low_atr',
                    base_currency='USD',settlement_scenario=True,max_positions=6,cost_bps=cost,extra_delay=delay,complete_initial=completion)
                check,ledger=reconcile(assets,path,orders,cost)
                path.to_parquet(out/f'{case}-path.parquet')
                (out/f'{case}-orders.json').write_text(json.dumps(orders,indent=2))
                (out/f'{case}-campaigns.json').write_text(json.dumps(dict(closed=closed,open=state),indent=2))
                r=dict(case=case,start=start,end=end,**metrics,completion_orders=sum(o['type']=='complete' for o in orders),ledger=check);rows.append(r)
                (out/'results.json').write_text(json.dumps(rows,indent=2));print({k:r[k] for k in ('case','total_return','max_drawdown','average_cash_weight','completion_orders')},flush=True)

if __name__=='__main__':main()
