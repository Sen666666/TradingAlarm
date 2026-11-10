"""Read saved rows, independently check counts and nine preselected examples; no engine."""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
from collections import Counter
import hashlib,json
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task'); P=ROOT/'pvr_pool_feasibility/a_recovery_full_diagnostic'; O=ROOT/'independent_review'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def version(rows,day):
 a=[x for x in rows if x['from']<=day and(not x.get('to')or day<x['to'])]; assert len(a)==1; return a[0]
a=load(P/'MINIMUM_UNIT_RESULTS.json'); b=load(P/'minimum-unit-2022-source-correction/MINIMUM_UNIT_RESULTS.json')
rows=b['results']+a['results'][1:]
sm={r['symbol']:r for r in load(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}; im={r['series']:r for r in load(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
rp=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json'); rules=load(rp)
checks=[]; samples=[]
for r in rows:
 rr=r['all_rows']; assert len(rr)==r['candidates']
 assert sum(x['passes_single_probe_necessary_conditions'] for x in rr)==r['passing_individual_minimum_probe_orders']
 assert sum(x['unknown']is not None for x in rr)==r['unknown']==0
 assert Counter(k for x in rr for k in x['necessary_condition_failures'])==Counter(r['failure_presence'])
 passes=[x for x in sorted(rr,key=lambda x:(x['original_rank'],x['sid']))if x['passes_single_probe_necessary_conditions']]
 assert passes[:3]==r['examples_first3_by_original_rank']
 checks.append(dict(day=r['day'],candidate_count=len(rr),not_excluded_count=len(passes),unknown=0))
 for x in passes[:3]:
  d=x['day']; nd=x['next_OPEN_day']; m=sm[x['sid']]; fact=pd.read_parquet(m['refs']['facts']); rawpath=next(k for k in m['source_sha256']if k.endswith('/signal.parquet')); raw=pd.read_parquet(rawpath); cp=pd.read_parquet(m['refs']['CP1']); f=fact.loc[pd.Timestamp(d)]; z=cp.loc[pd.Timestamp(d)]
  assert D(str(raw.loc[pd.Timestamp(nd),'raw_open']))==D(x['raw_OPEN']); assert D(str(fact.loc[pd.Timestamp(nd),'factor']))==D(x['factor_at_OPEN'])
  floor=max(D(str(f.i_floor)),D(str(z.candidate))); assert floor==D(x['original_mobile_floor_adjusted'])
  assert D(x['floor_raw'])==floor/D(x['factor_at_OPEN']); price=D(x['raw_OPEN'])*D('1.0005'); q=D(x['minimum_quantity']); gross=q*price
  assert price==D(x['adverse_price'])and gross==D(x['minimum_gross'])
  assert q*(price-D(x['floor_raw']))==D(x['minimum_nominal_risk'])
  qr=version(rules['quantity_versions'][x['sid']],nd)['rule']; assert q==qr['buy_minimum']
  v=version(rules['venue_versions'][x['sid']],nd)['venue']; fs=version(rules['fee_versions'][v],nd)['schedule']; fee=D(0)
  for c in fs['components']:
   if c.get('side','both')not in('buy','both'): continue
   basis=c.get('amount_basis','notional'); amount=gross if basis=='notional'else q if basis=='shares'else q*D(rules['security_metadata'][x['sid']]['par_value'])
   t=max(D(c.get('minimum_local','0')),amount*D(c['rate']))
   if c.get('maximum_local')is not None:t=min(t,D(c['maximum_local']))
   if c.get('rounding_unit')is not None:
    u=D(c['rounding_unit']);t=(t/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil'else ROUND_HALF_UP)*u
   fee+=t
  assert fee==D(x['minimum_buy_fee']); assert gross+fee==D(x['minimum_cash'])
  canon= W/'2022-normal-reference-20261031/inputs/stock-receipts'/f"{x['sid']}.json"if d[:4]=='2022'else W/'recovery-2023-readiness-20261101/inputs/stock-receipts'/f"{x['sid']}.json"if d[:4]=='2023'else ROOT/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/stock-receipts'/f"{x['sid']}.json"
  assert len([j for j in load(canon)if j['confirmed_day']==d and j['receipt_id']==x['CP1_id']])==1
  samples.append(dict(day=d,sid=x['sid'],gross=str(gross),fee=str(fee),nominal_risk=x['minimum_nominal_risk'],canonical_SHA=sha(canon),raw_SHA=sha(rawpath)))
result=dict(status='PASS_WITH_SCOPE_COUNTS_AND_NINE_FIXED_SAMPLE_ARITHMETIC_ONLY',counts=checks,samples=samples,
 original_2022_wrong_receipt_window=dict(preserved=True,unknown=a['results'][0]['unknown'],not_used_for_2022_count=True),
 scope=['All622 saved candidate classifications counted; independently reconstructed source price/floor/factor, dated minimum unit, fee and canonical receipt for first3 passing ranks per date only.', 'Not excluded by checked isolated numeric conditions; no lower bound on native executable opportunities, no order/reservation or full pending/consumed/serial portfolio guards.', 'Stage>=1 restricts tested route to mature active industry; this is not proof every original probe route requires maturity.', 'Next OPEN is ex-post execution reference only; original flat-state cash/NAV does not become hypothetical new-A history. No new account/PnL/avoidable-loss conclusion.'], reviewer_account_events=0, decision='A_PRIORITY_REJECTION_UNCHANGED_NO_NATIVE_OR_ECONOMIC_EXTENSION',
 inputs={str(p):sha(p)for p in [P/'MINIMUM_UNIT_RESULTS.json',P/'minimum-unit-2022-source-correction/MINIMUM_UNIT_RESULTS.json',P/'MINIMUM_UNIT_INTERPRETATION.json',P/'minimum_unit.py',P/'minimum_unit_2022_correction.py',rp,Path(__file__)]})
(O/'A_MINIMUM_UNIT_SUPPLEMENT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=result['status'],counts=checks,samples=len(samples))))
