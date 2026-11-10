"""Absolute score bins complement cross-sectional ranking, no threshold search."""
from pathlib import Path
import json
import pandas as pd
P=Path('results/strength-path-discrimination')
t=pd.read_parquet(P/'observations.parquet');rows=[]
for model in ('adaptive','anchored_neutral','momentum21'):
    for h in (5,21,63):
        g=t.dropna(subset=['adaptive','anchored_neutral','momentum21',f'asym{h}',f'return{h}']).copy()
        g['bin']=pd.cut(g[model],[0,2,4,6,8,10],include_lowest=True,labels=['0-2','2-4','4-6','6-8','8-10']);g['year']=g.date.dt.year
        baseline=g.groupby('date')[[f'asym{h}',f'return{h}']].mean()
        for (year,label),part in g.groupby(['year','bin'],observed=True):
            day=part.groupby('date')[[f'asym{h}',f'return{h}']].mean();delta=day-baseline.reindex(day.index)
            rows.append(dict(model=model,horizon=h,year=int(year),score_bin=str(label),observations=len(part),dates=len(day),mean_asymmetry=float(day[f'asym{h}'].mean()),mean_return=float(day[f'return{h}'].mean()),asymmetry_vs_same_date_all=float(delta[f'asym{h}'].mean()),return_vs_same_date_all=float(delta[f'return{h}'].mean())))
(P/'absolute-bins.json').write_text(json.dumps(rows,indent=2)+'\n')
for r in rows:
    if r['score_bin']=='8-10' and r['horizon']==21:print(r)
