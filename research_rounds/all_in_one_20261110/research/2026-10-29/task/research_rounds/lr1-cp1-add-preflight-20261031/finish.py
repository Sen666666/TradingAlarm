"""Compact final tables and event checks. Reads completed paths, no simulation."""
import adapter as M
from run_stage import rows,obj
from pathlib import Path
import pandas as pd,numpy as np,collections,time,json,gzip,shutil
O=M.O
def objects(sec,name):
 path=O/sec/('repair-full' if name=='ADD_delay1' else 'full')/'results'/f'{name}.json.gz'
 return obj(path)
def main():
 ss=pd.concat([pd.read_csv(O/s/'analysis/summary.csv') for s in ['TECH','DRUG']],ignore_index=True);ss.to_csv(O/'MATRIX_12.csv',index=False)
 bridges=[];opchecks=[];paired=[];examples=[];acts=[];sources=[];post=[];unknown=[];rawfiles={}
 for sec in ['TECH','DRUG']:
  assert M.read(O/sec/'analysis/ACCOUNTING.json')['passed']
  dd=[x for x in rows(O/sec/'full/results/daily.jsonl.gz') if x['account']!='ADD_delay1']+rows(O/sec/'repair-full/results/daily.jsonl.gz')
  prep=Path(M.read(O/sec/'full/results/META.json')['prep']);manifest=M.RR/'pvr-act-comparison-20261027/input/manifest.json' if sec=='TECH' else prep/'manifest.json'
  for rec in M.read(manifest)['series']:
   for part in [rec['raw'],rec.get('adjustment',{}).get('actions')]:
    if isinstance(part,dict) and part.get('path') and part.get('sha256'):rawfiles[part['path']]=part['sha256']
  for name in sorted({x['account'] for x in dd}):
   ds=[x for x in dd if x['account']==name];s=ss[(ss.sector==sec)&ss.account.eq(name)].iloc[0];positiondays=sum(len(x['positions']) for x in ds);layerdays=sum(len(x['layers']) for x in ds)
   unknown.append(dict(sector=sec,account=name,unknown_price_position_days=int(s.price_unknown_position_days),position_day_denominator=positiondays,unknown_price_fraction=float(s.price_unknown_position_days/positiondays) if positiondays else None,unknown_floor_layer_days=int(s.floor_unknown_layer_days),layer_day_denominator=layerdays))
  ints=pd.read_csv(O/sec/'analysis/intents.csv');stock=pd.read_csv(O/sec/'analysis/stock-bridge.csv')
  for stress in ['base','cost2','delay1']:
   a=ss[(ss.sector==sec)&ss.account.eq('L0_'+stress)].iloc[0];b=ss[(ss.sector==sec)&ss.account.eq('ADD_'+stress)].iloc[0]
   d=float(b.final_nav-a.final_nav);core=float(b.core_profit-a.core_profit);add=float(b.add_profit)
   assert abs(d-core-add)<.01
   tail=float(b.tail30_closed_profit-a.tail30_closed_profit);ordinary=float(b.ordinary_closed_profit-a.ordinary_closed_profit);opened=float(b.open_profit-a.open_profit)
   assert abs(d-tail-ordinary-opened)<.01
   bridges.append(dict(sector=sec,stress=stress,total_difference=d,core_contribution_difference=core,ADD_layer_profit=add,tail30_closed_difference=tail,ordinary_closed_difference=ordinary,open_difference=opened,fee_difference=b.fees-a.fees,slippage_difference=b.slippage-a.slippage))
   aa=objects(sec,'L0_'+stress);bb=objects(sec,'ADD_'+stress)
   for label,ob in [('L0',aa),('ADD',bb)]:
    for x in ob['audit']:
     if x['kind']=='risk_checkpoint' and x.get('event'):acts.append(dict(sector=sec,stress=stress,arm=label,**x))
   ia=ints[ints.account.eq('L0_'+stress)&ints.kind.eq('core')];ib=ints[ints.account.eq('ADD_'+stress)&ints.kind.eq('core')]
   joint=ia.merge(ib,on=['decision','sid'],suffixes=('_baseline','_candidate'))
   cashreject={}
   for x in bb['audit']:
    if x['kind']=='lot_allocation' and not x['minimum_selected']:cashreject[(x['sid'],x['at'][:10])]=x
   funded_by_signal=collections.defaultdict(list)
   for x in bb['audit']:
    if x['kind']=='lot_risk_funded':funded_by_signal[x['signal_at']].append(x)
   calendar=sorted(set(M.read(O/sec/'full/execution-rules-v2.json')['calendars']['A'])|{f'2026-10-{d}T09:30:00+08:00' for d in ['27','28','29','30']});cal=pd.DatetimeIndex(calendar)
   n=0
   for _,x in joint.iterrows():
    if x.funded_shares_baseline<=0 or x.funded_shares_candidate>0 or pd.notna(x.size_reject_candidate):continue
    possible=funded_by_signal[x.decision];j=cal.searchsorted(pd.Timestamp(x.decision),side='right');d=str(cal[j].date()) if j<len(cal) else None
    hit=cashreject.get((x.sid,d))
    if not hit:continue
    n+=1;adds=[z for z in possible if z['layer_kind']=='add']
    paired.append(dict(sector=sec,stress=stress,decision=x.decision,symbol=x.sid,baseline_funded_shares=int(x.funded_shares_baseline),candidate_funded_shares=0,allocation_at=hit['at'],minimum_cash=hit['minimum_cash'],ideal_cash=hit['ideal_cash'],ADD_orders_same_open=len(adds),ADD_reserved_cash_same_open=sum(float(z['gross'])+float(z['fees']) for z in adds)))
   keys_a=set(zip(ia.decision,ia.sid));keys_b=set(zip(ib.decision,ib.sid))
   post.append(dict(sector=sec,stress=stress,common_core_intents=len(keys_a&keys_b),baseline_only_core_intents=len(keys_a-keys_b),candidate_only_core_intents=len(keys_b-keys_a),common_core_baseline_funded_candidate_explicit_minimum_cash_rejected=n))
   # First actual transaction-set difference; descriptive timeline, not unique cause.
   ta=collections.defaultdict(list);tb=collections.defaultdict(list)
   for ob,by in [(aa,ta),(bb,tb)]:
    for t in ob['trades']:by[t['at']].append({k:t[k] for k in ['security_id','side','shares','gross_cny','fees_cny','price']})
   dates=sorted(set(ta)|set(tb));first=next((d for d in dates if sorted(ta[d],key=str)!=sorted(tb[d],key=str)),None)
   examples.append(dict(sector=sec,stress=stress,first_actual_fill_difference_at=first,baseline=ta[first] if first else [],candidate=tb[first] if first else [],largest_negative_stock_changes=stock[stock.stress.eq(stress)].sort_values('difference').head(3)[['symbol','name','difference']].to_dict('records'),largest_positive_stock_changes=stock[stock.stress.eq(stress)].sort_values('difference').tail(3)[['symbol','name','difference']].to_dict('records')))
   # Unique daily CP1 intent, actual core entry remains I-only, actual ADD layer stays ADD.
   for label,ob in [('L0',aa),('ADD',bb)]:
    seen=set();dups=0;wrong_core=0;addints=0
    for dc in ob['decisions']:
     for i in dc['intents']:
      if i['kind']=='add':
       key=(i['sid'],tuple(i['epoch']) if i['epoch'] is not None else None,dc['at']);dups+=key in seen;seen.add(key);addints+=1
    for t in ob['trades']:
     if t['side']=='buy' and t['kind']=='core':wrong_core+=t['reason']!='I_early_probe'
    assert not dups and not wrong_core
    opchecks.append(dict(sector=sec,stress=stress,policy=label,ADD_intents=addints,duplicate_CP1_intents=dups,non_I_core_entries=wrong_core))
   sources.append(dict(sector=sec,stress=stress,baseline=str(O/sec/'full/results'/f'L0_{stress}.json.gz'),candidate=str(O/sec/('repair-full' if stress=='delay1' else 'full')/'results'/f'ADD_{stress}.json.gz'),source_hash_baseline=M.sha(O/sec/'full/results'/f'L0_{stress}.json.gz'),source_hash_candidate=M.sha(O/sec/('repair-full' if stress=='delay1' else 'full')/'results'/f'ADD_{stress}.json.gz')))
  final=objects(sec,'ADD_delay1');ops=final['ops'];wait={x['order']:x for x in ops if x['kind']=='ADD_actual_wait'};created={x['order']:x for x in ops if x['kind']=='ADD_credit_created'};cons=[x for x in ops if x['kind']=='ADD_credit_consumed'];fromids=[x['from_order'] for x in cons]
  assert len(fromids)==len(set(fromids))
  for x in cons:
   assert x['from_order'] in wait and x['from_order'] in created
   assert created[x['from_order']]['at']==x['signal_at'];assert wait[x['from_order']]['at']<x['signal_at']<x['at']
  toids={x['to_order'] for x in cons};assert not any(x['from_order'] in toids for x in cons)
  M.save(O/sec/'SINGLE_USE_CREDIT_VERIFICATION.json',dict(passed=True,native_real_waits=len(wait),credit_created=len(created),credit_consumed=len(cons),twice_spent=0,inherited_zero_fill_rolled_again=0,source_wait_and_new_signal_clock_verified=True))
 for name,data in [('BENEFIT_COST_BRIDGE',bridges),('FUNDING_DISAGREEMENTS',paired),('FUNDING_COUNTS',post),('SOURCE_VERSIONS',sources)]:pd.DataFrame(data).to_csv(O/f'{name}.csv',index=False)
 M.save(O/'POST_VERIFICATION.json',dict(passed=True,policy_checks=opchecks,all_accounting_passed=True,all12_complete=True,role_decomposition_is_descriptive_not_causal=True))
 M.save(O/'KEY_TIMELINES.json',examples);M.save(O/'ACT_EVENTS.json',acts)
 # Original 42 flagged account-days are not 42 unique price gaps; preserve source.
 source=O.parent/'rb1-act-finite-20261031/PRICE_CONDITIONS.csv';shutil.copyfile(source,O/'UPSTREAM_PRICE_CONDITIONS.csv');p=pd.read_csv(source)
 for path,h in rawfiles.items():assert M.sha(path)==h,('raw/action input mutated',path)
 M.save(O/'RAW_ACTION_IDENTITY.json',dict(passed=True,files=len(rawfiles),expected_sha_from_frozen_input_manifest=True))
 M.save(O/'DATA_LIMITATIONS.json',dict(upstream_conditional_rows=len(p),upstream_unique_stock_dates=len(p[['sector','date','symbol']].drop_duplicates()),upstream_rows_are_different_old_accounts_not_current_positions=True,new_actual_unknown_position_days=unknown,snapshot_survivorship=True,historical_all_consumed=True,independent_holdout=False,daily_HLV_execution_proxy=True,dividend_pay_dates_and_bonus_sellable_dates_proxies_retained=True))
 print(ss[['sector','account','net_return','max_drawdown']].to_string(index=False),flush=True)
if __name__=='__main__':
 t=time.monotonic();status='started'
 try:main();status='complete'
 finally:
  s=M.read(O/'COMPUTE_TIME.json');elapsed=time.monotonic()-t;s['seconds']+=elapsed;s['stages'].append(dict(stage='final_read_only_verification',status=status,seconds=elapsed));M.save(O/'COMPUTE_TIME.json',s)
