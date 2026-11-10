"""Read-only completed-run analysis. Future labels are post-hoc diagnostics only.
Never instantiate Account/Runner, invoke run_continuous, or change ranking.
"""
from pathlib import Path
from decimal import Decimal as D
from bisect import bisect_left
import argparse,gzip,json,hashlib,sys
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parent.parent
LABELS=ROOT.parent/'equal_entry_validation_v1/FIXED_ORIGINAL_I_ENTRY_LABELS.parquet'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False,default=str))
def analyze(run):
 run=Path(run).resolve();done=read(run/'DONE.json');assert done['completed'] is True,'No completed run: never analyze partial economics'
 pre=read(run/'PREDECLARED.json');assert pre['arms']==['PVR','E31'];assert pre['start']=='2022-01-01' and pre['end']=='2026-05-15'
 for p,h in pre['source_freeze'].items():assert sha(p)==h,('run source changed',p)
 ids=set(read(U/'FREEZE.json')['stocks']);assert len(ids)==1709
 with gzip.open(run/'pair/daily.jsonl.gz','rt')as f:daily=[json.loads(line)for line in f]
 by={a:{}for a in pre['arms']}
 for r in daily:
  day=r['at'][:10];a=r['account'];assert day not in by[a];by[a][day]=r
 assert set(by['PVR'])==set(by['E31']);days=sorted(by['PVR']);assert days[-1]==pre['end']
 assert all(set(r['positions'])<=ids for r in daily)
 # Read native immutable input context only. This constructs no account and computes no indicators.
 sys.path.insert(0,str(ROOT/'inputs'));import continuous_inputs as C
 _,market,_=C.J.M.context(pre['end'],ids=sorted(ids))
 marks={};max_inventory_gap=D(0)
 for day in days:
  at=C.J.M.N.iso(by['PVR'][day]['at']);held=set(by['PVR'][day]['positions'])|set(by['E31'][day]['positions'])
  prices={s:m.cny_price(at)for s,m in market.marks(at,held).items()};marks[day]=prices
  for a in by:
   r=by[a][day];inventory=sum((D(str(q))*prices[s]for s,q in r['positions'].items()),D(0))
   gap=abs(inventory-D(r['inventory']));max_inventory_gap=max(max_inventory_gap,gap)
   assert gap<D('1e-8'),('CLOSE inventory reconstruction',a,day,str(gap))
 # Label denominator is frozen original-I entry events, not E3 proposals and not all theoretical market opportunities.
 f=pd.read_parquet(LABELS);fixed=f[f.sid.isin(ids)].copy()
 recomputed=fixed.complete60.eq(True)&fixed.mfe60.ge(.30)&fixed.ret60.ge(.20)
 assert np.array_equal(recomputed.to_numpy(),fixed.big60.eq(True).to_numpy()),'big60 definition drift'
 big=fixed[recomputed].copy();assert not big.original_epoch.duplicated().any()
 events=[];excluded=[]
 for row in big.to_dict('records'):
  entry=str(row['entry_day'])[:10];sid=row['sid'];k=bisect_left(days,entry)
  if k>=len(days)or days[k]!=entry or k+6>len(days):
   excluded.append(dict(sid=sid,original_epoch=row['original_epoch'],entry_day=entry,reason='entry_not_on_run_calendar_or_fewer_than_6_remaining_dates'));continue
  window=days[k:k+6];result=dict(sid=sid,original_epoch=row['original_epoch'],signal_day=row['day'],entry_day=entry,entry_year=int(entry[:4]),window_end=window[-1],window_days=6,end_day60=row['end_day60'],mfe60=float(row['mfe60']),ret60=float(row['ret60']),labels_posthoc_only=True)
  for a in by:
   flags=[];weights=[];quantities=[]
   for d in window:
    rr=by[a][d];q=int(rr['positions'].get(sid,0));flags.append(q>0);quantities.append(q)
    weights.append(float(D(q)*marks[d][sid]/D(rr['nav']))if q else 0.)
   result.update({a+'_participated':any(flags),a+'_held_days':sum(flags),a+'_first_held_day':next((d for d,held in zip(window,flags)if held),None),a+'_early_mean_NAV_fraction':sum(weights)/6,a+'_early_max_NAV_fraction':max(weights),a+'_held_previous_close':bool(k and by[a][days[k-1]]['positions'].get(sid,0)>0),a+'_entry_close_shares':quantities[0]})
  result['comparison']='BOTH'if result['PVR_participated']and result['E31_participated']else 'E31_ONLY_ADDED'if result['E31_participated']else 'PVR_ONLY_LOST'if result['PVR_participated']else 'NEITHER'
  result['early_mean_NAV_fraction_difference']=result['E31_early_mean_NAV_fraction']-result['PVR_early_mean_NAV_fraction'];events.append(result)
 ev=pd.DataFrame(events);assert len(ev)>0
 annual=[]
 for year,g in list(ev.groupby('entry_year'))+[('ALL',ev)]:
  n=len(g);row=dict(entry_year=year,big_events=n,unique_stocks=int(g.sid.nunique()),both=int(g.comparison.eq('BOTH').sum()),E31_only_added=int(g.comparison.eq('E31_ONLY_ADDED').sum()),PVR_only_lost=int(g.comparison.eq('PVR_ONLY_LOST').sum()),neither=int(g.comparison.eq('NEITHER').sum()))
  for a in by:
   row.update({a+'_participated_events':int(g[a+'_participated'].sum()),a+'_participation_rate':float(g[a+'_participated'].mean()),a+'_mean_early_NAV_fraction_all_events':float(g[a+'_early_mean_NAV_fraction'].mean()),a+'_mean_held_days':float(g[a+'_held_days'].mean())})
  row['participation_rate_difference']=row['E31_participation_rate']-row['PVR_participation_rate'];row['mean_early_NAV_fraction_difference']=float(g.early_mean_NAV_fraction_difference.mean());annual.append(row)
 # Independent daily-NAV annual metrics, including initial NAV in running peak.
 original={(r['account'],int(r['year'])):r for r in read(run/'ANNUAL_METRICS.json')};checks=[]
 for a,rows in by.items():
  prev=D(str(pre['initial_cash_each']));assert prev>0
  for y in sorted({d[:4]for d in days}):
   rr=[rows[d]for d in days if d.startswith(y)];vals=np.array([float(prev)]+[float(r['nav'])for r in rr]);peak=np.maximum.accumulate(vals)
   v=dict(account=a,year=int(y),start_NAV=str(prev),end_NAV=rr[-1]['nav'],return_fraction=float(D(rr[-1]['nav'])/prev-1),max_drawdown_fraction=float(np.min(vals/peak-1)),mean_inventory_fraction=float(np.mean([float(D(r['inventory'])/D(r['nav']))for r in rr])),mean_stock_count=float(np.mean([len(r['positions'])for r in rr])),days=len(rr))
   old=original[(a,int(y))]
   for key in ['return_fraction','max_drawdown_fraction','mean_inventory_fraction','mean_stock_count']:assert abs(v[key]-old[key])<1e-12,(a,y,key)
   assert D(v['start_NAV'])==D(old['start_NAV'])and D(v['end_NAV'])==D(old['end_NAV'])and v['days']==old['days']
   v['matches_run_ANNUAL_METRICS']=True;checks.append(v);prev=D(rr[-1]['nav'])
 # Full-period risk and capital recovery, independent of annual resets.
 overall=[]
 for a,rows in by.items():
  initial=D(str(pre['initial_cash_each']));values=[initial]+[D(rows[d]['nav'])for d in days]
  peak=initial;worst=D(0);peak_day='INITIAL';worst_peak='INITIAL';trough=None;chain=longest=0
  for d,v in zip(days,values[1:]):
   if v>=peak:peak=v;peak_day=d;chain=0
   else:chain+=1;longest=max(longest,chain)
   dd=v/peak-1
   if dd<worst:worst=dd;worst_peak=peak_day;trough=d
  overall.append(dict(account=a,initial_NAV=str(initial),final_NAV=str(values[-1]),total_return_fraction=float(values[-1]/initial-1),full_period_MDD_fraction=float(worst),drawdown_peak_day=worst_peak,drawdown_trough_day=trough,first_strictly_above_initial=next((d for d in days if D(rows[d]['nav'])>initial),None),longest_underwater_observed_sessions=longest,days_below_initial=sum(D(rows[d]['nav'])<initial for d in days),mean_inventory_fraction=float(np.mean([float(D(rows[d]['inventory'])/D(rows[d]['nav']))for d in days]))))
 save(O/'FULL_PERIOD_METRICS.json',overall)
 ev.to_csv(O/'BIG60_EVENT_PARTICIPATION.csv',index=False)
 ev[ev.comparison.isin(['E31_ONLY_ADDED','PVR_ONLY_LOST'])].to_csv(O/'BIG60_ADDED_LOST.csv',index=False)
 pd.DataFrame(annual).to_csv(O/'BIG60_ANNUAL_PARTICIPATION.csv',index=False)
 pd.DataFrame(checks).to_csv(O/'ANNUAL_METRICS_RECHECK.csv',index=False)
 save(O/'BIG60_EXCLUDED.json',excluded)
 inputs={str(p):sha(p)for p in [run/'DONE.json',run/'PREDECLARED.json',run/'pair/daily.jsonl.gz',run/'ANNUAL_METRICS.json',LABELS,U/'FREEZE.json',Path(__file__)]}
 summary=dict(status='PASS_COMPLETED_RUN_POSTHOC_ANALYSIS',account_runs=0,fixed_pool=1709,common_dates=len(days),frozen_fixed_pool_entry_labels=len(fixed),frozen_fixed_pool_big60_events=len(big),included_events=len(ev),excluded_events=len(excluded),max_reconstructed_inventory_gap=str(max_inventory_gap),annual_metric_checks=len(checks),overall=overall,annual=annual,input_sha256=inputs,definitions=dict(participation='Positive actual proxy-ledger daily closing position on >=1 of first6 shared run sessions starting frozen entry_day; includes pre-existing holdings.',early_NAV_fraction='Mean over those6 dates of actual shares * same native CLOSE mark / account NAV, zeros included. Event-average, not portfolio aggregate.',added_lost='Difference in event participation, not necessarily new purchases or strategy returns.',future_labels='complete60, mfe60>=.30, ret60>=.20 are post-hoc labels only, never ranking inputs.'),limitations=['No intraday occupancy inference; daily closing positions only.','Fixed original-I event label denominator is inherited, not exhaustive PIT market opportunities.','Canonical label price domain may differ from native account raw price domain; labels identify events only.','Events may overlap for the same stock: average event weights must not be summed as portfolio exposure.','Proxy fills/holdings are not real-world fills; original fixed future pool and preknown corporate-action assumptions remain.'])
 save(O/'SUMMARY.json',summary)
 for p,h in inputs.items():assert sha(p)==h,('analysis input changed',p)
 save(O/'OUTPUT_SHA256.json',{p.name:sha(p)for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})
 print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,default=ROOT/'run_1200000');args=ap.parse_args();analyze(args.run)
