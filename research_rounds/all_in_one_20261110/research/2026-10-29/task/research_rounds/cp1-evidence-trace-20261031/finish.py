"""Bounded read-only six-path logic checks and existing behavior joins; no accounts."""
from pathlib import Path
import sys,json,gzip,time,math,hashlib,importlib.util,collections
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
T=load('cp1_trace_finish_original',O/'trace.py')
def save(n,x):T.save(n,x)
def read(p):return json.loads(Path(p).read_text())
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def ramp(a,b,n):return np.linspace(a,b,n+1)[1:]
def make_paths():
 warm=100*np.exp(.0003*np.arange(150)+.002*np.sin(np.arange(150)*math.pi/3));p=warm[-1]
 startup=ramp(p,1.2*p,20);pull=ramp(startup[-1],1.1*p,8)
 failure=np.r_[startup,pull,ramp(pull[-1],.75*p,60)]
 recover=np.r_[failure[:52],ramp(failure[51],1.3*p,60)]
 tails=dict(slow_no_pullback=p*np.exp(.0015*np.arange(1,121)),single_jump_flat=np.repeat(1.1*p,120),
  lower_highs_lows=np.r_[ramp(p,1.4*p,20),ramp(1.4*p,1.16*p,10),ramp(1.16*p,1.32*p,12),ramp(1.32*p,1.12*p,10),ramp(1.12*p,1.27*p,12),ramp(1.27*p,1.08*p,10),ramp(1.08*p,1.22*p,12)],
  normal_pullback_advance=np.r_[startup,pull,ramp(pull[-1],1.3*p,60)],start_continuous_failure=failure,failure_recovery=recover)
 for k,v in tails.items():tails[k]=np.r_[v,np.repeat(v[-1],120-len(v))]
 return warm,tails
