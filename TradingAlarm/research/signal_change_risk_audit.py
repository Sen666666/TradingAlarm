"""Independent daily asset PNL, portfolio covariance and drawdown attribution."""
import json
from collections import defaultdict
import numpy as np
import pandas as pd
from build_stock_features import ROOT
from global_combined_transfer import load_all


def daily_pnl(assets,path,orders):
    events=defaultdict(list);fills=defaultdict(list);qty={s:0. for s in assets};rows=[]
    for s,a in assets.items():
        for e in a['dividends']:events[pd.Timestamp(e['ex_date'])].append((s,e['amount']))
    for o in orders:fills[pd.Timestamp(o['date'])].append(o)
    prior_nav=1e6
    for day,row in path.iterrows():
        pnl={s:qty[s]*(float(a['raw'].loc[day,'close'])-float(a['raw'].loc[a['raw'].index<day,'close'].iloc[-1])) for s,a in assets.items()}
        for s,amount in events[day]:pnl[s]+=qty[s]*amount
        for o in fills[day]:
            s=o['symbol'];pnl[s]+=o['units']*(float(assets[s]['raw'].loc[day,'close'])-o['raw_open'])-o['fee'];qty[s]+=o['units']
        assert abs(sum(pnl.values())-(row.nav*1e6-prior_nav))<1e-6
        rows.append(dict(date=day,**pnl));prior_nav=row.nav*1e6
    return pd.DataFrame(rows).set_index('date')


def summarize(path,pnl):
    wealth=path.nav*1e6;prior=wealth.shift(fill_value=1e6)
    returns=pnl.div(prior,axis=0);portfolio=returns.sum(axis=1)
    contribution={s:float(returns[s].cov(portfolio)/portfolio.var()) for s in pnl}
    assert abs(sum(contribution.values())-1)<1e-10
    running_peak=wealth.cummax().clip(lower=1e6);dd=wealth/running_peak-1;trough=dd.idxmin()
    before=wealth.loc[:trough];peak=before.idxmax() if before.max()>1e6 else None
    loss=pnl.loc[(pnl.index>peak) & (pnl.index<=trough)].sum() if peak is not None else pnl.loc[:trough].sum()
    peaknav=float(wealth.loc[peak]) if peak is not None else 1e6
    assert abs(loss.sum()-(wealth.loc[trough]-peaknav))<1e-6
    return dict(max_drawdown=float(dd.min()),peak=str(peak.date()) if peak is not None else 'initial_cash',trough=str(trough.date()),
        drawdown_dollars=loss.to_dict(),drawdown_fraction_of_peak=(loss/peaknav).to_dict(),
        variance_contribution=contribution,profit=pnl.sum().to_dict(),
        max_single_weight=float(path.filter(like='w_').max().max()))


def main():
    assets=load_all();out=ROOT/'results/signal-change-robustness';report={};stored={}
    for policy,folder in [('monthly','global-multihorizon'),('score_change','global-signal-change')]:
        p=ROOT/'results'/folder;case='full-single252-base'
        path=pd.read_parquet(p/f'{case}-path.parquet');orders=json.loads((p/f'{case}-orders.json').read_text())
        pnl=daily_pnl(assets,path,orders);pnl.to_parquet(out/f'{policy}-daily-pnl.parquet');report[policy]=summarize(path,pnl)
        stored[policy]=(path,pnl)
    # Same baseline peak/trough window for both, avoiding a comparison of
    # asset losses computed over different maximum-drawdown intervals.
    peak=pd.Timestamp(report['monthly']['peak']);trough=pd.Timestamp(report['monthly']['trough'])
    for policy,(path,pnl) in stored.items():
        losses=pnl.loc[(pnl.index>peak)&(pnl.index<=trough)].sum()
        nav=float(path.loc[peak,'nav'])*1e6
        assert abs(losses.sum()-(path.loc[trough,'nav']*1e6-nav))<1e-6
        report[policy]['shared_baseline_drawdown_window']=dict(peak=str(peak.date()),trough=str(trough.date()),return_fraction=float(losses.sum()/nav),asset_fraction_of_start=(losses/nav).to_dict())
    (out/'risk-attribution.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
