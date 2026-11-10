"""Within-bin rising/falling contrasts, both sides required on each date."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
P=Path('results/strength-path-discrimination');t=pd.read_parquet(P/'observations.parquet').sort_values(['symbol','date']);reports=[]
for model in ('adaptive','anchored_neutral','momentum21'):
    delta=t.groupby('symbol')[model].diff();g=t.assign(direction=np.sign(delta),score_bin=pd.cut(t[model],[0,2,4,6,8,10],labels=['0-2','2-4','4-6','6-8','8-10'],include_lowest=True))
    for h in (5,21,63):
        valid=g.dropna(subset=[f'asym{h}',f'return{h}','direction','score_bin']);valid=valid.loc[valid.direction.ne(0)]
        daily=valid.groupby(['date','score_bin','direction'],observed=True)[[f'asym{h}',f'return{h}']].mean().unstack('direction')
        for label in ['0-2','2-4','4-6','6-8','8-10']:
            if label not in daily.index.get_level_values('score_bin'):continue
            q=daily.xs(label,level='score_bin').dropna()
            if not len(q):continue
            for year,z in q.groupby(q.index.year):
                reports.append(dict(model=model,horizon=h,score_bin=label,year=int(year),paired_dates=len(z),rising_minus_falling_asymmetry=float((z[(f'asym{h}',1.)]-z[(f'asym{h}',-1.)]).mean()),rising_minus_falling_return=float((z[(f'return{h}',1.)]-z[(f'return{h}',-1.)]).mean())))
(P/'transitions.json').write_text(json.dumps(reports,indent=2)+'\n')
for r in reports:
    if r['score_bin']=='8-10' and r['horizon']==21:print(r)
