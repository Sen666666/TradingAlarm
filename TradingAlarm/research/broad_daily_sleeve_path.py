"""Daily marks of existing isolated fractional adjusted-price sleeves; not raw-share account."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
SOURCES=[('strength-calibrated-order-transfer485','pairwise_volume'),('strength-calibrated-order-transfer485','calibrated_pair_order_volume'),('strength-uniform-transfer485','uniform_pairwise_volume'),('strength-peer-gate-transfer485','peer_raw_volume'),('strength-peer-gate-transfer485','peer_relative_volume')]

def sleeve_path(calendar,marks,episodes,cost=.0015,fraction=.9):
    prices=marks.reindex(calendar).ffill().to_numpy();nav=np.ones(len(calendar));cash_path=np.ones(len(calendar));wealth=1.;last_end=-1
    for ep in sorted(episodes,key=lambda e:e['entry_date']):
        start=calendar.get_loc(pd.Timestamp(ep['entry_date']));closed=ep['status']=='closed'
        end=calendar.get_loc(pd.Timestamp(ep['exit_date'])) if closed else len(calendar)
        assert start>=last_end and end>start
        assert np.isfinite(prices[start:end]).all()
        cash=wealth*(1-fraction);units=wealth*fraction/(ep['entry_price']*(1+cost))
        nav[start:end]=cash+units*prices[start:end];cash_path[start:end]=cash
        if closed:
            wealth=cash+units*ep['exit_price']*(1-cost);nav[end:]=wealth;cash_path[end:]=wealth
        else:
            assert np.isclose(prices[-1],ep['exit_price'],rtol=1e-12)
            wealth=nav[-1]
        last_end=end
    return nav,cash_path

def main():
    out=ROOT/'results/broad-daily-sleeve-path';out.mkdir(exist_ok=True)
    manifest=json.loads((ROOT/'data/ths-refresh-20261018/validated-input-balanced-second500.json').read_text());frames={};dates=set()
    for rec in manifest['records']:
        p=ROOT/'data/ths-refresh-20261018'/f"{rec['ths_symbol']}-signal.parquet";assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['signal_sha256'];f=pd.read_parquet(p);frames[rec['symbol']]=f;dates.update(f.index[f.observed_bar])
    calendar=pd.DatetimeIndex(sorted(d for d in dates if pd.Timestamp('2024-01-01')<=d<=pd.Timestamp('2026-10-16')))
    reports=[];checks=[]
    for directory,model in SOURCES:
        root=ROOT/'results'/directory;all_ep=pd.read_parquet(root/'episodes.parquet');saved=json.loads((root/'sleeve-report.json').read_text())['rows']
        for delay,cost in [(0,15),(0,30),(1,15)]:
            table=all_ep.loc[all_ep.strategy.eq(model)&all_ep.delay.eq(delay)&all_ep.cutoff.eq('2026-10-16')];assert not table.status.eq('terminal_unknown').any()
            paths=[];cash=[]
            for symbol,f in frames.items():
                ep=table.loc[table.symbol.eq(symbol)].to_dict('records');marks=f.signal_close.where(f.bar_allows_trade).ffill()
                a,b=sleeve_path(calendar,marks,ep,cost/10000);paths.append(a);cash.append(b)
            path=pd.DataFrame(dict(nav=np.mean(paths,axis=0),cash=np.mean(cash,axis=0)),index=calendar)
            scenario='base' if delay==0 else 'delay1';case=f'{model}-{scenario}-{cost}';path.to_parquet(out/f'{case}.parquet')
            for cutoff in ['2024-12-31','2025-12-31','2026-10-16']:
                expected=next(x for x in saved if x['strategy']==model and x['allocation']=='equal_capital' and x['cutoff']==cutoff and x['scenario']==scenario and x['cost']==cost and x['terminal']=='last_mark')['equal_initial_sleeve_return']
                error=abs(path.loc[cutoff,'nav']-1-expected);assert error<1e-10,(case,cutoff,error);checks.append(dict(case=case,cutoff=cutoff,error=error))
            nav=path.nav;peak=nav.cummax().clip(lower=1);running_min=nav.cummin().clip(upper=1)
            reports.append(dict(case=case,total_return=float(nav.iloc[-1]-1),max_drawdown=float((nav/peak-1).min()),maximum_hindsight_trough_to_later_peak=float((nav/running_min-1).max()),year2026=float(nav.iloc[-1]/nav.loc['2025-12-31']-1),mean_cash_weight=float((path.cash/nav).mean())))
    (out/'summary.json').write_text(json.dumps(reports,indent=2));(out/'validation.json').write_text(json.dumps(dict(input_hashes=485,endpoint_checks=checks,limits=['Daily fractionaladjustedpricesleeves use90%owncashperentry, no redistributionbetweenstocks.','Matchesprior syntheticexecutionepisodes, not lot/tax/liquidity/corporateactioncashsettlement validation.','Marks use availableactive signalclose, carrypriorprice onmissingbars; no modeledintradaydrawdown.','Maxtrough-to-laterpeak selected hindsight is descriptive upperbound onpath gains, not predeclaredmarketcycleperformance.','No claim oftradablewholeaccount20%riskcontrol orfuture80%cycle; inspectedselected485stocks2024-2026.']),indent=2));print(pd.DataFrame(reports).to_string(index=False))
if __name__=='__main__':main()
