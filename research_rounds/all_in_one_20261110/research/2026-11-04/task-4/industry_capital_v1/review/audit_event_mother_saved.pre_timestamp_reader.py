"""Saved mother/preview identity only; no market load, accounts or projections."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import gzip,json,hashlib,time
R=Path(__file__).resolve().parent;I=R.parent;E=I/'events';W=I.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stream(p):
 with gzip.open(p,'rt')as f:
  for s in f:yield json.loads(s)
t0=time.monotonic();expected={};whole=Counter();tags=Counter()
for w in ['long','strong']:
 p=W/'new_price_trend_v1/funding/runs'/(w+'_OFF')/'pair/funding.jsonl.gz'
 for n,x in enumerate(stream(p)):
  if x['role']!='core'or'09:30:00'not in x['at']:continue
  whole[w]+=1;ts=set(x['result'].split(','))
  if ts&{'sector_capital','sector_risk'}:expected[w,n]=(x,ts)
seen=set();co=Counter();first={};nq=Counter();minrisk=[]
for x in stream(E/'CORE_SECTOR_REJECT_EVENTS.jsonl.gz'):
 k=x['window'],x['funding_stream_index'];assert k in expected and k not in seen;seen.add(k);raw,ts=expected[k];assert raw==x['raw_funding_row'];assert sorted(ts)==x['failure_tags']
 assert x['signal_day']<x['OPEN'] and x['at']==x['OPEN']+'T09:30:00+08:00'
 o=x['original_opportunity'];i=x['original_intent'];q=x['original_OPEN_contract_preview'];assert o['core_Q']is True and o['held']is False and not o['barriers']and'core'in o['roles'];assert i['role']=='core'and i['kind']=='core'and i['size_reject']is None
 assert int(q['dated_minimum_shares'])>=q['dated_quantity_rule']['buy_minimum']>0;assert int(q['dated_minimum_shares'])==q['dated_quantity_rule']['buy_minimum'];assert q['OPEN_preview_max_shares']>=q['dated_minimum_shares']and q['OPEN_preview_max_shares']<=i['cap'];assert(q['OPEN_preview_max_shares']-q['dated_minimum_shares'])%q['dated_quantity_rule']['buy_step']==0
 d=lambda s:D(str(s));assert d(q['dated_minimum_cash'])==d(q['dated_minimum_gross'])+d(q['dated_minimum_buy_fee']);assert d(q['dated_minimum_gross'])==D(q['dated_minimum_shares'])*d(q['execution_price_with_original_5bps']);assert d(q['execution_price_with_original_5bps'])==d(q['raw_OPEN'])*D('1.0005');assert d(q['raw_OPEN'])>d(q['protection_raw']);assert d(q['dated_minimum_CORE_protection_risk_with_fees'])<=d(i['risk_budget']);assert d(q['OPEN_preview_max_gross'])<=d(i['budget']);assert q['actual_rejected_order_quantity']is None and not q['candidate_execution_HLV_or_future_window_consulted']
 assert len(i['epoch'])==2;fkey=x['window'],x['sid'],tuple(i['epoch']);
 if fkey not in first or(x['OPEN'],x['funding_stream_index'])<(first[fkey]['OPEN'],first[fkey]['funding_stream_index']):first[fkey]=x
 co[x['window']]+=1;nq[x['classification']]+=1
assert seen==set(expected);ms=json.loads((E/'CORE_SECTOR_REJECT_MOTHER_SUMMARY.json').read_text());assert sum(co.values())==ms['events']==33569
for w in co:assert co[w]==ms['counts'][w]['selected_sector_reject_events']and whole[w]==ms['counts'][w]['CORE_OPEN_funding_rows']
prim=Counter(x['window']for x in first.values());cl=Counter(x['classification']for x in first.values())
sources=[Path(__file__),E/'CORE_SECTOR_REJECT_EVENTS.jsonl.gz',E/'extract_original_core_rejects.py',E/'enrich_original_quotes.py',E/'CORE_SECTOR_REJECT_MOTHER_SUMMARY.json',E/'CORE_BINDING_SUMMARY.json',E/'QUOTE_SUMMARY.json']+[W/'new_price_trend_v1/funding/runs'/(w+'_OFF')/'pair/funding.jsonl.gz'for w in ['long','strong']]
x={'passed':True,'scope':'All native actual CORE OPEN funding rows selected by sector_capital/sector_risk, exact saved funding-row identity, original legal-intent evidence, clock and saved Decimal LR-min/max preview arithmetic. No independent market/ledger replay.','raw_sector_reject_events':sum(co.values()),'by_window':dict(co),'first_observed_per_window_sid_native_source_I_epoch':dict(prim),'first_event_total':sum(prim.values()),'first_event_failure_classification':dict(cl),'raw_failure_classification':dict(nq),'mother_complete':True,'minimum_size_preview_saved_arithmetic_exact':True,'unverified':['Exact original pre-candidate full resources and FIFO donor feasibility','Full raw-window/corporate-action execution of candidate conditional paths','Unknown current-pool/sameOPEN migration; S0 old inventory does not include sameOPEN new admissions','Future labels, economic improvement or statistical independence'],'new_accounts':0,'new_marks':0,'new_state_restores':0,'source_sha256':{str(p.resolve()):sha(p)for p in sources},'seconds':time.monotonic()-t0}
(R/'EVENT_MOTHER_SAVED_REVIEW.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in x.items()if k not in ['source_sha256','unverified']},indent=2))
