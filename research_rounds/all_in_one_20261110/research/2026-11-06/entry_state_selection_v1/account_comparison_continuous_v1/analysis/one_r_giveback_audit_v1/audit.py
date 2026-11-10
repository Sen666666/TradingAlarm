from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
from datetime import datetime
import json,gzip,sys,ast,hashlib,bisect
import pandas as pd,numpy as np
P=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/account_comparison_continuous_v1')
PREP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
a=json.load(gzip.open(P/'run_1200000/pair/PVR.json.gz','rt'))
ds=[d for d in map(json.loads,gzip.open(P/'run_1200000/pair/daily.jsonl.gz','rt')) if d['account']=='PVR']
sm={r['symbol']:r for r in json.loads((U/'STOCK_MANIFEST.json').read_text())}
records={r['series_id']:r for r in json.loads((PREP/'manifest.json').read_text())['series']}
sys.path.insert(0,str(P/'inputs'));import continuous_inputs as C
fm=C.J.M.E.FastMarket.__new__(C.J.M.E.FastMarket);fm.cache_at=None
fm.rules=json.loads((C.J.M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json').read_text())
fm.protocol=json.loads((C.J.M.BP.C.OLD/'inputs-v2/economic-protocol.json').read_text())
def fee(sid,day,q,px):
 at=datetime.fromisoformat(day+' 09:30:00+08:00') if len(day)==10 else datetime.fromisoformat(day)
 sch=fm.fees(sid,at);par=fm.rules.get('security_metadata',{}).get(sid,{}).get('par_value')
 return float(sum(sch.incremental('sell',D(str(q))*D(str(px)),{},{},1,shares=q,par_value=par).values(),D(0)))
raw={};ff={}
def data(sid):
 if sid not in raw:
  p=Path(records[sid]['raw']['path']);f=pd.read_parquet(p)
  f.index=f.trade_date.astype(str).str[:10];raw[sid]=f
  ff[sid]=pd.read_parquet(sm[sid]['refs']['facts'],columns=['factor','i_target','i_floor']);ff[sid].index=ff[sid].index.astype(str).str[:10]
 return raw[sid],ff[sid]
layers={l['id']:l for l in a['layers']}
trades=a['trades'];buys={t['layer']:t for t in trades if t['side']=='buy'}
# Freeze risk at each layer's original buy protection line and actual filled quantity.
irisk={};rmeta={}
for k,t in buys.items():
 sid=t['security_id'];f,ff0=data(sid)
 factor=float(ff0.loc[t['at'][:10],'factor'])
 floor=float(t['floor'])/factor
 K=float(t['gross_cny'])+float(t['fees_cny']);q=t['shares'];px=floor*.9995
 risk=max(0.,K-q*px+fee(sid,t['at'],q,px))
 irisk[k]=risk;rmeta[k]=dict(risk=risk,floor_raw=floor,paid=K,qty=q,signal_day=t['signal_at'][:10])
# reconstruct completed original zero-to-zero rounds directly from actual layer overlap
rounds=[]
for sid in sorted({l['sid'] for l in layers.values()}):
 ls=sorted([l for l in layers.values() if l['sid']==sid],key=lambda l:(l['opened'],l['id']))
 cur=[];right=None
 def emit(cur):
  if not cur:return
  closed=max(l['closed'] for l in cur) if all(l['closed'] is not None for l in cur) else None
  r=dict(sid=sid,opened=min(l['opened'] for l in cur),closed=closed,layer_ids=[l['id'] for l in cur],pnl=sum(float(l['cash'])+float(l['dividend']) for l in cur) if closed else None,obs=[])
  r['key']=(sid,r['opened']);rounds.append(r)
 for l in ls:
  if cur and right is not None and l['opened']>=right:emit(cur);cur=[];right=None
  cur.append(l)
  if l['closed'] is None:right=None
  elif len(cur)==1:right=l['closed']
  elif right is not None:right=max(right,l['closed'])
 emit(cur)
rbylayer={k:r for r in rounds for k in r['layer_ids']}
rmap={r['key']:r for r in rounds}
days=[d['at'][:10] for d in ds];dayindex={d:i for i,d in enumerate(days)}
print('LOADED',len(ds),len(rounds),len(raw),'negative_initial_risk',sum(v<=0 for v in irisk.values()),flush=True)
# Replay only stored fills/actions and daily observations. No account, strategy or orders run.
active={};lqty={};lrisk={};allobs=[];divtot=defaultdict(float);splits=defaultdict(list)
ev=[(t['at'],1,i,'trade',t) for i,t in enumerate(trades)]
for i,j in enumerate(a['journal']):
 if j['kind']=='actual_split':ev.append((j['at'],0,i,'split',j));splits[j['at'][:10],j['sid']].append(j)
for i,d in enumerate(ds):ev.append((d['at'],2,i,'close',d))
for at,_,idx,kind,t in sorted(ev,key=lambda e:e[:3]):
 if kind=='split':
  sid=t['sid']
  if sid not in active:continue
  z=active[sid];ids=[k for k in z['r']['layer_ids'] if lqty.get(k,0)>0]
  target=int(sum(lqty[k] for k in ids)*D(t['ratio']));new=[int(lqty[k]*D(t['ratio'])) for k in ids]
  for j in range(target-sum(new)):new[j%len(new)]+=1
  for k,q in zip(ids,new):lqty[k]=q
  z['Q']=target
 elif kind=='trade':
  sid=t['security_id'];q=t['shares']
  if t['side']=='buy':
   if sid not in active:active[sid]=dict(r=rbylayer[t['layer']],Q=0,K=0.,cash=0.,paid=0.)
   z=active[sid];paid=float(t['gross_cny'])+float(t['fees_cny'])
   z['Q']+=q;z['K']+=paid;z['cash']-=paid;z['paid']+=paid;lqty[t['layer']]=q;lrisk[t['layer']]=irisk[t['layer']]
  else:
   z=active[sid];z['K']*=(z['Q']-q)/z['Q'];z['Q']-=q;z['cash']+=float(t['gross_cny'])-float(t['fees_cny'])
   for p in t['parts']:
    k=p['layer'];lrisk[k]*=(lqty[k]-p['shares'])/lqty[k];lqty[k]-=p['shares']
   if not z['Q']:del active[sid]
 else:
  assert {s:z['Q'] for s,z in active.items()}==t['positions'],at
  snaps=defaultdict(list)
  for l in t['layers']:snaps[l['sid']].append(l)
  day=at[:10]
  for sid,z in active.items():
   f,ff0=data(sid);bar=f.loc[day] if day in f.index else None
   good=bar is not None and bool(bar.observed_bar) and bool(bar.price_eligible) and not bool(bar.synthetic_event_bar) and np.isfinite(bar.close) and bar.close>0
   ls=snaps[sid];ids=[l['id'] for l in ls];risk=sum(lrisk[k] for k in ids)
   # Current live dividends plus fixed dividends of layers already closed by this day.
   div=sum(float(l['dividend']) for l in ls)+sum(float(layers[k]['dividend']) for k in z['r']['layer_ids'] if k not in ids and layers[k]['closed'] and layers[k]['closed']<=at)
   o=dict(day=day,sid=sid,Q=z['Q'],K=z['K'],cash=z['cash'],div=div,R=risk,valid=good,layers=ls,round=z['r'],paid=z['paid'])
   if good:
    close=float(bar.close);net=z['Q']*close*.9995-fee(sid,day,z['Q'],close*.9995)
    o.update(close=close,U=net-z['K'],net_round=z['cash']+net+div)
   z['r']['obs'].append(o);allobs.append(o)
old=pd.read_csv(P/'analysis/2022_independent_review/ROUND_DAILY_CLOSE.csv')
obmap={(o['sid'],o['round']['opened'],o['day']):o for o in allobs}
maxdelta=0.
for row in old.to_dict('records'):
 o=obmap[(row['sid'],row['opened'],row['day'])]
 assert o['Q']==row['Q'] and o['valid']==row['valid_actual_close']
 assert abs(o['K']-row['K_remaining'])<1e-6
 if o['valid']:maxdelta=max(maxdelta,abs(o['U']-row['U']))
print('OBS_VALIDATION',len(allobs),len(old),maxdelta,flush=True)
origreq=defaultdict(set)
for e in a['audit']:
 if e['kind']=='pilot_layer_exit':
  for k in e['layers']:origreq[e['at'][:10],layers[k]['sid']].add(k)
bids=pd.read_csv(P/'analysis/2022_independent_review/CLOSED_ROUNDS_MFE.csv')
bkeys={(r['sid'],r['opened']) for r in bids.to_dict('records') if r['group']=='B_POSITIVE_AT_LEAST_3PCT'}
brounds=[r for r in rounds if r['key'] in bkeys];assert len(brounds)==242
print('B_ROUNDS',len(brounds),'risk_min',min(o['R'] for r in brounds for o in r['obs']),flush=True)
# This is a fixed-path audit: first intervention only; subsequent original fills are not simulated.
divday=defaultdict(float)
for e in a['audit']:
 if e['kind']=='dividend_accrual':
  v=e['receivable'];divday[v['ex_at'][:10],v['security_id']]+=float(v['net_local'])
def open_eval(o):
 day=o['day'];sid=o['sid'];j=dayindex[day]+1
 if j>=len(days):return dict(status='NO_NEXT_COMMON_SESSION')
 nd=days[j];f=raw[sid];q=o['Q'];extra_div=divday[nd,sid]
 out=dict(day=nd,q=q,legal_t1=True,real_tradability='UNKNOWN_ALL_RAW_DAILY_OPENS')
 # all original shares at close are at least next-session sellable; newly credited split shares can be T+1 later
 if splits.get((nd,sid)):
  out.update(status='CORPORATE_ACTION_SPLIT_FULL_LIQUIDATION_NOT_T1_CONFIRMED');return out
 if nd not in f.index or not np.isfinite(f.loc[nd,'open']) or f.loc[nd,'open']<=0:
  out.update(status='MISSING_OPEN');return out
 bar=f.loc[nd];px=float(bar.open)*.9995
 past=f.loc[f.index<nd];vol=past.loc[np.isfinite(past.volume)&past.volume.gt(0),'volume'].tail(20)
 cap=int(vol.mean()*float(fm.protocol['participation_rate'])) if len(vol)==20 else 0
 allowed=fm._version('availability_versions',sid,datetime.fromisoformat(nd+' 09:30:00+08:00')).get('sell_allowed')
 warnings=[]
 if len(vol)<20:warnings.append('NO_PRIOR20_VOLUME')
 if q>cap:warnings.append('Q_EXCEEDS_PAST20_CAPACITY')
 if allowed is not True:warnings.append('SELL_PERMISSION_NOT_TRUE')
 if not bool(bar.observed_bar) or not bool(bar.price_eligible) or bool(bar.synthetic_event_bar):warnings.append('NO_REAL_ELIGIBLE_DAY')
 if not np.isfinite(bar.volume) or bar.volume<=0:warnings.append('POSTHOC_ZERO_OR_MISSING_VOLUME')
 if bar.high==bar.low:warnings.append('POSTHOC_FLAT_DAY')
 if np.isfinite(bar.volume) and q>bar.volume:warnings.append('POSTHOC_Q_EXCEEDS_DAILY_VOLUME')
 fee0=fee(sid,nd,q,px);net=q*px-fee0
 out.update(status='OPEN_PROXY_ONLY' if not warnings else 'FLAGGED_OPEN_UNCERTAIN',open=float(bar.open),price=px,fee=fee0,capacity=cap,warnings=warnings,U=net-o['K'],round_net=o['cash']+net+o['div']+extra_div,giveback_from_close=o['U']-(net-o['K']),extra_div=extra_div)
 return out
def riskline(o,target):
 lo=0.;hi=max(o.get('close',1)*2,(o['K']+target)/o['Q']*2)
 for _ in range(45):
  mid=(lo+hi)/2
  v=o['Q']*mid*.9995-fee(o['sid'],o['day'],o['Q'],mid*.9995)-o['K']
  if v<target:lo=mid
  else:hi=mid
 return (lo+hi)/2
results=[]
for r in rounds:
 if not r['closed']:continue
 obs=r['obs'];valid=[o for o in obs if o['valid'] and o['R']>0]
 arm=next((o for o in valid if o['U']>=o['R']),None)
 row={k:v for k,v in r.items() if k not in ['obs','key']}
 row.update(B2022=r['key'] in bkeys,arm_day=arm['day'] if arm else None,incomplete_close=any(not o['valid'] for o in obs))
 if arm:
  oi=obs.index(arm)
  firstnext=open_eval(arm)
  factor=float(ff[r['sid']].loc[arm['day'],'factor']);avg=arm['K']/arm['Q']
  lines=[(float(l['last_core_line']) if l['kind']=='core' else float(l['floor']))/factor for l in arm['layers']]
  row.update(arm_U=arm['U'],arm_R=arm['R'],arm_K=arm['K'],arm_Q=arm['Q'],arm_net_round=arm['net_round'],arm_next=firstnext,arm_all_orig_lines_below_cost=all(l<avg for l in lines),arm_any_orig_line_below_cost=any(l<avg for l in lines),arm_after_added_layers=len(arm['layers'])>1 or any(buys[l['id']]['at'][:10]>r['opened'][:10] for l in arm['layers']))
  stop=next((o for o in obs[oi+1:] if o['valid'] and o['R']>0 and o['U']<=.5*o['R']),None)
  if stop:
   si=obs.index(stop);requested=origreq[stop['day'],r['sid']]
   incremental_q=sum(l['qty'] for l in stop['layers'] if l['id'] not in requested)
   row.update(stop_day=stop['day'],stop_U=stop['U'],stop_R=stop['R'],stop_K=stop['K'],stop_Q=stop['Q'],stop_net_round=stop['net_round'],stop_next=open_eval(stop),incremental_q=incremental_q,all_orig_exit_already_requested=incremental_q==0,stop_after_position_change=stop['Q']!=obs[si-1]['Q'] or abs(stop['K']-obs[si-1]['K'])>1e-6,arm_to_stop_sessions=dayindex[stop['day']]-dayindex[arm['day']],adds_after_arm=sum(1 for k in r['layer_ids'] if arm['day']<buys[k]['at'][:10]<=stop['day']))
 results.append(row)
bykey={(r['sid'],r['opened']):r for r in results}
def summary(rs):
 armed=[r for r in rs if r['arm_day']]
 stopped=[r for r in armed if r.get('stop_day')]
 incr=[r for r in stopped if r['incremental_q']>0]
 nex=[r for r in armed if 'round_net' in r['arm_next']]
 stn=[r for r in incr if 'round_net' in r['stop_next']]
 return dict(n=len(rs),armed=len(armed),never_armed=len(rs)-len(armed),arm_after_additional_position=sum(r['arm_after_added_layers'] for r in armed),arm_all_orig_lines_below_cost=sum(r['arm_all_orig_lines_below_cost'] for r in armed),next_open_status=dict(Counter(r['arm_next']['status'] for r in armed)),arm_next_U_positive=sum(r['arm_next']['U']>0 for r in nex),arm_next_round_positive=sum(r['arm_next']['round_net']>0 for r in nex),next_giveback_median=float(np.median([r['arm_next']['giveback_from_close'] for r in nex])) if nex else None,stop_signals=len(stopped),already_all_orig_requested=len(stopped)-len(incr),incremental_exits=len(incr),incremental_stop_position_changed=sum(r['stop_after_position_change'] for r in incr),stop_open_status=dict(Counter(r['stop_next']['status'] for r in incr)),stop_open_U_positive=sum(r['stop_next']['U']>0 for r in stn),stop_open_round_positive=sum(r['stop_next']['round_net']>0 for r in stn),stop_open_round_nonpositive=sum(r['stop_next']['round_net']<=0 for r in stn),fixed_path_incremental_difference=sum(r['stop_next']['round_net']-r['pnl'] for r in stn),actual_pnl_incr=sum(r['pnl'] for r in incr),stopped_close_positive_U=sum(r['stop_U']>0 for r in incr),stopped_halfR_close_floor_gap_median=float(np.median([.5*r['stop_R']-r['stop_U'] for r in incr])) if incr else None)
B=[r for r in results if r['B2022']]
Y22=[r for r in results if r['closed'][:4]=='2022']
tops={y:sorted([r for r in results if r['closed'][:4]==y and r['pnl']>0],key=lambda r:-r['pnl'])[:20] for y in ['2024','2025']}
print('B_SUMMARY',json.dumps(summary(B)),flush=True)
print('2022_ALL_SUMMARY',json.dumps(summary(Y22)),flush=True)
for y,rs in tops.items():print('TOP20_'+y,json.dumps(summary(rs)),flush=True)
# Consistency and diagnostic breakdowns.
for rr in bids.to_dict('records'):
 r=bykey[(rr['sid'],rr['opened'])]
 assert abs(r['pnl']-rr['pnl'])<1e-6,(r['sid'],r['pnl'],rr['pnl'])
checks=[]
for r in rounds:
 if not r['closed'] or not r['obs']:continue
 o=r['obs'][-1]
 if dayindex[o['day']]+1>=len(days) or days[dayindex[o['day']]+1]!=r['closed'][:10] or not o['valid']:continue
 v=open_eval(o)
 if 'round_net' in v and not any(buys[k]['at'][:10]==r['closed'][:10] for k in r['layer_ids']):checks.append((abs(v['round_net']-r['pnl']),r['sid'],r['opened'],v['round_net'],r['pnl']))
print('ACTUAL_FINAL_CLOSE_MATCH',len(checks),'maxdiff',max(checks) if checks else None)
for name,rs in [('B',B),('Y22',Y22)]:
 inc=[r for r in rs if r.get('incremental_q',0)>0]
 print(name,'TRANSITIONS',dict(Counter(('win' if r['pnl']>0 else 'loss')+'->'+('win' if r['stop_next'].get('round_net',-1)>0 else 'loss') for r in inc)))
 armed=[r for r in rs if r['arm_day']]
 print(name,'ARM',dict(any_original_below=sum(r['arm_any_orig_line_below_cost'] for r in armed),nextwarnings=[(r['sid'],r['arm_day'],r['arm_next']['warnings']) for r in armed if r['arm_next'].get('warnings')],R_over_K_percentiles=np.percentile([r['arm_R']/r['arm_K'] for r in armed],[0,25,50,75,100]).tolist(),arm_to_stop_sessions_percentiles=np.percentile([r['arm_to_stop_sessions'] for r in inc],[0,25,50,75,100]).tolist(),adds_after_arm=sum(r['adds_after_arm']>0 for r in inc)))
 if name=='B':
  print('B_GIVEBACK',dict(arm_next_R_fraction_percentiles=np.percentile([r['arm_next']['giveback_from_close']/r['arm_R'] for r in armed],[0,25,50,75,100]).tolist(),stop_next_U_percentiles=np.percentile([r['stop_next']['U'] for r in inc],[0,25,50,75,100]).tolist(),stop_gap_to_halfR_percentiles=np.percentile([.5*r['stop_R']-r['stop_U'] for r in inc],[0,25,50,75,100]).tolist(),stop_close_positive_but_next_negative=sum(r['stop_U']>0 and r['stop_next']['U']<=0 for r in inc)))
print('WINNERS_DETAILS')
for y,rs in tops.items():
 for r in rs:
  if r.get('incremental_q',0)>0:
   print(json.dumps({k:r[k] for k in ['sid','opened','closed','pnl','arm_day','arm_U','arm_R','stop_day','stop_U','stop_R','stop_Q','incremental_q','stop_after_position_change','adds_after_arm','stop_next']}))
print('WORST_B_DETAILS')
for r in sorted([r for r in B if r['arm_day']],key=lambda r:r['pnl'])[:5]:
 print(json.dumps({k:v for k,v in r.items() if k not in ['layer_ids']}))
factor_changes=[]
for k,t in buys.items():
 ff0=ff[t['security_id']]
 sig=float(ff0.loc[t['signal_at'][:10],'factor']);cur=float(ff0.loc[t['at'][:10],'factor'])
 if abs(cur/sig-1)>1e-8:factor_changes.append((k,t['security_id'],t['signal_at'],t['at'],cur/sig))
print('BUY_SIGNAL_FACTOR_CHANGES',len(factor_changes),factor_changes[:10])
selected_ids=set(k for r in B+tops['2024']+tops['2025'] for k in r['layer_ids'])
print('SELECTED_FACTOR_CHANGES',[z for z in factor_changes if z[0] in selected_ids])
protection=[]
for r in B:
 if not r['arm_day']:continue
 o=next(o for o in rmap[r['sid'],r['opened']]['obs'] if o['day']==r['arm_day'])
 proposed=riskline(o,.5*o['R']);avg=o['K']/o['Q']
 protection.append(dict(sid=r['sid'],opened=r['opened'],day=o['day'],cost_avg=avg,profit_half_R_line=proposed,line_over_cost_pct=proposed/avg-1))
print('HALFR_LINE_COST_PERCENTILES',np.percentile([r['line_over_cost_pct'] for r in protection],[0,25,50,75,100]).tolist())
print('2022_B_UNTRIGGERED_AFTER_ARM',[(r['sid'],r['arm_day'],r['closed'],r['pnl']) for r in B if r['arm_day'] and not r.get('stop_day')])
print('TOP40_TOTAL',sum(r['pnl'] for rs in tops.values() for r in rs),'harm_count',sum(r.get('incremental_q',0)>0 and r['stop_next']['round_net']<r['pnl'] for rs in tops.values() for r in rs))
print('BAD_RISK_ZERO',[(k,buys[k]['security_id'],buys[k]['at'],rmeta[k]) for k in irisk if irisk[k]<=0])

O=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/account_comparison_continuous_v1/analysis/one_r_giveback_audit_v1")
def flatten(r):
 z={k:v for k,v in r.items() if not isinstance(v,dict)}
 for k,v in r.items():
  if isinstance(v,dict):z.update({k+'_'+k2:(json.dumps(v2) if isinstance(v2,(list,dict)) else v2) for k2,v2 in v.items()})
 return z
pd.DataFrame([flatten(r) for r in B]).to_csv(O/'B242_ROUNDS.csv',index=False)
pd.DataFrame([dict(close_year=y,rank=i+1,**flatten(r)) for y,rs in tops.items() for i,r in enumerate(rs)]).to_csv(O/'TOP40_WINNERS.csv',index=False)
dailyrows=[]
for r in brounds:
 for o in r['obs']:
  z={k:v for k,v in o.items() if k not in ['layers','round']}
  z['opened']=r['opened'];z['original_final_pnl']=r['pnl']
  factor=float(ff[r['sid']].loc[o['day'],'factor'])
  z['layer_snapshot']=json.dumps([dict(id=l['id'],kind=l['kind'],qty=l['qty'],original_initial_risk=irisk[l['id']],current_line_raw=(float(l['last_core_line']) if l['kind']=='core' else float(l['floor']))/factor) for l in o['layers']])
  for k in ['open','high','low','close','volume']:z['raw_'+k]=float(raw[r['sid']].loc[o['day'],k]) if o['day'] in raw[r['sid']].index else None
  dailyrows.append(z)
pd.DataFrame(dailyrows).to_csv(O/'B242_DAILY_RISK.csv',index=False)
pd.DataFrame(protection).to_csv(O/'B242_ARM_PROTECTION.csv',index=False)
summaryout=dict(status='REJECT_FIXED_MECHANISM_AS_STRATEGY_IMPROVEMENT',account_runs=0,parameter_grid_runs=0,real_execution_confirmed=False,B242=summary(B),all_closed_2022=summary(Y22),top20_by_closure_year={y:summary(rs) for y,rs in tops.items()},validation=dict(reconstructed_stock_close_observations=len(allobs),matched_2022_observations=len(old),max_2022_unrealized_difference=maxdelta,original_final_exit_proxy_reconciliations=len(checks),max_original_exit_net_difference=max(c[0] for c in checks)),limitations=['First-intervention-only frozen original fill path, not a counterfactual strategy or account.','All daily OPEN tradability remains unknown; no claim of executable profit.','The historical protection-armed state persists after later adds; this is a demonstrated mechanism failure, not silently repaired.','Top20 are ex-post diagnostic groups by round closure year; not signal inputs.'])
(O/'SUMMARY.json').write_text(json.dumps(summaryout,ensure_ascii=False,indent=2))
srcpaths=[P/'run_1200000/pair/PVR.json.gz',P/'run_1200000/pair/daily.jsonl.gz',P/'analysis/2022_independent_review/CLOSED_ROUNDS_MFE.csv',P/'analysis/2022_independent_review/ROUND_DAILY_CLOSE.csv',U/'STOCK_MANIFEST.json',PREP/'manifest.json',C.J.M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',C.J.M.BP.C.OLD/'inputs-v2/economic-protocol.json']
sourcehash={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in srcpaths}
used=set(k for r in B+tops['2024']+tops['2025'] for k in r['layer_ids'])
for sid in sorted({layers[k]['sid'] for k in used}):
 p=Path(records[sid]['raw']['path']);h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==records[sid]['raw']['sha256'];sourcehash[str(p)]=h
 p=Path(sm[sid]['refs']['facts']);h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==sm[sid]['output_sha256'][str(p)];sourcehash[str(p)]=h
(O/'SOURCE_SHA256.json').write_text(json.dumps(sourcehash,indent=2))
(O/'READOUT.md').write_text("# 1R后保护利润：固定单机制的原路径审计\n\n结论：否决将这个固定机制直接升级为策略改进。退出在概念上可以把部分亏损回合转成净赢，但本证据不支持靠简单锁利达到30%完整回合胜率，也不能保证保住大赢家。账户运行0次、参数网格0次、实际交易0次。\n\n## 冻结口径\n\n在观察机制结果前固定一个候选：各当前剩余层的入场原始风险合成为R_t；首次真实收盘净浮盈U_t达到R_t后激活；以后首次真实收盘U_t回落至0.5R_t以下，新增请求清空当前全股，下一共同交易日OPEN仅做报价诊断。\n\n每层原始风险 = max(含买费入场成本 − 初始股数×原保护线raw×(1−5bp) + 原保护线卖费, 0)。原保护线按实际买入日已知因子转换；跨除权日单位校验纠正了初稿的signal日因子转换，2022与40大赢家计数均未变化。新增层计入自身完整原始风险，部分卖出按层份额释放，拆股保持剩余风险金额不变。它是原结构风险代理，CORE引用线本来并非直接止损价，更不是保证最大损失。\n\nU按股票整体移动平均含费剩余成本计算；整回合净值另含此前已实现现金与应计股息，不混淆。只用真实、observed、eligible、非synthetic收盘判断。保留原路径至首次新增干预，之后不计算重新入场、资金再分配或新账户。\n\n## 2022的242个曾有≥3%净浮盈而最终亏损回合\n\n- 仅65个达到过1R，177个从未达到。65个的R_t/剩余成本中位数8.46%，四分位7.21%至10.92%；事后曾赚3%不等于已经赚够其原始风险。\n- 达1R后的下一共同OPEN代理，65个仍为正净浮盈、整回合亦正；其中2个翌日全日H=L，列为成交不确定。其余63个也只能称无此日线警告，不能证明现实开盘可成交。\n- 65个中，达1R当日30个所有原线仍低于全股平均成本，38个至少一条低于成本。CORE引用线与MOBILE实际保护线不混称。半R新增线中位高于平均成本4.42%，范围0.88%至11.56%，不是紧贴成本的纯保本线。\n- 半R收盘保护共62次触发；17次原规则当日已请求全部卖出，只有45次新增退出。\n- 45次新增退出中，次日OPEN代理只有29次整回合仍净赢，16次仍亏。35次触发收盘时剩余U仍正，其中7次到下一OPEN转负；另有1次由负转正。\n- 收盘已穿越半R金额线的差额中位451.71元，说明不能拿理论保护线当成交价。002911的半R线对应应留约3427元，触发收盘只剩795元，次日OPEN代理已经−5035元，原最终−8331元。\n- 19/45在激活后又加仓；14/45触发当天持股数或成本发生变化。不能把全部触发解释为价格回吐。\n\n这29个只是在原路径首次截断处的正净值，绝不是已验证能新增29个完整回合赢家；后续重新买入、资金占用、交易分组都会变化。45个的静态截断净值较原最终合计高69682元，也不是可追回或新账户收益。\n\n## 同规则检查2024/2025大赢家\n\n定义事后反证样本：按原完整回合清仓年份，2024与2025各取净利润最高20个，共40个；仅用于检查误伤，不用于选择参数。\n\n- 2024提前退出6/20，2025提前退出3/20，共9个；其中7个利润减少，2个是已有大部分利润兑现后的尾仓较早退出，不能全称错失大行情。\n- 9个静态截断后比原回合合计少58151.32元，40个原总净利487774.84元；两年各有1个原大赢家在代理提前出口变负。\n- 无激活后加仓也会错杀：300475，2025-09-22达到1R，9月25日触发、26日OPEN只余+1060.56元，原到11月21日完整回合+16673.42元。\n- 002779，2024-10-25达到1R，10月31日触发、11月1日OPEN只余+298.51元，原到12月16日+7110.26元。\n- 9个中5个触发当天仓位/成本变化。即使R_t已随全仓重算，永久激活状态仍会把小仓曾走对的保护资格带给后来大仓。002131最早U=27.66、R=26.35，之后加仓到7300股便触发，代理提前净值−1594.19元，原最终+10055.67元。这是机制结构性问题，不能只宣传亏转赢计数。\n\n没有看到结果后重置激活、换阈值或只删掉误伤案例。本候选不通过，另做机制必须重新说明问题并冻结，不能隐含晋升。\n\n## 完整2022交叉核验与边界\n\n原692个已闭回合中，该固定机制78次新增提前退出。静态方向为30个亏转赢、17个亏仍亏、31个赢仍赢；没有新账户胜率。由130/692达到30%至少需要208个赢，即净增加78个赢，30个静态方向变化既不足，也不是可直接兑现的净增加。\n\n用原逐笔实际买卖/拆股重建54820个持仓股票日；2022已有12987个观察的数量、有效性、含费剩余成本逐一一致，净浮盈最大差2.2e−11元。2624个有下一共同日完整清仓可对比的原回合，用最后收盘状态与实际次OPEN报价、费用、股息重构，净PnL最大差2.6e−11元。\n\n严格区分T+1时序与真实可成交：当日收盘才触发，最早下一共同OPEN；新拆股股数未满足可卖条件则标未知，不强行全卖。OPEN原始报价、过去20日容量与已有允许卖出元数据只是研究代理；缺少真实停牌/涨跌停队列/逐笔成交资料，因此所有现实成交均未知。全日H=L等仅事后警告，不反向用于信号。当前存续股票池和当前分类的选样偏差保留。\n\n文件：B242_ROUNDS.csv、B242_DAILY_RISK.csv、B242_ARM_PROTECTION.csv、TOP40_WINNERS.csv、SUMMARY.json、SOURCE_SHA256.json、audit.py。数据与报告仅为诊断，不是投资建议、账户改进或上线授权。\n")
(O/'OUTPUT_SHA256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'},indent=2))
print('SAVED',str(O),'B242_rows',len(B),'daily_rows',len(dailyrows),'source_hashes',len(sourcehash),flush=True)
