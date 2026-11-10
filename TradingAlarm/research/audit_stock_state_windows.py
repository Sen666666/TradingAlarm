"""Cross-check annual public state windows against independent local raw bars/calendar."""
import json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
SOURCE='/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet'
def main():
    paths=sorted((ROOT/'data/stock-state-windows').glob('*.json'));symbols=sorted({json.loads(p.read_text())['symbol'] for p in paths})
    local=pd.read_parquet(SOURCE,filters=[('symbol','in',symbols)],columns=['symbol','trade_date','open','high','low','close','volume'])
    calendar=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index
    reports=[]
    for p in paths:
        d=json.loads(p.read_text());f=pd.DataFrame(d['rows']);f['date']=pd.to_datetime(f.date);f=f.set_index('date')
        g=local[local.symbol.eq(d['symbol'])].set_index('trade_date');g=g[g.index.year==d['year']]
        common=f.index.intersection(g.index);traded=f.loc[common,'tradestatus'].eq('1');idx=common[traded]
        diffs=(f.loc[idx,['open','high','low','close']].astype(float)-g.loc[idx,['open','high','low','close']]).abs()
        cal=calendar[calendar.year==d['year']]
        reports.append(dict(symbol=d['symbol'],year=d['year'],rows=len(f),expected_observed_calendar=len(cal),missing_calendar_dates=[str(x.date()) for x in cal.difference(f.index)],extra_dates=[str(x.date()) for x in f.index[(f.index>=calendar.min())&(f.index<=calendar.max())].difference(cal)],outside_comparison_calendar=[str(x.date()) for x in f.index[(f.index<calendar.min())|(f.index>calendar.max())]],verified_interval_start=str(calendar.min().date()),verified_interval_end=str(calendar.max().date()),common_trading_rows=len(idx),max_ohlc_difference=float(diffs.max().max()),ohlc_mismatch_over_cent=int(diffs.gt(.010001).any(axis=1).sum()),suspended_rows=int(f.tradestatus.eq('0').sum()),suspended_local_positive_volume=int(g.reindex(f.index)[f.tradestatus.eq('0')].volume.gt(0).sum()),limitation='Cross-vendor/calendar agreement not exchange-certified limit prices; no execution readiness claim'))
    (ROOT/'results/stock-data-audit/stock-state-window-audit.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports,indent=2))
if __name__=='__main__':main()
