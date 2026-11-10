"""Retrospective interval matching; never used by a live signal."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
OUT=Path('results/anchored-tail-capture')

def interval_coverage(dates,episodes):
    active=np.zeros(len(dates),bool)
    for e in episodes.itertuples():
        end=pd.Timestamp(e.exit_date) if e.status=='closed' else pd.Timestamp(e.mark_date)+pd.Timedelta(days=1)
        active|=(dates>=pd.Timestamp(e.entry_date))&(dates<end)
    if not len(active):raise ValueError('empty reference interval')
    if not active.any():category='no_participation'
    elif active.all():category='full_interval'
    elif not active[0] and not active[-1]:category='late_and_early'
    elif not active[0]:category='late_start'
    elif not active[-1]:category='early_finish'
    else:category='internal_gaps'
    return dict(category=category,coverage=float(active.mean()),first_offset=int(np.flatnonzero(active)[0]) if active.any() else None,last_gap=int(len(active)-1-np.flatnonzero(active)[-1]) if active.any() else None)

def main():
    root=Path('data/ths-refresh-20261018');m=json.loads((root/'validated-input-balanced-second500.json').read_text())
    data={r['symbol']:pd.read_parquet(root/(r['ths_symbol']+'-signal.parquet')) for r in m['records']}
    allp=pd.read_parquet('results/strength-anchored-transfer485/episodes.parquet')
    p=allp.loc[allp.cutoff.eq('2026-10-16')&allp.delay.eq(0)]
    ref=p.loc[p.strategy.eq('adaptive_geometry_price_volume_split_units')&p.status.eq('closed')]
    rows=[]
    for name in ['anchored_price_volume','anchored_neutral_price_volume']:
        q=p.loc[p.strategy.eq(name)]
        for e in ref.itertuples():
            f=data[e.symbol];dates=f.index[f.observed_bar&f.volume.gt(0)&(f.index>=pd.Timestamp(e.entry_date))&(f.index<pd.Timestamp(e.exit_date))]
            match=interval_coverage(dates,q.loc[q.symbol.eq(e.symbol)])
            offset=match['first_offset']
            before=float(f.loc[dates[offset],'signal_open']/e.entry_price-1) if offset is not None else None
            rows.append(dict(symbol=e.symbol,entry_date=e.entry_date,exit_date=e.exit_date,reference_return=e.return15,tail=e.return15>=.3,year=int(e.entry_date[:4]),strategy=name,bars=len(dates),price_return_before_first_participation=before,**match))
    table=pd.DataFrame(rows);table.to_parquet(OUT/'matched-intervals.parquet',index=False);reports=[]
    for (name,tail,year),g in table.groupby(['strategy','tail','year']):
        reports.append(dict(strategy=name,tail=bool(tail),year=int(year),n=len(g),categories=g.category.value_counts().to_dict(),mean_coverage=float(g.coverage.mean()),median_coverage=float(g.coverage.median()),median_first_offset_when_participating=float(g.first_offset.median())))
    for (name,tail),g in table.groupby(['strategy','tail']):
        r=dict(strategy=name,tail=bool(tail),year='all',n=len(g),categories=g.category.value_counts().to_dict(),mean_coverage=float(g.coverage.mean()),median_coverage=float(g.coverage.median()),median_first_offset_when_participating=float(g.first_offset.median()));reports.append(r);print(r)
    (OUT/'summary.json').write_text(json.dumps(reports,indent=2)+'\n')
if __name__=='__main__':main()
