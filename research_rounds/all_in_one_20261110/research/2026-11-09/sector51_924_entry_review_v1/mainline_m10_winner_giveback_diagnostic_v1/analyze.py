import json,csv,hashlib
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
P=Path(__file__).parent;R=P.parent;run=R/'mainline_candidate_v10_positive_cp_initial_protection_run_v1';status=json.loads((run/'RUN_STATUS.json').read_text());assert status['completed_horizon'] and status['days']==41 and not status['blockers']
old=R/'mainline_winner_giveback_diagnostic_v1/analyze.py';ns={'__file__':str(P/'analyze.py')};exec(compile(old.read_text().split('paths={')[0],str(old),'exec'),ns);read,fee,bars=ns['read'],ns['fee'],ns['bars'];pd=ns['pd'];hashes=ns['hashes']
for fn in [old,R/'M10_PREDECLARED_EVALUATION.md',R/'mainline_candidate_v10_positive_cp_initial_protection/CONTRACT.md',R/'mainline_candidate_v10_positive_cp_initial_protection/engine.py',run/'RUN_STATUS.json'] : hashes[str(fn)]=hashlib.sha256(fn.read_bytes()).hexdigest()
audit=read(run/'INDEPENDENT_M10_VS_M7.json');base=read(R/'mainline_winner_giveback_diagnostic_v1/DIAGNOSTIC.json');fixed=[x['round_id'] for x in base['M7_1031']['top20']];key=lambda rid:rid.split('|')[0]+'|'+rid.split('|')[-1];fixedkeys={key(r) for r in fixed};casekeys={key(x['round_id']) for x in base['M7_1106']['cases']}|{'300085.SZ|2024-09-23'};data={};snapshots={};daily={}
for label,path in [('M7',R/'mainline_m7_long_horizon_sealed_v2/once_20260630'),('M10',run/'once_20241106')]:
 z={n:read(path/(n+'.json')) for n in ['ORDERS','CAPITAL_LOTS','HOLDINGS','ATTEMPTS','DAY_LEDGER','EQUITY_EVENTS','CANDIDATES','SECTOR_DAILY']};data[label]=z;groups=defaultdict(list);hs=defaultdict(list);og=defaultdict(list);eg=defaultdict(list)
 for c in z['CAPITAL_LOTS']:groups[c['round_id'],c['day']].append(c)
 for h in z['HOLDINGS']:hs[h['round_id'],h['day']].append(h)
 for o in z['ORDERS']:og[o['round_id']].append(o)
 for e in z['EQUITY_EVENTS']:
  if e.get('round_id') and e['event']=='ACCRUE_NET80':eg[e['round_id']].append(e)
 dr=defaultdict(list)
 for (rid,dt),ls in sorted(groups.items()):
  c=ls[0];s=c['sid'];q=sum(x['qty'] for x in ls);price=D(c['raw_mark'])*D('.9995');cash=sum((D(o['cash_delta']) for o in og[rid] if o['day']<=dt),D(0));div=sum((D(e['receivable_delta']) for e in eg[rid] if e['day']<=dt),D(0));net=cash+div+q*price-fee(s,dt,q,price);assert net==D(c['round_net'])
  floorpro=D(0);floors=[]
  for h in hs[rid,dt]:
   sig=h['effective_protection_signal'] if label=='M10' else h['protection_signal'];fl=D(sig)/D(h['factor']);px=fl*D('.9995');fp=h['qty']*px-fee(s,dt,h['qty'],px);floorpro+=fp;floors.append(dict(lot_id=h['lot_id'],qty=h['qty'],signal=sig,raw=fl,fee=fee(s,dt,h['qty'],px),net_proceeds=fp))
  dr[rid].append(dict(day=dt,net=net,qty=q,raw_close=c['raw_mark'],cashflow=cash,dividend=div,actual_layer_floor_net=cash+div+floorpro,actual_layer_floors=floors))
 daily[label]=dr
 for end in ['2024-10-31','2024-11-06']:
  rr=[]
  for rid,allrows in dr.items():
   ds=[d for d in allrows if d['day']<=end]
   if not ds:continue
   peak=max(ds,key=lambda x:x['net']);last=ds[-1];endhold=[d for d in ds if d['day']==end];finalqty=endhold[0]['qty'] if endhold else 0;cash=sum((D(o['cash_delta']) for o in og[rid] if o['day']<=end),D(0));div=sum((D(e['receivable_delta']) for e in eg[rid] if e['day']<=end),D(0));fn=endhold[0]['net'] if endhold else cash+div;ao=og[rid];sells=[o for o in ao if o['day']<=end and o['side'].startswith('SELL')];terminal=sells[-1] if sells and not finalqty else None
   rr.append(dict(run=label,end=end,round_id=rid,key=key(rid),sid=ao[0]['sid'],name=ao[0]['name'],peak_day=peak['day'],peak_net=peak['net'],peak_qty=peak['qty'],peak_actual_layer_floor_net=peak['actual_layer_floor_net'],final_net=fn,final_qty=finalqty,exit_day=terminal['day'] if terminal else None,exit_reason=terminal['reason'] if terminal else None,giveback=peak['net']-fn,giveback_pct=100*(peak['net']-fn)/peak['net'] if peak['net']>0 else None,last_floor_net=last['actual_layer_floor_net']))
  snapshots[label,end]=sorted(rr,key=lambda x:-x['peak_net'])
