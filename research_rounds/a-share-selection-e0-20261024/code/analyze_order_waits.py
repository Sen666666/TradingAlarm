"""Audit age of persistent logical buy intentions; no change to execution."""
import collections,gzip,json
import pandas as pd,numpy as np
from build_inputs import HERE,read,write,now,ref

def main():
 dates=pd.DatetimeIndex(pd.to_datetime([x[:10] for x in read(HERE/'inputs-v2/market-rules.json')['decision_cutoffs']]))
 profiles=read(HERE/'entry-quality-v2/profiles.json');rows=[]
 for x in profiles:
  decision=pd.Timestamp(x['decision_date']);fill=pd.Timestamp(x['first_fill_at']).tz_localize(None).normalize()
  rows.append(dict(x,wait_calendar_days=(fill-decision).days,wait_common_sessions=int(dates.searchsorted(fill)-dates.searchsorted(decision))))
 summaries=[]
 for aid in sorted({x['account'] for x in rows}):
  xs=[x for x in rows if x['account']==aid];waits=[x['wait_common_sessions'] for x in xs]
  summaries.append(dict(account=aid,funded_campaigns=len(xs),median_wait_sessions=float(np.median(waits)),p90_wait_sessions=float(np.quantile(waits,.9)),max_wait_sessions=max(waits),
   waits_over20_sessions=sum(x>20 for x in waits),max_wait_calendar_days=max(x['wait_calendar_days'] for x in xs)))
 last={}
 with gzip.open(HERE/'accounts-v2/daily.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line);last[x['account']]=x
 active=[]
 for aid in sorted({x['account'] for x in rows}):
  intents={};fills=collections.Counter()
  for x in read(HERE/'accounts-v2'/(aid+'.json'))['audit_log']:
   if x['kind']=='reserve':intents[x['order_id']]=x
   elif x['kind']=='release_buy':intents.pop(x['order_id'],None)
   elif x['kind']=='fill' and x['receipt']['side']=='buy':fills[x['order_id']]+=x['receipt']['shares']
  for oid,x in intents.items():
   d=pd.Timestamp(x['decision_at']).tz_localize(None).normalize();active.append(dict(account=aid,symbol=x['sid'],order_id=oid,decision_date=str(d.date()),
    wait_common_sessions=int(dates.searchsorted(pd.Timestamp('2026-10-22'))-dates.searchsorted(d)),has_ever_filled=fills[oid]>0,
    holds_stock_at_end=x['sid'] in last[aid]['positions'],original_gross_budget=x['gross_budget_cny']))
 out=HERE/'entry-quality-v2';pd.DataFrame(rows).to_csv(out/'entry-profiles-with-waits.csv',index=False,encoding='utf-8-sig');write(out/'order-wait-analysis.json',dict(recorded_at=now(),rows=summaries,
  longest_base_cases=sorted([x for x in rows if x['account'].endswith('_base')],key=lambda x:x['wait_common_sessions'],reverse=True)[:12],ending_active_logical_intents=active,
  policy='Frozen budget/share-cap logical intent persists without expiry until eligibility cancellation or completion; not a claim that a broker exchange order remains live across sessions.',
  more_than20_is_descriptive_one_month_bin_not_strategy_rule=True,new_accounts=0,source=ref(HERE/'accounts-v2/provenance.json')))
 print(summaries,flush=True)

if __name__=='__main__':main()
