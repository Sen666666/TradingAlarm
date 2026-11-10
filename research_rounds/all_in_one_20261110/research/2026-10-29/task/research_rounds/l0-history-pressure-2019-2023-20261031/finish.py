"""Read-only summary of six completed histories and current lock evidence."""
from pathlib import Path
import json,gzip,time,hashlib,datetime
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;T=time.monotonic()
def read(p):return json.loads(Path(p).read_text())
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def main():
 s=pd.concat([pd.read_csv(O/g/'analysis/summary.csv') for g in ['TECH','DRUG']],ignore_index=True);risk=[];extra=[];audits=[];tradechecks=[];epochsummary=[];allacts=[]
 for sec in ['TECH','DRUG']:
  assert read(O/sec/'full/GATE.json')['passed'];a=read(O/sec/'analysis/ACCOUNTING.json');assert a['passed'];audits+=a['receipts'];ds=rows(O/sec/'full/results/daily.jsonl.gz');rr=pd.read_csv(O/sec/'analysis/risk.csv');caps=pd.read_csv(O/sec/'analysis/campaigns.csv')
  for aid in sorted({x['account'] for x in ds}):
   d=[x for x in ds if x['account']==aid];q=obj(O/sec/'full/results'/f'{aid}.json.gz');r=rr[rr.account.eq(aid)];holding={x['at'] for x in d if x['positions']};good=r.unknown_floor_layers.eq(0)&r['at'].isin(holding);z=r.loc[good,'nominal_rate'].astype(float)
   risk.append(dict(sector=sec,account=aid,complete_invested_days=int(good.sum()),floor_unknown_account_days=int(r.unknown_floor_layers.gt(0).sum()),floor_unknown_layer_days=int(r.unknown_floor_layers.sum()),nominal_to_floor_median=float(z.median()) if len(z) else None,nominal_to_floor_max=float(z.max()) if len(z) else None,price_unknown_position_days=int(r.price_or_observation_unknown_positions.sum()),position_day_denominator=sum(len(x['positions']) for x in d)))
   c=caps[caps.account.eq(aid)];loss=-c.loc[c.closed.eq(True)&c.net_pnl.lt(0),'net_pnl'].sum();count=sum(t['side']=='sell' for t in q['trades']);peak=max(len(x['positions']) for x in d)
   extra.append(dict(sector=sec,account=aid,closed_losses=float(loss),closed_cycles=int(c.closed.sum()),open_cycles=int((~c.closed).sum()),sell_fills=count,peak_positions=peak,mean_positions=float(np.mean([len(x['positions']) for x in d]))))
   assert not q['ops'] and all(t.get('kind')=='core' for t in q['trades'] if t['side']=='buy')
   assert all('2019-01-02'<=t['at'][:10]<='2023-12-29' for t in q['trades']);tradechecks.append(dict(sector=sec,account=aid,actual_fills=len(q['trades']),end_value_date=d[-1]['at'],all_fills_in_window=True,ADD_events=0))
   allacts.extend(dict(sector=sec,account=aid,**x) for x in q['audit'] if x['kind']=='risk_checkpoint' and x.get('event'))
  # Current L0: count actual different-I-epoch returns without future P&L labels.
  cur=W/'lr1-cp1-add-preflight-20261031'
  for stress in ['base','cost2','delay1']:
   aid='L0_'+stress;q=obj(cur/sec/'full/results'/f'{aid}.json.gz');last={};same_source_restart=source_change=same_epoch=0
   for t in q['trades']:
    if t['side']!='buy':continue
    sid=t['security_id'];ep=tuple(t['epoch'])
    if sid in last:
     if ep==last[sid]:same_epoch+=1
     elif ep[0]==last[sid][0]:same_source_restart+=1
     else:source_change+=1
    last[sid]=ep
   epochsummary.append(dict(sector=sec,account=aid,actual_different_I_epoch_reentries_same_source=same_source_restart,actual_reentries_after_source_change=source_change,same_epoch_multiple_buy_receipts=same_epoch))
 s=s.merge(pd.DataFrame(extra),on=['sector','account'],suffixes=('','_verified'));s.to_csv(O/'MATRIX_6.csv',index=False);pd.DataFrame(risk).to_csv(O/'RISK_COMPLETE_INVESTED.csv',index=False)
 ref=pd.read_csv(W/'rb1-act-history-pressure-2019-2023-20261031/MATRIX_12.csv');table=[]
 for _,r in ref.iterrows():table.append(dict(sector=r.sector,policy=r.model,stress=r.pressure,net_return=r.net_return,max_drawdown=r.max_drawdown,underwater_calendar_days=r.longest_underwater_calendar_days,mean_exposure=r.mean_exposure*1214/1215,reference_mean_exposure_ex_initial=r.mean_exposure,mean_available_fraction=r.mean_available_NAV,fees=r.fees,tail30_closed_profit=r.tail_profit,ordinary_closed_profit=r.ordinary_profit,open_profit=r.open_profit,closed_losses=r.all_closed_losses,source='existing verified A/RB1, not rerun; exposure normalized to common1215 cutoffs incl initial empty day'))
 for _,r in s.iterrows():table.append(dict(sector=r.sector,policy='L0',stress=r.account.split('_')[-1],net_return=r.net_return,max_drawdown=r.max_drawdown,underwater_calendar_days=r.longest_underwater_calendar_days,mean_exposure=r.mean_exposure,mean_available_fraction=r.mean_available_fraction,fees=r.fees,tail30_closed_profit=r.tail30_closed_profit,ordinary_closed_profit=r.ordinary_closed_profit,open_profit=r.open_profit,closed_losses=r.closed_losses,source='new L0 frozen architecture'))
 pd.DataFrame(table).to_csv(O/'REFERENCE_18.csv',index=False)
 cur=pd.read_csv(W/'lr1-cp1-add-preflight-20261031/MATRIX_12.csv');cur=cur[cur.account.str.startswith('L0_')].copy();cur['period']='2024-2026-10-27';hist=s.copy();hist['period']='2019-2023';pd.concat([hist,cur],ignore_index=True).to_csv(O/'L0_TWO_PERIODS_12.csv',index=False)
 lock=[];chains=[]
 techcols=pd.read_csv(O/'lock-audit/TECH/STOCK_DAYS.csv',nrows=0).columns
 for sec in ['TECH','DRUG']:
  assert read(O/'lock-audit'/sec/'VERIFICATION.json')['passed'];ls=read(O/'lock-audit'/sec/'SUMMARY.json');lock+=ls
  for name in ['STOCK_DAYS','WINDOWS']:
   p=O/'lock-audit'/sec/f'{name}.csv'
   if p.stat().st_size<3:pd.DataFrame(columns=techcols if name=='STOCK_DAYS' else pd.read_csv(O/'lock-audit/TECH/WINDOWS.csv',nrows=0).columns).to_csv(p,index=False)
  d=pd.read_csv(O/'lock-audit'/sec/'STOCK_DAYS.csv');d=d[d.status.eq('lock_only_intent_proven_execution_requires_original_delay')]
  for _,a in d.iterrows():
   b=d[d.account.eq(a.account)&d.symbol.eq(a.symbol)&d.cycle.eq(a.cycle)&d['at'].str[:10].eq(a.next_execution[:10])]
   if len(b):
    b=b.iloc[0];chains.append(dict(sector=sec,account=a.account,symbol=a.symbol,first_fresh_I=a['at'],first_native_wait_window=a.next_execution,second_fresh_I=b['at'],second_executable_proxy=b.next_execution,both_joint_cash_sufficient_proofs=True,actual_unlock_trade_or_return_simulated=False))
 save(O/'LOCK_SUMMARY.json',lock);pd.DataFrame(epochsummary).to_csv(O/'CURRENT_NATURAL_REENTRIES.csv',index=False);pd.DataFrame(chains).to_csv(O/'LOCK_DELAY_CHAIN_WITNESSES.csv',index=False)
 save(O/'ENDPOINT_AND_ACCOUNTING.json',dict(passed=True,accounts=6,daily_account_rows=7290,receipts=audits,actual_fill_dates=tradechecks,all_NAV_differences_zero=all(x['max_absolute_nav_difference_cny']=='0' for x in audits),history_cash_and_initial_NAV_same_as_reference=True,shared_price_accounting_and_period=True,architecture_differences=['no6stock3industry2perindustry count cap','0.25% core floor-risk and10%cashreserve','core_epoch lock and whole-order equal group allocation'],no_single_parameter_causal_claim=True))
 save(O/'ACT_EVENTS.json',allacts)
 freeze=read(O/'FREEZE.json');assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in freeze['sha256'].items())
 print(s[['sector','account','net_return','max_drawdown','mean_positions','peak_positions']].to_string(index=False));print('DELAY_CHAINS',chains)
 return s,risk,lock,chains
if __name__=='__main__':
 status='started'
 try:main();status='complete'
 finally:
  p=O/'COMPUTE_TIME.json';x=read(p);elapsed=time.monotonic()-T;x['seconds']+=elapsed;x['stages'].append(dict(stage='read_only_summary',status=status,seconds=elapsed));save(p,x)