comparisons=[]
for end in ['2024-10-31','2024-11-06']:
 mm={label:{x['key']:x for x in snapshots[label,end]} for label in ['M7','M10']}
 for k in sorted(fixedkeys|casekeys):
  a,b=mm['M7'].get(k),mm['M10'].get(k);comparisons.append(dict(end=end,key=k,fixed_M7_top20=k in fixedkeys,preselected_case=k in casekeys,M7=a,M10=b,final_delta=(b['final_net'] if b else D(0))-(a['final_net'] if a else D(0))))
z=data['M10'];ad=[c for c in z['CANDIDATES'] if c.get('event')=='M10_INITIAL_CP_ADMISSION'];adopts=[c for c in ad if c['decision']=='ADOPT'];locks=[c for c in z['CANDIDATES'] if c.get('event')=='M10_INITIAL_BREACH'];neworders=[o for o in z['ORDERS'] if 'POSITIVE_CP_INITIAL_PROTECTION' in o.get('lot_reasons',{}).values()];opps=[]
for o in neworders:
 ids=[lid for lid,reason in o['lot_reasons'].items() if reason=='POSITIVE_CP_INITIAL_PROTECTION'];q=sum(o['lot_quantities'][lid] for lid in ids);s=o['sid'];rid=o['round_id'];bb=bars(s);ix=bb.index.get_loc(pd.Timestamp(o['day']));future=bb.iloc[ix+1:ix+6];future=future[future.index<=pd.Timestamp('2024-11-06')];assert len(future)>0;dt=str(future.index[-1].date());endraw=D(str(future.iloc[-1].raw_close));rawopen=D(str(bb.loc[o['day']].raw_open));allocfee=D(o['fee'])*D(q)/D(o['qty']);netsale=q*D(o['price'])-allocfee;endfee=fee(s,dt,q,endraw*D('.9995'));endnet=q*endraw*D('.9995')-endfee;preceding=[r for r in daily['M10'][rid] if r['day']<o['day']];pk=max(preceding,key=lambda r:r['net']);prev=preceding[-1]
 po=[p for p in z['ORDERS'] if p['round_id']==rid and p['order_seq']<o['order_seq']];cf=sum((D(p['cash_delta']) for p in po),D(0));allq=sum(p['qty'] if p['side'].startswith('BUY') else -p['qty'] for p in po);div=sum((D(e['receivable_delta']) for e in z['EQUITY_EVENTS'] if e.get('round_id')==rid and e['event']=='ACCRUE_NET80' and e['day']<=o['day']),D(0));opennet=cf+div+allq*D(o['price'])-fee(s,o['day'],allq,D(o['price']))
 evidence=[o['initial_protection_evidence'][lid] for lid in ids];floorraws=[D(ev['protection']['floor'])/D(str(bb.loc[o['day']].adjustment_factor)) for ev in evidence];lastad=[next(c for c in reversed(adopts) if c['lot_id']==lid and c['day']<o['day']) for lid in ids];cost=sum((D(next(b for b in z['ORDERS'] if b.get('lot_id')==lid and b['side'].startswith('BUY'))['all_in_cost'])*D(o['lot_quantities'][lid])/D(next(b for b in z['ORDERS'] if b.get('lot_id')==lid and b['side'].startswith('BUY'))['qty']) for lid in ids),D(0));window=bb.loc[o['day']:dt]
 opps.append(dict(order_seq=o['order_seq'],sid=s,name=o['name'],round_id=rid,day=o['day'],order_reason=o['reason'],total_order_qty=o['qty'],new_initial_qty=q,new_lot_ids=ids,raw_open=rawopen,fill_price=o['price'],actual_order_fee=o['fee'],allocated_new_lot_fee=allocfee,incremental_new_qty_fee=D(o['fee'])-fee(s,o['day'],o['qty']-q,D(o['price'])),new_lot_net_sale=netsale,new_lot_realized_ex_dividend=netsale-cost,peak_before_exit=pk['net'],peak_day=pk['day'],prev_close_net=prev['net'],actual_floor_net_before=prev['actual_layer_floor_net'],whole_round_at_execution_open_net=opennet,whole_round_final_net=next(r['final_net'] for r in snapshots['M10','2024-11-06'] if r['round_id']==rid),protected_raw_floor_min=min(floorraws),protected_raw_floor_max=max(floorraws),open_vs_stored_floor_pct=(rawopen/min(floorraws)-1)*100,last_adoption_gate_cp_net=[c['net_at_CP'] for c in lastad],last_adoption_actual_floor_net=[c['layered_pressure_after']['net'] for c in lastad],last_adoption_evidence=lastad,lock_evidence=evidence,endpoint=dt,sessions_after_sale=len(future),endpoint_raw_close=endraw,endpoint_hypothetical_fee=endfee,actual_sale_minus_endpoint_mark=netsale-q*endraw,sale_minus_fixed_hold_net=netsale-endnet,constant_factor=len(set(map(str,window.adjustment_factor)))==1,constant_origin=len(set(tuple(str(row[k]) for k in ['source_kind','source_path','segment_id']) for _,row in window.iterrows()))==1,valid_quotes=all(bool(row.observed_bar and row.price_eligible and not row.source_invalid and not row.synthetic_event_bar) for _,row in window.iterrows())))
