"""Bounded all-market I-root first-signal five-quote response, no accounts."""
from pathlib import Path
from collections import defaultdict,Counter
from fractions import Fraction
from decimal import Decimal as D
import bisect,csv,hashlib,json,math
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
E=O.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
SOURCES={};CACHE={}
VIEWS={'2022_weak':('2022-01-04','2022-12-30','2022_2024'),
       '2024_recovery':('2024-09-02','2024-11-29','2022_2024'),
       'strong':('2025-07-01','2026-06-30','strong')}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);SOURCES[str(p)]=sha(p);return json.loads(p.read_text())
def save(name,x):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def lines(p):
 p=Path(p);SOURCES[str(p)]=sha(p)
 with p.open() as f:return [json.loads(s) for s in f]
def csvsave(name,rows):
 if not rows:return
 with (O/name).open('x') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sign(x):return 'NO_MATURE_DATA' if x is None else 'positive' if x>0 else 'negative' if x<0 else 'zero'
def wquant(points,q):
 if not points:return None
 b=defaultdict(Fraction)
 for value,weight in points:b[value]+=weight
 total=sum(b.values(),Fraction());threshold=q*total;cum=Fraction()
 for value,weight in sorted(b.items()):
  cum+=weight
  if cum>=threshold:return float(value)
 raise AssertionError('quantile')
def weighted_stats(events_by_day):
 nonempty={d:z for d,z in events_by_day.items() if z};B=len(nonempty);N=sum(len(z) for z in nonempty.values())
 if not B:return dict(batch_count=0,events=0,median=None,positive_fraction=None,p10=None,negative_mean=None,mean=None,effective_weighted_events=None,max_event_weight=None,min_batch_size=None,max_batch_size=None,delayed_events=0,max_signal_to_maturity_sessions=None)
 points=[];negative_num=0.;negative_w=Fraction();positive=Fraction();mean=0.;squares=Fraction();maxw=Fraction();ages=[];delayed=0
 for day,z in nonempty.items():
  weight=Fraction(1,B*len(z))
  for e in z:
   r=e['return5'];points.append((r,weight));mean+=float(weight)*r;squares+=weight*weight;maxw=max(maxw,weight)
   if r>0:positive+=weight
   if r<0:negative_num+=float(weight)*r;negative_w+=weight
   ages.append(e['signal_to_maturity_market_sessions']);delayed+=bool(e['no_trade_days'])
 return dict(batch_count=B,events=N,median=wquant(points,Fraction(1,2)),positive_fraction=float(positive),p10=wquant(points,Fraction(1,10)),negative_mean=negative_num/float(negative_w) if negative_w else None,mean=mean,effective_weighted_events=1/float(squares),max_event_weight=float(maxw),min_batch_size=min(map(len,nonempty.values())),max_batch_size=max(map(len,nonempty.values())),delayed_events=delayed,max_signal_to_maturity_sessions=max(ages))

