"""Read frozen ACT-only logs. No imports of account engines, no economic replay."""
from pathlib import Path
import json, gzip, hashlib, time
from collections import Counter, defaultdict
import pandas as pd
import numpy as np

R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=R/'act_candidate_funnel_v1'
A=R/'act_only_ablation_continuous_v1'
P=A/'run/pair'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
OLD=R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1'
PERIODS={'ALL':('2022-01-01','2026-05-15'),'2022':('2022-01-01','2022-12-31'),'2024':('2024-01-01','2024-12-31'),'2024_0920_1015':('2024-09-20','2024-10-15'),'2026Jan':('2026-01-01','2026-01-31')}
ARMS=['PVR','NOACT']
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def rows(p):
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def csv(n,x):pd.DataFrame(x).to_csv(O/n,index=False)
begun=time.monotonic()
inputs=[P/f'{x}.jsonl.gz' for x in ['opportunities','funding','daily','industry','rank-policy']]+[P/f'{a}.json.gz' for a in ARMS]+[A/'analysis/STOCK_ROUNDS.csv',A/'analysis/LAYER_ATTRIBUTION.csv',A/'analysis/REPORT_FINAL_v2.md',A/'run/PREDECLARED.json',A/'run/DONE.json',A/'run/OUTPUT_HASHES.json',U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',OLD/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',OLD/'DOMAIN_SOURCE_SHA256.json',OLD/'reconstruct_domain.py']
before={str(p):sha(p) for p in inputs}
assert read(A/'run/DONE.json')['completed']
assert not (A/'run/FAILURE.json').exists()
hashcheck=read(A/'run/OUTPUT_HASHES.json')
print('FREEZE_KEYS',type(hashcheck).__name__,str(hashcheck)[:150],flush=True)
# The original published hash map is independently verified, without invoking any runner.
for k,v in hashcheck.items():
 p=Path(k) if Path(k).is_absolute() else A/'run'/k
 assert p.exists(),str(p)
 assert sha(p)==v,('frozen raw output changed',p)
dump('CONTRACT.json',dict(arms=ARMS,periods=PERIODS,account_runs=0,indicator_runs=0,source=A.as_posix(),native_birth_definition='stock + first e0_target 0->1 within segment; forward fill only within that segment while e0_target is on; identical to joint_v3.py 190-194; NOT original-I big60',period_clock='stock-day, role and funnel statistics use signal close date; actual entry clock also separately reported',unknown='No economic return assigned to untraded candidate. Missing trace stages UNKNOWN. Raw overlapping reasons separate from exclusive stage categories.',fixed_future_pool=1709,industry_count=90,rank_policy='PVR_SLOT1 original unique-stock slot permutation; no TopK cutoff; same-stock core before mobile',descriptive_only=True))

# Dates, ACT policy state, and held/exit state from the real close ledger.
daily={};days=[]
for d in rows(P/'daily.jsonl.gz'):
 day=d['at'][:10];daily[(d['account'],day)]=(d['on'],set(d['positions']),set(d['pending_sells']))
 if d['account']=='PVR':days.append(day)
assert len(days)==1054 and len(set(days))==1054
dayidx={d:i for i,d in enumerate(days)};prev={days[i]:days[i-1] for i in range(1,len(days))};nextday={days[i]:days[i+1] for i in range(len(days)-1)}
dayperiod={d:[p for p,(lo,hi) in PERIODS.items() if lo<=d<=hi] for d in days}

# Industry authorization is original state data, not a new breadth gate.
sector={};auxfreeze={}
for m in read(U/'INDUSTRY_MANIFEST.json'):
 p=Path(m['refs']['state']);auxfreeze[str(p)]=sha(p)
 assert auxfreeze[str(p)]==m['output_sha256'][str(p)]
 f=pd.read_parquet(p,columns=['day','E0_valid','attempt_id','stage'])
 for q in f[f.day.isin(days)].itertuples(index=False):sector[(m['series'],q.day)]=bool(q.E0_valid and pd.notna(q.attempt_id) and q.stage>0)
assert len(sector)==90*len(days)

