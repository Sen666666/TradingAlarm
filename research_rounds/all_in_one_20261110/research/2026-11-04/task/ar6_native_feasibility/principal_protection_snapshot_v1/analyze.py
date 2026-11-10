from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import json,gzip,hashlib,time
import pandas as pd
O=Path(__file__).resolve().parent;T=O.parents[1];W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
LAY=T/'risk_constraints/no60_continuation2023_finance/analysis/2022_2023/PVR_NO_CONFIRMED60/LAYERS.json'
EX=T/'pvr_pool_feasibility/market_phase_2022_2023/NO60_ACTUAL_EXECUTABLE_FILLS.json';SNAP=T/'pvr_pool_feasibility/continuation2023/run-2023/pair/daily.jsonl.gz'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 start=time.monotonic();assert not(O/'RESULTS.json').exists(),'no repeat'
 freeze=read(O/'SOURCE_FREEZE.json')
 for p,h in freeze['sources'].items():assert sha(p)==h,p
 base={r['layer']:r for r in read(LAY)};assert len(base)==1557 and all(r['qty']==0 for r in base.values())
 ex={}
 for a in read(EX):
  for x in a['actual_fills']:ex[x['layer']]=dict(price=x['price'],quantity=x['shares'],opened=x['at'],decision_at=a['signal_day']+' 15:10:00+08:00',initial_floor=a['frozen_floor_adjusted'])
 assert set(ex)==set(base)
 facts={sid:pd.read_parquet(p,columns=['factor','raw_close','segment_id']).loc['2022':'2023']for sid,p in freeze['facts'].items()}
 actions={sid:read(p)['events']for sid,p in freeze['actions'].items()};records={};witnesses=[];calendar=[]
 for k,b in base.items():
  e=ex[k];sid=b['sid'];ef=facts[sid].loc[pd.Timestamp(e['opened'][:10])];df=facts[sid].loc[pd.Timestamp(e['decision_at'][:10])]
  initial_unknown=[]
  if str(ef.segment_id)!=str(df.segment_id)or D(str(ef.factor))!=D(str(df.factor)):initial_unknown.append('DECISION_FILL_UNIT_CHANGED')
  if any(e['decision_at'][:10]<a['effective_date']<=e['opened'][:10]for a in actions[sid]):initial_unknown.append('DECISION_FILL_ACTION_INTERVAL')
  init_hit=None if initial_unknown else D(str(e['initial_floor']))/D(str(ef.factor))>=D(str(e['price']))
  records[k]=dict(**b,entry_execution_price=str(e['price']),entry_qty=e['quantity'],decision_at=e['decision_at'],entry_source_segment=str(ef.segment_id),entry_factor=str(ef.factor),initial_at_fill_hit=init_hit,initial_unknown=initial_unknown,observations=0,known_observations=0,unknown_observations=0,qty_changed_observations=0,pending_exit_observations=0,first_snapshot_hit=None,first_hit_without_pending_exit=None,first_revert_after_hit=None,unknown_after_hit=0,last_snapshot=None)
 with gzip.open(SNAP,'rt')as stream:
  for line in stream:
   snap=json.loads(line);day=snap['at'][:10]
   if not('2022-01-04'<=day<='2023-12-29'):continue
   calendar.append(day);pending=set(snap['pending_sells'])
   for lot in snap['layers']:
    k=lot['id'];r=records[k];sid=lot['sid'];e=ex[k];unknown=[];q=lot['qty'];line=lot['last_core_line']if lot['role']=='core'else lot['floor']
    assert sid==r['sid']and lot['role']==r['role']
    f=facts[sid].loc[pd.Timestamp(day)]if pd.Timestamp(day)in facts[sid].index else None
    if f is None:unknown.append('CURRENT_FACTS_ABSENT')
    elif str(f.segment_id)!=r['entry_source_segment']or D(str(f.factor))!=D(r['entry_factor']):unknown.append('CURRENT_SOURCE_FACTOR_CHANGED_NO_UNIT_CONVERSION')
    if any(e['opened'][:10]<a['effective_date']<=day for a in actions[sid]):unknown.append('POST_ENTRY_CORPORATE_ACTION_NO_NEW_CONVERSION')
    if line is None:unknown.append('EFFECTIVE_LINE_ABSENT')
    if D(str(lot['unit_cost']))!=D(str(float(e['price']))):unknown.append('CURRENT_UNIT_COST_DIFFERS_FROM_ORIGINAL_UNIT')
    if lot['qty']<=0:unknown.append('NO_REMAINING_SHARES')
    known=not unknown;rawline=None if not known else D(str(line))/D(str(f.factor));hit=None if not known else rawline>=D(str(e['price']))
    x=dict(layer=k,sid=sid,day=day,at=snap['at'],role=lot['role'],pool=lot['pool'],qty=q,qty_changed=q!=e['quantity'],epoch=lot['epoch'],attempt=lot['attempt'],source_segment=None if f is None else str(f.segment_id),current_factor=None if f is None else str(f.factor),effective_line_signal=None if line is None else str(line),effective_line_raw=None if rawline is None else str(rawline),entry_execution_price=e['price'],native_current_unit_cost=str(lot['unit_cost']),pending_stock_exit=sid in pending,pending_scope='ANY_STOCK_PENDING_EXIT_CONSERVATIVE_NOT_LAYER_ACK',known=known,unknown=unknown,current_floor_at_or_above_entry=hit)
    r['observations']+=1;r['known_observations']+=known;r['unknown_observations']+=not known;r['qty_changed_observations']+=x['qty_changed'];r['pending_exit_observations']+=x['pending_stock_exit']
    if hit and r['first_snapshot_hit']is None:r['first_snapshot_hit']=x
    if hit and not x['pending_stock_exit']and r['first_hit_without_pending_exit']is None:r['first_hit_without_pending_exit']=x
    if r['first_snapshot_hit']is not None and hit is False and r['first_revert_after_hit']is None:r['first_revert_after_hit']=x
    if r['first_snapshot_hit']is not None and hit is None:r['unknown_after_hit']+=1
    r['last_snapshot']=x;witnesses.append(x)
 assert len(calendar)==484
 pos={d:i for i,d in enumerate(calendar)}
 for r in records.values():
  r['first_hit_delay_sessions']=None if r['first_snapshot_hit']is None else pos[r['first_snapshot_hit']['day']]-pos[r['opened'][:10]]
  r['net_sign_POSTHOC']='positive'if D(r['net'])>0 else'negative'if D(r['net'])<0 else'zero'
  r['postfill_advance_claim']=r['first_snapshot_hit']is not None and r['initial_at_fill_hit']is False
 save('ALL_1557_LAYERS.json',list(records.values()))
 with gzip.open(O/'DAILY_SNAPSHOT_WITNESSES.jsonl.gz','wt',compresslevel=1)as f:
  for x in witnesses:f.write(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n')
 summary=[]
 for role in ['ALL','core','mobile']:
  for sign in ['ALL','positive','negative','zero']:
   rr=[r for r in records.values()if(role=='ALL'or r['role']==role)and(sign=='ALL'or r['net_sign_POSTHOC']==sign)]
   summary.append(dict(role=role,net_sign_POSTHOC=sign,layers=len(rr),initial_at_fill_hits=sum(r['initial_at_fill_hit']is True for r in rr),ever_snapshot_hit=sum(r['first_snapshot_hit']is not None for r in rr),ever_not_pending_hit=sum(r['first_hit_without_pending_exit']is not None for r in rr),postfill_progress_hits=sum(r['postfill_advance_claim']for r in rr),known_reverted_after_hit=sum(r['first_revert_after_hit']is not None for r in rr),unknown_after_hit_layers=sum(r['unknown_after_hit']>0 for r in rr),any_unknown_layers=sum(r['unknown_observations']>0 for r in rr),no_observation_layers=sum(r['observations']==0 for r in rr),hit_delay_histogram=dict(Counter(str(r['first_hit_delay_sessions'])for r in rr if r['first_hit_delay_sessions']is not None))))
 save('SUMMARY.json',summary)
 for p,h in freeze['sources'].items():assert sha(p)==h,p
 save('RESULTS.json',dict(passed=True,seconds=time.monotonic()-start,layers=1557,snapshot_dates=484,witnesses=len(witnesses),cutoff='2023-12-29',new_accounts=0,new_price_models=0,new_CA_conversion=False,entryprice_nominal_excludes_fees=True,no_grant_or_credit=True,not_permanent_graduation=True,no_automatic_followup=True))
if __name__=='__main__':main()
