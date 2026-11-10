"""All first-signal size/turnover context, no filtering or fillability claim."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import Counter
import json,hashlib,math,csv
import pandas as pd
import numpy as np

getcontext().prec=50
O=Path(__file__).parent;P=O.parent;SRC={};CACHE={};SLIP=D('.0005')


def read(p):
 SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())


def save(name,x):
 with (O/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')


def valid(x):return x is not None and math.isfinite(float(x)) and float(x)>0


def rawquote(e):
 p=Path(e['quote_source'])
 if str(p) not in CACHE:
  h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==e['quote_source_sha256']==FROZEN[str(p)]
  SRC[str(p)]=h;f=pd.read_parquet(p,columns=['raw_close']);assert f.index.is_unique and f.index.is_monotonic_increasing;CACHE[str(p)]=f
 f=CACHE[str(p)];d=pd.Timestamp(e['day'])
 if d not in f.index:return None,'NO_EXACT_SIGNAL_RAW_QUOTE'
 x=f.loc[d,'raw_close']
 return (D(str(x)),None) if valid(x) else (None,'INVALID_SIGNAL_RAW_CLOSE')


def dist(rr,key):
 vals=[float(r[key]) for r in rr if r[key] is not None and math.isfinite(float(r[key]))]
 quantiles=[0,.1,.25,.5,.75,.9,1]
 return dict(events_known=len(vals),events_unknown=len(rr)-len(vals),event_weighted_quantiles={str(q):float(np.quantile(vals,q)) for q in quantiles} if vals else None,
             weighting='one original first-signal event one observation; descriptive, not independent or capacity-screened')


rulespath=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
rules=read(rulespath);FROZEN=read(P/'SOURCE_MANIFEST.json')['sources']
context=read(P/'account_context/DAILY_ACCOUNT_CONTEXT.json');nav={(r['reference'],r['date']):D(r['NAV']) for r in context}
save('PROTOCOL.json',dict(quantity_source=str(rulespath),quantity_version_interval='from<=signal_day<to, null to open-ended; dated original research proxy',
 price='Original signal.parquet exact raw_close at signal CLOSE; original NORMAL slip0.0005; no nextOPEN prediction.',
 target='Original mobile gross target2% times baseline original actual decision-CLOSE NAV from account_context. Hypothetical reference for every market first, not actual funded order or role.',
 minimum='dated buy_minimum * raw_close *1.0005; gross only, fees not added. Flag min_gross>2%NAV is a necessary-budget comparison only.',
 no_capacity_threshold=True,no_market_event_filter=True,no_return_filter=True,new_accounts=0,new_orders=0))
views={'2022_weak':('2022-01-04','2022-12-30','2022_2024',5847),
       '2024_recovery':('2024-09-02','2024-11-29','2022_2024',1629),
       'strong':('2025-07-01','2026-06-30','strong',6108)}
allrows=[];summary={}
for view,(lo,hi,ref,expected) in views.items():
 events=read(P/view/'EVENTS.json');events=[e for e in events if lo<=e['day']<=hi];assert len(events)==expected
 out=[]
 for e in events:
  # Preserve all primary valid/unknown event IDs; never consult funding status.
  primary=valid(e['signal_close']) and valid(e['signal_amount'])
  N=nav.get((ref,e['day']));target=N*D('.02') if N is not None else None
  raw,rawerr=rawquote(e);vv=[v for v in rules['quantity_versions'].get(e['sid'],[]) if v['from']<=e['day'] and (v['to'] is None or e['day']<v['to'])]
  reason=[]
  if not primary:reason.append('PRIMARY_SIGNAL_QUOTE_UNKNOWN')
  if N is None:reason.append('BASELINE_DECISION_NAV_UNKNOWN')
  if rawerr:reason.append(rawerr)
  if len(vv)!=1:reason.append('QUANTITY_RULE_UNKNOWN_OR_NOT_UNIQUE')
  version=vv[0] if len(vv)==1 else None
  minimum=version['rule'].get('buy_minimum') if version else None
  if minimum is not None and (not isinstance(minimum,int) or minimum<=0):reason.append('INVALID_BUY_MINIMUM');minimum=None
  gross=D(minimum)*raw*(D(1)+SLIP) if minimum is not None and raw is not None else None
  ratio=gross/target if gross is not None and target is not None and target>0 else None
  known=not reason
  out.append(dict(view=view,signal_id=e['signal_id'],day=e['day'],sid=e['sid'],sector=e['sector'],union_signal_kind=e['union_signal_kind'],
    primary_signal_quote_valid=primary,primary_final_label_status=e['final_status'],primary_return5=e['return5'],
    signal_amount=e['signal_amount'],prior20_amount_median=e['prior20_amount_median'],prior20_valid_amount_count=e['prior20_valid_amount_count'],
    baseline_reference=ref,baseline_decision_NAV=N,mobile2pct_gross_target=target,signal_raw_close=raw,normal_slip=SLIP,
    quantity_version=version,buy_minimum=minimum,minimum_gross_with_normal_slip=gross,minimum_gross_over_target_ratio=ratio,
    minimum_gross_exceeds_mobile2pct_target=(gross>target if known else None),screen_status='KNOWN_NECESSARY_COMPARISON' if known else 'UNKNOWN',unknown_reasons=reason,
    signal_amount_over_mobile2pct_target=(D(str(e['signal_amount']))/target if valid(e['signal_amount']) and target else None),
    prior20_amount_over_mobile2pct_target=(D(str(e['prior20_amount_median']))/target if valid(e['prior20_amount_median']) and target else None),
    source_quote_path=e['quote_source'],source_quote_sha256=e['quote_source_sha256'],no_funding_filter_used=True))
 summary[view]=dict(primary_events=len(events),primary_quote_valid=sum(r['primary_signal_quote_valid'] for r in out),
    primary_quote_unknown=sum(not r['primary_signal_quote_valid'] for r in out),
    necessary_minimum_known=sum(r['screen_status']=='KNOWN_NECESSARY_COMPARISON' for r in out),
    minimum_exceeds_target=sum(r['minimum_gross_exceeds_mobile2pct_target'] is True for r in out),
    minimum_not_exceeds_target=sum(r['minimum_gross_exceeds_mobile2pct_target'] is False for r in out),
    minimum_unknown=sum(r['minimum_gross_exceeds_mobile2pct_target'] is None for r in out),
    unknown_reason_counts=dict(Counter(why for r in out for why in r['unknown_reasons'])),
    signal_amount=dist(out,'signal_amount'),prior20_amount_median=dist(out,'prior20_amount_median'),
    amount_over_mobile_target=dist(out,'signal_amount_over_mobile2pct_target'),
    prior20_amount_over_mobile_target=dist(out,'prior20_amount_over_mobile2pct_target'),
    minimum_gross_over_target=dist(out,'minimum_gross_over_target_ratio'))
 assert {r['signal_id'] for r in out}=={e['signal_id'] for e in events}
 save(view+'_ROWS.json',out);allrows.extend(out)
save('SUMMARY.json',summary)
flat=[]
for r in allrows:
 d={k:v for k,v in r.items() if k not in ['quantity_version','unknown_reasons']};d['quantity_rule_id']=r['quantity_version']['rule'].get('rule_id') if r['quantity_version'] else None;d['unknown_reasons']=';'.join(r['unknown_reasons']);flat.append(d)
with (O/'ALL_FIRST_SIGNALS.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
save('VALIDATION.json',dict(passed=True,events=len(allrows),source_raw_quote_files=len(CACHE),all_primary_ids_and_return_labels_preserved=True,
  original_source_manifest_quotes_SHA_checked=True,quantity_versions_no_imputation=True,no_actual_funding_dependency=True,new_accounts=0,new_orders=0,new_gates=0,
  limitations=['Minimum gross versus2% target is only a necessary sizing comparison at signalCLOSE, not fill certification.',
    'No fees/minimumcommission, nextOPEN gap, limit-up/down, halts, auction spread, depth, capacityparticipation, settlement, availablecash, competingcandidates or holding/riskcaps tested.',
    'Signal day amount and prior20median amount are descriptive turnover, not available executable depth or an execution-price guarantee.',
    'Original dated quantity table is explicitly a research proxy; actual exchange rules/announcement timing are not independently certified.',
    'Core-only and mobile-only market roots are all retained; mobile2% is a common hypothetical reference, not a claim all would receive mobile allocation.',
    'No liquidity threshold, no market mother/return filtering, no high-capacity-only relabeling.']))
SRC[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();save('SOURCE_SHA256.json',SRC)
print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