# Reproduce the already-frozen native birth labels from facts, not from price outcomes.
birthlookup={};birthnames={0:'UNKNOWN'};birthinfo={};eid=0
for no,m in enumerate(read(U/'STOCK_MANIFEST.json')):
 p=Path(m['refs']['facts']);auxfreeze[str(p)]=sha(p)
 assert auxfreeze[str(p)]==m['output_sha256'][str(p)]
 f=pd.read_parquet(p,columns=['segment_id','e0_target']).loc[:days[-1]]
 on=f.e0_target.fillna(False).astype(bool);opening=on & ~on.groupby(f.segment_id).shift(fill_value=False)
 z=pd.Series(0,index=f.index,dtype=np.int32)
 for d in f.index[opening]:
  eid+=1;z.loc[d]=eid;name=m['symbol']+':'+str(d.date());birthnames[eid]=name;birthinfo[eid]=(m['symbol'],str(d.date()),int(f.loc[d,'segment_id']))
 z=z.mask(z.eq(0)).groupby(f.segment_id).ffill().where(on,0).fillna(0).astype(np.int32)
 birthlookup[m['symbol']]=z.reindex(pd.DatetimeIndex(days),fill_value=0).to_numpy()
 if (no+1)%500==0:print('BIRTHS',no+1,round(time.monotonic()-begun,1),flush=True)
reversebirth={v:k for k,v in birthnames.items()}

rounds=pd.read_csv(A/'analysis/STOCK_ROUNDS.csv')
layers=pd.read_csv(A/'analysis/LAYER_ATTRIBUTION.csv')
initial={(r.account,int(r.id)) for r in layers[layers.initial_layer.eq(True)].itertuples()}
for r in layers.itertuples():
 assert birthnames[birthlookup[r.sid][dayidx[str(r.signal_at)[:10]]]]==r.birth_event,('native birth mismatch',r.account,r.id)
pending={};buys={};actual=[];rankkeys=set();actual_first_ids=set()
for arm in ARMS:
 a=json.load(gzip.open(P/f'{arm}.json.gz','rt'))
 for d in a['decisions']:
  for i in d['intents']:
   key=(arm,d['at'][:10],i['sid'],i['role']);assert key not in pending
   pending[key]=(i['cap'],float(i['budget']),i['priority_rank'],i.get('PVR_score'),i.get('CP1_id'))
 for t in a['trades']:
  if t['side']!='buy':continue
  role='mobile' if t['kind']=='add' else 'core';sig=t['signal_at'][:10];key=(arm,sig,t['security_id'],role)
  assert key not in buys;first=(arm,int(t['layer'])) in initial
  buys[key]=(first,t['at'][:10],t['shares'],float(t['gross_cny'])+float(t['fees_cny']))
  if first:actual_first_ids.add((arm,int(t['layer'])))
  actual.append(dict(account=arm,signal_day=sig,entry_day=t['at'][:10],sid=t['security_id'],role=role,first_entry=first,layer=int(t['layer']),shares=t['shares'],buy_cost=float(t['gross_cny'])+float(t['fees_cny']),native_birth=birthnames[birthlookup[t['security_id']][dayidx[sig]]]))
 del a
assert actual_first_ids==initial
for r in rows(P/'rank-policy.jsonl.gz'):
 for role in r['roles']:
  key=(r['account'],r['day'],r['sid'],role);assert key in pending
  assert pending[key][2]==r['priority_rank'];rankkeys.add(key)
assert rankkeys==set(pending)

# The close's earliest execution is the next shared trading open. No date-window
# inference is used to invent fills: all fills match actual signal_at and layer.
fund=defaultdict(list);rawfund=Counter();reserved_stocks=set()
for r in rows(P/'funding.jsonl.gz'):
 close=r['at'][11:16]=='15:10';signal=r['at'][:10] if close else prev.get(r['at'][:10])
 assert signal is not None
 key=(r['account'],signal,r['sid'],r['role']);fund[key].append(('CLOSE' if close else 'OPEN',r['result']))
 if not close:assert key in pending,('unmatched funding',key)
 if r['result']=='reserved':reserved_stocks.add(key[:3])
 for period in dayperiod[signal]:rawfund[(r['account'],period,'CLOSE' if close else 'OPEN',r['role'],r['result'])]+=1

