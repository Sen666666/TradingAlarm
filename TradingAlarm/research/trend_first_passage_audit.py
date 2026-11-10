"""Fixed future path diagnostic, not achievable PNL or a trading exit rule."""
import json
from pathlib import Path
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from strategy_signals import build_signals

OUT=Path('results/trend-first-passage-audit')
MODELS=['adaptive_geometry_price_volume_split_units','multiscale_price_volume','markov_volume_map','calibrated_local_price']


def first_passage(bars, entry, upper=1.3, lower=.9):
    for j,row in enumerate(bars.itertuples()):
        if row.open>=entry*upper:return 'up_first',j
        if row.open<=entry*lower:return 'down_first',j
        up=row.high>=entry*upper;down=row.low<=entry*lower
        if up and down:return 'ambiguous',j
        if up:return 'up_first',j
        if down:return 'down_first',j
    return 'neither',len(bars)


def main():
    OUT.mkdir(exist_ok=True,parents=True)
    (OUT/'protocol.json').write_text(json.dumps(dict(status='Frozen before outcomes',models=MODELS,entry='next observed adjusted open after dated signal',horizon=63,upper=.30,lower=-.10,selection='Registered long exposure at signal close; all eligible dates, not entry transitions only',same_bar='Open crossing resolves first; otherwise both high/low crossing is ambiguous, never counted as success',maturity='Complete63 observed bars, last bar same year as signal and <=2026-10-16',interpretation='Potential price path ordering, not fills, stops, achievable profit, or portfolio return',limits='Overlapping and correlated dates, selected survivors, reviewed development; no significance or unseen validation claims'),indent=2))
    etf,_=load_extended();hk,_=load_assets();rows=[]
    for group,assets in [('etf17',etf),('hk7',hk)]:
        signals={m:build_signals(assets,m) for m in MODELS}
        for symbol,a in assets.items():
            raw=a['raw'];valid=raw.index[raw.volume.gt(0)].intersection(a['signal'].index);f=a['signal'].reindex(valid).dropna(subset=['open','high','low','close'])
            for i in range(len(f)-63):
                d=f.index[i];end=f.index[i+63]
                if d.year<2022 or end.year!=d.year or end>pd.Timestamp('2026-10-16'):continue
                label,lag=first_passage(f.iloc[i+1:i+64],f.open.iloc[i+1])
                rows.append(dict(group=group,symbol=symbol,date=str(d.date()),year=d.year,label=label,bars_to_event=lag+1,**{m:float(signals[m][symbol].loc[d]) for m in MODELS}))
    f=pd.DataFrame(rows);f.to_parquet(OUT/'labels-and-exposure.parquet',index=False)
    results=[]
    for (group,year),g in f.groupby(['group','year']):
        base=g.label.eq('up_first').mean()
        for m in MODELS:
            chosen=g.loc[g[m].gt(0)];wins=g.label.eq('up_first');selected_wins=chosen.label.eq('up_first').sum()
            # Baseline matching the symbol composition of the selected dates.
            rates=g.groupby('symbol').label.apply(lambda x:x.eq('up_first').mean())
            matched=float(chosen.symbol.map(rates).mean()) if len(chosen) else None
            results.append(dict(group=group,year=int(year),model=m,all_dates=len(g),selected_dates=len(chosen),all_up_first=int(wins.sum()),selected_up_first=int(selected_wins),selected_down_first=int(chosen.label.eq('down_first').sum()),selected_ambiguous=int(chosen.label.eq('ambiguous').sum()),selected_neither=int(chosen.label.eq('neither').sum()),base_up_rate=float(base),selected_up_rate=float(selected_wins/len(chosen)) if len(chosen) else None,matched_symbol_year_up_rate=matched,opportunity_coverage=float(selected_wins/wins.sum()) if wins.sum() else None))
    (OUT/'summary.json').write_text(json.dumps(results,indent=2));print(pd.DataFrame(results).to_string(index=False))


if __name__=='__main__':main()
