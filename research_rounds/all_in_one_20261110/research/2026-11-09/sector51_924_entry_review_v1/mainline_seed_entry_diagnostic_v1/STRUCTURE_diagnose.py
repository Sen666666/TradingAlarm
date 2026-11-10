from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import json,csv,hashlib,math
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
O=ROOT/'mainline_seed_entry_diagnostic_v1';B=ROOT/'mainline_m7_cash_batch_design_v6/once_20260630';X=ROOT/'mainline_m7_extended_capture_diagnostic_v1'
Z=D(0)
prior=json.loads((O/'OUTPUT_SEAL.json').read_text())
assert len(prior)==49 and all(hashlib.sha256((O/n).read_bytes()).hexdigest()==h for n,h in prior.items())
hashes={}
def rd(p):
 hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,x):
 (O/('STRUCTURE_'+n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
 if isinstance(x,list) and x:
  with (O/('STRUCTURE_'+n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
rows=rd(O/'FILLED_SEED_CLASSIFICATION.json');sector=rd(B/'SECTOR_DAILY.json');orders=rd(B/'ORDERS.json');events=rd(B/'EVENT_REGISTRY.json')
sd={(r['day'],r['sector51']):r for r in sector};days=sorted({r['day'] for r in sector});ix={d:i for i,d in enumerate(days)}
seeds={x['round_id']:x for x in orders if x['side']=='BUY_SEED'}
sectlist=sorted({r['sector51'] for r in sector})
def finite(x):return x is not None and math.isfinite(float(x))
def pos(x):return -1 if not finite(x) else int(x>0)
def AND(*a):return 0 if 0 in a else -1 if -1 in a else 1
def OR(*a):return 1 if 1 in a else -1 if -1 in a else 0
def group(s,f):
 if (s,f)==(1,0):return 'S_ONLY'
 if (s,f)==(0,1):return 'F_ONLY'
 if (s,f)==(1,1):return 'BOTH'
 if (s,f)==(1,-1):return 'S_TRUE_F_UNKNOWN'
 if (s,f)==(-1,1):return 'S_UNKNOWN_F_TRUE'
 return 'OTHER_OR_UNKNOWN'
def evidence(r):
 prev=sd.get((days[ix[r['day']]-1],r['sector51'])) if ix[r['day']] else None
 improve=-1 if not prev or not finite(prev['rs5']) or not finite(r['rs5']) else int(r['rs5']>prev['rs5'])
 majority=bool(finite(r['breakout20_count']) and 2*r['breakout20_count']>=r['N'])
 return dict(rs5_improve=improve,previous_rs5=prev['rs5'] if prev else None,majority_20d_breakout_established=majority,breakout20_count=r['breakout20_count'],breakout20_required=(r['N']+1)//2,
  F_majority_role='NECESSARY_FOR_CURRENT_M' if r['F']==1 and r['S']==0 else 'PRESENT_BUT_S_SUFFICIENT' if r['F']==r['S']==1 else 'F_TRUE_S_UNKNOWN' if r['F']==1 else 'F_NOT_ESTABLISHED',
  F_known_failed_other_components=[k for k,v in {'Q':r['Q'],'RS5_POSITIVE':pos(r['rs5']),'RS5_IMPROVE':improve,'RETURN5_POSITIVE':pos(r['return5_median'])}.items() if v==0],
  breakout_below_majority_not_assumed_false_without_coverage_K=not majority)
qa=Counter()
for r in sector:
 s=AND(r['Q'],pos(r['rs10']),pos(r['rs20']),pos(r['return10_median']))
 assert s==r['S'],('S',r)
 mm=OR(r['S'],r['F']);mm=-1 if mm==1 and not finite(r['rs5']) else mm
 assert mm==r['M'],('M',r);qa['S_AND_M_rows_exact']+=1
 ev=evidence(r)
 if r['F']==1:
  assert r['Q']==1 and pos(r['rs5'])==1 and pos(r['return5_median'])==1 and ev['majority_20d_breakout_established']
  if ix[r['day']]:assert ev['rs5_improve']==1
  qa['F_true_all_necessary_predicates_verified']+=1
 if ix[r['day']]:
  pp=sd[(days[ix[r['day']]-1],r['sector51'])]
  def half(n,u):return -1 if not finite(n) or not finite(u) else 1 if 2*n>=r['N'] else 0 if 2*(n+u)<r['N'] else -1
  q=AND(r['state'],half(r['n'],r['U']),half(pp['n'],pp['U']))
  assert q==r['Q'],('Q',r);qa['Q_rows_exact']+=1
# Current M episode classification is about the current event, not a new threshold.
def episode(day,sec,birth):
 posi=ix[day];j=posi
 while j>0 and days[j-1]>=birth and sd[(days[j-1],sec)]['M']==1:j-=1
 start=days[j];pday=days[j-1] if j else None
 # Do not use a prior event's M as earlier M of this event.
 earlier=[sd[(d,sec)] for d in days[:j] if d>=birth]
 had_M=any(x['M']==1 for x in earlier);unknown_seen=any(x['M']==-1 for x in earlier)
 boundary='EVENT_BIRTH' if start==birth else 'OBSERVATION_LEFT_BOUNDARY' if j==0 else 'M_FALSE' if sd[(pday,sec)]['M']==0 else 'M_UNKNOWN' if sd[(pday,sec)]['M']==-1 else 'PRE_EVENT_M_TRUE'
 if had_M:
  typ='RECOVERY_AFTER_KNOWN_M_FALSE' if boundary=='M_FALSE' else 'RECOVERY_AFTER_M_UNKNOWN' if boundary=='M_UNKNOWN' else 'RECOVERY_OTHER'
 elif birth<days[0]:typ='LEFT_CENSORED_EVENT_FIRST_OBSERVED_M'
 elif unknown_seen:typ='FIRST_KNOWN_M_WITH_PRIOR_UNKNOWN'
 else:typ='FIRST_M_IN_EVENT'
 return dict(M_episode_start=start,M_episode_boundary=boundary,M_episode_origin=typ,at_M_episode_first_close=day==start,earlier_M_same_event=had_M,prior_unknown_same_event=unknown_seen,episode_start_S=sd[(start,sec)]['S'],episode_start_F=sd[(start,sec)]['F'],episode_start_path=group(sd[(start,sec)]['S'],sd[(start,sec)]['F']))
classified=[]
for r in rows:
 if r['phase']!='MATURE':continue
 seed=seeds[r['round_id']];e=events[seed['event_id']];s=sd[(r['plan_day'],r['sector51'])]
 assert (r['S'],r['F'],r['M'])==(s['S'],s['F'],s['M']) and r['M']==1
 classified.append(dict(**r,event_id=seed['event_id'],event_birth_day=e['birth_day'],SF_path=group(s['S'],s['F']),**evidence(s),**episode(r['plan_day'],r['sector51'],e['birth_day'])))
assert len(classified)==833 and sum(r['seed_day']>'2024-11-06' for r in classified)==479
def summary(rs):
 return dict(rounds=len(rs),net=sum((D(r['net']) for r in rs),Z),gross_gains=sum((max(Z,D(r['net'])) for r in rs),Z),gross_losses=-sum((min(Z,D(r['net'])) for r in rs),Z),positive=sum(D(r['net'])>0 for r in rs),losing=sum(D(r['net'])<0 for r in rs),seed_cost=sum((D(r['seed_cost']) for r in rs),Z),no_add=sum(r['add_count']==0 for r in rs),top_winners=[{k:r[k] for k in ['round_id','name','sector51','plan_day','seed_day','net','SF_path','M_episode_origin']} for r in sorted(rs,key=lambda r:D(r['net']),reverse=True)[:5]])
paths=['S_ONLY','F_ONLY','BOTH','S_TRUE_F_UNKNOWN','S_UNKNOWN_F_TRUE']
cohorts=[('ALL',classified),('AFTER_1106',[r for r in classified if r['seed_day']>'2024-11-06']),('STARTUP_OPEN_0923_0930',[r for r in classified if '2024-09-23'<=r['seed_day']<='2024-09-30']),('OPEN_0924',[r for r in classified if r['seed_day']=='2024-09-24']),('PV_OPEN_1024',[r for r in classified if r['seed_day']=='2024-10-24' and r['sector51']=='光伏风电设备'])]
summaries=[];episodes=[];majorities=[]
for cohort,rs in cohorts:
 for state in ['ALL','CLOSED','OPEN']:
  state_rs=[r for r in rs if state=='ALL' or (not r['final_qty'])==(state=='CLOSED')]
  for path in paths:summaries.append(dict(cohort=cohort,state=state,path=path,**summary([r for r in state_rs if r['SF_path']==path])))
  for origin in sorted({r['M_episode_origin'] for r in rs}):
   for path in paths:
    aa=[r for r in state_rs if r['M_episode_origin']==origin and r['SF_path']==path]
    episodes.append(dict(cohort=cohort,state=state,origin=origin,path=path,**summary(aa)))
  for path in paths:
   for maj in [True,False]:
    aa=[r for r in state_rs if r['SF_path']==path and r['majority_20d_breakout_established']==maj]
    majorities.append(dict(cohort=cohort,state=state,path=path,majority_established=maj,**summary(aa)))
# All 954 new rounds: industry ranking is kept separate from the 479 MATURE subset.
late_all=[r for r in rows if r['seed_day']>'2024-11-06'];rank=[]
for sec in sectlist:
 a=[r for r in late_all if r['sector51']==sec]
 rank.append(dict(sector51=sec,all_954_rounds=len(a),all_954_net=sum((D(r['net']) for r in a),Z)))
rank.sort(key=lambda r:r['all_954_net']);worst=[r['sector51'] for r in rank[:10]]
sector_summary=[]
for rr in rank:
 sec=rr['sector51']
 for path in paths:
  a=[r for r in classified if r['seed_day']>'2024-11-06' and r['sector51']==sec and r['SF_path']==path]
  for state in ['ALL','CLOSED','OPEN']:
   b=[r for r in a if state=='ALL' or (not r['final_qty'])==(state=='CLOSED')]
   sector_summary.append(dict(**rr,path=path,state=state,**summary(b)))
# Verify current-trial exit applicability from actual final reasons, including MATURE/no ADD.
exit_groups=[]
for cohort,rs in cohorts[:2]:
 for add in ['NO_ADD','HAD_ADD']:
  a=[r for r in rs if (r['add_count']==0)==(add=='NO_ADD')]
  for why in sorted({r['exit_reason'] or 'OPEN_AT_END' for r in a}):
   b=[r for r in a if (r['exit_reason'] or 'OPEN_AT_END')==why]
   exit_groups.append(dict(cohort=cohort,add_class=add,exit_reason=why,**summary(b)))
# Three fixed time sequences use CLOSE features, and separately list next-OPEN actual new seeds.
sequences=[]
for label,sec,start,end in [('STARTUP_SOFTWARE','软件与IT服务','2024-09-19','2024-09-30'),('OCTOBER_PV','光伏风电设备','2024-10-18','2024-10-31'),('NOVEMBER_METALS','金属钢铁','2024-11-01','2024-11-15')]:
 for day in days:
  if not start<=day<=end:continue
  r=sd[(day,sec)];nextday=days[ix[day]+1] if ix[day]+1<len(days) else None
  aa=[x for x in rows if x['plan_day']==day and x['sector51']==sec]
  sequences.append(dict(sequence=label,close_day=day,sector51=sec,next_OPEN=nextday,**{k:r[k] for k in ['N','n','U','state','Q','S','F','M','E','rs5','rs10','rs20','return5_median','return10_median','breakout20_count']},**{k:v for k,v in evidence(r).items() if k!='breakout20_count'},next_OPEN_actual_seed_count=len(aa),next_OPEN_actual_phases=dict(Counter(x['phase'] for x in aa)),next_OPEN_actual_names=[x['name'] for x in aa],next_OPEN_actual_rounds=[x['round_id'] for x in aa]))
# Distinct current-event M episodes avoid conflating 60 simultaneous seed orders with 60 regime renewals.
episode_rows=[]
keys=sorted({(r['event_id'],r['M_episode_start']) for r in classified})
for eid,start in keys:
 a=[r for r in classified if r['event_id']==eid and r['M_episode_start']==start];r=a[0]
 episode_rows.append(dict(event_id=eid,sector51=r['sector51'],event_birth_day=r['event_birth_day'],start=start,origin=r['M_episode_origin'],start_S=r['episode_start_S'],start_F=r['episode_start_F'],start_path=r['episode_start_path'],first_actual_seed=min(x['seed_day'] for x in a),last_actual_seed=max(x['seed_day'] for x in a),actual_mature_rounds=len(a),late_actual_rounds=sum(x['seed_day']>'2024-11-06' for x in a),net=sum((D(x['net']) for x in a),Z)))
qa=dict(qa);qa.update(actual_mature_count=len(classified),late_mature_count=479,original_49_files_unchanged=True,S_F_directly_exported=True,F_false_unknown_not_reconstructed_without_breakout20_K=True,known_F_true_requires_majority_by_original_formula=True,filtered_strategy_or_portfolio_run=False,all_local_only=True)
for name,x in [('PRIOR_OUTPUT_SEAL',prior),('ENTRY_ROWS',classified),('PATH_SUMMARY',summaries),('EPISODE_SUMMARY',episodes),('MAJORITY_SUMMARY',majorities),('SECTOR_SUMMARY',sector_summary),('LATE_INDUSTRY_RANK',rank),('EXISTING_EXIT_SUMMARY',exit_groups),('THREE_SEQUENCES',sequences),('DISTINCT_M_EPISODES',episode_rows),('QA',qa),('SOURCE_HASHES',hashes)]:save(name,x)
print(json.dumps(dict(summary=[r for r in summaries if r['cohort'] in ['ALL','AFTER_1106','OPEN_0924','PV_OPEN_1024'] and r['state']=='ALL'],episodes=[r for r in episodes if r['cohort']=='AFTER_1106' and r['state']=='ALL' and r['rounds']],worst_industries=rank[:10],distinct_episode_counts=dict(Counter(r['origin']+'|'+r['start_path'] for r in episode_rows)),qa=qa),ensure_ascii=False,default=str))