counts=Counter();eventsets=defaultdict(set);reasons=Counter();exclusive=Counter();roledata=[];scount=Counter();oppcounts=Counter();seenbuys=set();seenpending=set();qualunknown=Counter()
def stage(arm,day,name,sid,birth):
 for period in dayperiod[day]:
  counts[(arm,period,name)]+=1
  if birth:eventsets[(arm,period,name)].add(birth)
def terminal_for(key,planned):
 fs=fund.get(key,[]);openresults=[v for phase,v in fs if phase=='OPEN'];closeresults=[v for phase,v in fs if phase=='CLOSE']
 if key in buys:return 'ACTUAL_FIRST_ENTRY' if buys[key][0] else 'ACTUAL_HELD_ADD'
 if planned:
  if 'reserved' in openresults:return 'RESERVED_NO_FILL'
  if openresults:
   if 'industry_invalidated' in openresults:return 'OPEN_INDUSTRY_INVALIDATED'
   if any(v in ['missing_open','open_at_or_below_protection','open_minimum_exceeds_frozen_contract'] for v in openresults):return 'OPEN_PRICE_OR_FROZEN_SIZE_REJECT'
   return 'OPEN_BUDGET_OR_TOKEN_REJECT'
  if key[:3] in reserved_stocks:return 'SAME_STOCK_OTHER_ROLE_RESERVED'
  if key[1]==days[-1]:return 'RIGHT_CENSORED_NO_NEXT_OPEN'
  return 'UNKNOWN_PLANNED_NO_OPEN_RECORD'
 if closeresults:return 'CLOSE_SIZE_REJECT'
 return 'UNKNOWN_NO_PLAN'

