"""Causal ETF return-correlation proxy, explicitly not historical industry membership."""
import json,itertools
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sector_factors import expanded_assets
from build_stock_features import grouped
from stock_entry_diagnostic import select,HORIZONS
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/stock-sector-proxy-v1'
def best_proxy(stock,proxies,eligible,min_obs=100):
    scores={}
    for name in sorted(proxies):
        if not eligible.get(name,False):continue
        x=np.asarray(stock,float);y=np.asarray(proxies[name],float);valid=np.isfinite(x)&np.isfinite(y)
        if valid.sum()<min_obs or np.std(x[valid])==0 or np.std(y[valid])==0:continue
        corr=float(np.corrcoef(x[valid],y[valid])[0,1])
        if corr>0:scores[name]=corr
    if not scores:return None,None
    winner=min(scores,key=lambda n:(-scores[n],n));return winner,scores[winner]
def main():
    OUT.mkdir(exist_ok=True)
    protocol=dict(method='Maximum positive126session return correlation to historically available A-listed sector ETFs;minimum100 paired observed daily returns;require at least3seasoned proxies',gate='Matched ETF signal close>SMA200 and126return>0',universe='Existing continuous20 breakout+SMA200 monthly candidates; ETF sector proxies exclude broad market',comparison='Covered baseline versus proxy gate,each lowATR andRS top10;rank after gate,no future-return refill',limitation='Price association is not industry membership. Selected surviving ETFs; point-in-time bars only but retrospective research design; no account returns,execution or causal proof.',horizons=list(HORIZONS))
    p=OUT/'protocol.json'
    if p.exists() and json.loads(p.read_text())!=protocol:raise ValueError('protocol changed')
    p.write_text(json.dumps(protocol,indent=2))
    calendar=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values()
    assets={n:a for n,a in expanded_assets().items() if a['kind']=='equity' and a['currency']=='CNY' and a['sector']!='broad_cn'}
    proxy_returns={};ready={};gate={}
    for n,a in assets.items():
        c=a['signal'].close.reindex(calendar);proxy_returns[n]=c.pct_change(fill_method=None)
        ma=c.rolling(200,min_periods=200).mean();ret=c/c.shift(126)-1
        ready[n]=ma.notna()&ret.notna();gate[n]=c.gt(ma)&ret.gt(0)
    pr=pd.DataFrame(proxy_returns);rd=pd.DataFrame(ready);gt=pd.DataFrame(gate)
    candidates=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet');candidates=candidates[candidates.active20.eq(20)]
    wanted={s:g.date.tolist() for s,g in candidates.groupby('symbol')};rows=[]
    cols=['symbol','date','signal_close','observed_bar','positive_volume']
    for symbol,f in itertools.chain.from_iterable(grouped(pq.ParquetFile(ROOT/'data/stock-features'/p),cols) for p in ['local-features.parquet','ths-retired-features.parquet']):
        if symbol not in wanted:continue
        f=f.set_index('date').reindex(calendar);observed=f.observed_bar.eq(True)&f.positive_volume.eq(True)
        r=f.signal_close.pct_change(fill_method=None).where(observed&observed.shift(1,fill_value=False))
        for dt in wanted[symbol]:
            i=calendar.get_loc(dt)
            if i<125 or rd.loc[dt].sum()<3:continue
            window=slice(i-125,i+1)
            name,corr=best_proxy(r.iloc[window],pr.iloc[window],rd.loc[dt].to_dict())
            if name is not None:rows.append(dict(symbol=symbol,date=dt,proxy=name,correlation=corr,gate=bool(gt.loc[dt,name])))
    assignments=pd.DataFrame(rows);assignments.to_parquet(OUT/'assignments.parquet',index=False)
    data=candidates.merge(assignments,on=['symbol','date'],validate='one_to_one');results=[]
    for condition,base in [('covered_baseline',data),('sector_gate',data[data.gate])]:
        for strategy,key in [('low_atr','atr_fraction'),('rs','rs_order')]:
            chosen=select(base,key)
            # Include baseline signal dates with no eligible gate names as explicit zero-selection rows.
            for dt in sorted(data.date.unique()):
                g=chosen[chosen.date.eq(dt)]
                for h in HORIZONS:
                    v=g[f'forward_{h}'].dropna();results.append(dict(condition=condition,strategy=strategy,date=dt,horizon=h,selected=len(g),labels=len(v),mean=v.mean()))
    t=pd.DataFrame(results);t['period']=np.where(t.date.dt.year<2022,'2015-2021','2022+');t.to_csv(OUT/'by-date.csv',index=False)
    summary=t.groupby(['period','condition','strategy','horizon']).agg(signal_dates=('date','count'),labeled_dates=('mean','count'),selected=('selected','sum'),labels=('labels','sum'),mean_price_return=('mean','mean'));summary.to_csv(OUT/'summary.csv')
    paired=[]
    for (period,strategy,horizon),g in t.groupby(['period','strategy','horizon']):
        wide=g.pivot(index='date',columns='condition',values='mean').dropna()
        diff=wide.sector_gate-wide.covered_baseline
        paired.append(dict(period=period,strategy=strategy,horizon=int(horizon),paired_dates=len(diff),mean_gate_minus_baseline=float(diff.mean()),positive_difference_fraction=float(diff.gt(0).mean())))
    pd.DataFrame(paired).to_csv(OUT/'same-date-contrast.csv',index=False)
    (OUT/'coverage.json').write_text(json.dumps(dict(candidate_rows=len(candidates),assigned=len(data),proxy_symbols=sorted(assets),gate_rows=int(data.gate.sum()),first=str(data.date.min()),last=str(data.date.max()),execution_ready=False),indent=2))
    print(summary.to_string())
if __name__=='__main__':main()
