"""Cross-vendor daily adjusted-return check; no certification of account returns."""
import json
from pathlib import Path
import pandas as pd
from ths_signal_adjustment import signal_frame
from stock_signal_data import retired_signal_frame
ROOT=Path(__file__).resolve().parent
records=[];exceptions=[]
for p in sorted((ROOT/'data/retired-pilot').glob('*.json')):
    symbol=p.stem;ths=('USHD' if symbol.endswith('.SH') else 'USZD')+symbol[:6]
    try:
        a=signal_frame(json.loads((ROOT/'data/ths-raw'/f'{ths}.json').read_text()),json.loads((ROOT/'data/ths-rights'/f'{ths}.json').read_text()))
        b=retired_signal_frame(json.loads(p.read_text()),json.loads((ROOT/'data/retired-factors'/p.name).read_text()))
    except (FileNotFoundError,ValueError,KeyError):continue
    joined=pd.concat([a.loc[a.bar_allows_trade,'signal_close'].rename('ths'),b.loc[b.bar_allows_trade,'signal_close'].rename('bao')],axis=1,sort=True).dropna()
    # Consecutive common observations; some intervals can span missing sessions.
    diff=joined.pct_change(fill_method=None).diff(axis=1)['bao'].abs().dropna()
    for date,value in diff[diff.gt(.001)].items():
        exceptions.append(dict(symbol=symbol,date=str(date.date()),absolute_return_difference=float(value)))
    records.append(dict(symbol=symbol,intervals=len(diff),median_absolute_return_difference=float(diff.median()),max_absolute_return_difference=float(diff.max()),intervals_difference_over_10bp=int(diff.gt(.001).sum())))
out=dict(records=records,exceptions=exceptions,comparison='Adjusted-price returns between consecutive common traded observations; not necessarily adjacent exchange sessions.',limitation='Agreement cannot establish source completeness, settlement dates or executable returns.')
(ROOT/'results/stock-data-audit/ths-adjusted-return-crosscheck.json').write_text(json.dumps(out,indent=2))
print('symbols',len(records),'intervals',sum(x['intervals'] for x in records),'over10bp',sum(x['intervals_difference_over_10bp'] for x in records))
print(sorted(records,key=lambda x:x['max_absolute_return_difference'],reverse=True)[:5])
