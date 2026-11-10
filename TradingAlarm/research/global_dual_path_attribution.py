"""Explain portfolio-path changes without treating matched trades as independent."""
import json
import numpy as np
import pandas as pd
from build_stock_features import ROOT
from global_combined_transfer import load_all
from campaign_engine import features


def campaigns(folder,case,end,assets):
    data=json.loads((folder/f'{case}-campaigns.json').read_text())
    orders=json.loads((folder/f'{case}-orders.json').read_text());rows=[]
    for symbol,s in [(s['symbol'],s) for s in data['closed']]+list(data['open'].items()):
        os=[o for o in orders if o['campaign_id']==s['id']];buys=[o for o in os if o['units']>0]
        assert len(buys)==1 and buys[0]['type']=='entry'
        q=buys[0]['units'];exit=s.get('exit_date',end);raw=assets[symbol]['raw'];f=assets[symbol]['features']
        entry=pd.Timestamp(s['entry_date']);signal=pd.Timestamp(buys[0]['signal_date'])
        last=pd.Timestamp(exit);mark=float(raw.loc[:end,'close'].iloc[-1])
        pnl=s['sell_cash']+s['dividend_claims']+sum(o['units'] for o in os)*mark-s['buy_cash']
        held=f.loc[(f.index>=entry)&(f.index<last if 'exit_date' in s else f.index<=last)]
        risk=4*s['entry_atr'];prior=f.loc[:signal].iloc[-1]
        volume=raw.loc[:signal,'volume'];vr=float(volume.iloc[-1]/volume.iloc[-21:-1].mean())
        rows.append(dict(symbol=symbol,entry=s['entry_date'],exit=exit,status='closed' if 'exit_date' in s else 'open',
            quantity=q,pnl=pnl,unit_pnl=pnl/q,R=pnl/(q*risk),holding_closes=len(held),
            max_close_R=float((held.close-s['last_add']).max()/risk) if len(held) else None,
            above_MA200=bool(prior.close>prior.ma),entry_exit_already_active=bool(prior.trend_exit),volume_vs_previous20=vr,
            momentum126=float(prior.strength)))
    return rows


def match_key(r):return (r['symbol'],r['status'],r['exit'])


def compare(base,new):
    b={match_key(r):r for r in base};n={match_key(r):r for r in new}
    assert len(b)==len(base) and len(n)==len(new)
    shared=set(b)&set(n);quantity_effect=unit_effect=0.;shifted=0
    for key in shared:
        x,y=b[key],n[key]
        quantity_effect+=(y['quantity']-x['quantity'])*(y['unit_pnl']+x['unit_pnl'])/2
        unit_effect+=(y['unit_pnl']-x['unit_pnl'])*(y['quantity']+x['quantity'])/2
        shifted+=x['entry']!=y['entry']
    onlynew=[n[k] for k in n.keys()-b.keys()];onlybase=[b[k] for k in b.keys()-n.keys()]
    extra=sum(r['pnl'] for r in onlynew);removed=sum(r['pnl'] for r in onlybase)
    delta=sum(r['pnl'] for r in new)-sum(r['pnl'] for r in base)
    assert abs(delta-(quantity_effect+unit_effect+extra-removed))<1e-6
    def stats(rows):
        closed=[r for r in rows if r['status']=='closed'];loss=[r for r in closed if r['pnl']<0]
        return dict(count=len(rows),pnl=sum(r['pnl'] for r in rows),closed_win_rate=float(np.mean([r['pnl']>0 for r in closed])) if closed else None,
            ordinary_below3R=sum(r['pnl'] for r in rows if r['R']<3),tail_atleast3R=sum(r['pnl'] for r in rows if r['R']>=3),
            losing_closed=len(loss),losing_never_reached1R_close=sum(r['max_close_R'] is None or r['max_close_R']<1 for r in loss),
            median_loser_holding_closes=float(np.median([r['holding_closes'] for r in loss])) if loss else None,
            entries_above_MA200=sum(r['above_MA200'] for r in rows),
            entries_exit_already_active=sum(r['entry_exit_already_active'] for r in rows),
            exit_active_entry_pnl=sum(r['pnl'] for r in rows if r['entry_exit_already_active']),
            entries_volume_above_previous20=sum(r['volume_vs_previous20']>1 for r in rows))
    return dict(total_delta=delta,matched_episodes=len(shared),matched_entry_shifted=shifted,
        matched_quantity_effect=quantity_effect,matched_per_unit_effect=unit_effect,
        new_only=stats(onlynew),base_only=stats(onlybase)),onlynew,onlybase


def main():
    out=ROOT/'results/global-dual-risk';assets=load_all()
    for a in assets.values():a['features']=features(a)
    results=json.loads((out/'results.json').read_text());reports=[];details=[]
    for result in results:
        label,scenario=result['case'].split('-',1)
        source=ROOT/('results/global-combined-provisional' if label=='full' else 'results/global-combined-blocks')
        basecase=('' if label=='full' else label+'-')+'noadd-'+scenario
        end={'full':'2025-12-31','2007':'2012-12-31','2013':'2018-12-31','2019':'2025-12-31'}[label]
        base=campaigns(source,basecase,end,assets);new=campaigns(out,result['case'],end,assets)
        report,onlynew,onlybase=compare(base,new);report['case']=result['case']
        assert abs(report['total_delta']-(result['total_return']-result['control_return'])*1e6)<1e-6
        reports.append(report)
        for group,rows in [('dual_only',onlynew),('base_only',onlybase)]:details.extend(dict(case=result['case'],group=group,**r) for r in rows)
    (out/'path-attribution.json').write_text(json.dumps(dict(reports=reports,
        limitation='Match by symbol and same exit/terminal date; shifted entries retained. Quantity/per-unit decomposition is algebraic, not causal. Unmatched episodes are not pure extra-trade counterfactuals. MFE/holding duration are hindsight diagnostics, never permitted entry filters.'),indent=2))
    pd.DataFrame(details).to_parquet(out/'unmatched-campaigns.parquet',index=False)
    print(json.dumps([r for r in reports if r['case'].startswith('full')],indent=2))

if __name__=='__main__':main()
