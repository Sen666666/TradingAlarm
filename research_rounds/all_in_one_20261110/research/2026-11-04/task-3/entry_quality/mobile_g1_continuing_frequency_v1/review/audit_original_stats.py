"""Read-only original-book/summary audit; no strategy imports or account execution."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict
from datetime import datetime
import gzip, hashlib, json, math
import pandas as pd
getcontext().prec=50
R=Path(__file__).resolve().parent; F=R.parent; S=F/'stats'; Q=F.parent
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
bound={};checks=[]
def read(p,gz=False,lines=False):
 p=Path(p);bound[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as h:return [json.loads(x) for x in h] if lines else json.load(h)
def close(a,b):assert abs(D(str(a))-D(str(b)))<=D('1e-17'),(a,b)
def dt(s):return datetime.fromisoformat(s)
def bucket(r):
 if not r['exact_previous_CLOSE_observation']:return 'UNKNOWN_NO_EXACT_PREVIOUS_CLOSE'
 if r['G1_grade_ready'] is None:return 'UNKNOWN_GRADE_READY'
 if not r['G1_grade_ready']:return 'UNREADY'
 g=r['G1_grade']
 if g is None or not math.isfinite(g):return 'UNKNOWN_NAN_GRADE'
 return 'NEGATIVE' if g<0 else 'ZERO' if g==0 else 'ONE' if g==1 else 'WARM_GE2' if g>=2 else 'OTHER_READY_BELOW2'
M=read(S/'SOURCE_MANIFEST.json');assert sha(S/'extract_original_stats.py')==M['script_sha256']
summary=read(S/'SUMMARY.json'); carries=read(S/'B_2025_CARRY_MOBILE_ROWS.json')
outputs={}; books={}; days={};prefix={}; observed=[]
for window,fn,lo,hi in [('2022_2024','A_2022_2024_MOBILE_ROWS.json','2022-01-04','2024-12-31'),('strong','B_2026H1_NEW_MOBILE_ROWS.json','2026-01-01','2026-06-30')]:
 rows=read(S/fn); outputs[window]=rows; ip=M['inputs'][window]
 b=read(ip['book'],True); books[window]=b; daily=read(ip['daily'],True,True);days[window]=daily
 assert bound[str(Path(ip['book']).resolve())]==M['source_sha256'][ip['book']]
 assert bound[str(Path(ip['daily']).resolve())]==M['source_sha256'][ip['daily']]
 clocks=[dt(x['at']) for x in daily]; nmap={x['id']:x for x in b['layers']}; buys={t['layer']:(i,t) for i,t in enumerate(b['trades']) if t['side']=='buy'}
 expected={t['layer'] for t in b['trades'] if t['side']=='buy' and t['kind']=='add' and lo<=t['at'][:10]<=hi}
 assert expected=={r['layer'] for r in rows} and len(expected)==len(rows)
 fees=defaultdict(lambda:D(0)); sells=defaultdict(list)
 for ti,t in enumerate(b['trades']):
  if t['side']!='sell':continue
  for pi,p in enumerate(t['parts']):
   fees[p['layer']]+=D(p['shares'])*D(t['price'])-D(p['net_cash'])
   if b['metadata'][str(p['layer'])]['role']=='mobile':sells[t['security_id']].append((dt(t['at']),ti,p['layer'],b['metadata'][str(p['layer'])].get('stock_structure')))
 for r in rows:
  lid=r['layer']; ti,t=buys[lid]; n=nmap[lid];meta=b['metadata'][str(lid)]
  assert ti==r['book_buy_trade_index'] and t['shares']==r['actual_fill_shares'] and t['security_id']==r['sid']
  assert dt(t['at'])==dt(r['actual_fill_at']) and meta['role']=='mobile'
  prev=max(x for x in clocks if x<dt(t['at'])); decision=dt(meta['budget_order'].split('|')[1])
  assert prev==decision==dt(r['intent_decision_at'])==dt(r['previous_A_market_CLOSE_at'])
  assert bucket(r)==r['G1_bucket'] and r['grade_source_day']==decision.date().isoformat()
  close(t['gross_cny'],r['actual_buy_gross']);close(t['fees_cny'],r['actual_buy_fee']);close(D(t['gross_cny'])+D(t['fees_cny']),r['actual_input_gross_plus_buy_fee']);close(fees[lid],r['actual_allocated_sell_fee_by_endpoint'])
  assert (n['qty']==0)==r['closed_by_endpoint'] and n['qty']==r['ending_qty']
  close(D(n['cash'])+D(r['ending_mark_value'])+D(n['dividend']),r['original_endpoint_net_contribution'])
  close(D(r['original_strict_realized'])+D(r['original_open_unrealized'])+D(r['original_dividend_AR']),r['original_endpoint_net_contribution'])
  history=[s for s in sells[r['sid']] if s[0]<decision]
  same=[s for s in history if s[3]==r['original_stock_structure']]
  observed.append(dict(window=window,layer=lid,sid=r['sid'],decision=r['intent_decision_at'],grade=r['G1_grade'],bucket=r['G1_bucket'],prior_any_mobile_sell=bool(history),prior_same_root_mobile_sell=bool(same),net=r['original_endpoint_net_contribution']))
 # Independently sum every monetary/count SUMMARY cell from the row file.
 for z in [x for x in summary if x['cohort']==rows[0]['cohort']]:
  g=z['grade_group']
  rr=rows if g=='ALL_MOBILE' else [r for r in rows if (bucket(r) in ['NEGATIVE','ZERO','ONE','OTHER_READY_BELOW2'] if g=='LT2_READY' else bucket(r)=='WARM_GE2' and r['G1_grade']==int(g[5:]) if g in ['WARM_2','WARM_3','WARM_4'] else bucket(r)==g)]
  assert z['layers']==len(rr)
  for k in ['actual_fill_shares','actual_input_gross_plus_buy_fee','actual_buy_gross','actual_buy_fee','actual_allocated_sell_fee_by_endpoint','total_actual_fees_by_endpoint','original_strict_realized','original_open_unrealized','original_dividend_AR','original_endpoint_net_contribution']:
   close(sum((D(str(r[k])) for r in rr),D(0)),z[k])
  assert z['fully_closed_layers']==sum(r['closed_by_endpoint'] for r in rr)
  assert z['open_layers']==sum(not r['closed_by_endpoint'] for r in rr)
  assert z['holding_cross_year_layers']==sum(r['holding_cross_calendar_year'] for r in rr)
  assert z['signal_fill_cross_year_layers']==sum(r['signal_fill_cross_calendar_year'] for r in rr)
 checks.append(dict(window=window,all_original_buy_identity_clock_fees_cash_bridge=len(rows),all_summary_rows=sum(x['cohort']==rows[0]['cohort'] for x in summary),all_G1_ready=sum(r['G1_grade_ready'] is True for r in rows)))
# Carry cohort membership and inherited historical acquisition clock, not new H1 fills.
cut=next(x for x in days['strong'] if x['at'][:10]=='2025-12-31')
assert {x['id'] for x in cut['layers'] if x['kind']=='add'}=={r['layer'] for r in carries}
assert all(r['actual_fill_at'][:10]<'2026-01-01' for r in carries)
cs=read(S/'CARRY_SUMMARY.json')
close(sum((D(r['original_endpoint_net_contribution']) for r in carries),D(0)),cs['lifetime_through_Jun30']['original_endpoint_net_contribution'])
close(sum((D(r['original_2026H1_wealth_change_from_carry']) for r in carries if r['original_2026H1_wealth_change_from_carry'] is not None),D(0)),cs['original_2026H1_carry_wealth_change_sum_known_only'])
# Six selected grade/ready direct-source checks, including cross-year intent.
samples=[('2022_2024',1931),('2022_2024',84),('strong',739),('strong',756),('strong',629),('carry',531)]
sm=read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'); sm={x['symbol']:x for x in sm}; grade_samples=[]
for w,lid in samples:
 rr=carries if w=='carry' else outputs[w];r=next(x for x in rr if x['layer']==lid);p=Path(sm[r['sid']]['refs']['facts']);bound[str(p)]=sha(p)
 assert bound[str(p)]==M['source_sha256'][str(p)]==sm[r['sid']]['output_sha256'][str(p)]
 f=pd.read_parquet(p,columns=['g_grade','g_ready']).loc[pd.Timestamp(r['grade_source_day'])]
 assert float(f.g_grade)==r['G1_grade'] and bool(f.g_ready)==r['G1_grade_ready']
 grade_samples.append({k:r[k] for k in ['layer','sid','actual_fill_at','intent_decision_at','G1_grade','G1_grade_ready']})
# Direct original old TaiBao sell, which disproves no-prior-sell across all years.
b=books['2022_2024'];t=b['trades'][1260]
assert t['side']=='sell' and t['security_id']=='601601.SH' and t['at'][:10]=='2022-09-30' and any(p['layer']==639 for p in t['parts'])
tb=next(x for x in observed if x['window']=='2022_2024' and x['layer']==1931)
assert tb['prior_any_mobile_sell'] and not tb['prior_same_root_mobile_sell']
# Independent candidate scope descriptive counts; no economic replay or changed-path claim.
selection=[]
for w in outputs:
 for scope,col in [('all_history_same_stock','prior_any_mobile_sell'),('same_stock_structure','prior_same_root_mobile_sell')]:
  rr=[r for r in observed if r['window']==w and r[col] and r['bucket'] in ['NEGATIVE','ZERO','ONE','OTHER_READY_BELOW2']]
  selection.append(dict(window=w,scope=scope,rows=len(rr),negative_rows=sum(r['bucket']=='NEGATIVE' for r in rr),one_rows=sum(r['bucket']=='ONE' for r in rr),original_endpoint_net_contribution=str(sum((D(r['net']) for r in rr),D(0))),layer_ids=[r['layer'] for r in rr]))
res=dict(status='PASS_ORIGINAL_STATISTICS_FULL_ROW_AGGREGATES_WITH_SIX_GRADE_SAMPLES',remaining_statistical_blocks=[],checks=checks,carry_membership=49,source_grade_direct_sample_count=len(grade_samples),source_grade_samples=grade_samples,taibao_1931_scope_counterexample=tb,taibao_639_original_sell=dict(trade_index=1260,raw=t),independent_scope_selection_descriptive_only=selection,source_sha256=bound,limits=['Direct grade/ready source re-read is six samples, not all995 source symbols.','All216? rows are only original facts/filled paths, not all eligible opportunities.','Endpoint marks reused from prior audited layer row fields; no cold valuation recomputation.','Carry membership/aggregate checked, all49 cutoff raw-mark domain not independently rebuilt.','No proposed filtered account, funding, execution, return or causal saving calculated.'],new_accounts=0,new_backtests=0,new_strategy_imports=0,new_candidate_fills=0)
res['limits'][1]='All2157 new MOBILE rows and49 carry rows are original filled paths, not all eligible opportunities.'
(R/'ORIGINAL_STATS_AUDIT.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(status=res['status'],checks=checks,selection=selection,grade_samples=len(grade_samples),carry=49),ensure_ascii=False))