def main():
 protocol=read(O/'PROTOCOL.json');assert protocol['status'].startswith('frozen')
 sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 native=read(E/'first_entry_regime/native_state/SOURCE_MANIFEST.json');mp=Path(native['original_ACT_source_path']);assert sha(mp)==native['original_ACT_source_sha256'];SOURCES[str(mp)]=sha(mp)
 market=pd.read_csv(mp,index_col=0,parse_dates=True);assert market.index.is_unique and market.index.is_monotonic_increasing
 calendar=[str(d.date()) for d in market.index];ix={d:j for j,d in enumerate(calendar)};calindex=pd.to_datetime(calendar)
 signals=lines(O/'input_readiness/SIGNALS.jsonl');assert len(signals)==25407 and len({e['signal_id'] for e in signals})==len(signals)
 assert not any(e['left_censored_root'] for e in signals)
 context=read(O/'account_context/DAILY_ACCOUNT_CONTEXT.json')
 # The context is not consulted by market-event selection, labels or aggregation.
 if isinstance(context,dict):
  contextrows=context.get('rows',context.get('daily',[]));assert contextrows
 else:contextrows=context
 context_by_date={}
 for r in contextrows:
  d=str(r.get('day',r.get('date',r.get('at'))))[:10];context_by_date[d]=r

 def quotes(sid):
  if sid in CACHE:return CACHE[sid]
  m=sm[sid];paths=[p for p in m['source_sha256'] if p.endswith('/signal.parquet')];assert len(paths)==1;path=Path(paths[0]);assert sha(path)==m['source_sha256'][str(path)];SOURCES[str(path)]=sha(path)
  cols=['close','amount','volume','observed_bar','synthetic_event_bar','source_invalid','price_eligible','volume_eligible','segment_id']
  f=pd.read_parquet(path,columns=cols);assert f.index.is_unique and f.index.is_monotonic_increasing
  present=calindex.isin(f.index);g=f.reindex(calindex)
  a={k:g[k].to_numpy(float) for k in ['close','amount','volume','segment_id']}
  flags={k:g[k].eq(True).to_numpy(bool) for k in ['observed_bar','synthetic_event_bar','source_invalid','price_eligible','volume_eligible']}
  code=np.full(len(calendar),2,dtype=np.int8) #2 missing quote: never silently skip.
  obs=present&flags['observed_bar']&~flags['synthetic_event_bar'];code[present]=3
  price=obs&~flags['source_invalid']&np.isfinite(a['close'])&(a['close']>0);code[obs]=4
  notrade=price&np.isfinite(a['amount'])&np.isfinite(a['volume'])&(a['amount']>=0)&(a['volume']>=0)&((a['amount']==0)|(a['volume']==0));code[notrade]=1
  p=price&flags['price_eligible']&~notrade;code[p]=5
  valid=p&flags['volume_eligible']&np.isfinite(a['amount'])&np.isfinite(a['volume'])&(a['amount']>0)&(a['volume']>0);code[valid]=0
  a.update(code=code,source=str(path),source_sha256=SOURCES[str(path)]);CACHE[sid]=a;return a

 def label(event,last_index):
  e={k:event[k] for k in ['signal_id','window','day','sid','sector','union_signal_kind','original_I_root','original_I_root_start','source_segment','evaluation_window']}
  q=quotes(e['sid']);s=ix[e['day']];segment=float(e['source_segment']);valid=[];notrade=[];bad=None;badcode=None;maturity=None;r=None
  if q['code'][s]!=0 or not math.isfinite(q['segment_id'][s]) or q['segment_id'][s]!=segment:
   bad=s;badcode='SIGNAL_QUOTE_NOT_VALID_'+str(int(q['code'][s]))
  else:
   for j in range(s+1,last_index+1):
    c=int(q['code'][j])
    if not math.isfinite(q['segment_id'][j]) or q['segment_id'][j]!=segment:
     #Missing quote remains missing, not a made-up domain reset.
     bad=j;badcode='MISSING_QUOTE' if c==2 else 'PRICE_DOMAIN_UNKNOWN_OR_CHANGED';break
    if c==1:notrade.append(calendar[j]);continue
    if c!=0:bad=j;badcode={2:'MISSING_QUOTE',3:'NOT_OBSERVED_OR_SYNTHETIC',4:'INVALID_SOURCE_PRICE',5:'UNKNOWN_TRADE_QUOTE'}[c];break
    valid.append(calendar[j])
    if len(valid)==5:maturity=j;r=float(q['close'][j]/q['close'][s]-1);break
  earlier=np.flatnonzero((q['code'][:s]==0)&(q['segment_id'][:s]==segment))[-20:]
  amounts=q['amount'][earlier]
  e.update(signal_close=None if bad==s else float(q['close'][s]),signal_amount=None if bad==s else float(q['amount'][s]),prior20_valid_amount_count=len(earlier),prior20_amount_median=float(np.median(amounts)) if len(earlier)==20 else None,
   valid_close_days=valid,no_trade_days=notrade,first_bad_day=None if bad is None else calendar[bad],first_bad_reason=badcode,
   maturity_day=None if maturity is None else calendar[maturity],return5=r,
   signal_to_maturity_market_sessions=None if maturity is None else maturity-s,
   quote_source=q['source'],quote_source_sha256=q['source_sha256'],
   source_max_used_day=calendar[maturity if maturity is not None else bad if bad is not None else last_index],
   final_status='MATURED' if maturity is not None else 'SIGNAL_QUOTE_UNKNOWN' if bad==s else 'HORIZON_AMBIGUOUS' if bad is not None else 'RIGHT_CENSORED_NOT_FIVE',label_observation_end=calendar[last_index])
  return e

 viewevents={};daily_by_view={};future_by_view={};summary={};prefixchecks=[]
 for view,(lo,hi,sourcewin) in VIEWS.items():
  first,last=ix[lo],ix[hi];tail=min(last+5,len(calendar)-1)
  source=[e for e in signals if e['window']==sourcewin and e['day']<=hi]
  ev=[label(e,tail) for e in source];byid={e['signal_id']:e for e in ev};mature=defaultdict(list);issued=defaultdict(list)
  for e in ev:
   issued[e['day']].append(e)
   if e['maturity_day'] is not None:mature[e['maturity_day']].append(e)
  rows=[]
  for j in range(first,last+1):
   day=calendar[j];batchdays=calendar[max(0,j-4):j+1];batches={d:mature.get(d,[]) for d in batchdays};stats=weighted_stats(batches)
   scoped=[e for e in ev if lo<=e['day']<=day];states=Counter()
   for e in scoped:
    if e['maturity_day'] is not None and e['maturity_day']<=day:states['matured']+=1
    elif e['first_bad_day'] is not None and e['first_bad_day']<=day:states['signal_unknown' if e['first_bad_day']==e['day'] else 'horizon_ambiguous']+=1
    else:states['not_yet_five']+=1
   newest=max((d for d,z in batches.items() if z),default=None)
   row=dict(view=view,day=day,lookback_first=batchdays[0],lookback_last=day,**stats,feedback_state=sign(stats['median']),new_mature_events=len(mature.get(day,[])),new_signal_events=len(issued.get(day,[])),latest_batch_day=newest,information_age_market_sessions=None if newest is None else j-ix[newest],scope_issued_to_date=len(scoped),scope_matured_to_date=states['matured'],scope_pending_to_date=states['not_yet_five'],scope_horizon_ambiguous_to_date=states['horizon_ambiguous'],scope_signal_unknown_to_date=states['signal_unknown'])
   row['market_R5_asof']=None if j<5 else float(market.market.iloc[j]/market.market.iloc[j-5]-1)
   row['market_R5_state']=sign(row['market_R5_asof'])
   rows.append(row)
  #Outcome-only next-session comparison, kept separate from the as-of series.
  future=[]
  for row in rows:
   j=ix[row['day']];nd=calendar[j+1] if j+1<len(calendar) else None
   target=[] if nd is None or nd>hi else [e for e in issued.get(nd,[]) if lo<=e['day']<=hi]
   known=[e for e in target if e['return5'] is not None]
   fs=weighted_stats({nd:known}) if known else weighted_stats({})
   future.append(dict(view=view,asof_day=row['day'],feedback_state=row['feedback_state'],market_R5_state=row['market_R5_state'],target_signal_day=nd,status='OUTSIDE_TARGET_WINDOW' if nd is None or nd>hi else 'NO_TARGET_SIGNALS' if not target else 'NO_EVALUABLE_TARGETS' if not known else 'PARTIAL_TARGET_LABELS' if len(known)<len(target) else 'COMPLETE',target_events=len(target),target_evaluable=len(known),target_missing=len(target)-len(known),future_cohort_median=fs['median'],future_cohort_positive_fraction=fs['positive_fraction'],future_cohort_p10=fs['p10'],evaluation_only=True))
  statesummary={}
  for state in ['positive','negative','zero','NO_MATURE_DATA']:
   z=[x for x in future if x['feedback_state']==state];v=[x for x in z if x['future_cohort_median'] is not None]
   statesummary[state]=dict(asof_days=len(z),evaluable_future_days=len(v),future_statuses=dict(Counter(x['status'] for x in z)),target_events=sum(x['target_events'] for x in z),target_evaluable=sum(x['target_evaluable'] for x in z),target_missing=sum(x['target_missing'] for x in z),mean_next_cohort_median=None if not v else float(np.mean([x['future_cohort_median'] for x in v])),median_next_cohort_median=None if not v else float(np.median([x['future_cohort_median'] for x in v])),mean_next_positive_fraction=None if not v else float(np.mean([x['future_cohort_positive_fraction'] for x in v])),mean_next_p10=None if not v else float(np.mean([x['future_cohort_p10'] for x in v])))
  rng=np.random.default_rng(20261104);diffs=[];N=len(future);numblocks=math.ceil(N/5)
  for _ in range(1000):
   starts=rng.integers(0,N,size=numblocks);sample=[future[(int(s)+k)%N] for s in starts for k in range(5)][:N]
   p=[x['future_cohort_median'] for x in sample if x['feedback_state']=='positive' and x['future_cohort_median'] is not None];n=[x['future_cohort_median'] for x in sample if x['feedback_state']=='negative' and x['future_cohort_median'] is not None]
   if p and n:diffs.append(float(np.mean(p)-np.mean(n)))
  scoped=[e for e in ev if lo<=e['day']<=hi]
  strata=[]
  for marketstate in ['positive','negative','zero']:
   for feedback in ['positive','negative','zero','NO_MATURE_DATA']:
    z=[x for x in future if x['market_R5_state']==marketstate and x['feedback_state']==feedback and x['future_cohort_median'] is not None]
    strata.append(dict(market_R5_state=marketstate,feedback_state=feedback,days=len(z),mean_future_cohort_median=None if not z else float(np.mean([x['future_cohort_median'] for x in z]))))
  summary[view]=dict(days=N,scope_first_signals=len(scoped),including_warmup_first_signals=len(ev),label_tail_end=calendar[tail],label_status_counts=dict(Counter(e['final_status'] for e in scoped)),matured_by_analysis_end=sum(e['maturity_day'] is not None and e['maturity_day']<=hi for e in scoped),matured_in_fixed_tail=sum(e['maturity_day'] is not None and e['maturity_day']>hi for e in scoped),no_trade_delayed_events=sum(bool(e['no_trade_days']) for e in scoped),feedback_days=dict(Counter(x['feedback_state'] for x in rows)),next_day_groups=statesummary,positive_minus_negative_bootstrap95=None if not diffs else [float(np.quantile(diffs,.025)),float(np.quantile(diffs,.975))],valid_bootstrap_resamples=len(diffs),market_asof_strata=strata,
   capacity=dict(signal_amount_quantiles=np.quantile([e['signal_amount'] for e in scoped if e['signal_amount'] is not None],[.1,.5,.9]).tolist() if any(e['signal_amount'] is not None for e in scoped) else None,prior20_amount_known=sum(e['prior20_amount_median'] is not None for e in scoped),actual_fillability_or_capacity_not_verified=True))
  viewevents[view]=ev;daily_by_view[view]=rows;future_by_view[view]=future
  save(Path(view)/'EVENTS.json',ev);save(Path(view)/'DAILY_FEEDBACK.json',rows);save(Path(view)/'EVALUATION_ONLY_NEXT_DAY.json',future);csvsave(Path(view)/'DAILY_FEEDBACK.csv',rows);csvsave(Path(view)/'EVALUATION_ONLY_NEXT_DAY.csv',future)
  print('FIVE_CLOSE_VIEW',view,json.dumps(summary[view],ensure_ascii=False),flush=True)
  #Actual source prefixes for all events contributing to selected checkpoints.
  for checkpoint in sorted({lo,calendar[min(first+5,last)],calendar[(first+last)//2],hi}):
   cj=ix[checkpoint];used=[e for e in ev if e['maturity_day'] is not None and calendar[max(0,cj-4)]<=e['maturity_day']<=checkpoint]
   prefix=[label(next(e for e in source if e['signal_id']==old['signal_id']),cj) for old in used]
   assert all(a['maturity_day']==b['maturity_day'] and a['return5']==b['return5'] and b['source_max_used_day']<=checkpoint for a,b in zip(used,prefix))
   a=weighted_stats({d:[e for e in used if e['maturity_day']==d] for d in calendar[max(0,cj-4):cj+1]});b=weighted_stats({d:[e for e in prefix if e['maturity_day']==d] for d in calendar[max(0,cj-4):cj+1]});assert a==b
   tampered=[dict(e,return5=999. if i%2 else -999.) if e['maturity_day'] is not None and e['maturity_day']>checkpoint else e for i,e in enumerate(ev)]
   c=weighted_stats({d:[e for e in tampered if e['maturity_day']==d] for d in calendar[max(0,cj-4):cj+1]});assert c==a
   prefixchecks.append(dict(view=view,checkpoint=checkpoint,real_event_prefixes=len(prefix),prefix_quote_cutoff_exact=True,future_label_perturbation_exact=True))

 #Join account facts only after market construction, without selecting events.
 joined=[]
 for view,rs in daily_by_view.items():
  for r in rs:
   c=context_by_date.get(r['day']);assert c is not None,(view,r['day'])
   joined.append(dict(market_feedback=r,original_account=c))
 save('MARKET_AND_ACCOUNT_DAILY.json',joined)
 save('SUMMARY.json',summary);save('PREFIX_CHECKS.json',dict(passed=True,checks=prefixchecks,scope='Physical date-index quote cutoff for all used events at12 checkpoints, plus all-future-label tamper. Not full independent recalculation; reviewer separately checks source and prefix cases.'))
 save('SOURCE_MANIFEST.json',dict(sources=SOURCES,script_sha256=sha(__file__),stock_quote_sources=len(CACHE),account_events=0,new_models=0,new_signals=0,new_policy=0))
 print('FIVE_CLOSE_COMPLETE',len(joined),'days',len(CACHE),'stockquote sources',flush=True)

if __name__=='__main__':main()
