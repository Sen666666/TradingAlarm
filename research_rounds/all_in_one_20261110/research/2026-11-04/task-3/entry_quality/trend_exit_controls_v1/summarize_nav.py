"""Direct NAV/transaction summaries; no layer accounting reconstruction."""
from pathlib import Path
from decimal import Decimal as D,getcontext
import gzip,json,csv
import numpy as np
getcontext().prec=60
O=Path(__file__).resolve().parent
PERIODS={'full_2022_2024':('2022-01-01','2024-12-31'),'bear2022':('2022-01-01','2022-12-31'),'year2023':('2023-01-01','2023-12-31'),'year2024':('2024-01-01','2024-12-31'),'from924':('2024-09-24','2024-12-31'),'after1008':('2024-10-09','2024-12-31'),'strong':('2025-07-01','2026-06-30')}
def main():
 out=[]
 for arm in json.loads((O/'STATE_MACHINE_FREEZE.json').read_text())['active_arms']:
  for window in ['2022_2024','strong']:
   p=O/'runs'/arm/window;assert json.loads((p/'DONE.json').read_text())['completed']
   with gzip.open(p/'pair/daily.jsonl.gz','rt') as f:rr=[json.loads(x) for x in f]
   with gzip.open(p/'pair/B.json.gz','rt') as f:book=json.load(f)
   vv=np.array([float(x['nav']) for x in rr]);globalpeak=np.maximum.accumulate(np.r_[1e6,vv])[1:]
   for name,(lo,hi) in PERIODS.items():
    ix=[j for j,x in enumerate(rr) if lo<=x['at'][:10]<=hi]
    if not ix:continue
    start=D(rr[ix[0]-1]['nav']) if ix[0] else D(1000000);end=D(rr[ix[-1]]['nav']);vals=vv[ix];peak=np.maximum.accumulate(np.r_[float(start),vals])[1:]
    ts=[t for t in book['trades'] if lo<=t['at'][:10]<=hi]
    out.append(dict(arm=arm,window=window,period=name,first_day=rr[ix[0]]['at'][:10],last_day=rr[ix[-1]]['at'][:10],days=len(ix),starting_NAV=start,ending_NAV=end,wealth_change=end-start,return_pct=(end/start-1)*100,max_local_drawdown_pct=float(np.max(1-vals/peak))*100,max_since_account_start_drawdown_pct=float(np.max(1-vals/globalpeak[ix]))*100,mean_exposure_pct=float(np.mean([float(rr[j]['inventory'])/float(rr[j]['nav']) for j in ix]))*100,trade_count=len(ts),buy_count=sum(t['side']=='buy' for t in ts),sell_count=sum(t['side']=='sell' for t in ts),fees=sum((D(t['fees_cny']) for t in ts),D(0)),gross_turnover=sum((D(t['gross_cny']) for t in ts),D(0))))
 for x in out:
  base=next(y for y in out if y['arm']=='BASELINE' and y['period']==x['period']);x.update(wealth_change_difference_vs_base=x['wealth_change']-base['wealth_change'],ending_NAV_difference_vs_base=x['ending_NAV']-base['ending_NAV'],return_pct_difference_vs_base=x['return_pct']-base['return_pct'],local_DD_difference_pp=x['max_local_drawdown_pct']-base['max_local_drawdown_pct'])
 (O/'NAV_SUMMARY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
 with (O/'NAV_SUMMARY.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
 for name in PERIODS:
  print(name,[(x['arm'],round(float(x['wealth_change']),2),round(float(x['return_pct']),3),round(x['max_local_drawdown_pct'],3),round(float(x['wealth_change_difference_vs_base']),2)) for x in out if x['period']==name])
if __name__=='__main__':main()
