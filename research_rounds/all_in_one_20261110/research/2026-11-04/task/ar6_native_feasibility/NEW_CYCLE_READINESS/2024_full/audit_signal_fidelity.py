"""Actual2024 planner logs vs newly loaded frozen facts; no Account/events."""
from pathlib import Path
from types import SimpleNamespace
from collections import Counter,defaultdict
from decimal import Decimal as Dec
import json,gzip,time,math
import pandas as pd
import cycle2024_adapter as C
O=C.O/'SIGNAL_FIDELITY';O.mkdir(exist_ok=True)
FOCUS_START,FOCUS_END='2024-09-24','2024-10-10'
def rows(p):
 with gzip.open(p,'rt')as f:
  for line in f:
   if line.strip():yield json.loads(line)
def save(n,x):C.save(O/n,x)
def counter():return Counter()
def main():
 begun=time.monotonic();shared,receipts,cp,states,ir,identity=C.inputs();bundle,market,facts=shared
 probe=SimpleNamespace(facts=facts,market=market,cp=cp)
 scores=C.D.scores();days=C.read(C.NEW_SCORE)['decision_calendars']['2024']
 stage={s:{x['day']:x for x in rr if x['day'].startswith('2024')}for s,rr in states.items()}
 recovery=pd.read_csv(C.J.M.O/'recovery.csv',index_col=0,parse_dates=True)
 expected={};daily_expected=[]
 for n,day in enumerate(days,1):
  at=C.J.M.N.iso(day+'T15:10:00+08:00');clock,op=C.J.W.stock_opportunities(probe,at)
  ordered=sorted(op,key=lambda x:(-(x['rank']if x['rank']is not None else -1),x['sid']))
  by={x['sid']:dict(x,H1_position=i,CP1_id=receipts[x['sid']].get(day,{}).get('receipt_id'))for i,x in enumerate(ordered)}
  assert len(by)==1709
  expected[day]=by
  daily_expected.append(dict(day=day,core_Q=sum(x['core_Q']is True for x in op),mobile_Q=sum(x['mobile_Q']is True for x in op),
   CP1=sum(x['stock_CP1']for x in op),eligible_mobile=sum(x['mobile_candidate']for x in op),
   PVR_ready=sum(scores.at(s,day)is not None for s in by),market_stage=dict(Counter(stage[s][day]['stage_name']for s in stage)),
   fast=bool(recovery.loc[day].fast_on),breakout=bool(recovery.loc[day].breakout)))
  if n%40==0:print('FACT_FIDELITY',n,'/242',round(time.monotonic()-begun,2),flush=True)
 save('EXPECTED_DAILY_INPUTS.json',daily_expected)
 results=[];mismatches=[]
 pure={'bundle','market','facts','cp','pv','matrix','matrix_days','industry_rows','industry_cp','receipts','actions_by_date','episode_starts','RECOVERY','RECOV'}
 for policy in ['original','no60']:
  root=C.root(policy);p=root/'run-2024/pair';monthly=defaultdict(counter);focus={}
  daily={x['at'][:10]:x for x in rows(p/'daily.jsonl.gz')if x['at'].startswith('2024')};assert len(daily)==242
  for day,d in daily.items():
   m=monthly[day[:7]];m['closes']+=1;m['ACT_on']+=int(d['on']);m['held_stock_days']+=len(d['positions'])
   if FOCUS_START<=day<=FOCUS_END:
    at=C.J.M.N.iso(day+'T15:10:00+08:00');marks=market.marks(at,d['positions']);nav=Dec(d['nav'])
    weights={s:Dec(q)*marks[s].cny_price(at)/nav for s,q in d['positions'].items()}
    assert sum((Dec(q)*marks[s].cny_price(at)for s,q in d['positions'].items()),Dec(0))==Dec(d['inventory'])
    role=defaultdict(Dec);pool=defaultdict(Dec)
    for x in d['layers']:
     value=Dec(x['qty'])*marks[x['sid']].cny_price(at);role[x['role']]+=value;pool[x['pool']]+=value
    focus[day]=dict(on=d['on'],NAV=d['nav'],inventory=d['inventory'],exposure_fraction=str(Dec(d['inventory'])/nav),held_stocks=len(d['positions']),
     pending_intents=d['pending_intents'],top10_weights=[dict(sid=s,weight=str(v))for s,v in sorted(weights.items(),key=lambda x:-x[1])[:10]],
     role_weights={k:str(v/nav)for k,v in role.items()},pool_weights={k:str(v/nav)for k,v in pool.items()},
     opportunities=Counter(),barriers=Counter(),funding_OPEN=Counter(),funding_CLOSE=Counter(),funding_open_sids=defaultdict(set),
     buys=0,sells=0,buy_gross=Dec(0),sell_gross=Dec(0),ranked_stocks=0,ranked_PVR_ready=0)
  checks=Counter();seen=Counter()
  for x in rows(p/'opportunities.jsonl.gz'):
   day=x['day']
   if not day.startswith('2024'):continue
   e=expected[day][x['sid']];m=monthly[day[:7]];seen[day]+=1;checks['opportunity_records']+=1
   comparisons={'core_Q':e['core_Q'],'mobile_Q':e['mobile_Q'],'CP1_id':e['CP1_id'],'sector':e['sector'],'rank':e['H1_position']}
   for k,v in comparisons.items():
    if x[k]!=v:mismatches.append(dict(policy=policy,day=day,sid=x['sid'],field=k,actual=x[k],expected=v))
    checks[k+'_comparisons']+=1
   assert e['stock_CP1']==(e['CP1_id']is not None)
   if ('mobile'in x['roles'])!=bool(e['mobile_Q']is True and e['CP1_id']):mismatches.append(dict(policy=policy,day=day,sid=x['sid'],field='mobile_role'))
   if ('ACT_paused'in x['barriers'])!=(not daily[day]['on']):mismatches.append(dict(policy=policy,day=day,sid=x['sid'],field='ACT_barrier'))
   m['opportunity_records']+=1;m['core_Q']+=int(x['core_Q']is True);m['mobile_Q']+=int(x['mobile_Q']is True);m['CP1']+=int(x['CP1_id']is not None)
   m['eligible_mobile']+=int('mobile'in x['roles']);m['roles_any']+=int(bool(x['roles']));m['ACT_paused_stockdays']+=int('ACT_paused'in x['barriers'])
   if day in focus:
    z=focus[day];z['opportunities'].update(dict(core_Q=int(x['core_Q']is True),mobile_Q=int(x['mobile_Q']is True),CP1=int(x['CP1_id']is not None),
       eligible_mobile=int('mobile'in x['roles']),core_role=int('core'in x['roles']),held=int(x['held']),roles_any=int(bool(x['roles']))))
    z['barriers'].update(x['barriers'])
  assert checks['opportunity_records']==413578 and all(v==1709 for v in seen.values())
  for x in rows(p/'industry.jsonl.gz'):
   day=x['day']
   if not day.startswith('2024'):continue
   e=stage[x['sector']][day];checks['actual_stage_events']+=1
   if x['market_stage']!=e['stage_name']:mismatches.append(dict(policy=policy,day=day,sector=x['sector'],field='market_stage'))
   if e['E0_valid']and x['episode']!=e['E0_episode']:mismatches.append(dict(policy=policy,day=day,sector=x['sector'],field='industry_episode'))
   monthly[day[:7]]['stage_event_'+x['market_stage']]+=1
  for x in rows(p/'rank-policy.jsonl.gz'):
   day=x['day']
   if not day.startswith('2024'):continue
   value=scores.at(x['sid'],day);checks['rank_records']+=1
   if value!=x['PVR']or (value is not None)!=x['PVR_ready']:mismatches.append(dict(policy=policy,day=day,sid=x['sid'],field='PVR_value'))
   monthly[day[:7]]['ranked_stock_intents']+=1;monthly[day[:7]]['ranked_PVR_ready']+=int(x['PVR_ready'])
   if day in focus:focus[day]['ranked_stocks']+=1;focus[day]['ranked_PVR_ready']+=int(x['PVR_ready'])
  for x in rows(p/'funding.jsonl.gz'):
   day=x['at'][:10]
   if not day.startswith('2024'):continue
   phase='OPEN'if '09:30'in x['at']else'CLOSE';monthly[day[:7]]['funding_'+phase+'_'+x['result']]+=1
   if day in focus:
    focus[day]['funding_'+phase][x['result']]+=1
    if phase=='OPEN':focus[day]['funding_open_sids'][x['result']].add(x['sid'])
  with gzip.open(p/'B.json.gz','rt')as f:book=json.load(f)
  for x in book['audit']:
   if x['kind']!='risk_checkpoint'or not x['at'].startswith('2024'):continue
   day=x['at'][:10];e=recovery.loc[day];checks['ACT_input_records']+=1
   if x['fast']!=bool(e.fast_on)or x['breakout']!=bool(e.breakout):mismatches.append(dict(policy=policy,day=day,field='ACT_recovery_input'))
   if x['on']!=daily[day]['on']:mismatches.append(dict(policy=policy,day=day,field='ACT_daily_state'))
   monthly[day[:7]]['fast_days']+=int(x['fast']);monthly[day[:7]]['breakout_days']+=int(x['breakout'])
   if x.get('event'):monthly[day[:7]]['ACT_'+x['event']]+=1
   if day in focus:focus[day]['actual_ACT_checkpoint']=x
  for x in book['trades']:
   day=x['at'][:10]
   if day not in focus:continue
   if x['side']=='buy':focus[day]['buys']+=1;focus[day]['buy_gross']+=Dec(x['gross_cny'])
   elif x['side']=='sell':focus[day]['sells']+=1;focus[day]['sell_gross']+=Dec(x['gross_cny'])
  proof=C.read(root/'VERIFIED_HORIZON_IMPORT.json');copied=set(proof['all_strategy_fields_equal']);assert not(copied&pure)
  for day in focus:focus[day]['funding_open_sids']={k:len(v)for k,v in focus[day]['funding_open_sids'].items()}
  result=dict(policy=policy,checks=dict(checks),monthly={k:dict(v)for k,v in sorted(monthly.items())},focus=focus,
    actual_parent_copied_strategy_fields=sorted(copied),future_input_fields_absent_from_copy=sorted(pure),
    pure_episode_lookup_rebuilt=proof['parent_lookup_reconstructed_from_immutable_state'],source_identity=C.sha(root/'HORIZON_SOURCE_FREEZE.json'))
  save(policy+'-ACTUAL_VS_FROZEN.json',result);results.append(dict(policy=policy,checks=dict(checks)))
  print('ACTUAL_FIDELITY_SIDE_DONE',policy,dict(checks),round(time.monotonic()-begun,2),flush=True)
 save('MISMATCHES.json',mismatches)
 summary=dict(passed=not mismatches,account_events=0,completed_sources_unchanged=True,checks=results,mismatch_count=len(mismatches),
  scope='Actual all2024 planner Q/H1/CP1/ACT/stage/score logs vs freshly loaded frozen2024 facts; no new account execution.',
  fullmonth_dates=242,focus=[FOCUS_START,FOCUS_END],source=__file__,source_sha256=C.sha(__file__),seconds=time.monotonic()-begun)
 save('GATE.json',summary);print('SIGNAL_FIDELITY_DONE',json.dumps(summary),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(error=repr(e),traceback=__import__('traceback').format_exc(),account_events=0));raise