# Independent marked-PnL decomposition and economic order diffs; no causal allocation assumption.
attribution={};trace=[]
for end in ['2024-10-31','2024-11-06']:
 by={}
 for label,z in data.items():
  v=defaultdict(lambda:D(0))
  for o in z['ORDERS']:
   if o['day']<=end:v[o['sid']]+=D(o['cash_delta'])
  for h in z['HOLDINGS']:
   if h['day']==end:v[h['sid']]+=D(h['market_value'])
  for e in z['EQUITY_EVENTS']:
   if e['day']<=end and e['event']=='ACCRUE_NET80':v[e['sid']]+=D(e['receivable_delta'])
  by[label]=v
 rows=[dict(sid=s,M7=by['M7'][s],M10=by['M10'][s],delta=by['M10'][s]-by['M7'][s]) for s in set(by['M7'])|set(by['M10'])];rows.sort(key=lambda r:-abs(r['delta']));attribution[end]=rows
led={k:{x['day']:x for x in z['DAY_LEDGER']} for k,z in data.items()}
for dt in sorted(set(led['M7'])&set(led['M10'])):
 row=dict(day=dt)
 for f in ['cash','market_value','NAV','receivable']:row[f+'_delta']=D(led['M10'][dt][f])-D(led['M7'][dt][f])
 trace.append(row)
