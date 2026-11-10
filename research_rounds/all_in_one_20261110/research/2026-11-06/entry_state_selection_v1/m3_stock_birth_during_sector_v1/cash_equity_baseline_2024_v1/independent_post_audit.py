"""Independent persisted-ledger audit; never imports or runs strategy engine."""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
import json,hashlib,collections
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;E=O.parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
dt=lambda v:pd.Timestamp(v)
close=lambda a,b:abs(D(str(a))-D(str(b)))<D('0.0000001')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
rules=read(B/'inputs-v2/market-rules.json')
def version(rows,day):
 rows=[x for x in rows if x['from']<=day and (not x.get('to') or day<x['to'])]
 assert len(rows)==1;return rows[0]
def fee(sid,day,q,p,side):
 day=str(dt(day).date());venue=version(rules['venue_versions'][sid],day)['venue'];schedule=version(rules['fee_versions'][venue],day)['schedule'];total=D(0)
 for c in schedule['components']:
  if c.get('side','both') not in ['both',side]:continue
  basis=c.get('amount_basis','notional');amount=D(q)*D(str(p)) if basis=='notional' else D(q) if basis=='shares' else D(q)*D(str(rules['security_metadata'][sid]['par_value']))
  x=max(D(str(c.get('minimum_local',0))),amount*D(str(c['rate'])))
  if c.get('maximum_local') is not None:x=min(x,D(str(c['maximum_local'])))
  if c.get('rounding_unit') is not None:
   u=D(str(c['rounding_unit']));x=(x/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*u
  total+=x
 return total
z=pd.read_csv(O/'economic/ROUNDS.csv',float_precision='round_trip',low_memory=False).set_index('round_id',drop=False)
a=pd.read_csv(O/'economic/ACTIONS.csv',float_precision='round_trip')
regs=pd.read_csv(O/'economic/REGISTRATIONS.csv',float_precision='round_trip')
led=pd.read_csv(O/'economic/CLAIM_LEDGER.csv',float_precision='round_trip')
claims=read(O/'economic/CLAIMS.json');events={e['economic_event_id']:e for e in read(O/'ECONOMIC_EVENTS.json')}
assert len(events)==165 and z.index.is_unique
groups={rid:g.to_dict('records') for rid,g in a.groupby('round_id',sort=False)}
cb=collections.defaultdict(list)
for c in claims:cb[c['owner_round_id']].append(c)
assert len({tuple(c['key']) for c in claims})==len(claims)
checks=collections.Counter();allchecks=[]
for rid,r in z.iterrows():
 trades=groups.get(rid,[]);q=0;cash=D(0);fees=D(0);spent=D(0);bought={}
 for x in trades:
  n=int(x['q']);p=D(str(x['price']));f=D(str(x['fee']));day=str(dt(x['day']).date());buy=x['side'].startswith('buy')
  assert close(f,fee(r.sid,day,n,p,'buy' if buy else 'sell')),(rid,'fee')
  if buy:q+=n;cash-=n*p+f;spent+=n*p+f;bought[day]=bought.get(day,0)+n
  else:assert n<=q-bought.get(day,0),(rid,'T+1');q-=n;cash+=n*p-f
  fees+=f;assert q>=0;checks['trade_fees']+=1
 paid=sum((D(c['amount']) for c in cb[rid] if c['settled']),D(0));rec=sum((D(c['amount']) for c in cb[rid] if c['recognized'] and not c['settled']),D(0))
 if trades:
  assert q==r.core_qty+r.add_qty and close(fees,r.all_fees) and close(spent,r.total_buy_cash)
  assert close(cash+paid,r.cash_after_payouts) and close(rec,r.receivable_after_payouts)
 assert close(paid+rec,r.dividend_net80_total)
 if r.status=='COMPLETE_CONDITIONAL_STOCK_ROUND':assert q==0 and close(cash+paid+rec,r.net_pnl)
 if 'UNKNOWN' in r.status:
  assert all(dt(x['day'])<=dt(r.status_day) for x in trades)
  if r.failure_phase=='OPEN':assert all(dt(x['day'])<dt(r.status_day) for x in trades),(rid,'OPEN_UNKNOWN traded')
 checks['round_ledger']+=1
for c in claims:
 e=events[c['economic_event_id']];r=z.loc[c['owner_round_id']];assert r.sid==e['sid'] and r.arm==c['arm']
 rec=dt(e['record_date']);trs=[x for x in groups.get(r.round_id,[]) if dt(x['day'])<=rec]
 q=sum(int(x['q'])*(1 if x['side'].startswith('buy') else -1) for x in trs)
 core=sum(int(x['q']) for x in trs if x['side']=='buy_core')
 assert q==c['record_q'] and core==c['core_record_q'];assert D(c['amount'])==D(q)*D(e['d_cash'])*D('.8')
 assert D(c['core_amount'])==D(core)*D(e['d_cash'])*D('.8')
 ll=led[(led.round_id==r.round_id)&(led.economic_event_id==c['economic_event_id'])]
 assert len(ll)==int(c['recognized'])+int(c['settled'])
 for x in ll.to_dict('records'):
  if x['event']=='ACCRUE_NET80':assert dt(x['day'])==dt(e['ex_date']) and close(x['cash_delta'],0) and close(x['receivable_delta'],c['amount'])
  else:assert x['event']=='PAY_CLOSE_TRANSFER' and dt(x['day'])==dt(e['pay_date']) and close(x['cash_delta'],c['amount']) and close(x['receivable_delta'],-D(c['amount']))
 if c['settled'] and pd.notna(r.get('exit_day')) and dt(r.exit_day)<=dt(e['pay_date']):checks['claims_settled_on_or_after_exit']+=1
 checks['claims_inventory_owner_clock']+=1
for x in regs.to_dict('records'):
 eid=x['economic_event_id'];e=events[eid];assert x['sid']==e['sid'] and dt(x['inventory_snapshot_day'])==dt(e['record_date'])
 if x['state']=='UNKNOWN':assert pd.isna(x['record_q'])
 elif x['state']!='HELD':assert x['record_q']==0
 else:
  rid=x['owner_round_id'];r=z.loc[rid];assert r.sid==e['sid'] and dt(r.entry_day)<=dt(e['record_date'])
  q=sum(int(t['q'])*(1 if t['side'].startswith('buy') else -1) for t in groups[rid] if dt(t['day'])<=dt(e['record_date']))
  assert q==x['record_q'] and q>0
 checks['registration_rows']+=1
# Closed/active holding prefixes may never cross a known unadmitted effective day.
admitted={(e['sid'],dt(e['ex_date'])) for e in events.values()}
for sid,g in z[z.entry_day.notna()].groupby('sid'):
 g=g.sort_values('entry_day');previous=None
 for r in g.itertuples():
  if previous is not None:assert dt(r.entry_day)>previous,(sid,'overlapping/reentered unknown round')
  end=dt(r.exit_day) if r.status=='COMPLETE_CONDITIONAL_STOCK_ROUND' else dt(r.status_day)
  previous=end if r.status=='COMPLETE_CONDITIONAL_STOCK_ROUND' else pd.Timestamp('2026-06-30')
  source=read(AS/'inputs-v1/actions'/f'{sid}.json')
  for e in source['events']:
   day=dt(e['effective_date'])
   if dt(r.entry_day)<day<=end and (sid,day) not in admitted:
    assert day==end and 'UNKNOWN' in r.status,(r.round_id,'crossed unadmitted',day)
    checks['unadmitted_terminal_boundaries']+=1
 checks['same_security_groups']+=1
# Independent core-only initial lot at FULL entry/exit with its own sell fee.
rep=pd.read_csv(O/'report/CORE_AND_FULL_ROUNDS.csv',float_precision='round_trip')
for r in rep[rep.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')].itertuples():
 q=int(r.entry_q);bf=fee(r.sid,r.entry_day,q,r.entry_price,'buy');sf=fee(r.sid,r.exit_day,q,r.exit_price,'sell');div=sum((D(c['core_amount']) for c in cb[r.round_id] if c['recognized']),D(0));cost=q*D(str(r.entry_price))+bf;net=q*D(str(r.exit_price))-sf-cost+div
 assert close(bf,r.core_buy_fee) and close(sf,r.core_sell_fee) and close(div,r.core_dividend_net80) and close(cost,r.core_buy_cash) and close(net,r.core_net) and close(net/cost,r.core_return)
 checks['core_independent_fee_rounds']+=1
cov=pd.read_csv(O/'report/FINANCIAL_COVERAGE.csv')
assert not cov[cov.financial_coverage_status.eq('COVERAGE_UNKNOWN')].evidence_usable_closed.any()
assert not cov[~cov.execution_status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')].evidence_usable_closed.any()
for r in cov.itertuples():
 if pd.isna(z.loc[r.round_id].entry_day):continue
 ac=read(AS/'inputs-v1/actions'/f'{r.sid}.json')
 bad=ac.get('raw_response_empty') or not ac.get('coverage_evidence') or any(not read(e['path']).get('records') for e in ac.get('coverage_evidence',[]))
 if bad:assert r.financial_coverage_status=='COVERAGE_UNKNOWN' and not r.evidence_usable_closed
 checks['financial_coverage_rows']+=1
# Bind exact output/source seals and checked prefix evidence.
for p,h in read(O/'economic/OUTPUT_HASHES.json').items():assert sha(O/'economic'/p)==h
for p,h in read(O/'economic/SOURCE_HASHES.json').items():assert sha(Path(p))==h
pre=read(O/'PRE_ECONOMIC_AUDIT.json');prefix=read(O/'PREFIX_QA.json')
assert pre['engine_sha256']==sha(O/'engine.py')==prefix['engine_sha256']
assert pre['driver_sha256']==sha(O/'run.py')==prefix['driver_sha256']
assert all(prefix[n]['match'] for n in ['ACTIONS','DECISIONS','RANKING_AUDIT','CLAIM_LEDGER','REGISTRATIONS'])
out={'result':'PASS_INDEPENDENT_PERSISTED_LEDGER_CHECKS','checks':dict(checks),'engine_sha256':sha(O/'engine.py'),'driver_sha256':sha(O/'run.py'),'economic_run_sha256':sha(O/'ECONOMIC_RUN_ONCE.json'),'economic_output_seal_sha256':sha(O/'economic/OUTPUT_HASHES.json'),'prefix_qa_sha256':sha(O/'PREFIX_QA.json'),'report_sha256':sha(O/'report.py'),'economic_reruns_by_auditor':0,'limits':['NON_PIT historical/static source','NET80 not actual tax','No real account or orderability certification','Core is initial-lot diagnostic at FULL entry/exit, not separate strategy','Financial coverage unknown excluded from evidence scope','Prefix check verifies consumer truncation only; excludes available_from because truncated calendar cannot represent next session.']}
(O/'POST_ECONOMIC_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
