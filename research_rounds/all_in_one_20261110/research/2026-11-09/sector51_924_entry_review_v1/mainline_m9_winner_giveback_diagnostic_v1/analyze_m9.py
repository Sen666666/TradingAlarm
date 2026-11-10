import json,hashlib,csv,sys
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
P=Path(__file__).parent;R=P.parent
# Reuse exact read-only fee and verified-bar helpers; execute only definitions before the old paths/run loop.
old=R/'mainline_winner_giveback_diagnostic_v1/analyze.py';ns={'__file__':str(P/'analyze_m9.py')};exec(compile(old.read_text().split('paths={')[0],str(old),'exec'),ns)
read,fee,bars=ns['read'],ns['fee'],ns['bars'];pd=ns['pd'];hashes=ns['hashes'];hashes[str(old)]=hashlib.sha256(old.read_bytes()).hexdigest()
oldresult=read(R/'mainline_winner_giveback_diagnostic_v1/DIAGNOSTIC.json');audit=read(R/'mainline_candidate_v9_persistent_stock_failure_run_v1/INDEPENDENT_M9_VS_M7.json')
paths={'M7':R/'mainline_m7_long_horizon_sealed_v2/once_20260630','M9':R/'mainline_candidate_v9_persistent_stock_failure_run_v1/once_20241106'}
data={};ranks={};daily={};end='2024-11-06'
for run,p in paths.items():
 z={n:read(p/(n+'.json')) for n in ['ORDERS','CAPITAL_LOTS','HOLDINGS','ATTEMPTS','DAY_LEDGER','EQUITY_EVENTS']};data[run]=z;ds=defaultdict(dict);og=defaultdict(list);eg=defaultdict(list)
 for o in z['ORDERS']:og[o['round_id']].append(o)
 for e in z['EQUITY_EVENTS']:
  if e.get('round_id') and e['event']=='ACCRUE_NET80':eg[e['round_id']].append(e)
 for c in z['CAPITAL_LOTS']:
  if c['day']<=end:ds[c['round_id']].setdefault(c['day'],[]).append(c)
 rr=[];dr={}
 for rid,byday in ds.items():
  dr[rid]=[]
  for day,ls in sorted(byday.items()):
   c=ls[0];q=sum(x['qty'] for x in ls);raw=D(c['raw_mark']);cash=sum((D(o['cash_delta']) for o in og[rid] if o['day']<=day),D(0));div=sum((D(e['receivable_delta']) for e in eg[rid] if e['day']<=day),D(0));net=cash+div+q*raw*D('.9995')-fee(c['sid'],day,q,raw*D('.9995'));assert net==D(c['round_net'])
   dr[rid].append(dict(day=day,net=net,qty=q,raw_close=raw,cashflow=cash,dividend=div))
  a=next(a for a in z['ATTEMPTS'] if a['id']==rid);peak=max(dr[rid],key=lambda x:x['net']);last=dr[rid][-1];fn=D(a['marked_net_pnl']) if a['final_qty']==0 else last['net'];row=dict(run=run,round_id=rid,sid=a['sid'],name=og[rid][0]['name'],peak_day=peak['day'],peak_net=peak['net'],peak_qty=peak['qty'],final_net=fn,final_qty=a['final_qty'],exit_day=a.get('exit_day'),giveback=peak['net']-fn,giveback_pct=100*(peak['net']-fn)/peak['net'] if peak['net']>0 else None);rr.append(row)
 ranks[run]=sorted(rr,key=lambda x:x['peak_net'],reverse=True);daily[run]=dr
# Matched round comparison. sid + signal date remains robust to altered round sequence counters.
key=lambda r:r['sid']+'|'+r['round_id'].split('|')[-1]
maps={k:{key(x):x for x in rr} for k,rr in ranks.items()};comparison=[]
for k in sorted(set(maps['M7'])|set(maps['M9'])):
 a,b=maps['M7'].get(k),maps['M9'].get(k);comparison.append(dict(key=k,M7=a,M9=b,final_delta=(b['final_net'] if b else D(0))-(a['final_net'] if a else D(0))))
