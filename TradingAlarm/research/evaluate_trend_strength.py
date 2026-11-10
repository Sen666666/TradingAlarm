"""Descriptive validation of frozen causal strength, no trading optimization."""
import json,hashlib
import numpy as np
import pandas as pd
from build_stock_features import ROOT
from trend_strength_model import strength_frame
from geometric_strength import geometric_frame


def main(output='trend-strength-v1'):
    out=ROOT/'results'/output;protocol=json.loads((out/'protocol.json').read_text());data=ROOT/'data/ths-refresh-20261018';manifest=json.loads((data/'validated-input-balanced-all500.json').read_text());rows=[]
    for n,r in enumerate(manifest['records']):
        p=data/f"{r['ths_symbol']}-signal.parquet";assert hashlib.sha256(p.read_bytes()).hexdigest()==r['signal_sha256'];f=pd.read_parquet(p);f=f[f.observed_bar & f.volume.gt(0)]
        dates=pd.Series(f.index,index=f.index)
        for model,joint in [('price_only',False),('price_volume',True)]:
            if protocol.get('estimator')=='geometry':
                s=geometric_frame(f.signal_close,f.close,f.volume,joint)
            else:
                s=strength_frame(f.signal_close,f.close,f.volume,joint,estimator=protocol.get('estimator','constant'))
            s['symbol']=r['symbol'];s['board']=r['board'];s['model']=model;s['date']=s.index;s['year']=s.index.year
            for h in (5,21):
                label=f.signal_close.shift(-h)/f.signal_open.shift(-1)-1
                # No cross-year label leakage in yearly descriptive summaries.
                label=label.where(dates.shift(-h).dt.year.eq(dates.dt.year))
                s[f'forward{h}']=label
            rows.append(s.loc['2024-01-01':])
        if (n+1)%25==0:print('strength symbols',n+1,flush=True)
    t=pd.concat(rows,ignore_index=True);t['bin']=pd.cut(t.strength,bins=[0,2,4,6,8,10],labels=['0-2','2-4','4-6','6-8','8-10'],include_lowest=True).astype('string');t.to_parquet(out/'strength-observations.parquet',index=False)
    reports=[]
    for board in ['ALL',*sorted(t.board.unique())]:
        part=t if board=='ALL' else t[t.board.eq(board)]
        for (model,year,b),g in part.dropna(subset=['bin']).groupby(['model','year','bin']):
            for h in (5,21):
                valid=g.dropna(subset=[f'forward{h}']);daily=valid.groupby('date')[f'forward{h}'].mean();positive=valid.assign(positive=valid[f'forward{h}'].gt(0)).groupby('date').positive.mean()
                reports.append(dict(board=board,model=model,year=int(year),strength_bin=b,horizon=h,observations=len(valid),missing_or_crossyear_labels=len(g)-len(valid),dates=len(daily),date_balanced_forward_mean=float(daily.mean()) if len(daily) else None,date_balanced_positive_fraction=float(positive.mean()) if len(positive) else None))
    (out/'validation-report.json').write_text(json.dumps(dict(reports=reports,input_symbols=len(manifest['records']),causal_tests=3,meaning='Observed-session forwardlabels,nextopenentryreference,no fees or executableportfolio. Same-day stocks average first,then dates;overlapping horizons and sharedmarkets correlated,not IID significance. Yearboundarylabels omitted. No thresholds fitted.'),indent=2)+'\n')
    for r in reports:
        if r['board']=='ALL' and r['horizon']==21:print(r,flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',default='trend-strength-v1');main(p.parse_args().output)
