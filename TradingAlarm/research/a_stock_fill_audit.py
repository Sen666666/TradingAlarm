"""Flag zero-range execution bars without inferring dated price-limit rules."""
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from build_stock_features import ROOT,SOURCE,grouped

OUT=ROOT/'results/a-stock-fill-audit'


def main():
    OUT.mkdir(exist_ok=True)
    trades=pd.read_parquet(ROOT/'results/a-stock-campaign-signals/campaigns.parquet').reset_index(names='campaign_row')
    wanted={n:g for n,g in trades.groupby('symbol')};rows=[]
    def inspect(symbol,raw,source):
        if symbol not in wanted:return
        if raw.index.duplicated().any():raise ValueError('Duplicate raw execution date')
        for r in wanted[symbol].to_dict('records'):
            for side in ['entry','exit']:
                date=r[side+'_date']
                if pd.isna(date):continue
                date=pd.Timestamp(date)
                if date not in raw.index:raise ValueError('Claimed fill lacks observed source bar')
                bar=raw.loc[date]
                if source=='local':assert np.isclose(bar.open*bar.reference_adjustment_factor,r[side+'_price'])
                zero=bool(np.isclose(bar.high,bar.low,rtol=1e-10,atol=1e-10))
                rows.append(dict(campaign_row=r['campaign_row'],symbol=symbol,source=source,side=side,date=str(date.date()),zero_range=zero,volume=float(bar.volume)))
    for symbol,f in grouped(pq.ParquetFile(SOURCE),['symbol','trade_date','open','high','low','volume','reference_adjustment_factor']):
        inspect(symbol,f.set_index('trade_date'),'local')
    for symbol,g in wanted.items():
        if g.source.iloc[0]!='ths_retired':continue
        code,market=symbol.split('.');name=('USHD' if market=='SH' else 'USZD')+code+'.json'
        raw=pd.DataFrame(json.loads((ROOT/'data/ths-raw'/name).read_text())['bars']);raw['date']=pd.to_datetime(raw.date)
        inspect(symbol,raw.set_index('date'),'ths_retired')
    flags=pd.DataFrame(rows);assert flags.volume.gt(0).all()
    flags.to_parquet(OUT/'fill-flags.parquet',index=False)
    ids=set(flags.loc[flags.zero_range,'campaign_row']);trades['has_zero_range_fill']=trades.campaign_row.isin(ids)
    summary=dict(scope='Frozen2022+baseline actual simulatedentry/exitdates;rawvendorOHLC shape checks.',
        definition='High equals low within numerical tolerance;may be a limit queue or illiquidity. Not proof of non-fill,not dated up/down-limit classification.',
        fills=len(flags),zero_range_fills=int(flags.zero_range.sum()),zero_range_entries=int((flags.zero_range&flags.side.eq('entry')).sum()),zero_range_exits=int((flags.zero_range&flags.side.eq('exit')).sum()),affected_campaigns=len(ids),
        limitation='DailyOHLC cannot reconstruct opening queue or actualfillable size;do not delete flaggedprofitabletrades andcall it a rerun.')
    known=trades[trades.status.ne('terminal_unknown')]
    summary['groups']=[dict(zero_range_fill=bool(key),campaigns=len(g),marked_mean_R=float(g.R_cost15.mean()),marked_total_R=float(g.R_cost15.sum())) for key,g in known.groupby('has_zero_range_fill')]
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