def synth():
 # Freeze exact arrays before invoking original model. No path edits after outputs.
 warm,tails=make_paths();freeze=dict(warm=list(warm),tails={k:list(v) for k,v in tails.items()},constant_volume=1e6,constant_amount=1e8,
  no_policy_actions=True,third_stage_note='Only mechanical reachability: two receipts after episode opening could permit two promotions; not actual stage controller.')
 save('SIX_PATHS_INPUT_FROZEN',freeze)
 sys.path.insert(0,str(RR/'pv-participation-response-20261020/code'));N=load('cp1_synth_native_numeric',RR/'pv-participation-response-20261020/code/numeric.py');P=load('cp1_synth_native_participation',RR/'pv-participation-response-20261020/code/participation.py')
 sys.path.insert(0,str(RR/'pv-strength-b5-20261025/code'));B=load('cp1_synth_original_b5',RR/'pv-strength-b5-20261025/code/policy.py')
 def calc(c):
  ix=pd.bdate_range('2025-01-02',periods=len(c));op=np.r_[c[0],c[:-1]];bars=pd.DataFrame(dict(open=op,high=np.maximum(op,c),low=np.minimum(op,c),close=c,volume=1e6),index=ix)
  ev=N.event_frame_numeric(bars.close,bars.volume,joint=True,event_exit=False);st,_=P.participation_frame(bars,ev,mode='volume');f=bars.copy();f['segment_id']=0;f['valid_price_observation']=True;f['price_observation']=np.arange(len(f));f['event']=ev.event;f['confirmed_pivot_price']=ev.confirmed_pivot_price;f['ready']=st.ready;f['previous_close']=f.close.shift();f['volume_baseline']=f.volume.shift().rolling(21,min_periods=21).median()
  for k in ['volume_ratio','declined','high_effort']:f[k]=st[k]
  f['decline_candidate']=False;f['candidate_lower']=np.nan;f['candidate_reclaim']=np.nan;e,_=B.e0_policy(f)
  # With constant volume no volume-decline memory exists, exact old policy equivalence.
  assert np.array_equal(e.target.to_numpy(dtype=int),st.target.to_numpy(dtype=int));np.testing.assert_allclose(e.floor.astype(float),st.floor,equal_nan=True,rtol=0,atol=0)
  q=pd.DataFrame(dict(close=c,amount=1e8,segment_id=0,e0_valid=e.target.astype(bool),e0_down=ev.event.eq(-1),i_floor=e.floor.astype(float)),index=ix);z=T.M.calculate(q)
  return ev,e,q,z
 summary=[];allrows=[];results={}
 for name,tail in tails.items():
  ev,e,f,z=calc(np.r_[warm,tail]);results[name]=(ev,e,f,z);ep=(e.target.eq(1)&e.target.shift(fill_value=0).ne(1)).cumsum();records=[];third=[]
  for eid,g in e.groupby(ep):
   active=g.index[g.target.eq(1)]
   if not len(active):continue
   opened=active[0];rs=[d for d in active if bool(z.loc[d,'receipt']) and d>opened and d>=f.index[150]]
   if rs:
    records.append(dict(episode=int(eid),opened=str(opened.date()),last_active=str(active[-1].date()),receipts=[str(d.date()) for d in rs],receipt_count=len(rs)))
    if len(rs)>=2:third.append(dict(episode=int(eid),two_postopening_receipts_by=str(rs[1].date()),tail_observation=int(f.index.get_loc(rs[1])-149)))
  rr,_,_=T.trace('SYNTH6:'+name,f,z,ev,e.target.astype(bool))
  rr=[r for r in rr if r['confirmed_day']>=str(f.index[150].date())]
  table=f.join(ev[['event','confirmed_pivot_price']]).join(z[['receipt','candidate','anchor','scale','credit','delta_frontier','reset_reason']]);table['E0_episode']=ep;table['path']=name;table['tail_observation']=np.arange(len(f))-149;table.to_parquet(O/f'SYNTH6_{name}.parquet')
  allrows.extend(dict(path=name,**r) for r in rr);summary.append(dict(path=name,tail_receipts=int(z.receipt.iloc[150:].sum()),tail_positive_events=int(ev.event.iloc[150:].eq(1).sum()),tail_negative_events=int(ev.event.iloc[150:].eq(-1).sum()),tail_E0_openings=int((e.target.eq(1)&e.target.shift(fill_value=0).ne(1)).iloc[150:].sum()),episodes=records,mechanical_third_stage=third,old_E0_policy_exact=True))
 # The same data prefix must have the same E0 and CP1, before knowing branch.
 prefixes=[]
 for a,b,nt in [('normal_pullback_advance','start_continuous_failure',28),('failure_recovery','start_continuous_failure',52)]:
  for j in [0,1,3]:pd.testing.assert_frame_equal(results[a][j].iloc[:150+nt],results[b][j].iloc[:150+nt],check_exact=True)
  ev,e,f,z=calc(np.r_[warm,tails[a]][:150+nt]);pd.testing.assert_frame_equal(z,results[a][3].iloc[:150+nt],check_exact=True,check_freq=False)
  prefixes.append(dict(path_a=a,path_b=b,common_tail_observations=nt,full_output_equal=True,physical_cutoff_equal=True))
 save('SIX_PATHS_RESULTS',summary);save('SIX_PATHS_RECEIPTS',allrows);save('SIX_PATHS_PREFIX',prefixes)
 return summary
