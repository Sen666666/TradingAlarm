import json,hashlib
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/participation')
S=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/semiconductor-2026H1-readonly/SEMICONDUCTOR_OPPORTUNITY_FUNNEL.json')
C=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/g-s-C-August-continuation-v1-20261102/analysis/C10-FIRST_OPPORTUNITIES.json')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs={str(p):sha(p)for p in [S,C,ROOT/'PROTOCOL.txt',ROOT/'audit_funding.py']}
a=json.loads(S.read_text()); rows=a['all_receipts'];assert len(rows)==a['denominator'];assert len({(r['sid'],r['signal_day'],r['receipt'])for r in rows})==len(rows)
cats=Counter(r['category']for r in rows);assert cats==a['categories']
funded={r['sid']for r in rows if r['category']=='reserved_and_filled'}
sem={'unit':a['unit'],'stock_count_with_any_signal':len({r['sid']for r in rows}),'stock_count_with_filled_signal':len(funded),'stock_count_with_signals_but_no_filled_signal_in_this_mother':len({r['sid']for r in rows}-funded),'signal_events':len(rows),'categories':dict(cats),'monthly':{}}
for m in sorted({r['signal_day'][:7]for r in rows}):
 x=[r for r in rows if r['signal_day'].startswith(m)];sem['monthly'][m]={'signal_events':len(x),'unique_stocks':len({r['sid']for r in x}),'categories':dict(Counter(r['category']for r in x))}
r=json.loads(C.read_text());assert len({(x['first_market_qualified']['sid'],x['first_market_qualified']['offered_context'])for x in r})==len(r)
c10={'unit':r[0]['mother'],'contexts':len(r),'stocks_with_any_context':len({x['first_market_qualified']['sid']for x in r}),'statuses':dict(Counter(x['status']for x in r)),'by_offered_use':{}}
for use in sorted({x['first_market_qualified']['offered_use']for x in r}):
 x=[x for x in r if x['first_market_qualified']['offered_use']==use]
 c10['by_offered_use'][use]={'contexts':len(x),'unique_stocks':len({z['first_market_qualified']['sid']for z in x}),'statuses':dict(Counter(z['status']for z in x)),'filled_unique_stocks':len({z['first_market_qualified']['sid']for z in x if z['first_actual_fill'] is not None})}
assert sum(c10['statuses'].values())==len(r)
assert all(sha(Path(p))==h for p,h in inputs.items())
out={'financial_events':0,'no_new_price_labels':True,'semiconductor_old_PVR_H1_2026':sem,'C10_July_August_2025':c10,'source_sha256':inputs}
(ROOT/'FUNDING_RESULTS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
