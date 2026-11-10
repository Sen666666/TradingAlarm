"""Prespecified entry/exit consistency experiment; reproduce every matched default control."""
import json
import pandas as pd
from build_stock_features import ROOT
from campaign_engine import run_campaign
from global_combined_transfer import load_all,reconcile
from portfolio_data import total_return_frame


def main():
    out=ROOT/'results/global-entry-consistency';out.mkdir(exist_ok=True)
    hypothesis=json.loads((out/'protocol.json').read_text())
    (out/'protocol.json').write_text(json.dumps(hypothesis,indent=2))
    results=[]
    blocks=[('full','2007-01-01','2025-12-31'),('2007','2007-01-01','2012-12-31'),('2013','2013-01-01','2018-12-31'),('2019','2019-01-01','2025-12-31')]
    for label,start,end in blocks:
        assets=load_all()
        for a in assets.values():
            a['raw']=a['raw'].loc[:end].copy();a['dividends']=[e for e in a['dividends'] if e['ex_date']<=end]
            a['signal']=total_return_frame(a['raw'],a['dividends'],[])
        for scenario,cost,delay in [('base',15,0),('cost2',30,0),('delay1',15,1)]:
            control_folder=ROOT/('results/global-combined-provisional' if label=='full' else 'results/global-combined-blocks')
            control_case=('' if label=='full' else label+'-')+'noadd-'+scenario
            kwargs=dict(start=start,pyramid=False,exit_mode='trend',ranking='low_atr',base_currency='USD',settlement_scenario=True,max_positions=6,cost_bps=cost,extra_delay=delay)
            cm,cp,co,cc,cs=run_campaign(assets,**kwargs)
            pd.testing.assert_frame_equal(cp,pd.read_parquet(control_folder/f'{control_case}-path.parquet'))
            assert co==json.loads((control_folder/f'{control_case}-orders.json').read_text())
            assert dict(closed=cc,open=cs)==json.loads((control_folder/f'{control_case}-campaigns.json').read_text())
            trace=[];metrics,path,orders,closed,state=run_campaign(assets,avoid_active_exit=True,decision_audit=trace,**kwargs)
            sizing=[r for r in trace if r['event']=='sizing'];buys=[r for r in sizing if r['units']>0]
            for r in buys:
                assert r['planned_risk_before']+r['planned_risk_added']<=r['planned_risk_limit']+1e-6
            check,ledger=reconcile(assets,path,orders,cost);case=label+'-'+scenario
            path.to_parquet(out/f'{case}-path.parquet')
            (out/f'{case}-orders.json').write_text(json.dumps(orders,indent=2))
            (out/f'{case}-campaigns.json').write_text(json.dumps(dict(closed=closed,open=state),indent=2))
            pnlrows=[]
            for symbol,s in [(s['symbol'],s) for s in closed]+list(state.items()):
                os=[o for o in orders if o['campaign_id']==s['id']];first=next(o for o in os if o['type']=='entry')
                value=sum(o['units'] for o in os)*float(assets[symbol]['raw'].close.iloc[-1])
                pnl=s['sell_cash']+s['dividend_claims']+value-s['buy_cash'];risk=4*s['entry_atr']*first['units']
                pnlrows.append(dict(symbol=symbol,id=s['id'],pnl=pnl,R=pnl/risk,status='closed' if 'exit_date' in s else 'open'))
            assert abs(sum(r['pnl'] for r in pnlrows)-metrics['total_return']*1e6)<1e-6
            (out/f'{case}-attribution.json').write_text(json.dumps(pnlrows,indent=2))
            result=dict(case=case,control_exact=True,control_return=cm['total_return'],control_mdd=cm['max_drawdown'],**metrics,
                ordinary_below3R_pnl=sum(r['pnl'] for r in pnlrows if r['R']<3),tail_pnl=sum(r['pnl'] for r in pnlrows if r['R']>=3),
                open_pnl=sum(r['pnl'] for r in pnlrows if r['status']=='open'),ledger=check,verified_buy_constraints=len(buys))
            results.append(result);(out/'results.json').write_text(json.dumps(results,indent=2))
            print({k:result[k] for k in ('case','control_return','total_return','max_drawdown','average_cash_weight','ordinary_below3R_pnl')},flush=True)

if __name__=='__main__':main()