def behavior():
 B=W/'behavior-contract-20261031';cases=[c for c in read(B/'CANDIDATES_PENDING_REVIEW.json') if 'sector' in c];meta=read(RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json');ids=read(W/'native-I-cache-interface-20261031/FREEZE.json')['stocks'];pool={c['sector']:[s for s in ids if meta[s]['sector_id']==c['sector']] for c in cases};stocks=sorted(set(sum(list(pool.values()),[])));native={s:pd.read_parquet(W/'native-I-cache-interface-20261031/facts'/f'{s}.parquet') for s in stocks};orig=RR/'continuous-protection-lines-20261028/signals';coverage=[];cp={}
 for s in stocks:
  p=orig/f'{s}.parquet';fact=T.COM.PREP/'facts'/f'{s}.parquet';has=p.exists() and fact.exists()
  coverage.append(dict(sid=s,sector=meta[s]['sector_id'],name=meta[s]['name'],original_CP1_cache=p.exists(),original_fullwarm_facts=fact.exists(),usable_original_CP1=has,native_I_first=str(native[s].index.min().date()) if len(native[s]) else None))
  if has:cp[s]=pd.read_parquet(p)
 daily=read(B/'DAILY_CASE_BEHAVIOR.json');receipts=read(O/'RECEIPTS.json');books={p:obj(W/'mainline-forward-Q1-20261031'/p/'results/T3.json.gz') for p in ['RAW','ATT']};out=[];joined=[]
 for case in cases:
  ss=pool[case['sector']];rlist=[r for r in receipts if r['canonical_series']==case['sector'] and case['start']<=r['confirmed_day']<=case['end']];fx=pd.read_parquet(W/'mainline-absolute-Q4-20261031/industry-facts'/f"{case['sector']}.parquet");same=0;later=0;unknown=0
  for r in rlist:
   d=pd.Timestamp(r['confirmed_day']);ep=r['original_E0_episode_id'];following=[x['confirmed_day'] for x in receipts if x['canonical_series']==case['sector'] and x['confirmed_day']>r['confirmed_day']];next_r=min(following) if following else None
   candidates=fx.index[(fx.index>=d)&(fx.index<=pd.Timestamp(case['end']))];valid=[]
   for day in candidates:
    if next_r and day>=pd.Timestamp(next_r):break
    if not bool(fx.loc[day,'e0_target']):break
    valid.append(day)
   raw=lambda day:[s for s in ss if day in native[s].index and bool(native[s].loc[day,'i_buy']) and bool(native[s].loc[day,'i_target'])]
   raw_same=raw(d);first_raw=next(((str(day.date()),raw(day)) for day in valid if raw(day)),None)
   stockcp=[s for s in ss if s in cp and d in cp[s].index and bool(cp[s].loc[d,'receipt'])]
   pols=['RAW'] if case['quarter']=='2025Q3' else ['RAW','ATT'];actual=[]
   for pol in pols:
    intent_by={dd['at'][:10]:[i for i in dd['intents'] if i['sid'] in ss] for dd in books[pol]['decisions'] if case['start']<=dd['at'][:10]<=case['end']}
    first_intent=next(((str(day.date()),intent_by.get(str(day.date()),[])) for day in valid if intent_by.get(str(day.date()))),None)
    dr=next(x for x in daily if x['review_id']==case['review_id'] and x['policy']==('COMMON_Q3' if case['quarter']=='2025Q3' else pol) and x['day']==r['confirmed_day'])
    actual.append(dict(policy='COMMON_Q3' if case['quarter']=='2025Q3' else pol,same_day_postQ_intents=intent_by.get(r['confirmed_day'],[]),first_postQ_intent_in_authorization_interval=first_intent,current_industry_weight=dr['sector_NAV_weight'],actual_buy_cash_that_day=dr['actual_buy_cash'],stage_upgrade_implemented=False))
   same+=bool(raw_same);later+=first_raw is not None;unknown+=len(ss)-sum(s in cp for s in ss)
   joined.append(dict(review_id=case['review_id'],industry=case['industry'],industry_receipt_id=r['receipt_id'],confirmed_day=r['confirmed_day'],formation_start=r['formation_start_exclusive'],candidate=r['original_candidate'],same_day_rawI_symbols=raw_same,same_day_stock_CP1_known_positive=stockcp,stock_CP1_covered=len([s for s in ss if s in cp]),stock_CP1_unknown=len([s for s in ss if s not in cp]),first_rawI_in_authorization_interval=first_raw,next_industry_receipt=next_r,interval_end=str(valid[-1].date()) if valid else None,endpoint_note='case quarter/next industry receipt/E0 invalid; later across quarter unknown, not declared illegal',behavior=actual))
  out.append(dict(review_id=case['review_id'],industry=case['industry'],pool_stocks=len(ss),industry_receipts=len(rlist),same_day_rawI_receipts=same,within_interval_rawI_receipts=later,full_pureQ_overlap='unknown; rawI is candidate upper layer, original postQ intents are observed account-dependent lower layer',stock_CP1_cached=sum(s in cp for s in ss),stock_CP1_missing=sum(s not in cp for s in ss)))
 save('CASE_STOCK_CP1_COVERAGE',coverage);save('CASE_RECEIPT_BEHAVIOR',joined);save('CASE_RECEIPT_SUMMARY',out)
 return out,coverage
if __name__=='__main__':
 t=time.monotonic();s=synth();print('SIX_PATHS',json.dumps([dict(path=x['path'],receipts=x['tail_receipts'],potential_third=len(x['mechanical_third_stage'])) for x in s]),flush=True);b,c=behavior();save('FINISH_VERIFICATION',dict(passed=True,seconds=time.monotonic()-t,no_new_economic_paths=True,six_paths_frozen_before_calculation=True,case_unique_stocks=len(c),stock_CP1_available=sum(x['usable_original_CP1'] for x in c),case_summaries=b));print('DONE',round(time.monotonic()-t,3),json.dumps(b,ensure_ascii=False),flush=True)