for n,r in enumerate(rows(P/'opportunities.jsonl.gz')):
 arm,day,sid=r['account'],r['day'],r['sid'];key3=(arm,day,sid);bi=int(birthlookup[sid][dayidx[day]]);on,heldset,exitset=daily[(arm,day)];assert r['held']==(sid in heldset)
 barriers=r['barriers'];roles=r['roles'];active=sector[(r['sector'],day)];sector_signal=not any(b.startswith('sector_up:') for b in barriers)
 oppcounts[arm]+=1;stage(arm,day,'01_FIXED_UNIVERSE',sid,bi)
 if bi:stage(arm,day,'01b_ACTIVE_NATIVE_STRUCTURE_PRESENT',sid,bi)
 if on:stage(arm,day,'02_ACT_ON',sid,bi)
 if on and sector_signal:stage(arm,day,'03_ACT_ON_SECTOR_SIGNAL_PASS',sid,bi)
 if on and sector_signal and active:stage(arm,day,'04_ACT_ON_SECTOR_SIGNAL_AND_ACTIVE',sid,bi)
 raw_q=r['core_Q'] is True or (r['mobile_Q'] is True and bool(r['CP1_id']))
 if raw_q:stage(arm,day,'RAW_ANY_FRESH_SIGNAL_Q',sid,bi)
 if roles:stage(arm,day,'RAW_ANY_ROLE',sid,bi)
 if roles and not r['held']:stage(arm,day,'RAW_FLAT_ROLE',sid,bi)
 if on and sector_signal and active and raw_q:stage(arm,day,'05_ALL_ABOVE_FRESH_SIGNAL_Q',sid,bi)
 if roles and not barriers:stage(arm,day,'NATIVE_NO_BARRIER_ROLE',sid,bi)
 legal=bool(roles and not barriers and active)
 if legal:stage(arm,day,'06_LEGAL_ROLE_AFTER_INDUSTRY',sid,bi)
 plans=[role for role in roles if key3+(role,) in pending]
 if plans:stage(arm,day,'NATIVE_ALL_PENDING_STOCKDAYS',sid,bi)
 if legal and plans:stage(arm,day,'07_LEGAL_POSITIVE_SIZE_RANKED',sid,bi)
 if legal and not r['held'] and plans:stage(arm,day,'08_FLAT_POSITIVE_SIZE_RANKED',sid,bi)
 if any(key3+(role,) in buys for role in roles):
  stage(arm,day,'09_ACTUAL_BUY_STOCKDAYS',sid,bi)
  if any(buys[key3+(role,)][0] for role in roles if key3+(role,) in buys):stage(arm,day,'10_ACTUAL_FIRST_ENTRY_STOCKDAYS',sid,bi)
 for period in dayperiod[day]:
  for b in barriers:reasons[(arm,period,'OPPORTUNITY_BARRIER_OVERLAP',b)]+=1
 # Exclusive hierarchy intentionally states one first-failed analysis stage,
 # not a causal decomposition of simultaneous failed checks.
 if not on:term='01_ACT_PAUSED'
 elif not sector_signal:term='02_SECTOR_SIGNAL_FAIL_OR_UNKNOWN'
 elif not active:term='03_INDUSTRY_ATTEMPT_INACTIVE'
 elif not raw_q:term='04_NO_FRESH_SIGNAL_OR_STOCK_Q'
 elif not roles:term='05_NO_ROLE_HELD_OR_CORE_EPOCH_LOCK'
 elif barriers:term='06_ACCOUNT_PENDING_BARRIER'
 elif not plans:term='07_CLOSE_SIZE_OR_UNKNOWN_NO_PLAN'
 else:
  terms=[terminal_for(key3+(role,),True) for role in plans]
  if 'ACTUAL_FIRST_ENTRY' in terms:term='12_ACTUAL_FIRST_ENTRY'
  elif 'ACTUAL_HELD_ADD' in terms:term='13_ACTUAL_HELD_ADD'
  elif 'RESERVED_NO_FILL' in terms:term='11_RESERVED_NO_FILL'
  elif 'OPEN_BUDGET_OR_TOKEN_REJECT' in terms:term='10_OPEN_BUDGET_OR_TOKEN_REJECT'
  elif 'OPEN_PRICE_OR_FROZEN_SIZE_REJECT' in terms:term='09_OPEN_PRICE_OR_FROZEN_SIZE_REJECT'
  elif 'OPEN_INDUSTRY_INVALIDATED' in terms:term='08_OPEN_INDUSTRY_INVALIDATED'
  else:term='14_'+','.join(sorted(set(terms)))
 for period in dayperiod[day]:exclusive[(arm,period,term)]+=1
 for role in roles:
  key=key3+(role,);plan=pending.get(key);buy=buys.get(key);planned=plan is not None
  if planned:seenpending.add(key)
  if buy:seenbuys.add(key)
  if barriers:terminal='OPPORTUNITY_BARRIER'
  elif not active:terminal='INDUSTRY_INACTIVE_AT_SIGNAL'
  else:terminal=terminal_for(key,planned)
  fs=fund.get(key,[]);closers=';'.join(v for phase,v in fs if phase=='CLOSE');openrs=';'.join(v for phase,v in fs if phase=='OPEN')
  roledata.append((arm,day,sid,r['sector'],role,r['held'],r['core_Q'],r['mobile_Q'],r['CP1_id'],bi,active,';'.join(barriers),planned,plan[2] if plan else np.nan,plan[3] if plan else np.nan,plan[0] if plan else np.nan,closers,openrs,buy[0] if buy else False,buy[1] if buy else '',buy[2] if buy else 0,terminal))
 if (n+1)%1000000==0:print('OPPORTUNITIES',n+1,round(time.monotonic()-begun,1),flush=True)
assert seenpending==set(pending) and seenbuys==set(buys)
assert all(v==1709*1054 for v in oppcounts.values())
for arm in ARMS:
 for period,(lo,hi) in PERIODS.items():assert sum(v for (a,p,t),v in exclusive.items() if a==arm and p==period)==1709*sum(lo<=d<=hi for d in days)
