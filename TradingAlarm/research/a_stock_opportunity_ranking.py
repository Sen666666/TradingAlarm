"""Prior-close opportunity ranks, descriptive only; not a funded portfolio."""
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from build_stock_features import ROOT, grouped


def rank_candidates(candidates):
    result=candidates.copy()
    for score, ascending in [('momentum126_21',False),('atr_fraction',True)]:
        rank=result.groupby('date')[score].rank(method='average',pct=True,ascending=ascending)
        result[score+'_quintile']=np.ceil(rank*5).clip(1,5).astype('Int64')
    return result


def main():
    out = ROOT / 'results/a-stock-opportunity-ranking'
    out.mkdir(exist_ok=True)
    protocol = dict(
        purpose='Diagnose same-date price-only allocation without changing entries/exits.',
        candidates='Every cached symbol-date with close>prior55high, finiteMA200 and positive finiteATR20. Include held names and candidates subsequently unable to fill: never rank only future successful fills.',
        ranks='Same-signal-date percentile, average ties: momentum126_21 descending attractiveness; ATR20/close ascending attractiveness. Fixed quintiles; no window or threshold search.',
        outcomes='Join actual independent-symbol baseline campaigns by symbol and prior signaldate, then fixed historical snapshots. MeanR is not a capital constrained portfolio; ranks do not simulate alternative entries or capacity.',
        limits='Incomplete historical universe, revised adjustedprices and execution assumptions persist. All data reused; correlated overlapping snapshots not independent tests. First20percent rank is descriptive,not adopted rule.')
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2))
    campaigns = pd.read_parquet(ROOT/'results/a-stock-zero-range-stress/campaigns.parquet')
    first_signal_date = pd.Timestamp(campaigns.signal_date.min())
    pieces = []
    columns = ['symbol','date','signal_close','breakout55','sma200','atr20','momentum126_21']
    for name in ('local-features.parquet','ths-retired-features.parquet'):
        for symbol, frame in grouped(pq.ParquetFile(ROOT/'data/stock-features'/name),columns):
            eligible = (frame.date.ge(first_signal_date) & frame.signal_close.gt(frame.breakout55)
                        & np.isfinite(frame.sma200) & np.isfinite(frame.atr20) & frame.atr20.gt(0))
            f = frame.loc[eligible,['symbol','date','signal_close','atr20','momentum126_21']].copy()
            f['atr_fraction'] = f.atr20 / f.signal_close
            pieces.append(f[['symbol','date','momentum126_21','atr_fraction']])
    candidates = pd.concat(pieces,ignore_index=True)
    assert not candidates.duplicated(['symbol','date']).any()
    candidates=rank_candidates(candidates)
    candidates['signal_date'] = candidates.date.dt.strftime('%Y-%m-%d')
    candidates.to_parquet(out/'all-candidates.parquet',index=False)
    context = campaigns[['symbol','entry_date','signal_date']].merge(
        candidates.drop(columns='date'),on=['symbol','signal_date'],how='left',validate='many_to_one',indicator=True)
    assert context._merge.eq('both').all(), context.loc[context._merge.ne('both')].head(5).to_dict('records')
    assert (pd.to_datetime(context.signal_date)<pd.to_datetime(context.entry_date)).all()
    context = context.drop(columns='_merge')
    context.to_parquet(out/'entry-context.parquet',index=False)
    snapshots = pd.read_parquet(ROOT/'results/a-stock-zero-range-stress/cutoffs/snapshots.parquet')
    snapshots = snapshots.merge(context,on=['symbol','entry_date'],validate='many_to_one')
    records=[]
    for feature in ('momentum126_21','atr_fraction'):
        for (cutoff, bucket), sample in snapshots.groupby(['cutoff',feature+'_quintile']):
            known=sample[sample.status.ne('stale_unknown')]
            records.append(dict(feature=feature,cutoff=cutoff,quintile=int(bucket),campaigns=len(sample),
                unknown=len(sample)-len(known),mean_R15=float(known.R_cost15.mean()),
                mean_R30=float(known.R_cost30.mean()),
                equal_signal_date_mean_R15=float(known.groupby('signal_date').R_cost15.mean().mean())))
    daily = candidates.groupby('date').size()
    entry_daily=campaigns.groupby('signal_date').size().sort_values(ascending=False)
    summary=dict(candidate_rows=len(candidates),signal_dates=len(daily),
        median_candidates_per_signal_date=float(daily.median()),max_candidates_one_date=int(daily.max()),
        actual_campaigns=len(campaigns),top10_signal_dates_entry_share=float(entry_daily.head(10).sum()/len(campaigns)),
        missing_momentum_entry_count=int(context.momentum126_21.isna().sum()),
        records=records, interpretation=protocol['outcomes'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
    for r in records:
        if r['cutoff']==snapshots.cutoff.max():print(r)


if __name__=='__main__':main()
