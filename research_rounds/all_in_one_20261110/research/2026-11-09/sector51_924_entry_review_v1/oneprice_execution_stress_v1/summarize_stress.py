"""Read-only-source, post-run comparison. No strategy execution or parameter changes."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,sys,hashlib
import pandas as pd
R=Path(sys.argv[1]);S=R/'full_20241031_once';rd=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();f=rd(R/'FREEZE.json');B=Path(f['source_facts'])/'full_20241031_once';Z=D(0)
def save(name,rows):
 (R/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str)+'\n')
 if isinstance(rows,list):pd.DataFrame(rows).to_csv(R/(name+'.csv'),index=False)
a=rd(S/'DAY_LEDGER.json');base=rd(B/'DAY_LEDGER.json');b={x['day']:x for x in base};orders=rd(S/'ORDERS.json');bo=rd(B/'ORDERS.json');last=a[-1]['day'];baseline_covered=[x for x in bo if x['day']<=last]
assert rd(S/'SOURCE_HASHES.json')==rd(B/'SOURCE_HASHES.json'),'SOURCE_FACT_SET_MISMATCH'
diffs=[]
for row in a:
 dt=row['day']
 if dt not in b:continue
 x=dict(day=dt)
 for k in ['cash','receivable','market_value','NAV','net_liquidation_NAV','stocks','shares','weight_pct','fees_paid']:
  x['scenario_'+k]=row[k];x['baseline_'+k]=b[dt][k];x['difference_'+k]=str(D(str(row[k]))-D(str(b[dt][k])))
 diffs.append(x)
save('DAILY_BASELINE_DIFFERENCES',diffs)
bsec={(x['day'],x['sector51']):x for x in rd(B/'SECTOR_DAILY.json')};sec=[]
for x in rd(S/'SECTOR_DAILY.json'):
 k=(x['day'],x['sector51'])
 if k not in bsec:continue
 row=dict(day=k[0],sector51=k[1])
 for field in ['stocks','market_value','account_weight_pct','marked_net_pnl','seeds_filled','adds_filled','sells_filled','open_rejected']:
  row['scenario_'+field]=x[field];row['baseline_'+field]=bsec[k][field];row['difference_'+field]=str(D(str(x[field]))-D(str(bsec[k][field])))
 sec.append(row)
save('DAILY_SECTOR_DIFFERENCES',sec)
manifest={x['symbol']:x for x in rd('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};raw={}
def z(s,d):
 if s not in raw:raw[s]=pd.read_parquet(next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet')))
 return raw[s].loc[pd.Timestamp(d)]
one=[]
for t in baseline_covered:
 r=z(t['sid'],t['day'])
 if len({D(str(r[k])) for k in ['raw_open','raw_high','raw_low','raw_close']})==1:one.append(dict(t,raw_oneprice=str(r.raw_open)))
save('BASELINE_ONEPRICE_ORDERS',one)
seeds=[x for x in one if x['side']=='BUY_SEED'];rids={x['round_id'] for x in seeds};adds=[x for x in bo if x['round_id'] in rids and x['side']=='BUY_ADD'];save('BASELINE_BARRED_SEED_DESCENDANT_ADDS',adds)
attempts={x['id']:x for x in rd(B/'ATTEMPTS.json')};so=rd(S/'NO_FILLS.json');line=[]
for seed in seeds:
 rid=seed['round_id'];tr=[x for x in bo if x['round_id']==rid];aa=[x for x in adds if x['round_id']==rid];other=[x for x in orders if x['sid']==seed['sid'] and x['side']=='BUY_SEED'];nf=[x for x in so if x['sid']==seed['sid'] and x['side']=='BUY_SEED' and x['day']==seed['day']]
 line.append(dict(sid=seed['sid'],name=seed['name'],baseline_round=rid,seed_day=seed['day'],seed_signal_day=seed['signal_day'],seed_qty=seed['qty'],scenario_blocked_same_seed=bool(nf),baseline_add_count=len(aa),baseline_add_quantity=sum(x['qty'] for x in aa),baseline_add_cost=str(sum((-D(x['cash_delta']) for x in aa),Z)),baseline_add_dates=[x['day'] for x in aa],baseline_attempt=attempts[rid],scenario_alternative_seed_trades=other,baseline_lineage_trades=tr,comparison_horizon=last,baseline_lineage_horizon=base[-1]['day']))
save('BARRED_SEED_PATH_LINEAGES',line)
# All aggregate trade changes include quantities driven by wider shared-cash path effects.
def agg(ts):
 out={}
 for t in ts:
  k=(t['day'],t['sid'],t['side']);r=out.setdefault(k,dict(qty=0,cash=Z,fees=Z,count=0));r['qty']+=t['qty'];r['cash']+=D(t['cash_delta']);r['fees']+=D(t['fee']);r['count']+=1
 return out
sa=agg(orders);ba=agg(baseline_covered);td=[]
for k in sorted(set(sa)|set(ba)):
 aa=sa.get(k,dict(qty=0,cash=Z,fees=Z,count=0));bb=ba.get(k,dict(qty=0,cash=Z,fees=Z,count=0))
 if aa!=bb:td.append(dict(day=k[0],sid=k[1],side=k[2],scenario=aa,baseline=bb,delta_qty=aa['qty']-bb['qty'],delta_cash=str(aa['cash']-bb['cash']),delta_fees=str(aa['fees']-bb['fees'])))
save('ALL_TRADE_PATH_DIFFERENCES',td)
candidates=rd(S/'CANDIDATES.json');rejects=[x for x in candidates if x['phase']=='OPEN' and x['decision'] not in ['PASS','NO_FILL_ONEPRICE_EXPOST']];save('ALL_OPEN_REJECTIONS',rejects)
# Strong output invariants independent of scenario engine.
source={str(p):sha(p) for p in [Path(__file__),R/'FREEZE.json',S/'ORDERS.json',S/'DAY_LEDGER.json',S/'OPEN_INTENTS.json',S/'OPEN_RESERVATIONS.json',S/'NO_FILLS.json',B/'ORDERS.json',B/'DAY_LEDGER.json']}
summary=dict(scenario_end=last,baseline_end=base[-1]['day'],same_source_hashes=True,scenario_status=rd(R/'RUN_STATUS.json'),matching_checkpoints=[x for x in diffs if x['day'] in ['2024-09-23','2024-09-25','2024-09-26','2024-09-27','2024-09-30','2024-10-08','2024-10-09','2024-10-31']],last_difference=diffs[-1],scenario_nofills=so,baseline_oneprice_orders=len(one),barred_seed_descendant_ADDs=len(adds),barred_seed_descendant_ADD_quantity=sum(x['qty'] for x in adds),trade_path_differences=len(td),rejection_counts=dict(Counter(x['decision'] for x in rejects)),source_hashes=source,limitations=['Conditional ex-post OHLC equality gate; not historical auction/queue reconstruction, verified limit-up/down status, or return lower bound.','Original whole-OPEN intents and maximum quantities are frozen before gate. No-fill buy reservations remain unavailable throughout the batch; failed sales never supply cash.','Raw OPEN +/- 5bp remains an accounting proxy, not evidence of a real executable price within H/L.','2024-09-24 onward rapid market-wide upside, future speed/breadth, persistent sectors and order access were unknowable at each decision time.','Current roster and industry classifications are not PIT; 1692 selected members are not full historical A-shares.','Small seed quantities do not bound downstream ADD, future reentry, shared-cash or return effects.','Shared-cash path changes are not a clean causal attribution to individual original orders.'])
save('COMPARISON_SUMMARY',summary)
lines=['# Independent one-price execution stress comparison','',f'Facts: {Path(f["source_facts"]).name}. Certified scenario through {last}; baseline through {base[-1]["day"]}. All original baseline artifacts remain unchanged.','',f'No-fills: {len(so)}. Baseline one-price orders over common horizon: {len(one)}. Baseline ADD descendants of barred seeds: {len(adds)}. Aggregate trade path differences: {len(td)}.','', '## Matching-date NAV differences']
for x in summary['matching_checkpoints']:lines.append(f'- {x["day"]}: scenario NAV {D(x["scenario_NAV"]):,.2f}; baseline {D(x["baseline_NAV"]):,.2f}; difference {D(x["difference_NAV"]):+,.2f}; scenario stocks {x["scenario_stocks"]}, weight {D(x["scenario_weight_pct"]):.4f}%.')
lines+=['','## Limitations']+['- '+x for x in summary['limitations']]+['','## Files','- full_20241031_once: full scenario account, holdings, orders, all 50 sectors, equity, CP, candidates, intents, reservations and no-fills.','- DAILY_BASELINE_DIFFERENCES and DAILY_SECTOR_DIFFERENCES: full daily comparisons.','- BARRED_SEED_PATH_LINEAGES and BASELINE_BARRED_SEED_DESCENDANT_ADDS: downstream paths, including alternative scenario entries.','- ALL_TRADE_PATH_DIFFERENCES: indirect funding/quantity changes.','- ALL_OPEN_REJECTIONS: all ordinary rejected OPEN requests.','- FREEZE and source/output hashes preserve provenance.']
(R/'READOUT.md').write_text('\n'.join(lines)+'\n');save('ANALYSIS_OUTPUT_SEAL',{p.name:sha(p) for p in R.iterdir() if p.is_file() and p.name!='ANALYSIS_OUTPUT_SEAL.json'})
print(json.dumps({k:summary[k] for k in ['scenario_end','baseline_end','last_difference','barred_seed_descendant_ADDs','trade_path_differences']},ensure_ascii=False,default=str))
