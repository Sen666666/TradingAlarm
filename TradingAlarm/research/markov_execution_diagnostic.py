"""Frozen-model diagnostic; order matching is not a causal PNL attribution."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from strategy_signals import build_signals

OUT = Path('results/markov-execution-diagnostic')
SOURCE = Path('results/strength-markov-map')


def order_groups(orders):
    groups = {}
    for o in orders:
        key = (o['symbol'], o['signal_date'], 'entry' if o['units'] > 0 else 'exit')
        g = groups.setdefault(key, dict(units=0., fees=0., dates=[]))
        g['units'] += o['units']; g['fees'] += o['fee']; g['dates'].append(o['date'])
    return groups


def components(close, open1, close1, open2):
    v = np.log([open1 / close, close1 / open1, open2 / close1])
    assert abs(v.sum() - np.log(open2 / close)) < 1e-12
    return dict(signal_gap=v[0], first_intraday=v[1], second_gap=v[2], open_to_open=v[1]+v[2])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'protocol.json').write_text(json.dumps(dict(
        strategies=['markov_price_map', 'markov_volume_map'],
        source=str(SOURCE), parameters_changed=False,
        matching='symbol, signal_date, side; aggregate partial fills',
        price_paths='adjusted observed bars, signal close then next two observed opens; no execution attribution',
        interpretation='delay1 can cancel pending orders on state reversal; do not call it a pure latency stress',
        review_status='2022-2026 already reviewed development data'), indent=2))
    etf, _ = load_extended(); hk, _ = load_assets()
    rows=[]; comparisons=[]
    for group, assets in [('etf17', etf), ('hk7', hk)]:
        for strategy in ['markov_price_map', 'markov_volume_map']:
            signals=build_signals(assets, strategy)
            b,d=[order_groups(json.loads((SOURCE/f'{group}-{strategy}-daily-{sc}-orders.json').read_text())) for sc in ['base','delay1']]
            missing=set(b)-set(d); matched=set(b)&set(d)
            missing_rows=[]
            for symbol, date, side in sorted(missing):
                a=assets[symbol]; raw=a['raw']; s=signals[symbol]
                eligible=raw.index[(raw.index>pd.Timestamp(date)) & raw.volume.gt(0) & raw.high.gt(raw.low)]
                # At the second eligible opening the engine uses the last preceding close.
                prior=s.index[s.index<eligible[1]][-1] if len(eligible)>1 else None
                reversed_by_second=bool(s.loc[prior] != s.loc[date]) if prior is not None else None
                missing_rows.append(dict(symbol=symbol,signal_date=date,side=side,reversed_by_second_eligible_open=reversed_by_second))
            comparisons.append(dict(group=group,strategy=strategy,base_groups=len(b),delay_groups=len(d),matched=len(matched),base_only=len(missing),delay_only=len(set(d)-set(b)),base_only_reversed=sum(r['reversed_by_second_eligible_open'] is True for r in missing_rows),missing=missing_rows))
            for symbol,a in assets.items():
                raw=a['raw']; f=a['signal'].reindex(raw.index[raw.volume.gt(0)]).dropna(subset=['open','close'])
                s=signals[symbol].reindex(f.index); change=s.diff()
                for i in range(1,len(f)-2):
                    date=f.index[i]
                    if date < pd.Timestamp('2022-01-01') or date > pd.Timestamp('2026-10-16') or change.iloc[i]==0: continue
                    if f.index[i+2]>pd.Timestamp('2026-10-16'):continue
                    rows.append(dict(group=group,strategy=strategy,symbol=symbol,date=str(date.date()),year=date.year,side='entry' if change.iloc[i]>0 else 'exit',**components(f.close.iloc[i],f.open.iloc[i+1],f.close.iloc[i+1],f.open.iloc[i+2])))
    frame=pd.DataFrame(rows);frame.to_csv(OUT/'signal-paths.csv',index=False)
    yearly=frame.groupby(['group','strategy','side','year']).open_to_open.agg(['size','mean'])
    yearly['mean_bps']=yearly['mean']*10000
    yearly.to_csv(OUT/'yearly-path-summary.csv')
    summaries=[]
    for key,g in frame.groupby(['group','strategy','side']):
        summaries.append(dict(zip(['group','strategy','side'],key),n=len(g),**{c+'_mean_bps':float(g[c].mean()*10000) for c in ['signal_gap','first_intraday','second_gap','open_to_open']}))
    (OUT/'order-comparison.json').write_text(json.dumps(comparisons,indent=2))
    (OUT/'path-summary.json').write_text(json.dumps(summaries,indent=2))
    print(json.dumps([{k:v for k,v in c.items() if k!='missing'} for c in comparisons],indent=2))
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':main()
