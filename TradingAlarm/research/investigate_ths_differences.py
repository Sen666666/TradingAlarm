"""Decompose cross-vendor discrepancies into raw prices and adjustment multipliers."""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import pandas as pd
from ths_signal_adjustment import signal_frame
from stock_signal_data import retired_signal_frame
ROOT=Path(__file__).resolve().parent
source=json.loads((ROOT/'results/stock-data-audit/ths-adjusted-return-crosscheck.json').read_text())
rows=[]
for symbol in sorted({x['symbol'] for x in source['exceptions']}):
    ths=('USHD' if symbol.endswith('.SH') else 'USZD')+symbol[:6]
    rights=json.loads((ROOT/'data/ths-rights'/f'{ths}.json').read_text())
    a=signal_frame(json.loads((ROOT/'data/ths-raw'/f'{ths}.json').read_text()),rights)
    factors=json.loads((ROOT/'data/retired-factors'/f'{symbol}.json').read_text())
    b=retired_signal_frame(json.loads((ROOT/'data/retired-pilot'/f'{symbol}.json').read_text()),factors)
    common=a.index[a.bar_allows_trade].intersection(b.index[b.bar_allows_trade]).sort_values()
    for e in [x for x in source['exceptions'] if x['symbol']==symbol]:
        dt=pd.Timestamp(e['date']);prev=common[common.get_loc(dt)-1]
        vals={}
        for name,f in [('ths',a),('bao',b)]:
            vals[name]=dict(prior_raw=float(f.loc[prev,'close']),raw=float(f.loc[dt,'close']),factor_ratio=float(f.loc[dt,'factor']/f.loc[prev,'factor']),signal_return=float(f.loc[dt,'signal_close']/f.loc[prev,'signal_close']-1))
        raw_diff=abs(vals['ths']['raw']-vals['bao']['raw'])>1e-7 or abs(vals['ths']['prior_raw']-vals['bao']['prior_raw'])>1e-7
        factor_diff=abs(vals['ths']['factor_ratio']-vals['bao']['factor_ratio'])>1e-6
        theoretical=vals['ths']['prior_raw']/vals['ths']['factor_ratio']
        rounded=float(Decimal(str(theoretical)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
        tick_explains=factor_diff and not raw_diff and abs(vals['bao']['factor_ratio']-vals['ths']['prior_raw']/rounded)<1e-6
        events=[r for r in rights['records'] if prev<pd.to_datetime(str(r['1']))<=dt]
        rows.append(dict(symbol=symbol,date=e['date'],prior=str(prev.date()),values=vals,raw_difference=raw_diff,factor_difference=factor_diff,cent_rounding_explains_factor_difference=tick_explains,ths_events=events,bao_events=[r for r in factors['rows'] if prev<pd.Timestamp(r['dividOperateDate'])<=dt]))
report=dict(records=rows,raw_only=sum(r['raw_difference'] and not r['factor_difference'] for r in rows),factor_only=sum(r['factor_difference'] and not r['raw_difference'] for r in rows),both=sum(r['factor_difference'] and r['raw_difference'] for r in rows),limitation='Decomposition locates disagreement; neither vendor is automatically ground truth.')
(ROOT/'results/stock-data-audit/ths-return-difference-investigation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False))