df=pd.DataFrame(roledata,columns=['account','signal_day','sid','sector','role','held_at_signal','core_Q','mobile_Q','CP1_id','native_birth_id','industry_active','barriers','original_pending','priority_rank','PVR_score','frozen_cap','close_result','open_result','actual_first_entry','actual_entry_day','actual_buy_shares','exclusive_role_stage'])
df['native_birth']=df.native_birth_id.map(birthnames)
df['no_barrier']=df.barriers.eq('');df['legal_ranked']=df.no_barrier&df.industry_active&df.original_pending;df['actual_buy']=df.actual_buy_shares.gt(0)
assert df.loc[df.actual_buy,'legal_ranked'].all()
assert df.loc[df.actual_first_entry,'held_at_signal'].eq(False).all()
assert df.loc[df.actual_buy & ~df.actual_first_entry,'held_at_signal'].eq(True).all()
assert df.loc[df.actual_buy,'native_birth'].ne('UNKNOWN').all()
df.to_parquet(O/'ROLE_CANDIDATE_TRACE.parquet',index=False)
csv('ACTUAL_BUY_TRACE.csv',actual)
csv('STOCKDAY_FUNNEL.csv',[dict(account=a,period=p,stage=s,stockdays=n,native_birth_events=len(eventsets[(a,p,s)])) for (a,p,s),n in sorted(counts.items())])
csv('EXCLUSIVE_STOCKDAY_STAGES.csv',[dict(account=a,period=p,exclusive_stage=s,stockdays=n) for (a,p,s),n in sorted(exclusive.items())])
csv('OVERLAPPING_OPPORTUNITY_REASONS.csv',[dict(account=a,period=p,source=s,reason=b,rows=n) for (a,p,s,b),n in sorted(reasons.items())])
csv('RAW_FUNDING_RESULTS.csv',[dict(account=a,period=p,phase=phase,role=role,result=result,rows=n) for (a,p,phase,role,result),n in sorted(rawfund.items())])

# Per-role stockday/event/fresh-CP counts and exact inclusive/exclusive stages.
rr=[];er=[];consumers=[];competition=[];eventrows=[];overlap=[];posthoc=[]
stages={'ROLE_OBSERVED':lambda x:np.ones(len(x),dtype=bool),'NO_BARRIER':lambda x:x.no_barrier,'LEGAL_INDUSTRY_ACTIVE':lambda x:x.no_barrier&x.industry_active,'POSITIVE_SIZE_RANKED':lambda x:x.legal_ranked,'NATIVE_PENDING_BEFORE_INDUSTRY_ROUTE':lambda x:x.original_pending,'OPEN_RESERVED':lambda x:x.open_result.str.contains('reserved',regex=False),'ACTUAL_BUY':lambda x:x.actual_buy,'ACTUAL_FIRST_ENTRY':lambda x:x.actual_first_entry}
for period,(lo,hi) in PERIODS.items():
 q=df[df.signal_day.between(lo,hi)]
 for (arm,role,held),g in q.groupby(['account','role','held_at_signal']):
  for stage_name,fn in stages.items():
   z=g[fn(g)];rr.append(dict(account=arm,period=period,role=role,held_at_signal=held,stage=stage_name,role_stockdays=len(z),stocks=z.sid.nunique(),days=z.signal_day.nunique(),native_birth_events=z.loc[z.native_birth_id.ne(0),'native_birth'].nunique(),fresh_CP1_events=z.CP1_id.nunique()))
  for terminal,z in g.groupby('exclusive_role_stage'):er.append(dict(account=arm,period=period,role=role,held_at_signal=held,exclusive_stage=terminal,role_stockdays=len(z)))
 for arm in ARMS:
  g=q[q.account.eq(arm)];flat=g[~g.held_at_signal];f=flat[flat.legal_ranked]
  mixed=f.groupby(['signal_day','sid']).role.agg(list)
  d=f.groupby('signal_day').sid.nunique();sec=f.groupby(['signal_day','sector']).sid.nunique()
  comp=set(tuple(x) for x in sec[sec>=2].index);datecomp=set(d[d>=2].index)
  consumers.append(dict(account=arm,period=period,flat_legal_ranked_stockdays=len(f[['signal_day','sid']].drop_duplicates()),flat_core_roles=int(f.role.eq('core').sum()),flat_mobile_roles=int(f.role.eq('mobile').sum()),core_mobile_same_stockdays=int(mixed.map(lambda x:len(x)==2).sum()),days_with_any=len(d),days_with_two_or_more=int((d>=2).sum()),within_sector_competitive_candidate_stockdays=len(f[[tuple(x) in comp for x in f[['signal_day','sector']].to_numpy()]][['signal_day','sid']].drop_duplicates()),within_sector_competitive_day_sectors=len(comp),actual_first_entries=int(g.actual_first_entry.sum()),rank_cutoff_dropped=0,rank_reordering_source='all pending; no top-K',flat_vs_held_competition='coupled same account, not independent mobile K20'))
  for scope,z in [('ALL_ROLES',g),('FLAT',flat),('HELD',g[g.held_at_signal])]:
   for stage_name,fn in stages.items():
    t=z[fn(z)]
    for b in t.loc[t.native_birth_id.ne(0),'native_birth'].unique():eventrows.append((arm,period,scope,stage_name,b))
  for clock,col in [('SIGNAL','signal_day'),('EXECUTION','actual_entry_day')]:
   z=df[df.account.eq(arm)&df.actual_first_entry&df[col].between(lo,hi)]
   competition.append(dict(account=arm,period=period,clock=clock,actual_first_entries=len(z),core=int(z.role.eq('core').sum()),mobile=int(z.role.eq('mobile').sum())))