for end,rows in attribution.items():assert sum((r['delta'] for r in rows),D(0))==next(r['NAV_delta'] for r in trace if r['day']==end)
fields=['day','sid','side','qty','price','reason'];cs={k:Counter(tuple(o[f] for f in fields) for o in z['ORDERS']) for k,z in data.items()};diffs={k:[dict(zip(fields,t),multiplicity=n) for t,n in (cs[k]-cs['M10' if k=='M7' else 'M7']).items()] for k in cs}
adopted={c['lot_id'] for c in adopts};soldnew={lid for o in opps for lid in o['new_lot_ids']};locked={c['lot_id'] for c in locks};stats=dict(admission_decisions=dict(Counter(c['decision'] for c in ad)),adoptions=len(adopts),first_adoptions=sum(not c['old_protection'] for c in adopts),raises=sum(bool(c['old_protection']) for c in adopts),adopted_lots=len(adopted),breach_events=len(locks),breached_lots=len(locked),unbreached_adopted_lots=len(adopted-locked),new_exit_orders=len(opps),new_exit_lots=len(soldnew),new_exit_shares=sum(o['new_initial_qty'] for o in opps),positive_layer_after=sum(D(c['layered_pressure_after']['net'])>0 for c in adopts),positive_new_initial_realized=sum(o['new_lot_realized_ex_dividend']>0 for o in opps),negative_whole_round_at_open=sum(o['whole_round_at_execution_open_net']<0 for o in opps),opportunity_exit_better=sum(o['sale_minus_fixed_hold_net']>0 for o in opps),opportunity_hold_better=sum(o['sale_minus_fixed_hold_net']<0 for o in opps))
result=dict(scope='Predeclared fixed M7 1031 top20 and prior cases; development validation only; completed outputs, no strategy rerun',reconciliation='All round-day net exact; stock marked PnL delta reconciles NAV delta',stats=stats,fixed_M7_top20_rounds=fixed,comparisons=comparisons,new_initial_exits=opps,stock_marked_pnl_attribution=attribution,daily_cash_inventory_trace=trace,order_differences=diffs,all_M10_rounds_1106=snapshots['M10','2024-11-06'],source_hashes=hashes,caveats=['Actual layer pressure uses effective_protection_signal for M10 and separate sell fee per lot, never legacy SEED protection_signal.','Gate net_at_CP prices all shares at one candidate CP, but only INITIAL protection changes; neither gate nor floor pressure guarantees fills or profit.','New exits identified by lot_reasons, not aggregate reason; actual fee allocated pro-rata to new quantity, and separately incremental fee shown.','Opportunity endpoints limited to next5 source trading days <=11/6, same fixed sold INITIAL quantity, no capital redeployment, not causal portfolio gain.','Rows with corporate-action factor/source changes or invalid quotes require qualification; no extrapolated later outcome.'])
(P/'M10_DIAGNOSTIC.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
for name,rows in [('NEW_INITIAL_EXIT_OPPORTUNITIES',[{k:v for k,v in o.items() if k not in ['last_adoption_evidence','lock_evidence']} for o in opps]),('CASH_INVENTORY_TRACE',trace),('M10_ROUND_RANKING',snapshots['M10','2024-11-06'])]:
 with (P/(name+'.csv')).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(dict(stats=stats,exits=[{k:o[k] for k in ['sid','name','day','new_initial_qty','peak_before_exit','whole_round_at_execution_open_net','whole_round_final_net','protected_raw_floor_min','open_vs_stored_floor_pct','endpoint','sale_minus_fixed_hold_net','new_lot_realized_ex_dividend']} for o in opps],cases=[c for c in comparisons if c['end']=='2024-11-06' and c['key'] in ['300085.SZ|2024-09-23','000158.SZ|2024-09-23','002261.SZ|2024-09-23','002049.SZ|2024-09-26','002865.SZ|2024-10-23']],attribution={k:v[:15] for k,v in attribution.items()}),ensure_ascii=False,default=str))
