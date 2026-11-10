from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
from statistics import median
import json,csv,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent/'mainline_m7_cash_batch_design_v6/once_20260630';A='2024-11-06';E='2025-01-20';Z=D(0)
def rd(p):return json.loads(p.read_text())
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
 if isinstance(x,list) and x:
  with (O/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
def sm(rs,k):return sum((D(r.get(k,0)) for r in rs),Z)
def quant(rs):
 arr=sorted(D(x) for x in rs)
 def at(p):
  if not arr:return None
  pos=D(len(arr)-1)*D(p);i=int(pos);frac=pos-i;return arr[i]+(arr[min(i+1,len(arr)-1)]-arr[i])*frac
 return dict(min=min(arr) if arr else None,p10=at('.1'),median=at('.5'),p90=at('.9'),max=max(arr) if arr else None)
orders=rd(R/'ORDERS.json');attempts=rd(R/'ATTEMPTS.json');cohort=rd(O/'SEGMENT_1106_ROUNDS.json');og=defaultdict(list)
for o in orders:og[o['round_id']].append(o)
new=[r for r in cohort if r['cohort']=='NEW_AFTER_1106']
for r in new:
 os=og[r['round_id']];seed=next(o for o in os if o['side']=='BUY_SEED');r['phase']=seed['allocation_phase'];r['seed_notional']=seed['notional'];r['seed_raw_notional']=D(seed['notional'])/D('1.0005')
 r['model_slippage']=sum((abs(D(o['price'])-D(o['price'])/(D('1.0005') if o['side'].startswith('BUY') else D('.9995')))*o['qty'] for o in os),Z)
 r['fill_price_plus_div_pnl']=D(r['segment_pnl'])+D(r['segment_fees']);r['raw_price_plus_div_pnl']=r['fill_price_plus_div_pnl']+r['model_slippage']
rows=[]
for role,phase in [('INITIAL','EVENT'),('INITIAL','RESIDUAL'),('EXPANSION','MATURE')]:
 for added in ['ALL','NO_ADD','ADDED']:
  rs=[r for r in new if r['seed_role']==role and r['phase']==phase and (added=='ALL' or bool(r['add_count'])==(added=='ADDED'))]
  for state in ['ALL','CLOSED','OPEN']:
   ss=[r for r in rs if state=='ALL' or bool(r['final_qty'])==(state=='OPEN')]
   rows.append(dict(role=role,phase=phase,add_class=added,state=state,rounds=len(ss),net=sm(ss,'segment_pnl'),fees=sm(ss,'segment_fees'),model_slippage=sm(ss,'model_slippage'),fill_price_plus_div_pnl=sm(ss,'fill_price_plus_div_pnl'),raw_price_plus_div_pnl=sm(ss,'raw_price_plus_div_pnl'),seed_notional_distribution=quant([r['seed_notional'] for r in ss]),seed_allin_nav_pct_distribution=quant([r['seed_account_pct'] for r in ss]),hold_intervals_distribution=quant([r['trading_intervals_held'] for r in ss]) if state=='CLOSED' else None))
# Fixed five original-winner flat intervals: prices only, never executable return attribution.
mp=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');manifest={r['symbol']:r for r in rd(mp)};hashes={str(mp):hashlib.sha256(mp.read_bytes()).hexdigest()}
starts={'000158.SZ':'2024-10-29','002261.SZ':'2024-10-29','300085.SZ':'2024-10-14','002049.SZ':'2024-11-19','002865.SZ':'2024-11-08'}
opps=[];endpoints=[]
for sid,start in starts.items():
 pp=Path(next(p for p in manifest[sid]['source_sha256'] if p.endswith('/signal.parquet')));h=hashlib.sha256(pp.read_bytes()).hexdigest();assert h==manifest[sid]['source_sha256'][str(pp)];hashes[str(pp)]=h;b=pd.read_parquet(pp).loc[start:E];assert not b.empty
 assert b.observed_bar.all() and b.price_eligible.all() and not b.source_invalid.any() and not b.synthetic_event_bar.any()
 assert len(b[['source_kind','source_path','segment_id']].drop_duplicates())==1
 assert b.adjustment_factor.max()==b.adjustment_factor.min(), (sid,'corporate action requires explicit bridge')
 ss=sorted([a for a in attempts if a['sid']==sid and a.get('exit_day') and a['exit_day']>=start],key=lambda a:a['exit_day'])
 for a in ss:
  ds=a['exit_day'];os=og[a['id']];sale=next(o for o in reversed(os) if o['side'].startswith('SELL'));rawopen=D(sale['price'])/D('.9995');nextbuy=next((o for o in orders if o['sid']==sid and o['side']=='BUY_SEED' and o['day']>ds),None)
  until=nextbuy['day'] if nextbuy else E;window=b.loc[ds:until];window=window.loc[window.index<pd.Timestamp(until)] if nextbuy else window
  if window.empty:continue
  endpoint=D(nextbuy['price'])/D('1.0005') if nextbuy else D(str(b.loc[E,'raw_close']));maxday=str(window.raw_close.idxmax().date());maxclose=D(str(window.raw_close.max()));minday=str(window.raw_close.idxmin().date());minclose=D(str(window.raw_close.min()))
  opps.append(dict(sid=sid,name=sale['name'],exited_round=a['id'],full_exit_day=ds,last_sell_qty=sale['qty'],raw_exit_open=rawopen,actual_last_sell_fill=sale['price'],next_seed_day=nextbuy['day'] if nextbuy else None,next_seed_qty=nextbuy['qty'] if nextbuy else None,comparison_end=until,endpoint_kind='next_actual_buy_open' if nextbuy else 'certified_end_close',endpoint_raw_price=endpoint,endpoint_price_change_pct=(endpoint/rawopen-1)*100,flat_interval_max_close_day=maxday,flat_interval_max_close=maxclose,flat_interval_max_close_change_pct=(maxclose/rawopen-1)*100,flat_interval_min_close_day=minday,flat_interval_min_close=minclose,flat_interval_min_close_change_pct=(minclose/rawopen-1)*100))
# Gap totals since exact 11/6, with order coverage check.
gaps=rd(O/'EXECUTED_SALE_GAPS.json');gs=[g for g in gaps if g['day']>A and not g['corporate_action_on_day']];actualsells=[o for o in orders if o['day']>A and o['side'].startswith('SELL')]
summary=dict(anchor=A,end=E,new_rounds=len(new),new_net=sm(new,'segment_pnl'),new_fees=sm(new,'segment_fees'),new_model_slippage=sm(new,'model_slippage'),new_fill_price_plus_div_pnl=sm(new,'fill_price_plus_div_pnl'),new_raw_price_plus_div_pnl=sm(new,'raw_price_plus_div_pnl'),phase_role_counts=dict(Counter(r['seed_role']+'_'+r['phase'] for r in new)),actual_sell_orders_since_anchor=len(actualsells),gap_covered_sale_orders=sum(g['day']>A for g in gaps),gap_excluded_action_day_orders=sum(g['day']>A and g['corporate_action_on_day'] for g in gaps),negative_raw_open_gap_sold_shares=-sum((min(Z,D(g['raw_open_gap_on_sold_shares'])) for g in gs),Z),positive_raw_open_gap_sold_shares=sum((max(Z,D(g['raw_open_gap_on_sold_shares'])) for g in gs),Z),worst_gap_sales=sorted(gs,key=lambda g:D(g['raw_open_gap_on_sold_shares']))[:15],notes=['All cohort group ALL/CLOSED/OPEN and add classifications overlap; do not add across overlapping tables.','Prices-only flat intervals show opportunity and avoided declines, no hypothetical funded portfolio. No aggregation into causal return.','All price bars and sources verified through certified 1/20, factor and lineage constant within each fixed-five diagnostic.','Net PnL already includes actual fees and modeled fills. Raw-price PnL adds back fixed modeled slippage; this is decomposition, not an executable no-cost alternative.'])
assert summary['actual_sell_orders_since_anchor']==summary['gap_covered_sale_orders']
for n,x in [('PHASE_ROLE_ADD_COSTS',rows),('FIXED_FIVE_FLAT_PRICE_PATHS',opps),('DETAIL_SUMMARY',summary),('PRICE_SOURCE_HASHES',hashes)]:save(n,x)
print(json.dumps({'summary':summary,'phase_rows':[r for r in rows if r['state']=='ALL'],'opportunities':opps},ensure_ascii=False,default=str))