retire=[o for o in data['M9']['ORDERS'] if o['reason']=='PERSISTENT_STOCK_NONPROFIT_EXPANSION_RETIREMENT'];opps=[]
for o in retire:
 s=o['sid'];rid=o['round_id'];bb=bars(s);ix=bb.index.get_loc(pd.Timestamp(o['day']));future=bb.iloc[ix+1:ix+6];future=future[future.index<=pd.Timestamp(end)];assert len(future)>0
 er=future.iloc[-1];ed=str(future.index[-1].date());q=o['qty'];rawopen=D(str(bb.loc[o['day']].raw_open));px=D(str(er.raw_close));window=bb.loc[o['day']:ed]
 valid=all(bool(row.observed_bar and row.price_eligible and not row.source_invalid and not row.synthetic_event_bar) for _,row in window.iterrows());facconstant=len(set(str(v) for v in window.adjustment_factor))==1;originconstant=len(set(tuple(str(row[x]) for x in ['source_kind','source_path','segment_id']) for _,row in window.iterrows()))==1
 holdnet=q*px*D('.9995')-fee(s,ed,q,px*D('.9995'));sale=D(o['cash_delta']);ds=[x for x in daily['M9'][rid] if x['day']<o['day']];peak=max(ds,key=lambda x:x['net']);prior=ds[-1]
 priororders=[x for x in data['M9']['ORDERS'] if x['round_id']==rid and x['order_seq']<o['order_seq']];cash=sum((D(x['cash_delta']) for x in priororders),D(0));remaining=sum(x['qty'] if x['side'].startswith('BUY') else -x['qty'] for x in priororders);div=sum((D(e['receivable_delta']) for e in data['M9']['EQUITY_EVENTS'] if e.get('round_id')==rid and e['event']=='ACCRUE_NET80' and e['day']<=o['day']),D(0));opennet=cash+div+remaining*rawopen*D('.9995')-fee(s,o['day'],remaining,rawopen*D('.9995'))
 buycost=D(0)
 for lid,qty in o['lot_quantities'].items():
  buy=next(x for x in data['M9']['ORDERS'] if x.get('lot_id')==lid and x['side'].startswith('BUY'));buycost+=D(buy['all_in_cost'])*D(qty)/D(buy['qty'])
 opps.append(dict(sid=s,name=o['name'],round_id=rid,retirement_day=o['day'],qty=q,raw_sale_open=rawopen,actual_sale_price=o['price'],actual_sale_fee=o['fee'],actual_sale_net=sale,retired_share_allocated_buy_cost=buycost,retired_share_realized_ex_dividend=sale-buycost,pre_retirement_peak_day=peak['day'],pre_retirement_peak_net=peak['net'],signal_close_net=prior['net'],whole_round_pre_execution_open_net=opennet,whole_round_end_net=next(x['final_net'] for x in ranks['M9'] if x['round_id']==rid),endpoint_day=ed,sessions_after_sale=len(future),full_five_sessions=len(future)==5,endpoint_raw_close=px,raw_fixed_share_price_difference=q*(rawopen-px),actual_sale_minus_endpoint_mark=sale-q*px,endpoint_hypothetical_sale_fee=fee(s,ed,q,px*D('.9995')),endpoint_hypothetical_net=holdnet,sale_minus_fixed_hold_net=sale-holdnet,valid_quotes=valid,constant_factor=facconstant,constant_origin=originconstant,interpretation='positive=exit beats fixed-share holding to endpoint; noncausal opportunity diagnostic'))
# Exact cash and inventory divergence trace, with no counterfactual attribution.
fields=['day','sid','side','qty','price','reason'];cs={k:Counter(tuple(o[f] for f in fields) for o in z['ORDERS']) for k,z in data.items()};differences={k:[dict(zip(fields,t),multiplicity=n) for t,n in (cs[k]-cs['M9' if k=='M7' else 'M7']).items()] for k in cs}
led={k:{x['day']:x for x in z['DAY_LEDGER']} for k,z in data.items()};trace=[]
for day in sorted(set(led['M7'])&set(led['M9'])):
 if day>end:continue
 row=dict(day=day)
 for f in ['cash','market_value','NAV','receivable']:row[f+'_delta']=D(led['M9'][day][f])-D(led['M7'][day][f])
 trace.append(row)
# Stock marked PnL reconciliation at requested endpoints: exact accounting decomposition, not isolated-exit causality.
attrib={}
for dt in ['2024-10-31','2024-11-06']:
 stock={}
 for run,z in data.items():
  v=defaultdict(lambda:D(0))
  for o in z['ORDERS']:
   if o['day']<=dt:v[o['sid']]+=D(o['cash_delta'])
  for h in z['HOLDINGS']:
   if h['day']==dt:v[h['sid']]+=D(h['market_value'])
  for e in z['EQUITY_EVENTS']:
   if e['day']<=dt and e['event']=='ACCRUE_NET80':v[e['sid']]+=D(e['receivable_delta'])
  stock[run]=v
 rows=[dict(sid=s,M7=stock['M7'][s],M9=stock['M9'][s],delta=stock['M9'][s]-stock['M7'][s]) for s in set(stock['M7'])|set(stock['M9'])];rows.sort(key=lambda x:-abs(x['delta']));assert sum((x['delta'] for x in rows),D(0))==D(audit[dt]['M9']['NAV'])-D(audit[dt]['M7']['NAV']);attrib[dt]=rows
res=dict(round_reconciliation='EXACT ZERO ERROR',rankings=ranks,matched_rounds=comparison,retirement_opportunities=opps,order_differences=differences,daily_cash_inventory_trace=trace,stock_marked_pnl_attribution=attrib,source_hashes=hashes,caveats=['机会差限定随后5个源交易日收盘，若不足则截到策略认证11/6；不引用11/6之后表现。所有11窗口行情有效且factor/origin是否恒定逐行给出。','未建反事实融资账户，不含替代投资、再入、利息；固定卖出股数并非实际会继续持有的股数。','同sid同signal_day匹配轮次，不用会随退出改变的轮次序号。MFE仅实际有库存收盘净清算峰值。','个股标记PnL差严格加总为账户NAV差，但这只是会计分解，不是退出规则的独立因果贡献。','实际卖出价格及费用保留；比较端也计算继承费用和5bp卖出滑点，不把原始收盘差冒充净收益。'])
(P/'M9_DIAGNOSTIC.json').write_text(json.dumps(res,ensure_ascii=False,indent=2,default=str))
for name,rows in [('RETIREMENT_OPPORTUNITIES',opps),('CASH_INVENTORY_TRACE',trace),('M9_ROUND_RANKING',ranks['M9'])]:
 with (P/(name+'.csv')).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(dict(opps=opps,winner_comparison=[x for x in comparison if x['key'] in ['000158.SZ|2024-09-23','002261.SZ|2024-09-23','300085.SZ|2024-09-23','002049.SZ|2024-09-26','002865.SZ|2024-10-23']],attribution={k:v[:12] for k,v in attrib.items()},trace=[x for x in trace if x['day']<='2024-09-27']),ensure_ascii=False,default=str))
