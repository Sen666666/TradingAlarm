"""Synthetic adjusted-price episode admission experiment, not a broker account backtest."""
import json,hashlib
from pathlib import Path
import pandas as pd
import numpy as np
from adaptive_geometric_strength import adaptive_frame
from geometric_strength import strength_exposure
from sector_factors import expanded_assets
from ths_volume_units import ths_split_consistent_volume
from volume_units import split_consistent_volume
OUT=Path('results/sector-episode-allocation')

def allocate(episodes,marks,mapping,gates,variant,cost):
    cash=1.;held={};rows=[];trades=[];prior_nav=1.;cost/=10000
    entries={d:g for d,g in episodes.groupby('entry_date')}
    for day,prices in marks.iterrows():
        ds=str(day.date())
        for s in list(held):
            h=held[s]
            if h['exit_date']==ds:
                value=h['units']*h['exit_price']*(1-cost);cash+=value
                trades.append(dict(symbol=s,entry=h['entry_date'],exit=ds,pnl=value-h['budget'],return_fraction=value/h['budget']-1,status='closed'));del held[s]
        candidates=[]
        for e in entries.get(ds,pd.DataFrame()).to_dict('records'):
            s=e['symbol'];sd=pd.Timestamp(e['signal_date']);group=mapping.get((sd,s))
            # Same mapping coverage restriction for all arms.
            if group is None or pd.isna(group) or s in held:continue
            if variant!='stock_only' and not gates.get((sd,group),False):continue
            candidates.append((e,group))
        for e,group in sorted(candidates,key=lambda x:(-x[0]['strength'],x[0]['symbol'])):
            if len(held)>=9:break
            if variant=='gate_group_cap' and sum(h['group']==group for h in held.values())>=3:continue
            budget=min(.1*prior_nav,max(0.,cash-.1*prior_nav))
            if budget<.099*prior_nav:continue
            cash-=budget;held[e['symbol']]=dict(e,group=group,budget=budget,units=budget/(e['entry_price']*(1+cost)))
        value=sum(h['units']*float(prices[s]) for s,h in held.items());nav=cash+value
        assert cash>=-1e-12 and np.isfinite(nav)
        rows.append(dict(date=day,nav=nav,cash=cash,positions=len(held),exposure=value/nav));prior_nav=nav
    for s,h in held.items():
        value=h['units']*float(marks.iloc[-1][s]);trades.append(dict(symbol=s,entry=h['entry_date'],exit=str(marks.index[-1].date()),pnl=value-h['budget'],return_fraction=value/h['budget']-1,status='open_marked'))
    path=pd.DataFrame(rows).set_index('date');t=pd.DataFrame(trades,columns=['symbol','entry','exit','pnl','return_fraction','status'])
    assert abs(t.pnl.sum()-(path.nav.iloc[-1]-1))<1e-10
    return path,t

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=dict(model='adaptive_geometry_price_volume_split_units',start='2024-01-01',end='2026-10-16',variants=['stock_only','gate','gate_group_cap'],mapping=['proxy','relative_proxy'],costs=[15,30],allocation='9 maximum positions; each admission10%previous close NAV including cost; retain10%cash; no rebalancing winners; cap3entry-group positions in group-cap arm',selection='Existing standalone executable entry episodes ranked by signal-date stock strength; no future return used; rejected episode not reconsidered',gate='Same adaptive volume-corrected ETF strength hysteresis at original signal date; entry-only gate, original individual stock exits unchanged',limitations=['Adjusted-price fractional pooled episode experiment, not raw-share account','No lot sizes, minimum fees, market impact or portfolio pending-order competition','Admission groups frozen per holding; three positions is not a hard mark-to-market sector cap','Existing485survivor sample; observed development period; correlation groups not historical industry membership','No claim of feasible account80%gain or20%drawdown target achieved'])
    p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==protocol
    p.write_text(json.dumps(protocol,indent=2))
    root=Path('data/ths-refresh-20261018');manifest=json.loads((root/'validated-input-balanced-second500.json').read_text());marks={};strengths={}
    ep=pd.read_parquet('results/strength-range-transfer485/episodes.parquet');ep=ep.loc[ep.strategy.eq(protocol['model'])&ep.delay.eq(0)&ep.cutoff.eq(protocol['end'])].copy()
    for i,r in enumerate(manifest['records']):
        p=root/f"{r['ths_symbol']}-signal.parquet";q=root/'rights'/f"{r['ths_symbol']}.json"
        assert hashlib.sha256(p.read_bytes()).hexdigest()==r['signal_sha256'];assert hashlib.sha256(q.read_bytes()).hexdigest()==r['rights_sha256']
        f=pd.read_parquet(p);v=ths_split_consistent_volume(f.volume,json.loads(q.read_text()));obs=f.loc[f.observed_bar&f.volume.gt(0)]
        strength=adaptive_frame(obs.signal_close,obs.close,v.reindex(obs.index)).strength
        strengths[r['symbol']]=strength;marks[r['symbol']]=obs.signal_close
        if (i+1)%100==0:print('signals',i+1,flush=True)
    ep['strength']=[float(strengths[e.symbol].loc[:e.signal_date].iloc[-1]) for e in ep.itertuples()];assert np.isfinite(ep.strength).all()
    marks=pd.DataFrame(marks).sort_index().ffill().loc[protocol['start']:protocol['end']]
    assets={s:a for s,a in expanded_assets().items() if a['kind']=='equity' and a['currency']=='CNY' and a['sector']!='broad_cn'};gates={}
    for s,a in assets.items():
        v=split_consistent_volume(a['raw'].volume,a['splits']);score=adaptive_frame(a['signal'].close,a['raw'].close,v).strength
        gate=strength_exposure(score);gates.update({(d,s):bool(b) for d,b in gate.items()})
    ep.to_parquet(OUT/'candidate-input.parquet',index=False);marks.to_parquet(OUT/'marks-input.parquet')
    pd.DataFrame([dict(date=d,proxy=s,gate=b) for (d,s),b in gates.items()]).to_parquet(OUT/'gates-input.parquet',index=False)
    source=pd.read_parquet('results/sector-stock-daily-mapping/assignments.parquet');results=[]
    for column in protocol['mapping']:
        mapping={(r.date,r.symbol):getattr(r,column) for r in source.itertuples()}
        for variant in protocol['variants']:
            for cost in protocol['costs']:
                path,trades=allocate(ep,marks,mapping,gates,variant,cost);name=f'{column}-{variant}-{cost}'
                path.to_parquet(OUT/f'{name}-path.parquet');trades.to_parquet(OUT/f'{name}-trades.parquet')
                closed=trades.loc[trades.status.eq('closed')];wins=closed.loc[closed.pnl.gt(0),'pnl'];losses=closed.loc[closed.pnl.lt(0),'pnl']
                before=path.loc[:'2025-12-31'].nav.iloc[-1]
                results.append(dict(case=name,total_return=float(path.nav.iloc[-1]-1),synthetic_drawdown=float((path.nav/path.nav.cummax()-1).min()),return2026=float(path.nav.iloc[-1]/before-1),mean_exposure=float(path.exposure.mean()),closed_trades=len(closed),win_rate=float(closed.pnl.gt(0).mean()),payoff=float(wins.mean()/abs(losses.mean())),ordinary_pnl=float(trades.loc[trades.return_fraction.lt(.3),'pnl'].sum()),tail30_pnl=float(trades.loc[trades.return_fraction.ge(.3),'pnl'].sum())))
    (OUT/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
    (OUT/'validation.json').write_text(json.dumps(dict(verified_stock_and_rights_hashes=970,synthetic_cash_pnl_reconciliations=len(results),account_backtest=False),indent=2))
if __name__=='__main__':main()
