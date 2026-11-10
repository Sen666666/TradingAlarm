"""Entry-time labels from completed prior CLOSE only; outcomes kept separately."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,csv,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent/'mainline_m7_cash_batch_design_v6/once_20260630';A='2024-11-06';Z=D(0)
def read(n):return json.loads((R/(n+'.json')).read_text())
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
 if isinstance(x,list) and x:
  with (O/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
def sm(rs,k):return sum((D(r.get(k,0)) for r in rs),Z)
orders=read('ORDERS');attempts=read('ATTEMPTS');funding=read('FUNDING_REQUESTS');cand=read('CANDIDATES');led=read('DAY_LEDGER');sectors=read('SECTOR_DAILY');caps=read('CAPITAL_LOTS');E=led[-1]['day'];ix={r['day']:i for i,r in enumerate(led)};og=defaultdict(list);ag={a['id']:a for a in attempts};sg={(r['day'],r['sector51']):r for r in sectors};cg=defaultdict(list)
for o in orders:og[o['round_id']].append(o)
for c in cand:cg[c.get('sid')].append(c)
fr=defaultdict(list)
for f in funding:
 if f['event']=='SEED' and f['decision']=='PASS':fr[f['day'],f['sid']].append(f)
seeds={rid:next(o for o in os if o['side']=='BUY_SEED') for rid,os in og.items()}
closed=[a for a in attempts if not a['final_qty']]
for a in closed:
 a['_exit_seq']=max(o['order_seq'] for o in og[a['id']] if o['side'].startswith('SELL'));a['_seed_event']=seeds[a['id']].get('event_id')
closed.sort(key=lambda a:(a['exit_day'],a['_exit_seq']))
sidclosed=defaultdict(list);secclosed=defaultdict(list);eventclosed=defaultdict(list)
for a in closed:sidclosed[a['sid']].append(a);secclosed[a['sector51']].append(a);eventclosed[a['_seed_event']].append(a)
# Reconstruct only persisted stock state, no strategy import or historical replay.
SR=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');Q=SR/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
source_hashes=read('SOURCE_HASHES'); stock_source_hashes={}
for p in [Q/'KNOWN3.parquet',Q/'RIGHT3.parquet',SR/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet']:
 h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==source_hashes[str(p)];stock_source_hashes[str(p)]=h
known3=pd.read_parquet(Q/'KNOWN3.parquet').loc[:E];right3=pd.read_parquet(Q/'RIGHT3.parquet').loc[:E]
ps=pd.read_parquet(SR/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',columns=['sid','day','state']);ps=ps[ps.day<=pd.Timestamp(E)].pivot(index='day',columns='sid',values='state').reindex(index=known3.index,columns=known3.columns)
known=known3 & ps.ge(0);stock=right3.where(known,False).astype(int).where(known,-1)
rows=[]
for rid,seed in seeds.items():
 if seed['day']<=A:continue
 a=ag[rid];day=seed['day'];plan=seed['plan_day'];signal=seed['signal_day'];sec=a['sector51'];state=sg[plan,sec];fs=fr[day,a['sid']];assert len(fs)==1,(rid,fs);f=fs[0]
 same=[r for r in sidclosed[a['sid']] if r['exit_day']<=plan];prev=same[-1] if same else None;streak=0
 for old in reversed(same):
  if D(old['marked_net_pnl'])<0:streak+=1
  else:break
 history=[r for r in secclosed[sec] if r['exit_day']<=plan];batchday=history[-1]['exit_day'] if history else None;batch=[r for r in history if r['exit_day']==batchday];batchnet=sm(batch,'marked_net_pnl');batchstreak=0
 for bd in sorted({r['exit_day'] for r in history},reverse=True):
  if sm([r for r in history if r['exit_day']==bd],'marked_net_pnl')<0:batchstreak+=1
  else:break
 eid=seed.get('event_id');evknown=[r for r in eventclosed[eid] if r['exit_day']<=plan] if eid else [];evnet=sm(evknown,'marked_net_pnl')
 prevrejections=[c for c in cg[a['sid']] if c.get('phase')=='OPEN' and c.get('event')=='SEED' and c.get('signal_day')==signal and c.get('day')<day and c.get('decision')!='PASS']
 # Same-day exit is deliberately excluded: it was not known at decision CLOSE.
 sameday=[r for r in sidclosed[a['sid']] if r['exit_day']==day and r['_exit_seq']<seed['order_seq']]
 row=dict(round_id=rid,sid=a['sid'],name=seed['name'],sector51=sec,birth_type=a['birth_type'],signal_day=signal,plan_day=plan,entry_day=day,entry_order_seq=seed['order_seq'],event_id=eid,event_birth_day=eid.rsplit('|',1)[-1] if eid else None,role=seed['capital_role'],allocation_phase=seed['allocation_phase'],seed_qty=seed['qty'],seed_notional=seed['notional'],seed_cash=-D(seed['cash_delta']),seed_account_pct=-D(seed['cash_delta'])/D(a['nav0'])*100,entry_M=seed['M'],entry_E=seed['E'],entry_M_streak=f['M_streak'],prior_CLOSE_sector_state=state['state'],prior_CLOSE_sector_strength=state['strength'],prior_CLOSE_M=state['M'],prior_CLOSE_E=state['E'],prior_CLOSE_S=state['S'],prior_CLOSE_Q=state['Q'],prior_CLOSE_F=state['F'],signal_to_entry_intervals=ix[day]-ix[signal],signal_to_plan_intervals=ix[plan]-ix[signal],prior_OPEN_rejection_count=len(prevrejections),prior_OPEN_rejections=[{k:c.get(k) for k in ['day','decision','allocation_phase','violated_caps']} for c in prevrejections],retained_after_previous_OPEN_rejection=bool(prevrejections),prior_known_same_sid_round=prev['id'] if prev else None,prior_known_same_sid_exit=prev['exit_day'] if prev else None,prior_known_same_sid_pnl=prev['marked_net_pnl'] if prev else None,prior_known_same_sid_loss=bool(prev and D(prev['marked_net_pnl'])<0),same_sid_known_consecutive_losses=streak,prev_exit_to_entry_intervals=ix[day]-ix[prev['exit_day']] if prev else None,new_signal_after_prev_exit=signal>prev['exit_day'] if prev else None,same_day_exit_not_known_at_plan=[r['id'] for r in sameday],sector_last_known_exit_day=batchday,sector_last_known_closed_rounds=len(batch),sector_last_known_closed_batch_pnl=batchnet if batch else None,sector_latest_batch_negative=bool(batch and batchnet<0),sector_consecutive_negative_closure_dates=batchstreak,same_event_known_closed_rounds=len(evknown),same_event_known_loss_rounds=sum(D(r['marked_net_pnl'])<0 for r in evknown),same_event_known_closed_net=evnet,same_event_known_closed_net_negative=bool(evknown and evnet<0),outcome_add_count=a['add_count'],outcome_final_qty=a['final_qty'],outcome_exit_day=a.get('exit_day'),outcome_marked_pnl=a['marked_net_pnl'])
 assert row['entry_M']==row['prior_CLOSE_M']
 row['prior_CLOSE_stock_state']=int(stock.loc[pd.Timestamp(plan),a['sid']]);row['signal_CLOSE_stock_state']=int(stock.loc[pd.Timestamp(signal),a['sid']]);truestreak=0
 for st in reversed(stock.loc[:plan,a['sid']].tolist()):
  if st==1:truestreak+=1
  else:break
 row['stock_true_streak_at_plan']=truestreak;row['prior_CLOSE_sector_return5_median']=state['return5_median'];row['prior_CLOSE_sector_return10_median']=state['return10_median']
 rows.append(row)
# Summaries use causal entry labels; outcome returns are descriptive of actual selected entries.
def group(label,rs):
 return dict(group=label,count=len(rs),closed=sum(not r['outcome_final_qty'] for r in rs),open=sum(bool(r['outcome_final_qty']) for r in rs),net=sm(rs,'outcome_marked_pnl'),seed_cash=sm(rs,'seed_cash'),no_ADD_count=sum(not r['outcome_add_count'] for r in rs),no_ADD_net=sm([r for r in rs if not r['outcome_add_count']],'outcome_marked_pnl'),entry_days=dict(Counter(r['entry_day'] for r in rs)))
summary=[]
for label,rs in [('ALL_NEW',rows),('MATURE',[r for r in rows if r['allocation_phase']=='MATURE']),('INITIAL',[r for r in rows if r['role']=='INITIAL'])]:
 summary.append(group(label,rs))
 for flag in ['prior_known_same_sid_loss','sector_latest_batch_negative','same_event_known_closed_net_negative','retained_after_previous_OPEN_rejection']:
  for val in [False,True]:summary.append(group(label+'__'+flag+'__'+str(val),[r for r in rs if r[flag]==val]))
 for streak in [0,1,2,3]:summary.append(group(label+'__SID_LOSS_STREAK_'+str(streak)+('PLUS' if streak==3 else ''),[r for r in rs if (r['same_sid_known_consecutive_losses']>=streak if streak==3 else r['same_sid_known_consecutive_losses']==streak)]))
sector=[]
for sec in sorted({r['sector51'] for r in rows}):
 rs=[r for r in rows if r['sector51']==sec and r['allocation_phase']=='MATURE'];no=[r for r in rs if not r['outcome_add_count']]
 if not rs:continue
 sector.append(dict(sector51=sec,rounds=len(rs),net=sm(rs,'outcome_marked_pnl'),no_ADD_rounds=len(no),no_ADD_net=sm(no,'outcome_marked_pnl'),same_sid_prior_loss_count=sum(r['prior_known_same_sid_loss'] for r in rs),same_sid_prior_loss_net=sm([r for r in rs if r['prior_known_same_sid_loss']],'outcome_marked_pnl'),sector_prior_negative_batch_count=sum(r['sector_latest_batch_negative'] for r in rs),sector_prior_negative_batch_net=sm([r for r in rs if r['sector_latest_batch_negative']],'outcome_marked_pnl'),same_event_prior_negative_count=sum(r['same_event_known_closed_net_negative'] for r in rs),same_event_prior_negative_net=sm([r for r in rs if r['same_event_known_closed_net_negative']],'outcome_marked_pnl'),signal_days=dict(Counter(r['signal_day'] for r in rs)),entry_days=dict(Counter(r['entry_day'] for r in rs))))
sector.sort(key=lambda r:r['net'])
sidseq=[]
for sid in sorted({r['sid'] for r in rows if r['prior_known_same_sid_loss']}):
 rs=[r for r in rows if r['sid']==sid and r['prior_known_same_sid_loss']];sidseq.append(dict(sid=sid,name=rs[0]['name'],sector51=rs[0]['sector51'],reentries_after_known_loss=len(rs),max_known_loss_streak=max(r['same_sid_known_consecutive_losses'] for r in rs),net=sm(rs,'outcome_marked_pnl'),paths=[{k:r[k] for k in ['signal_day','plan_day','entry_day','allocation_phase','entry_M','entry_E','prior_known_same_sid_round','prior_known_same_sid_exit','prior_known_same_sid_pnl','same_sid_known_consecutive_losses','prev_exit_to_entry_intervals','new_signal_after_prev_exit','outcome_exit_day','outcome_marked_pnl']} for r in rs]))
sidseq.sort(key=lambda r:r['net'])
entrylabels=[]
mature=[r for r in rows if r['allocation_phase']=='MATURE']
for k in ['birth_type','entry_M_streak','signal_to_entry_intervals','prior_OPEN_rejection_count','prior_CLOSE_sector_state','prior_CLOSE_sector_strength','prior_CLOSE_stock_state','stock_true_streak_at_plan']:
 for val in sorted({r[k] for r in mature},key=str):entrylabels.append(dict(label=k,value=val,**group(str(val),[r for r in mature if r[k]==val])))
result=dict(anchor=A,end=E,summary=summary,stock_state_at_decision='Reconstructed from hash-verified frozen KNOWN3/RIGHT3 and PVR STOCK_DAILY; exact formula in joint51_candidate_v9_facts/engine.py; only signal and plan CLOSE values, never entry evening.',causal_definition='All prior outcomes use full rounds whose exit_day <= plan_day. Same-day OPEN exits are excluded from prior-CLOSE known labels. Latest sector batch means all rounds closed on its most recent known exit date; not a claim all individual industry opportunities failed. Same-event loss is only realized known closed subtotal, not future completion of an industry event.',caveats=['No candidate filter is simulated. Conditional outcome subgroup numbers cannot be treated as recoverable profits; financing, other candidates and later exits would change.','Latest sector negative batch and own-sid prior loss need not imply current fresh opportunity is invalid; they are measurements for predeclared design.','NO_ADD is future actual path, separate from causal entry labels.','Orders born before 11/6 and entered after are classified new by actual first fill, consistent with accounting.'])
for n,x in [('ENTRY_TIME_SEQUENCE_ROWS',rows),('MATURE_SECTOR_FAILURES',sector),('KNOWN_LOSS_SID_REENTRIES',sidseq),('MATURE_ENTRY_LABELS',entrylabels),('ENTRY_TIME_SEQUENCE_SUMMARY',result)]:save(n,x)
save('STOCK_STATE_SOURCE_HASHES',stock_source_hashes)
save('ENTRY_SEQUENCE_SOURCE_HASHES',{n:hashlib.sha256((R/(n+'.json')).read_bytes()).hexdigest() for n in ['ORDERS','ATTEMPTS','FUNDING_REQUESTS','CANDIDATES','DAY_LEDGER','SECTOR_DAILY','CAPITAL_LOTS']})
print(json.dumps({'summary':summary,'sector_top':sector[:12],'entry_labels':entrylabels,'worst_sid_sequences':sidseq[:10]},ensure_ascii=False,default=str))
