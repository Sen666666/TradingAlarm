"""Original canonical corporate-action calendar join, no account/feature model."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
P=Path(__file__).resolve().parent;O=P/'entry_risk_commitment_review';SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def main():
 mp=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json');meta={x['series_id']:x for x in read(mp)['series']};allrows={ref:read(O/(ref+'_ENTRIES.json')) for ref in ['2022_2024','strong']};ids={x['sid'] for ee in allrows.values() for x in ee};cache={};statuses={}
 for sid in ids:
  m=meta[sid];ref=m['adjustment']['actions'];ap=Path(ref['path']);assert sha(ap)==ref['sha256'];a=read(ap);assert a['series_id']==sid and a['status'] in ['reviewed_terms','declared_research_proxy'] and a['currency']==m['currency'] and a.get('coverage_evidence') and not a.get('unresolved');events=a['events'];assert isinstance(events,list) and len({x['effective_date'] for x in events})==len(events)
  for e in events:assert e['source_id'] and D(e['cash_per_old_share'])>=0 and D(e['split_ratio'])>0
  cache[sid]=events;statuses[sid]=a['status']
 out={}
 for ref,ee in allrows.items():
  rr=[]
  for x in ee:
   events=[a for a in cache[x['sid']] if x['decision_at'][:10]<a['effective_date']<=x['opened'][:10]]
   if events or x['reference_unknown_reasons']:rr.append(dict(layer=x['layer'],sid=x['sid'],role=x['role'],decision_at=x['decision_at'],opened=x['opened'],factor_or_source_unknown=x['reference_unknown_reasons'],canonical_action_events_in_interval=events,action_present_without_factor_or_source_flag=bool(events and not x['reference_unknown_reasons']),original_risk_class=x['risk_reference_class'],net=x['net']))
  out[ref]=dict(actual_fills=len(ee),action_interval_fills=sum(bool(x['canonical_action_events_in_interval']) for x in rr),factor_or_source_flagged_fills=sum(bool(x['factor_or_source_unknown']) for x in rr),additional_action_interval_without_factor_source_flag=sum(x['action_present_without_factor_or_source_flag'] for x in rr),all_flagged_rows=rr)
 (O/'ACTIONS_INTERVAL_CHECK.json').write_text(json.dumps(dict(rows=out,sources=SRC,calendar_identity_status_counts={k:sum(v==k for v in statuses.values()) for k in set(statuses.values())},script_sha256=sha(__file__),account_events=0,action_calendar_scope='Original canonical normalized declared/reviewed terms; pay/sellable dates may remain unknown; not independent live publication certification'),ensure_ascii=False,indent=2));print({ref:{k:v for k,v in a.items() if k!='all_flagged_rows'} for ref,a in out.items()})
if __name__=='__main__':main()
