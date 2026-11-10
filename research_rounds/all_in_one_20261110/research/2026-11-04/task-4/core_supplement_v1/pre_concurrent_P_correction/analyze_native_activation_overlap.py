"""Separate missing supplemental P from later native-I authorization; evaluation only."""
from pathlib import Path
from collections import defaultdict
import hashlib,json,pickle,time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;SRC={}
def read(p):
 p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def period(r):
 d=r['day']
 return (d[:4]if d<'2024-09-24'else'2024_924_to_end')if r['window']=='long'else('2025_H2'if d<'2026-01-01'else'2026_H1')
def main():
 start=time.monotonic();SRC[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 e=read(O/'ALL_A_GAP_EPISODES.json');lookup={(r['window'],r['sid'],r['e0_run_start']):r for r in e}
 wait=read(O/'ALL_B_TO_P_WAIT.json');P=read(O/'P_EVENTS.json')
 fp=O.parent/'new_price_trend_v1/PRICE_FEATURES.pkl';SRC[str(fp)]=hashlib.sha256(fp.read_bytes()).hexdigest()
 with fp.open('rb')as h:features=pickle.load(h)
 rows=[];firsts={}
 for r in wait:
  if r['state']!='A_I_never_started_in_E0':continue
  q=lookup[(r['window'],r['sid'],r['e0_run_start'])];i=q['first_original_I_active'];f=features[r['sid']]
  assert i is None or i>r['day']
  n=f.index.get_loc(pd.Timestamp(i))-f.index.get_loc(pd.Timestamp(r['day']))if i else None
  progress=(float(f.loc[i,'close'])/float(f.loc[r['day'],'close'])-1)*100 if i else None
  z=dict(r,native_I_day=i,native_I_wait_observations=n,native_I_within20=n is not None and n<=20,
         native_I_before_or_on_P=bool(i and(r['next_P_day']is None or i<=r['next_P_day'])),
         price_progress_B_to_native_I_pct=progress)
  rows.append(z);firsts.setdefault((r['window'],r['sid'],r['source_segment'],r['e0_run_start']),z)
 summaries=[]
 for unit,a in [('all_A_B',rows),('first_observed_A_B_per_window_E0',list(firsts.values()))]:
  groups=defaultdict(list)
  for r in a:groups[(r['window'],period(r))].append(r)
  for k,g in groups.items():
   known=[r for r in g if r['price_horizon20_known']];missing=[r for r in known if not r['P_within20']]
   progress=[r['price_progress_B_to_native_I_pct']for r in g if r['native_I_within20']]
   summaries.append(dict(unit=unit,window=k[0],period=k[1],A_B=len(g),
    native_I_within20=sum(r['native_I_within20']for r in g),
    native_I_before_or_on_P=sum(r['native_I_before_or_on_P']for r in g),
    mature_no_P20=len(missing),mature_no_P20_but_native_I_within20=sum(r['native_I_within20']for r in missing),
    mature_no_P20_and_no_native_I20=sum(not r['native_I_within20']for r in missing),
    no_P_or_native_I20_but_max_close20_above20pct=sum(not r['native_I_within20']and r['first_B_max_close_return20_pct']>=20 for r in missing),
    native_I20_median_wait=float(np.median([r['native_I_wait_observations']for r in g if r['native_I_within20']]))if progress else None,
    median_price_progress_to_native_I_pct=float(np.median(progress))if progress else None))
 prows=[]
 for r in P:
  if r['state']!='A_I_never_started_in_E0':continue
  q=lookup[(r['window'],r['sid'],r['e0_run_start'])];i=q['first_original_I_active'];f=features[r['sid']]
  n=f.index.get_loc(pd.Timestamp(i))-f.index.get_loc(pd.Timestamp(r['day']))if i else None
  prows.append(dict(window=r['window'],sid=r['sid'],day=r['day'],native_I_day=i,native_I_wait_after_P=n,
   price_progress_P_to_native_I_pct=(float(f.loc[i,'close'])/r['close']-1)*100 if i else None))
 save('A_BREAKOUT_NATIVE_I_OVERLAP.json',rows);save('A_BREAKOUT_NATIVE_I_SUMMARY.json',summaries)
 save('A_PULLBACK_NATIVE_I_OVERLAP.json',prows)
 save('ACTIVATION_OVERLAP_SCOPE.json',dict(seconds=time.monotonic()-start,new_accounts=0,
  A_B_rows=len(rows),A_P_rows=len(prows),caveat='Native I authorization timing is not actual qualified intent, funding, fill or investment return. No supplemental P does not mean the additive policy blocks the unchanged old entry.'))
 save('ACTIVATION_OVERLAP_SOURCE_SHA256.json',SRC)
 print(json.dumps(summaries,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