csv('ROLE_FUNNEL.csv',rr);csv('EXCLUSIVE_ROLE_STAGES.csv',er);csv('CONSUMER_COVERAGE.csv',consumers);csv('FIRST_ENTRY_TWO_CLOCKS.csv',competition)
ed=pd.DataFrame(eventrows,columns=['account','period','holding_scope','stage','native_birth']).drop_duplicates()
ed.to_parquet(O/'NATIVE_BIRTH_STAGE_MEMBERSHIP.parquet',index=False)
for (period,scope,stage_name),g in ed.groupby(['period','holding_scope','stage']):
 sa=set(g[g.account.eq('PVR')].native_birth);sb=set(g[g.account.eq('NOACT')].native_birth)
 overlap.append(dict(period=period,holding_scope=scope,stage=stage_name,PVR=len(sa),NOACT=len(sb),common=len(sa&sb),PVR_only=len(sa-sb),NOACT_only=len(sb-sa)))
csv('NATIVE_BIRTH_CROSS_ARM_OVERLAP.csv',overlap)

# Only ACTUAL rounds have outcomes; candidates never receive counterfactual PnL.
outcomes=[]
for (arm,birth),g in rounds.groupby(['account','anchor_birth']):
 closed=g.closed.notna();allclosed=bool(closed.all());pnl=float(g.pnl.sum())
 outcomes.append(dict(account=arm,native_birth=birth,actual_rounds=len(g),completed_rounds=int(closed.sum()),unclosed_rounds=int((~closed).sum()),closed_all_rounds=allclosed,closed_winner_birth=allclosed and pnl>0,has_actual_complete_30pct_round=bool((closed&g.return_on_all_buy_cost.ge(.3)).any()),actual_birth_pnl=pnl))
outcomes=pd.DataFrame(outcomes);outcomes.to_csv(O/'ACTUAL_NATIVE_BIRTH_OUTCOMES.csv',index=False)
for (arm,period,scope,stage_name),g in ed.groupby(['account','period','holding_scope','stage']):
 aout=outcomes[outcomes.account.eq(arm)];z=g.merge(aout,on=['account','native_birth'],how='left',validate='one_to_one')
 posthoc.append(dict(account=arm,period=period,holding_scope=scope,stage=stage_name,native_birth_events=len(z),no_actual_round_in_this_arm=int(z.actual_rounds.isna().sum()),actual_closed_winner_births=int(z.closed_winner_birth.eq(True).sum()),actual_complete_30pct_births=int(z.has_actual_complete_30pct_round.eq(True).sum()),warning='posthoc event coverage only; no hypothetical returns for absent trades; one birth may contain multiple rounds'))
