"""Fixed weekly as-of diagnostic from frozen labels; no execution engine import."""
from pathlib import Path
from decimal import Decimal as D
from datetime import date,timedelta
import pandas as pd,numpy as np
import json,gzip,hashlib,time,collections,csv
O=Path(__file__).resolve().parent;W=O.parent;P=W/'opportunity-quality-ranking-20261031'
WINDOWS={'2022':('2022-01-01','2022-12-31'),'2025_26':('2025-07-01','2026-06-30')}
def read(p):return json.loads(Path(p).read_text())
def stream(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def enc(x):
 if isinstance(x,D):return str(x)
 if hasattr(x,'item'):return x.item()
 raise TypeError(type(x).__name__)
def save(name,x):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=enc)+'\n');t.replace(p)
def monday(s):
 d=date.fromisoformat(s);return (d-timedelta(days=d.weekday())).isoformat()
def add(s,n):return (date.fromisoformat(s)+timedelta(days=n)).isoformat()
def group(v):return 'unknown' if v is None else 'positive' if v>0 else 'negative' if v<0 else 'zero'
def mean(xs):return float(np.mean(xs)) if xs else None
def stats(rs,clock,future=False):
 # Include every candidate before evaluating availability.
 valid=[x for x in rs if x['label']['valid']];daily=collections.defaultdict(list)
 for x in valid:daily[x['day'] if clock=='authorization' else x['label']['end_day']].append(x)
 ret=[x['label']['return_pct'] for x in valid];byindustry=collections.Counter(x['sector'] for x in rs);bystock=collections.Counter(x['sid'] for x in rs)
 out=dict(events=len(rs),stocks=len(bystock),industries=len(byindustry),labelled=len(valid),censored=len(rs)-len(valid),effective_dates=len(daily),mean=mean([mean([x['label']['return_pct'] for x in a]) for a in daily.values()]),event_mean=mean(ret),event_median=float(np.median(ret)) if ret else None,positive_fraction=mean([mean([x['label']['return_pct']>0 for x in a]) for a in daily.values()]),event_positive_mean=mean([x for x in ret if x>0]),event_negative_mean=mean([x for x in ret if x<0]),top3_industry_event_share=sum(n for _,n in byindustry.most_common(3))/len(rs) if rs else None,max_stock_event_share=max(bystock.values())/len(rs) if rs else None)
 if future:out['right_tail_fraction']=mean([mean([x['label']['right_tail_MFE30'] for x in a]) for a in daily.values()])
 return out

