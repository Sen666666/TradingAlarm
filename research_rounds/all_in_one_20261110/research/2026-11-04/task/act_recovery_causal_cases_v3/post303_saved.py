"""303 actual post-Oct8 layers only. Original receipts / saved risks, no new pricing."""
import json,gzip,csv,hashlib
from decimal import Decimal as D, getcontext
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
getcontext().prec=80
paths={
 'book':'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/B.json.gz',
 'daily':'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/daily.jsonl.gz',
 'layers':'attribution_2024_chain_v2/No60_post_oct8_ALL_LAYERS.json',
 'risk':'risk_constraints/entry_initial_risk_scale_v1/THIN_ENTRIES.json',
 'risk_result':'risk_constraints/entry_initial_risk_scale_v1/RESULTS.json',
 'actions':'attribution_2024_chain_v2/No60_ALL_HISTORICAL_ENTRY_ACTIONS.json',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before={k:sha(ROOT/p) for k,p in paths.items()}
def load(k):return json.load(open(ROOT/paths[k]))
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
lr={x['layer']:x for x in load('layers') if x['group']=='new_actual_fill_in_phase'}
rr={x['layer']:x for x in load('risk') if x['population']=='post_Oct8_new303_at_2024_cutoff'}
aa={x['layer']:x for x in load('actions') if x['layer'] in lr}
assert len(lr)==303 and lr.keys()==rr.keys()==aa.keys()
for lid,x in lr.items(): assert abs(D(x['wealth'])-D(rr[lid]['net']))<D('1e-20')
with gzip.open(ROOT/paths['book'],'rt') as f:b=json.load(f)
with gzip.open(ROOT/paths['daily'],'rt') as f:ds=[json.loads(l) for l in f]
days=[x['at'][:10] for x in ds];ix={d:i for i,d in enumerate(days)}
def desc(v):
 v=sorted(v); n=len(v)
 if not n:return {'count':0}
 return {'count':n,'min':v[0],'sum':sum(v,D(0)),'p10':v[(n-1)*10//100],'p50':v[(n-1)*50//100],'p90':v[(n-1)*90//100],'p95':v[(n-1)*95//100],'max':v[-1],'quantile_method':'empirical lower order statistic floor((n-1)*p), no fitted threshold'}
def stats(ids):
 ids=list(ids)
 return {'layers':len(ids),'wealth':sum((D(lr[l]['wealth']) for l in ids),D(0)),
 'initial_nominal_R_CNY':desc([D(rr[l]['actual_initial_nominal_risk']) for l in ids]),
 'initial_nominal_R_pct_own_decision_NAV':desc([D(rr[l]['actual_initial_risk_pct_decisionNAV']) for l in ids]),
 'source_reference_unknown_flags':dict(Counter(z for l in ids for z in rr[l]['reference_unknown_reasons']))}
groups={'all303':stats(lr)}
for role in ['core','mobile']:groups[role]=stats(l for l in lr if lr[l]['role']==role)
for action in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']:
 groups[action]=stats(l for l in lr if lr[l]['action']==action)
dayrows=[]
for r in ds:
 if r['at'][:10]<='2024-10-08':continue
 risk=D(r['pool_probe'][1])+D(r['pool_confirmed'][1])
 dayrows.append({'at':r['at'],'NAV':r['nav'],'inventory':r['inventory'],'whole_account_saved_mark_floor_nominal_CNY':risk,'whole_account_saved_mark_floor_nominal_pct_NAV':risk/D(r['nav'])*100,'saved_pool_probe':r['pool_probe'],'saved_pool_confirmed':r['pool_confirmed']})
cv=[r['whole_account_saved_mark_floor_nominal_pct_NAV'] for r in dayrows]
save('POST303_RISK_AND_CONCURRENT.json',{'groups':groups,'concurrent_whole_account_daily':dayrows,'concurrent_summary':{'days':len(dayrows),'mean_CLOSE_nominal_pct_NAV':sum(cv)/len(cv),'max_CLOSE_nominal_pct_NAV':max(cv),'maximum_at':dayrows[cv.index(max(cv))]['at']},'note':'Initial R cumulative sums are turnover statistics, not concurrent risk, maximum loss or guaranteed stop loss. Concurrent values reuse whole-account native pool fields, include old Oct8 holdings, are not the 303 cohort alone or intraday risk. Initial R excludes fees/gaps beyond price-to-frozen-line definition.'})

requests=defaultdict(list); sells=defaultdict(list)
for e in b['audit']:
 if e['kind']=='pilot_layer_exit':
  for lid in e['layers']:
   if lid in lr:requests[lid].append(e)
for t in b['trades']:
 if t['side']=='sell':
  for p in t['parts']:
   if p['layer'] in lr:sells[p['layer']].append({'trade':t,'part':p})
exits=[]
for lid in sorted(lr):
 qs=requests[lid];ss=sells[lid]
 assert qs and ss
 first=qs[0];firstsale=ss[0]['trade'];lastsale=ss[-1]['trade']
 i=ix[first['at'][:10]];nd=days[i+1] if i+1<len(days) else None
 expected=nd+' 09:30:00+08:00' if nd else None
 exits.append({'layer':lid,'sid':lr[lid]['sid'],'role':lr[lid]['role'],'action':lr[lid]['action'],'first_request':first,'expected_next_OPEN':expected,'first_actual_sale_at':firstsale['at'],'last_actual_sale_at':lastsale['at'],'first_sale_NEXT_OPEN':firstsale['at']==expected,'complete_sale_NEXT_OPEN':lastsale['at']==expected,'sale_part_receipts':ss,'request_count':len(qs),'later_request_reasons':[q['reason'] for q in qs[1:]],'explicit_block_reason':'UNKNOWN; no per-attempt rejection logged in original book' if firstsale['at']!=expected else None})
buy_j={j['layer']:j for j in b['journal'] if j['kind']=='real_buy_fill' and j['layer'] in lr}
assert buy_j.keys()==lr.keys()
confirmed_later=[j for j in buy_j.values() if j['pool']=='confirmed' and j['at'][:10]>'2024-10-10']
def witness(j):
 lid=j['layer'];return {'journal_fill':j,'entry_risk':rr[lid],'action':aa[lid],'saved_wealth':lr[lid]['wealth'],'exit_timing':next(z for z in exits if z['layer']==lid)}
named=[j for j in confirmed_later if j['sid'] in ['002583.SZ','601360.SH']]
save('POST303_EXIT_EXECUTION_AND_CONFIRMED.json',{'layers':303,'first_sale_next_OPEN':sum(x['first_sale_NEXT_OPEN'] for x in exits),'complete_sale_next_OPEN':sum(x['complete_sale_NEXT_OPEN'] for x in exits),'multiple_actual_sale_parts_layers':sum(len(x['sale_part_receipts'])>1 for x in exits),'known_request_layers':len(exits),'delayed_layers':[x for x in exits if not x['first_sale_NEXT_OPEN']],'all_layers':exits,'actual_fill_pools':dict(Counter(j['pool'] for j in buy_j.values())),'confirmed_actual_fills_after_first_2024Oct10':len(confirmed_later),'confirmed_after_first_day_examples':[witness(j) for j in confirmed_later[:3]],'confirmed_named_witnesses':[witness(j) for j in named],'note':'All links from original pilot_layer_exit requests and actual trades.parts; no quote/price inference for rejected attempts. Next-OPEN execution does not guarantee realized loss <= initial nominal R.'})

ratios={}
allrat=[]
for role in ['core','mobile']:
 ids=[l for l in lr if lr[l]['role']==role]
 neg=[l for l in ids if D(lr[l]['wealth'])<0]
 unknown=[l for l in neg if rr[l]['reference_unknown_reasons'] or not rr[l].get('actual_initial_nominal_risk')]
 zero=[l for l in neg if l not in unknown and D(rr[l]['actual_initial_nominal_risk'])==0]
 valid=[l for l in neg if l not in unknown+zero and D(rr[l]['actual_initial_nominal_risk'])>0]
 vv=[]
 for l in valid:
  loss=-D(lr[l]['wealth']);R=D(rr[l]['actual_initial_nominal_risk']);vv.append({'layer':l,'sid':lr[l]['sid'],'name':lr[l]['name'],'opened':lr[l]['opened'],'action':lr[l]['action'],'role':role,'initial_nominal_R':R,'negative_wealth_magnitude':loss,'loss_over_initial_nominal_R':loss/R,'cost':rr[l]['cost'],'final_exit_reason':lr[l]['final_exit_reason'],'next_OPEN_execution':next(z for z in exits if z['layer']==l)['first_sale_NEXT_OPEN']})
 def over(t):
  z=[v for v in vv if v['loss_over_initial_nominal_R']>t]
  return {'count':len(z),'negative_wealth_magnitude_sum':sum((v['negative_wealth_magnitude'] for v in z),D(0)),'initial_nominal_R_sum':sum((v['initial_nominal_R'] for v in z),D(0)),'layers':[v['layer'] for v in z]}
 ratios[role]={'all_layers':len(ids),'negative_layers':len(neg),'negative_wealth_magnitude_sum':sum((-D(lr[l]['wealth']) for l in neg),D(0)),'negative_R_known_positive':len(valid),'negative_R_zero':zero,'negative_reference_unknown':[{'risk':rr[l],'wealth':lr[l]['wealth']} for l in unknown],'loss_over_R_distribution':desc([v['loss_over_initial_nominal_R'] for v in vv]),'strictly_above_1R':over(D(1)),'strictly_above_2R':over(D(2))}
 allrat.extend(vv)
examples=sorted(allrat,key=lambda x:x['negative_wealth_magnitude'],reverse=True)[:3]
save('POST303_NEGATIVE_WEALTH_OVER_INITIAL_R.json',{'scope':'Original layer actual wealth, including original fees/recognized dividends or dividend AR; not gross sale loss or dynamic protection line risk. Unknown reference CA flagged layer excluded from ratio main table, source numeric R retained. Descriptive ratio not breach/violation proof or maximum-loss guarantee. Core I semantics not independently reconstructed.','by_role':ratios,'examples_selection':'Three greatest negative wealth magnitudes among valid-R losing layers, post hoc diagnostic only. No P&L label is an input signal.','examples':examples,'all_negative_valid_R_layers':allrat})
assert before=={k:sha(ROOT/p) for k,p in paths.items()}
save('POST303_SOURCE_BINDING.json',{'source_sha256':{k:{'path':v,'sha256':before[k]} for k,v in paths.items()},'script_SHA256':sha(Path(__file__)),'new_account_events':0,'new_backtests':0,'new_prices':0,'new_indicator_computation':0,'checks':['303 source IDs match all three sources','per-layer saved wealth equals source risk net within retained Decimal rounding1e-20','all303 have original first layer-exit request and actual sale parts','source post SHAs unchanged'],'independent_review':'NOT_NEWLY_REVIEWED; inherited original finance/entry-risk audits do not certify this new grouping.'})
print(json.dumps({'groups':groups,'exit_next':sum(x['first_sale_NEXT_OPEN'] for x in exits),'complete_next':sum(x['complete_sale_NEXT_OPEN'] for x in exits),'pool_counts':dict(Counter(j['pool'] for j in buy_j.values())),'confirmed_later':len(confirmed_later),'negative_R':ratios,'three_examples':examples},ensure_ascii=False,default=str))