csv('POSTHOC_ACTUAL_WINNER_COVERAGE.csv',posthoc)
cohort=[]
for arm in ARMS:
 for period,(lo,hi) in PERIODS.items():
  g=rounds[rounds.account.eq(arm)&rounds.opened.str[:10].between(lo,hi)]
  for kind,z in g.groupby('initial_kind'):
   c=z[z.closed.notna()];cohort.append(dict(account=arm,period=period,initial_role='mobile' if kind=='add' else kind,entry_clock='execution',first_entries=len(z),complete_rounds=len(c),open_rounds=len(z)-len(c),complete_winners=int(c.pnl.gt(0).sum()),complete_win_rate=float(c.pnl.gt(0).mean()) if len(c) else None,complete_30pct_rounds=int(c.return_on_all_buy_cost.ge(.3).sum()),complete_round_net=float(c.pnl.sum()),outcome_cutoff='2026-05-15'))
csv('ACTUAL_FIRST_ENTRY_COHORT_OUTCOMES.csv',cohort)

# Confirm old isolated empty-mobile queue identity; E31 is never merged into NOACT.
old=pd.read_parquet(OLD/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');old=old[old.account.eq('PVR')]
new=df[df.account.eq('PVR')&df.role.eq('mobile')&~df.held_at_signal&df.legal_ranked]
ok=set(zip(old.day,old.sid));nk=set(zip(new.signal_day,new.sid))
oldmatch=old.merge(new,left_on=['day','sid'],right_on=['signal_day','sid'],suffixes=('_old','_new'),validate='one_to_one')
qa_old=dict(old_PVR_rows=len(old),new_PVR_rows=len(new),common=len(ok&nk),old_only=len(ok-nk),new_only=len(nk-ok),CP1_exact=bool(oldmatch.CP1_id_old.eq(oldmatch.CP1_id_new).all()),priority_rank_exact=bool(oldmatch.original_priority_rank.eq(oldmatch.priority_rank).all()),PVR_max_error=float((oldmatch.original_PVR-oldmatch.PVR_score).abs().max()),NOACT_source_distinct=True,old_other_arm='E31; excluded',same_queue=ok==nk)
dump('OLD_EMPTY_MOBILE_QUEUE_IDENTITY.json',qa_old)
assert qa_old['same_queue'] and qa_old['CP1_exact'] and qa_old['priority_rank_exact'] and qa_old['PVR_max_error']==0
no=df[df.account.eq('NOACT')&df.role.eq('mobile')&~df.held_at_signal&df.legal_ranked];ns=set(zip(no.signal_day,no.sid));dump('PVR_NOACT_EMPTY_MOBILE_QUEUE_OVERLAP.json',dict(PVR=len(nk),NOACT=len(ns),common=len(nk&ns),PVR_only=len(nk-ns),NOACT_only=len(ns-nk),unit='signal_day+sid; fresh CP1 implied; not native birth'))

# Initial pause/sector accounting is explicitly ordered, not claimed independent.
dump('QA.json',dict(passed=True,account_runs=0,indicator_runs=0,source_output_hashes_verified=len(hashcheck),opportunity_rows=dict(oppcounts),role_rows=len(df),original_pending_role_rows=len(pending),actual_buy_orders=len(buys),actual_first_entries=len(initial),native_birth_actual_layer_match=len(layers),all_actual_buys_legal_ranked=True,flat_vs_add_exact=True,exclusive_stockday_partition_exact=True,rank_policy_rows_cover_pending_exact=True,old_queue_identity=qa_old,unknown_planned_no_open_record=int(df.exclusive_role_stage.eq('UNKNOWN_PLANNED_NO_OPEN_RECORD').sum()),no_plan_unknown=int(df.exclusive_role_stage.eq('UNKNOWN_NO_PLAN').sum()),seconds=time.monotonic()-begun))
assert before=={str(p):sha(p) for p in inputs}
assert auxfreeze=={p:sha(p) for p in auxfreeze}
dump('INPUT_SHA256.json',before|auxfreeze)
dump('OUTPUT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
print('DONE',json.dumps(read(O/'QA.json'),ensure_ascii=False),flush=True)
print(pd.DataFrame(consumers).to_string(index=False),flush=True)
