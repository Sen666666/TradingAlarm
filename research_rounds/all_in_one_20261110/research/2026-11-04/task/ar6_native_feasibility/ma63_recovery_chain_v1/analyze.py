from pathlib import Path
from collections import Counter
import json,hashlib,gzip,time
import pandas as pd
O=Path(__file__).resolve().parent;T=O.parents[1];B=T/'benchmark_2022_2023';P=T/'pvr_pool_feasibility/market_phase_2022_2023'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 t=time.monotonic();assert not(O/'RESULTS.json').exists(),'no automatic rerun'
 freeze=read(O/'SOURCE_FREEZE.json')
 for p,h in freeze['sources'].items():assert sha(p)==h,p
 signals=read(B/'logs/MA63_90_signals.json');h=pd.read_csv(B/'inputs/510300_history.csv',index_col=0);days=[s['day']for s in signals];pos={d:i for i,d in enumerate(days)};assert len(days)==484
 prior=h.loc[h.index<days[0]].iloc[-1];prevMA=float(prior.ma63);prevON=bool(prior.on);prevPrice=float(prior.signal_close);daily=[];episodes=[];ep=None
 def position(p,m):return 'ABOVE'if p>m else'BELOW'if p<m else'EQUAL'
 for i,s in enumerate(signals):
  d=s['day'];p=float(s['signal_close']);m=float(s['MA63']);on=bool(s['on']);assert p==float(h.loc[d,'signal_close'])and m==float(h.loc[d,'ma63'])and on==bool(h.loc[d,'on'])
  event=('START_ON'if on else'START_OFF')if i==0 else('UP_CROSS'if on else'DOWN_CROSS')if on!=prevON else'none'
  if event!='none':
   if ep is not None:ep['next_cross_day']=d;ep['right_censored']=False
   ep=dict(episode_id=f'E{len(episodes)+1:02d}',type='ON'if on else'OFF',start_kind=event,start_day=d,last_same_state_day=d,next_cross_day=None,right_censored=True,initial_left_censored=i==0,signal_days=[]);episodes.append(ep)
  ep['signal_days'].append(d);ep['last_same_state_day']=d
  slope=m-prevMA
  daily.append(dict(day=d,decision_close=d+' 15:10:00+08:00',signal_close=p,ma63=m,ma63_prior=prevMA,ma63_slope_1=slope,ma63_slope_direction='up'if slope>0 else'down'if slope<0 else'flat',on=on,prior_on_from_history=prevON,benchmark_simulator_prior_on=s['prior_on'],price_position=position(p,m),prior_price_position=position(prevPrice,prevMA),episode_id=ep['episode_id'],episode_type=ep['type'],on_episode_id=ep['episode_id']if on else None,cross_event=event,benchmark_next_market_OPEN=None if i+1==len(days)else days[i+1]+' 09:30:00+08:00'))
  prevMA=m;prevON=on;prevPrice=p
 for e in episodes:e['on_observations']=len(e['signal_days'])if e['type']=='ON'else 0
 save('DAILY.json',daily);pd.DataFrame(daily).to_csv(O/'DAILY.csv',index=False);save('ALL_EPISODES.json',episodes)
 save('CROSS_EVENTS.json',[r for r in daily if r['cross_event']!='none'])
 funnel=read(P/'FUNNEL_DAILY.json');benchfills=read(B/'logs/MA63_90_fills.json');policy={};restore=[]
 for label,path in freeze['native_books'].items():
  with gzip.open(path,'rt')as f:bk=json.load(f)
  cp={r['at'][:10]:r for r in bk['audit']if r['kind']=='risk_checkpoint'and r['at'][:10]in pos};assert len(cp)==484
  fd={r['day']:r['counts']for r in funnel[label]};assert list(fd)==days
  ex=read(P/(label+'_ACTUAL_EXECUTABLE_FILLS.json'));flatfills=[]
  for r in ex:
   for fill in r['actual_fills']:flatfills.append(dict(at=fill['at'],fill_day=fill['at'][:10],decision_day=r['signal_day'],sid=r['sid'],role=r['role'],budget_order=fill['budget_order'],shares=fill['shares'],original_factual_admission_proof=r['factual_same_time_signal_legal_quantity_and_cash_admission_proof']))
  flatfills.sort(key=lambda r:r['at']);newdays=[d for d in days if fd[d].get('planned_role_intents',0)>0]
  policy[label]=dict(cp=cp,funnel=fd,actual=flatfills,newdays=newdays)
  for q in cp.values():
   if q.get('event')=='resume':
    d=q['at'][:10];dec=next((a for a in newdays if a>=d),None);fill=next((a for a in flatfills if a['decision_day']>=d),None)
    restore.append(dict(policy=label,resume_CLOSE=q['at'],first_new_decision_CLOSE=None if dec is None else dec+' 15:10:00+08:00',first_fill=fill,resume_to_first_fill_sessions=None if fill is None else pos[fill['fill_day']]-pos[d],no_fill_right_censored=fill is None))
 save('ORIGINAL_RESUME_TO_FILL.json',restore)
 actcycles=[]
 for label,z in policy.items():
  active=None
  for d,q in z['cp'].items():
   if q.get('event')=='pause':active=dict(policy=label,pause_CLOSE=q['at'],first_flat_CLOSE=None,resume_CLOSE=None,right_censored=True)
   if active is not None:
    if q['flat']and active['first_flat_CLOSE']is None:active['first_flat_CLOSE']=q['at']
    if q.get('event')=='resume':active['resume_CLOSE']=q['at'];active['right_censored']=False;actcycles.append(active);active=None
  if active is not None:actcycles.append(active)
 save('ORIGINAL_ACT_PAUSE_CYCLES.json',actcycles)
 save('NATIVE_ACT_DAILY.json',{label:[{k:q.get(k)for k in ['at','on','flat','event','fast','breakout']}for q in z['cp'].values()]for label,z in policy.items()})
 chains=[]
 for e in episodes:
  start=e['start_day'];end=e['last_same_state_day'];group=set(e['signal_days']);nextop=daily[pos[start]]['benchmark_next_market_OPEN']
  for label,z in policy.items():
   current=z['cp'][start];res=next((q for d,q in z['cp'].items()if d>=start and q.get('event')=='resume'),None)
   dec=next((d for d in z['newdays']if d>=start),None);fill=next((q for q in z['actual']if q['decision_day']>=start),None)
   counts=sum((Counter(z['funnel'][d])for d in e['signal_days']),Counter())
   admitted=[q for q in z['actual']if q['decision_day']in group]
   row=dict(episode_id=e['episode_id'],type=e['type'],start_kind=e['start_kind'],start_day=start,last_same_state_day=end,next_cross_day=e['next_cross_day'],signal_observations=len(group),policy=label,original_ACT_at_start={k:current.get(k)for k in ['at','on','flat','event','fast','breakout']},original_ACT_events_inside=[{k:q.get(k)for k in ['at','on','flat','event']}for d,q in z['cp'].items()if d in group and q.get('event')],benchmark_next_OPEN=nextop,benchmark_first_proxy_fill_from_start_signal=next((q for q in benchfills if q['signal_day']==start),None),resume_needed_at_start=not current['on'],first_original_resume_after_start=None if res is None else res['at'],resume_within_episode=res is not None and res['at'][:10]in group,resume_delay_sessions=None if res is None else pos[res['at'][:10]]-pos[start],first_new_decision_CLOSE=None if dec is None else dec+' 15:10:00+08:00',first_decision_within_episode=dec in group,first_decision_delay_sessions=None if dec is None else pos[dec]-pos[start],first_actual_fill_from_new_decision=fill,first_fill_within_signal_episode=fill is not None and fill['decision_day']in group,first_fill_delay_sessions=None if fill is None else pos[fill['fill_day']]-pos[start],observed_no_resume_by_cutoff=res is None,raw_and_original_admission_counts=dict(counts),actual_original_fill_records_from_episode_decisions=len(admitted),counterfactual_executable_opportunities='UNKNOWN_NO_FULL_NATIVE_PREVIEW',no_new_policy_return=True)
   chains.append(row)
 save('ALL_EPISODE_NATIVE_CHAINS.json',chains)
 windows=[]
 for label,z in policy.items():
  for name,lo,hi in [('OPEN_Jun7_Jun17__decision_Jun6_Jun16','2022-06-06','2022-06-16'),('literal_CLOSE_Jun7_Jun17','2022-06-07','2022-06-17')]:
   ds=[d for d in days if lo<=d<=hi];windows.append(dict(policy=label,window=name,decision_days=ds,counts=dict(sum((Counter(z['funnel'][d])for d in ds),Counter())),counterfactual_executable_count=None,counterfactual_status='UNKNOWN_NOT_ZERO'))
 save('JUNE_DELAY_OPPORTUNITY_STRATA.json',windows)
 for p,hsh in freeze['sources'].items():assert sha(p)==hsh,p
 save('RESULTS.json',dict(passed=True,seconds=time.monotonic()-t,days=484,true_UP=sum(r['cross_event']=='UP_CROSS'for r in daily),true_DOWN=sum(r['cross_event']=='DOWN_CROSS'for r in daily),START_ON_separate=True,episodes=len(episodes),native_policies=2,new_accounts=0,new_signal_or_MA_calculations=0,new_native_previews=0,benchmark_execution_scope='EXISTING_RAW_DAILY_PROXY_NOT_VENUE_EXECUTION_CERTIFIED',no_automatic_followup=True))
if __name__=='__main__':main()