def main():
 started=time.monotonic();im=read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json');src=next(p for p in im[0]['source_sha256'] if p.endswith('/signal.parquet'));assert sha(src)==im[0]['source_sha256'][src]
 frame=pd.read_parquet(src,columns=['observed_bar','price_eligible','synthetic_event_bar']);valid=frame.observed_bar&frame.price_eligible&~frame.synthetic_event_bar;calendar=[str(d.date()) for d in frame.index[valid]];weekdays=collections.defaultdict(list)
 for d in calendar:weekdays[monday(d)].append(d)
 marketpath=W/'mainline-absolute-Q4-20261031/recovery.csv';market=pd.read_csv(marketpath,index_col=0,parse_dates=True);mi={str(d.date()):j for j,d in enumerate(market.index)};mp=market.market.to_numpy();daysource={src:sha(src),str(marketpath):sha(marketpath),str(O/'PROTOCOL.txt'):sha(O/'PROTOCOL.txt'),str(Path(__file__)):sha(__file__)}
 for win,(lo,hi) in WINDOWS.items():
  original=stream(P/win/'CANDIDATES.jsonl.gz');labels={(x['sid'],x['day'],x['receipt']):x['labels']['21'] for x in stream(P/win/'PRICE_LABELS.jsonl.gz')}
  for r in original:r['label']=labels[r['sid'],r['day'],r['receipt']]
  for f in ['CANDIDATES.jsonl.gz','PRICE_LABELS.jsonl.gz']:daysource[str(P/win/f)]=sha(P/win/f)
  base='2022-normal-reference-20261031' if win=='2022' else 'q2-normal-continuation-20261031';root=W/base/'runs/B_diag/pair';daily=stream(root/'daily.jsonl.gz');ds={r['at'][:10]:r for r in daily}
  with gzip.open(root/'B.json.gz','rt') as h:book=json.load(h)
  for f in ['daily.jsonl.gz','B.json.gz']:daysource[str(root/f)]=sha(root/f)
  expect={d for d in calendar if lo<=d<=hi};assert set(ds)==expect,'full market/actual-account date mismatch';assert {d for d in mi if lo<=d<=hi}==expect,'original market clock calendar mismatch'
  rows=[];boundary=[];first=monday(lo);last=monday(hi);weeks=[];week=first
  while week<=last:weeks.append(week);week=add(week,7)
  for week in weeks:
   sessions=weekdays.get(week,[])
   if not sessions:boundary.append(dict(week=week,reason='no_market_session_no_checkpoint'));continue
   t=sessions[-1]
   if not lo<=t<=hi:boundary.append(dict(week=week,actual_last_market_session=t,reason='true_week_checkpoint_outside_fixed_window',in_window_sessions=[d for d in sessions if lo<=d<=hi]));continue
   nw=add(week,7);nextsessions=weekdays.get(nw,[]);nextend=add(nw,6);truncated=not (lo<=nw and nextend<=hi)
   # Calendar weekend outside the window is harmless if all next-week market sessions lie inside.
   if nextsessions:truncated=any(not lo<=d<=hi for d in nextsessions)
   else:truncated=not (lo<=nw and nextend<=hi)
   account=ds[t];trades=[x for x in book['trades'] if x['side']=='buy' and week<=x['at'][:10]<=t];jb={x['layer']:x for x in book['journal'] if x['kind']=='real_buy_fill'};cash=sum((D(x['gross_cny'])+D(x['fees_cny']) for x in trades),D(0));cc=sum((D(x['gross_cny'])+D(x['fees_cny']) for x in trades if jb[x['layer']]['role']=='mobile' and jb[x['layer']]['pool']=='confirmed'),D(0))
   j=mi[t];previous=[i for i,d in enumerate(market.index) if str(d.date())<week][-1];marketweekly=(mp[j]/mp[previous]-1)*100;mr21=(mp[j]/mp[j-21]-1)*100 if j>=21 else None
   for variant in ['all_events','first_new_attempt']:
    universe=original if variant=='all_events' else [r for r in original if r['first_complete_attempt']]
    known=[r for r in universe if r['label']['valid'] and week<=r['label']['end_day']<=t]
    future=[r for r in universe if nw<=r['day']<=nextend]
    assert all(r['day']<r['label']['end_day']<=t for r in known)
    assert all(r['day']>t for r in future)
    assert not {(r['sid'],r['day'],r['receipt']) for r in known}&{(r['sid'],r['day'],r['receipt']) for r in future}
    k=stats(known,'maturity');f=stats(future,'authorization',True);known_group=group(k['mean']);futurestatus='future_week_truncated' if truncated else 'no_market_session' if not nextsessions else 'no_candidates' if not future else 'label_unavailable' if not f['labelled'] else 'partly_censored' if f['censored'] else 'complete'
    rows.append(dict(window=win,variant=variant,week_start=week,checkpoint=t,next_week_start=nw,next_week_end=nextend,next_week_market_sessions=len(nextsessions),future_week_truncated=truncated,future_status=futurestatus,main_comparison_eligible=futurestatus=='complete',known_group=known_group,known=k,future=f,known_max_end=max((r['label']['end_day'] for r in known),default=None),future_min_authorization=min((r['day'] for r in future),default=None),future_max_label_end=max((r['label']['end_day'] for r in future if r['label']['valid']),default=None),known_inherited_events=sum(r['attempt_inherited'] for r in known),future_inherited_events=sum(r['attempt_inherited'] for r in future),market_week_return_pct=marketweekly,market_R21_asof_pct=mr21,market_R21_asof_group=group(mr21),Bdiag_NAV=account['nav'],Bdiag_exposure_pct=float(D(account['inventory'])/D(account['nav'])*100),Bdiag_ACT_on=account['on'],Bdiag_week_all_new_buy_cash=cash,Bdiag_week_confirmed_mobile_new_buy_cash=cc))
  allrows=rows
  save(Path(win)/'WEEKLY.json',allrows);save(Path(win)/'CALENDAR_BOUNDARIES.json',boundary)
  flat=[]
  for r in allrows:
   rr={k:v for k,v in r.items() if k not in ['known','future']}
   for key in ['known','future']:rr.update({key+'_'+a:b for a,b in r[key].items()})
   flat.append(rr)
  dest=O/win/'WEEKLY.csv'
  with dest.open('w') as h:
   writer=csv.DictWriter(h,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
  print('WEEKS',win,'checkpoints',len(allrows)//2,'calendar boundaries',boundary,flush=True)
  summary=[]
  for variant in ['all_events','first_new_attempt']:
   rr=[r for r in allrows if r['variant']==variant];use=[r for r in rr if r['main_comparison_eligible']]
   for mgroup in ['all','positive','negative','zero','unknown']:
    scoped=rr if mgroup=='all' else [r for r in rr if r['market_R21_asof_group']==mgroup]
    for kg in ['positive','negative','zero','unknown']:
     whole=[r for r in scoped if r['known_group']==kg];valid=[r for r in whole if r['main_comparison_eligible']];ys=[r['future']['mean'] for r in valid];absolute=sum(abs(x) for x in ys);top=sorted((abs(x) for x in ys),reverse=True)
     summary.append(dict(window=win,variant=variant,market_asof_group=mgroup,known_group=kg,total_checkpoints=len(whole),complete_future_weeks=len(valid),future_status_counts=dict(collections.Counter(r['future_status'] for r in whole)),known_mean_week_equal=mean([r['known']['mean'] for r in whole if r['known']['mean'] is not None]),future_return_mean_week_equal=mean(ys),future_return_median_week=float(np.median(ys)) if ys else None,future_positive_week_fraction=mean([x>0 for x in ys]),future_tail_daily_then_week_equal=mean([r['future']['right_tail_fraction'] for r in valid]),future_events=sum(r['future']['events'] for r in valid),future_unique_stocks_in_week_sum=sum(r['future']['stocks'] for r in valid),asof_exposure_mean=mean([r['Bdiag_exposure_pct'] for r in whole]),asof_market_R21_mean=mean([r['market_R21_asof_pct'] for r in whole if r['market_R21_asof_pct'] is not None]),max_week_absolute_mean_share=top[0]/absolute if absolute else None,top3_weeks_absolute_mean_share=sum(top[:3])/absolute if absolute else None))
   print('MAIN',win,variant,[{k:r[k] for k in ['known_group','total_checkpoints','complete_future_weeks','future_return_mean_week_equal','future_return_median_week','future_tail_daily_then_week_equal','asof_market_R21_mean']} for r in summary if r['variant']==variant and r['market_asof_group']=='all'],flush=True)
  save(Path(win)/'SUMMARY.json',summary)
  excluded=dict(frozen_candidates=len(original),inherited_candidate_events=sum(r['attempt_inherited'] for r in original),inherited_stock_attempt_first_unknown=sum(r['first_stock_attempt_in_window'] and r['attempt_inherited'] for r in original),first_new_attempt_events=sum(r['first_complete_attempt'] for r in original),new_attempt_followup_excluded_from_first_variant=sum(not r['attempt_inherited'] and not r['first_stock_attempt_in_window'] for r in original),source_authorization_window_left_truncated=True,actual_checkpoint_count=len(allrows)//2,first_checkpoint=allrows[0]['checkpoint'],last_checkpoint=allrows[-1]['checkpoint'])
  save(Path(win)/'DENOMINATORS.json',excluded)
 save('FREEZE.json',dict(source_SHA256=daysource,predeclared_horizon=21,thresholds='natural sign only',new_account_paths=0));save('COMPLETION.json',dict(readonly=True,new_account_paths=0,new_model_calculations=0,seconds=time.monotonic()-started));print('DONE',round(time.monotonic()-started,3),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
