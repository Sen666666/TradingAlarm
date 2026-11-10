"""Independent actual-sell timestamp joins, not a proposed account or return."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from decimal import Decimal as D,getcontext
import gzip,hashlib,json
getcontext().prec=50
O=Path(__file__).resolve().parent;F=O.parent;X=F/'reentry_filter';Q=F.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
SRC={}
def read(p,gz=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as h:return json.load(h)
def dt(s):return datetime.fromisoformat(s)
def eq(a,b):assert abs(D(str(a))-D(str(b)))<=D('1e-17'),(a,b)
rows=read(X/'ORIGINAL_MOBILE_FILLS_WITH_MEMORY.json');summ=read(X/'SUMMARY.json');proto=read(X/'PROTOCOL.json')
validation=read(X/'SOURCE_AND_VALIDATION.json');assert sha(X/'screen.py')==validation['script_sha256']
known={}
for fn in ['A_2022_2024_MOBILE_ROWS.json','B_2026H1_NEW_MOBILE_ROWS.json','B_2025_CARRY_MOBILE_ROWS.json']:
 for r in read(F/'stats'/fn):known[(r['original_account_window'],r['layer'])]=r
witnesses=[];counts=[];subset_cells=0
for w in ['2022_2024','strong']:
 p=Q/'trend_exit_controls_v1/runs/BASELINE'/w/'pair/B.json.gz';b=read(p,True);assert SRC[str(p.resolve())]==validation['source_sha256'][str(p.resolve())]
 meta=b['metadata'];history=defaultdict(list);native={x['id']:x for x in b['layers']}
 for ti,t in enumerate(b['trades']):
  if t['side']=='sell':
   for part in t['parts']:
    if part['shares']>0 and meta[str(part['layer'])]['role']=='mobile':history[t['security_id']].append((dt(t['at']),ti,part['layer'],meta[str(part['layer'])].get('stock_structure')))
 expected={t['layer'] for t in b['trades'] if t['side']=='buy' and t['kind']=='add'}
 rr=[r for r in rows if r['window']==w];assert expected=={r['layer'] for r in rr} and len(expected)==len(rr)
 for r in rr:
  key=(w,r['layer']);root=meta[str(r['layer'])].get('stock_structure');assert root==r['stock_structure']
  prior=[s for s in history[r['sid']] if s[0]<dt(r['decision_at'])];same=[s for s in prior if s[3]==root]
  assert bool(prior)==r['prior_any_mobile_sale'] and bool(same)==r['prior_same_root_mobile_sale']
  for scope,hist,flag in [('any',prior,'main_gate'),('root',same,'same_root_gate')]:
   expected_gate='NO_PRIOR_SALE_NO_ADDED_GATE' if not hist else 'UNKNOWN_G1' if not r['G1_ready'] else 'PASS_G1_GE2' if r['grade']>=2 else 'FAIL_G1_LT2'
   assert r[flag]==expected_gate
   last=r['last_prior_any_sale' if scope=='any' else 'last_prior_same_root_sale']
   if hist:
    latest=max(hist,key=lambda x:(x[0],x[1]));assert last['book_trade_index']==latest[1] and dt(last['at'])==latest[0]
   else:assert last is None
  if key in known:
   k=known[key];assert r['grade']==k['G1_grade'] and r['G1_ready']==k['G1_grade_ready']
   for field,other in [('net','original_endpoint_net_contribution'),('cost','actual_input_gross_plus_buy_fee'),('buy_fee','actual_buy_fee'),('sell_fee','actual_allocated_sell_fee_by_endpoint'),('strict_realized','original_strict_realized'),('open_unrealized','original_open_unrealized'),('recognized_dividend_AR','original_dividend_AR')]:eq(r[field],k[other])
  assert (native[r['layer']]['qty']==0)==bool(r['closed'])
  if (w,r['layer']) in [('2022_2024',1931),('strong',739)]:witnesses.append(r)
 lo,hi=summ[w]['fill_window'];fr=[r for r in rr if lo<=r['opened'][:10]<=hi]
 groups=[('original_fill_cohort',fr),('all_G1_lt2_original_fills',[r for r in fr if r['G1_ready'] and r['grade']<2]),('main_any_prior_sale',[r for r in fr if r['main_gate']=='FAIL_G1_LT2']),('appendix_same_root',[r for r in fr if r['same_root_gate']=='FAIL_G1_LT2'])]
 for name,gg in groups:
  z=summ[w][name];z=z['actual_fills'] if name in ['main_any_prior_sale','appendix_same_root'] else z
  assert z['actual_fill_layers']==len(gg) and z['stocks']==len({r['sid'] for r in gg})
  for field,out in [('net','original_net_contribution'),('strict_realized','strict_realized'),('open_unrealized','open_unrealized'),('recognized_dividend_AR','recognized_dividend_AR'),('buy_fee','buy_fees'),('sell_fee','sell_fees'),('cost','actual_buycash')]:eq(sum((D(r[field]) for r in gg),D(0)),z[out])
  eq(sum((max(D(0),D(r['net'])) for r in gg),D(0)),z['original_positive_net']);eq(sum((min(D(0),D(r['net'])) for r in gg),D(0)),z['original_negative_net'])
  assert z['closed_layers']==sum(bool(r['closed']) for r in gg)
  subset_cells+=1
 counts.append(dict(window=w,all_actual_mobile_fill_rows=len(rr),report_fill_rows=len(fr),memory_flags_and_timestamps_independently_checked=len(rr)))
tb=next(r for r in witnesses if r['window']=='2022_2024');assert tb['main_gate']=='FAIL_G1_LT2' and tb['same_root_gate']=='NO_PRIOR_SALE_NO_ADDED_GATE'
same_day=next(r for r in witnesses if r['window']=='strong');assert same_day['last_prior_any_sale']['at'][:10]==same_day['decision_at'][:10] and dt(same_day['last_prior_any_sale']['at'])<dt(same_day['decision_at'])
# The owner's signal-side counters are read for clock/interface review only, not independently re-scanned.
for w in summ:
 for name in ['main_any_prior_sale','appendix_same_root']:
  s=summ[w][name]['signals'];assert s['newly_blocked_original_generated_intents']==sum(s['of_newly_blocked_original_funding_status'].values())
  assert s['memory_and_G1_lt2_opportunities']==s['originally_barrier_blocked_opportunities']+s['barrier_free_opportunities']
result=dict(status='PASS_ORIGINAL_ACTUAL_FILL_MEMORY_AND_AGGREGATES_WITH_SCOPE_LIMITS',remaining_blocks=[],counts=counts,actual_fill_economic_subset_cells_checked=subset_cells,known_stats_joined_rows=len(known),witnesses=witnesses,source_sha256=SRC,
 explicit_corrections=['TaiBao1931 any-history gate FAIL is caused by actual2022 layer639 sale; same-current-root has no prior sale.','grade<0 is negative grade, while native cold requires grade<=-2 or acute_down.'],
 not_independently_rederived=['Full255MB all-qualified-opportunity source/grade/root reconstruction and2055/354 newly-blocked-intent counts.','All OPEN original rejection reasons or semi19-intent/all-originally-rejected counts from raw logs.','Four cold-chain/warm-control extractions beyond the original samples specified in ORIGINAL_STATS_AUDIT.','Candidate blocked order execution, cash, subsequent fills or account profitability.'],
 checks_do_not_imply_effect='All touched contributions are original path descriptions. Partial MOBILE sell counts in main protocol; whole-stock flat is not required.',new_accounts=0,new_backtests=0,strategy_imports=0,new_fills=0)
(O/'REENTRY_FILTER_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(status=result['status'],counts=counts,subset_cells=subset_cells,known=len(known)),ensure_ascii=False))
