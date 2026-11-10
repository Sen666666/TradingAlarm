"""Post-result exploratory diagnosis; no signal or account changes."""
from pathlib import Path
import pandas as pd,json
p=Path(__file__).resolve().parents[1]/'results';summary=[];detail=[]
for path in sorted(p.glob('*-signals.csv')):
 s=path.name.removesuffix('-signals.csv');f=pd.read_csv(path,index_col='date',parse_dates=True);f=f.loc[f.close.gt(0)&f.volume.gt(0)];n=0
 for date,row in f.loc[f.exited.eq(1)].iterrows():
  i=f.index.get_loc(date);after=f.iloc[i+1:];enter=after.index[after.entered.eq(1)];end=enter[0] if len(enter) else f.index[-1];gap=f.loc[date:end].iloc[1:];gap=gap.loc[gap.target.eq(0)];up=gap.leg_direction.eq(1);n+=int(up.sum())
  detail.append(dict(symbol=s,exit=str(date.date()),leg_at_exit=row.leg_direction,next_entry=str(enter[0].date()) if len(enter) else None,flat_observations=len(gap),flat_up_observations=int(up.sum())))
 summary.append(dict(symbol=s,exits=int(f.exited.sum()),exits_with_up_detector=int((f.exited.eq(1)&f.leg_direction.eq(1)).sum()),flat_up_observations=n))
pd.DataFrame(summary).to_csv(p/'reentry-summary.csv',index=False);pd.DataFrame(detail).to_csv(p/'reentry-gaps.csv',index=False)
print(pd.DataFrame(summary).to_string(index=False));print(pd.DataFrame(detail).query("symbol=='HK09618' and exit>='2024-08-01' and exit<='2024-12-31'").to_string(index=False))
