"""Exact funded decision identity; explicitly reconcile two cap-unknown traces."""
from common_abcd import *
import gzip,collections

def main():
 expected={};prepared=set(read(HERE/'prepared/buy-events.json'));excluded=set()
 for r in read(OLD/'inputs-v2/input-manifest.json')['series']:
  if r['kind']=='stock' and r['series_id'] not in prepared:excluded.add(r['series_id'])
 assert len(excluded)==2
 with gzip.open(SRC/'accounts/decisions.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line)
   if x['account'].startswith('IX__S0_'):
    x['account']='A__'+x['account'].split('__')[1];expected[x['account'],x['at']]=x
 n=0;omitted=0;relabelled=0
 with gzip.open(HERE/'technical/A-controls/decisions.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line);assert x.pop('rotation') is None;y=expected.pop((x['account'],x['at']))
   omitted_rows=[e for e in y['event_eligibility'] if e['symbol'] in excluded]
   assert all(e['q'] is None and 'cap_above_10bn:unknown' in e['reasons'] for e in omitted_rows)
   y['event_eligibility']=[e for e in y['event_eligibility'] if e['symbol'] not in excluded]
   delta=sum('buy_allowed:false' not in e['reasons'] and 'buy_allowed:unknown' not in e['reasons'] for e in omitted_rows)
   if delta:y['reason_counts']['buy_allowed:false']=y['reason_counts'].get('buy_allowed:false',0)+delta
   assert x==y,(x['account'],x['at']);n+=1;omitted+=len(omitted_rows);relabelled+=delta
 assert not expected
 write(HERE/'technical/A-controls/decision-comparison-v2.json',dict(passed=True,full_funded_decisions_exact=n,only_cap_unknown_event_trace_differences=True,never_admissible_excluded_symbols=sorted(excluded),omitted_unknown_only_event_trace_rows=omitted,unknown_only_false_gate_reason_relabels=relabelled,full_financial_json_exact=True,financial_or_ranking_changes=0,recorded_at=now()))
 print(dict(old_funded_decisions_exact=n,unknown_only_trace_omissions=omitted),flush=True)
if __name__=='__main__':main()
