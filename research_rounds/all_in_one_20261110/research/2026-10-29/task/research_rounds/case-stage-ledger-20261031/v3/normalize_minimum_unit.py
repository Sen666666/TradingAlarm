"""Diagnostic labels only; never alter original funding logs or trading rules."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import gzip,json,hashlib,shutil
import numpy as np,pandas as pd
import launch_v3 as L
J=L.J;O=J.O/'risk-occupancy-diagnostic';ROOT=Path('/Users/bytedance/Documents/ChatGPT/money')
def records(p):
 with gzip.open(p,'rt') as f:
  for x in f:yield json.loads(x)
def dist(values):
 v=[float(x) for x in values]
 return dict(n=len(v),minimum=min(v),p25=float(np.quantile(v,.25)),median=float(np.median(v)),p75=float(np.quantile(v,.75)),maximum=max(v)) if v else dict(n=0)
def main():
 aud=O/'independent-audit';aud.mkdir(exist_ok=True);manifest={}
 for src in [Path('/tmp/risk-diagnostic-audit.mIef8p/EVIDENCE.json'),Path('/tmp/risk-diagnostic-audit.mIef8p/audit.py')]:
  dst=aud/src.name;shutil.copy2(src,dst);manifest[str(src)]=dict(copy=str(dst),source_sha256=L.sha(src),copy_sha256=L.sha(dst))
 L.save(aud/'COPY_MANIFEST.json',manifest)
 Base=J.M.E.FastMarket.__mro__[1];m=Base.__new__(Base)
 m.rules=L.read(ROOT/'research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');m.protocol=L.read(J.BP.C.OLD/'inputs-v2/economic-protocol.json')
 meta=L.read(ROOT/'research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json');sm={r['symbol']:r for r in L.read(L.U/'STOCK_MANIFEST.json')}
 a=json.load(gzip.open(J.O/'run-universe/pair/B.json.gz','rt'));nav={x['at'][:10]:D(x['nav']) for x in a['decisions']}
 daily={r['at'][:10]:r for r in records(J.O/'run-universe/pair/daily.jsonl.gz') if r['account']=='B'}
 eligible={(r['sid'],r['day']):r['receipt'] for r in records(O/'ELIGIBLE_CP1.jsonl.gz')};raw={};out=[]
 fund=J.O/'run-universe/pair/funding.jsonl.gz';oldsha=L.sha(fund)
 for r in records(fund):
  if r['account']!='B' or r.get('role')!='mobile' or r['result']!='no_nominal_gap':continue
  sid=r['sid'];day=r['at'][:10];at=J.M.N.iso(r['at']);rule=Base.quantity(m,sid,at)
  if sid not in raw:raw[sid]=pd.read_parquet(sm[sid]['refs']['facts'],columns=['raw_close']).raw_close
  price=D(str(raw[sid].loc[day]));n=nav[day];q=D(daily[day]['positions'].get(sid,0));gap=max(D(0),n*D('.1')-q*price);budget=min(n*D('.02'),gap)
  minimum=D(rule.buy_minimum)*price;assert rule.buy_floor(int(budget/price))==0
  out.append(dict(receipt=eligible[(sid,day)],sid=sid,name=meta[sid]['name'],day=day,original_result='no_nominal_gap',
   diagnostic_reason='positive_budget_below_legal_minimum_gross_unit' if budget>0 else 'zero_remaining_stock_nominal_gap',
   budget=str(budget),decision_NAV=str(n),raw_close=str(price),held_quantity=int(q),legal_minimum_quantity=rule.buy_minimum,
   minimum_gross_before_slippage_and_fee=str(minimum),shortfall=str(minimum-budget),positive_budget=budget>0))
 assert len(out)==len({r['receipt'] for r in out});pos=[r for r in out if r['positive_budget']]
 summary=dict(original_label_receipts=len(out),original_label_stocks=len({r['sid'] for r in out}),positive_budget_blocked_receipts=len(pos),
  positive_budget_blocked_stocks=len({r['sid'] for r in pos}),zero_remaining_stock_gap_receipts=len(out)-len(pos),
  positive_budget_CNY=dist([D(r['budget']) for r in pos]),legal_minimum_gross_CNY=dist([D(r['minimum_gross_before_slippage_and_fee']) for r in pos]),
  minimum_gross_minus_positive_budget_CNY=dist([D(r['shortfall']) for r in pos]),
  minimum_gross_minus_positive_budget_pct_decision_NAV=dist([100*D(r['shortfall'])/D(r['decision_NAV']) for r in pos]),
  minimum_quantity_counts=dict(Counter(r['legal_minimum_quantity'] for r in pos)),
  unit='unique canonical CP1 receipt; repeated stocks/dates are not independent market samples',original_file_unchanged=L.sha(fund)==oldsha,
  original_funding_sha256=oldsha,no_replay_or_policy_change=True,
  minimum_cost_definition='signal-date legal gross unit only; fees/slippage additional; diagnoses original pre-intent cap=0')
 L.save(O/'GLOBAL_MINIMUM_UNIT_BLOCK_SUMMARY.json',summary);L.save(O/'NORMALIZED_MINIMUM_UNIT_DIAGNOSTIC.json',out)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
