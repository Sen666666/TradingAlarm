"""Same-source closing-price labels and within-date comparisons, no account replay."""
from pathlib import Path
import sys,json,gzip,time,collections
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;sys.path.insert(0,str(W/'q2-normal-continuation-20261031'));import continuation as E
J,L,IO=E.J,E.L,E.IO
N=J.W.load('opportunity_original_price_filter',W/'native-I-cache-interface-20261031/cache.py')
def read(p):return json.loads(Path(p).read_text())
def stream(p):
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def save(p,x):IO.write_json(p,J.T.norm(J.W.canon(J.T.norm(x))))
def main():
 t=time.monotonic();freeze=read(O/'CANDIDATE_FREEZE.json');data={x['window']:list(stream(O/x['window']/'CANDIDATES.jsonl.gz')) for x in freeze['windows']}
 for x in freeze['windows']:assert L.sha(O/x['window']/'CANDIDATES.jsonl.gz')==x['candidate_file_SHA256']
 save(O/'LABEL_FREEZE.json',dict(before_label_computation=True,candidate_freeze_SHA256=L.sha(O/'CANDIDATE_FREEZE.json'),code_SHA256=L.sha(__file__),protocol_SHA256=L.sha(O/'PROTOCOL.txt'),horizons=[21,63],MFE_tail=.3,new_account_paths=0))
 sm={r['symbol']:r for r in read(L.U/'STOCK_MANIFEST.json')};by=collections.defaultdict(list)
 for win,rs in data.items():
  for r in rs:by[r['sid']].append((win,r))
 labels={};price_audit=[]
 for k,(sid,points) in enumerate(sorted(by.items()),1):
  rec=sm[sid];path=next(p for p in rec['source_sha256'] if p.endswith('/signal.parquet'));assert L.sha(path)==rec['source_sha256'][path],'original signal changed'
  signal=pd.read_parquet(path);f=N.eligible_prices(signal);cached_full=pd.read_parquet(rec['refs']['facts'],columns=['close','segment_id']);cached=cached_full.loc[:rec['cache_through']];aligned=f.reindex(cached.index)
  assert np.array_equal(cached.close.to_numpy(),aligned.close.to_numpy(),equal_nan=True) and np.array_equal(cached.segment_id.to_numpy(),aligned.segment_id.to_numpy(),equal_nan=True),(sid,'same-source cached price prefix mismatch')
  dates=f.index;prices=f.close.to_numpy(float);segments=f.segment_id.to_numpy();lookup={str(d.date()):i for i,d in enumerate(dates)}
  for win,r in points:
   pos=lookup.get(r['day']);out={}
   for h in [21,63]:
    if pos is None:out[str(h)]=dict(valid=False,reason='anchor_missing');continue
    available=len(prices)-pos-1
    if available<h:out[str(h)]=dict(valid=False,reason='right_censored',available_observations=available,source_end=str(dates[-1].date()));continue
    if not np.all(segments[pos:pos+h+1]==segments[pos]):out[str(h)]=dict(valid=False,reason='source_segment_break');continue
    pathret=prices[pos+1:pos+h+1]/prices[pos]-1
    out[str(h)]=dict(valid=True,return_pct=float(pathret[-1]*100),MAE_pct=float(min(0.,pathret.min())*100),MFE_pct=float(max(0.,pathret.max())*100),right_tail_MFE30=bool(pathret.max()>=.3),end_day=str(dates[pos+h].date()),calendar_days=int((dates[pos+h]-dates[pos]).days))
   labels[win,r['sid'],r['day'],r['receipt']]=out
  price_audit.append(dict(sid=sid,path=path,SHA256=rec['source_sha256'][path],same_source_numeric_price_prefix_exact=True,cache_contract_through=rec['cache_through'],extra_reference_tail_not_used=len(cached_full)-len(cached),last_usable_observation=str(dates[-1].date()),valid_price_observations=len(f)))
  if k%300==0:print('LABEL_STOCKS',k,'of',len(by),round(time.monotonic()-t,2),flush=True)
 save(O/'PRICE_SOURCE_AUDIT.json',price_audit)
 for win,rs in data.items():IO.write_gzip_jsonl(O/win/'PRICE_LABELS.jsonl.gz',[dict(sid=r['sid'],day=r['day'],receipt=r['receipt'],labels=labels[win,r['sid'],r['day'],r['receipt']]) for r in rs])
 labelled_at=time.monotonic();print('LABELS_DONE',round(labelled_at-t,2),flush=True)
 def stats(win,rs,h):
  good=[];cens=collections.Counter()
  for r in rs:
   z=labels[win,r['sid'],r['day'],r['receipt']][str(h)]
   if z['valid']:good.append((r,z))
   else:cens[z['reason']]+=1
  result=dict(events=len(rs),unique_stocks=len({r['sid'] for r in rs}),candidate_dates=len({r['day'] for r in rs}),labelled_events=len(good),labelled_dates=len({r['day'] for r,z in good}),censored=dict(cens))
  if not good:return dict(result,event_mean_pct=None,event_median_pct=None,positive_fraction=None,mean_positive_pct=None,mean_negative_pct=None,MAE_mean_pct=None,MFE_mean_pct=None,right_tail_fraction=None,date_equal_mean_pct=None,daily={})
  a=np.array([z['return_pct'] for r,z in good]);daily=collections.defaultdict(list)
  for r,z in good:daily[r['day']].append(z)
  dm={d:dict(mean_pct=float(np.mean([z['return_pct'] for z in zs])),positive_fraction=float(np.mean([z['return_pct']>0 for z in zs])),right_tail_fraction=float(np.mean([z['right_tail_MFE30'] for z in zs])),events=len(zs)) for d,zs in daily.items()}
  return dict(result,event_mean_pct=float(a.mean()),event_median_pct=float(np.median(a)),positive_fraction=float(np.mean(a>0)),mean_positive_pct=float(a[a>0].mean()) if (a>0).any() else None,mean_negative_pct=float(a[a<0].mean()) if (a<0).any() else None,MAE_mean_pct=float(np.mean([z['MAE_pct'] for r,z in good])),MFE_mean_pct=float(np.mean([z['MFE_pct'] for r,z in good])),right_tail_fraction=float(np.mean([z['right_tail_MFE30'] for r,z in good])),date_equal_mean_pct=float(np.mean([z['mean_pct'] for z in dm.values()])),date_equal_positive_fraction=float(np.mean([z['positive_fraction'] for z in dm.values()])),date_equal_right_tail_fraction=float(np.mean([z['right_tail_fraction'] for z in dm.values()])),mean_calendar_days=float(np.mean([z['calendar_days'] for r,z in good])),daily=dm)
 def paired(left,right):
  days=sorted(set(left['daily'])&set(right['daily']));delta=[left['daily'][d]['mean_pct']-right['daily'][d]['mean_pct'] for d in days]
  return dict(common_dates=len(days),left_date_equal_mean_pct=float(np.mean([left['daily'][d]['mean_pct'] for d in days])) if days else None,right_date_equal_mean_pct=float(np.mean([right['daily'][d]['mean_pct'] for d in days])) if days else None,mean_same_day_difference_pct=float(np.mean(delta)) if delta else None,median_same_day_difference_pct=float(np.median(delta)) if delta else None,days_left_mean_higher_fraction=float(np.mean(np.array(delta)>0)) if delta else None)
 allsummary=[]
 for win,rows in data.items():
  for variant,rs in [('all_events',rows),('first_stock_attempt_within_window',[r for r in rows if r['first_stock_attempt_in_window']]),('first_complete_attempt',[r for r in rows if r['first_complete_attempt']])]:
   for h in [21,63]:
    market=stats(win,rs,h);qs={str(q):stats(win,[r for r in rs if r['quintile']==q],h) for q in range(1,6)};common=set.intersection(*(set(z['daily']) for z in qs.values()));qcompare=dict(common_dates=len(common),date_equal_means_pct={q:float(np.mean([v['daily'][d]['mean_pct'] for d in common])) if common else None for q,v in qs.items()},Q1_minus_Q5=paired(qs['1'],qs['5']))
    accounts={}
    for ref in ['B3','B_diag']:
     selected=stats(win,[r for r in rs if r[ref]['selected']],h);unselected=stats(win,[r for r in rs if not r[ref]['selected']],h);paused=stats(win,[r for r in rs if r[ref]['ACT_paused']],h);unpaused=stats(win,[r for r in rs if not r[ref]['ACT_paused']],h)
     accounts[ref]=dict(selected=selected,not_selected=unselected,matched_selected_minus_not=paired(selected,unselected),ACT_paused_candidates=paused,ACT_unpaused_candidates=unpaused,all_candidate_dates_without_any_confirmed_fill=len({r['day'] for r in rs}-{r['day'] for r in rs if r[ref]['selected']}),unselected_but_probe_mobile_funded_events=sum(not r[ref]['selected'] and r[ref]['probe_mobile_funded'] for r in rs),unselected_but_same_stock_core_funded_events=sum(not r[ref]['selected'] and r[ref]['same_stock_core_funded'] for r in rs))
    result=dict(window=win,variant=variant,horizon=h,market=market,H1_quintiles=qs,common_quintile_dates=qcompare,accounts=accounts);save(O/win/variant/f'SUMMARY_{h}.json',result);allsummary.append(result)
    if variant=='all_events' and h==21:print('MAIN21',win,'market',market['event_mean_pct'],market['event_median_pct'],'positive',market['positive_fraction'],'Q1-Q5',qcompare['Q1_minus_Q5'],'selection',{r:a['matched_selected_minus_not'] for r,a in accounts.items()},flush=True)
 save(O/'SUMMARY.json',allsummary);save(O/'COMPLETION.json',dict(readonly=True,new_account_paths=0,label_seconds=labelled_at-t,summary_seconds=time.monotonic()-labelled_at,total_seconds=time.monotonic()-t,candidates=sum(len(r) for r in data.values()),stocks=len(by),source_prices_not_new_model_calculations=True,no_policy_or_threshold_changes=True))
if __name__=='__main__':
 try:main()
 except BaseException as e:save(O/'LABEL_ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
