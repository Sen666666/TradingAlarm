"""Descriptive cash-blend and exact order-based excursion audit; no new strategy."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path('results/broad-shared-first-cross');OLD=Path('results/broad-shared-slots');OUT=Path('results/shared-entry-path-audit')

def match_cash_blend(old,target_exposure,capital=1e6):
    exposure=1-old.cash/(capital*old.nav)
    def mean(a):return float((a*old.nav*exposure/(1-a+a*old.nav)).mean())
    if not 0<=target_exposure<=mean(1)+1e-12:raise ValueError('Cannot match exposure with unlevered static cash blend')
    lo,hi=0.,1.
    for _ in range(60):
        mid=(lo+hi)/2
        if mean(mid)<target_exposure:lo=mid
        else:hi=mid
    a=(lo+hi)/2;nav=1-a+a*old.nav
    return a,nav,mean(a)

def episode_marks(orders,marks):
    start=pd.Timestamp(orders[0]['date']);end=pd.Timestamp(orders[-1]['date'])
    dates=marks.loc[start:end].index;units=pd.Series(0.,index=dates);flows=units.copy();buy=0.
    for o in orders:
        day=pd.Timestamp(o['date']);value=o['units']*o['raw_open'];units.loc[day]+=o['units'];flows.loc[day]-=value+o['fee']
        if o['units']>0:buy+=value+o['fee']
    quantity=units.cumsum();pnl=flows.cumsum()+quantity*marks.reindex(dates).ffill()
    assert quantity.iloc[-1]<1e-8 and quantity.min()>=-1e-8
    assert pnl.notna().all()
    return pnl,buy

def main():
    OUT.mkdir(exist_ok=True,parents=True);summary=json.loads((ROOT/'summary.json').read_text());blends=[]
    for r in summary:
        if r['case']=='control_rank':continue
        name=r['case']+'-'+r['scenario'];new=pd.read_parquet(ROOT/f'{name}-path.parquet');old=pd.read_parquet(OLD/f'{name}-path.parquet')
        target=float((1-new.cash/(new.nav*1e6)).mean());alpha,nav,matched=match_cash_blend(old,target)
        assert abs(matched-target)<1e-12
        blends.append(dict(case=name,old_funded_fraction=alpha,matched_mean_equity_weight=matched,cash_blend_return=float(nav.iloc[-1]-1),new_return=float(new.nav.iloc[-1]-1),cash_blend_mdd=float((nav/nav.cummax().clip(lower=1)-1).min()),new_mdd=float(new.drawdown.min())))
    (OUT/'cash-blend.json').write_text(json.dumps(blends,indent=2))
    data=Path('data/ths-refresh-20261018');manifest=json.loads((data/'validated-input-balanced-second500.json').read_text());frames={};hashes={}
    for r in manifest['records']:
        p=data/f"{r['ths_symbol']}-signal.parquet";h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==r['signal_sha256'];hashes[str(p)]=h
        frames[r['symbol']]=pd.read_parquet(p)
    scores=pd.read_parquet('results/broad-exit-disagreement/all-observed-signals.parquet');scores={s:g.set_index('date') for s,g in scores.groupby('symbol')}
    rows=[];errors=[];paths=[]
    for directory,label in [(OLD,'state'),(ROOT,'first_cross')]:
        case='group_gate_cap-base';episodes=pd.read_parquet(directory/'episodes.parquet');episodes=episodes[episodes.case.eq(case)];assert episodes.status.eq('closed').all()
        orders=json.loads((directory/f'{case}-orders.json').read_text());seen=set()
        for i,e in enumerate(episodes.itertuples()):
            chosen=[(j,o) for j,o in enumerate(orders) if o['symbol']==e.symbol and e.entry_date<=o['date']<=e.exit_date]
            assert not seen.intersection(j for j,_ in chosen);seen.update(j for j,_ in chosen)
            frame=frames[e.symbol];marks=frame.signal_close.ffill();pnl,buy=episode_marks([o for _,o in chosen],marks)
            error=abs(pnl.iloc[-1]-e.pnl);assert error<1e-6;assert abs(buy-e.buy_cash)<1e-6;errors.append(error)
            peak=max(0.,float(pnl.max()));peakdate=pnl.idxmax() if peak>0 else None;peak_return=peak/buy;realized=e.pnl/buy
            kind='retained_tail30' if realized>=.3 else 'gave_back_tail30' if peak_return>=.3 else 'profitable_then_loss' if peak>0 and e.pnl<0 else 'never_positive_loss' if e.pnl<0 else 'ordinary_win'
            row=dict(model=label,symbol=e.symbol,entry=e.entry_date,exit=e.exit_date,kind=kind,pnl=e.pnl,purchase_cash=buy,return_net=realized,peak_close_pnl=peak,peak_close_return=peak_return,peak_date=str(peakdate.date()) if peakdate is not None else None,close_giveback=peak-e.pnl,days_peak_to_exit=int((pnl.index>peakdate).sum()) if peakdate is not None else None)
            rows.append(row)
            daily=pd.DataFrame({'date':pnl.index,'pnl':pnl.values,'return_on_total_purchase_cash':pnl.values/buy});daily['symbol']=e.symbol;daily['entry']=e.entry_date;daily['model']=label
            daily['strength']=scores[e.symbol].strength.reindex(pnl.index,method='ffill').values;paths.append(daily)
        assert len(seen)==len(orders)
    frame=pd.DataFrame(rows);frame.to_parquet(OUT/'episodes.parquet',index=False);pd.concat(paths,ignore_index=True).to_parquet(OUT/'episode-daily-paths.parquet',index=False)
    aggregates=[]
    for (model,kind),g in frame.groupby(['model','kind']):
        aggregates.append(dict(model=model,kind=kind,count=len(g),account_contribution=float(g.pnl.sum()/1e6),mean_peak_return=float(g.peak_close_return.mean()),mean_realized_return=float(g.return_net.mean()),median_peak_to_exit=float(g.days_peak_to_exit.median()) if g.days_peak_to_exit.notna().any() else None))
    (OUT/'categories.json').write_text(json.dumps(aggregates,indent=2))
    (OUT/'validation.json').write_text(json.dumps(dict(episodes=len(rows),input_hashes=hashes,max_episode_pnl_error=max(errors),limitations=['Cash-blend alpha fitted to full-sample average equity weight: retrospective attribution only, not a deployable allocation. It blends recorded old NAV with idle cash, not a new smaller-account execution with recalculated minimum fees.','Matching average exposure does not match daily timing, assets, volatility or tail risk.','Excursions use observed daily closes with actual executed cashflows and fees, not intraday highs or achievable peak exits.','Peak uses total eventual purchase cash as denominator; descriptive hindsight partition, never an entry/exit feature.','Two selected A485 development portfolios, not independent evidence of transferability.','Only closed episodes in these two capped base portfolios; verified all orders assigned exactly once.']),indent=2))
    print(pd.DataFrame(blends).to_string(index=False));print(pd.DataFrame(aggregates).to_string(index=False))
if __name__=='__main__':main()
