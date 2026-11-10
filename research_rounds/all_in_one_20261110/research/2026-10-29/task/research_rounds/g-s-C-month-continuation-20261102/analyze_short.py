"""Read saved short-window native states only; no account event is advanced."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
import sys, json, time, hashlib
import month_runtime as M
sys.path.insert(0, str(M.C.OLD))
from verify_saved import check_json

Z=D(0); HERE=M.HERE; OUT=HERE/'short_window_analysis'
START={'2022':'2022-01-07','2025_26':'2025-07-04'}
END={'2022':'2022-01-12','2025_26':'2025-07-09'}
MED={'600285.SH','600572.SH','600332.SH','600535.SH','600329.SH'}
def read(p):return M.read(p)
def save(name,x):M.E.IO.write_json(OUT/name,x,encoder=M.E.encode)
def sha(p):return M.P.sha(p)
def absdiff(a,b):assert abs(a-b)<D('0.000000000001'), (a,b)
def accounting(x):
 a=x['account']; b=a['balance']; layers={z['id']:z for z in a['layers']}; buying={}; sales=defaultdict(list)
 held=defaultdict(int); ever=set(); labels={}; sells=[]
 for tr in a['trades']:
  sid=tr['security_id']
  if tr['side']=='buy':
   lid=tr['layer'];assert lid not in buying
   labels[lid]='add' if held[sid] else 'reentry' if sid in ever else 'first'
   held[sid]+=tr['shares'];ever.add(sid);buying[lid]=tr
  else:
   held[sid]-=tr['shares'];assert held[sid]>=0
   for p in tr['parts']:sales[p['layer']].append(dict(**p,at=tr['at'],receipt=tr['receipt_id'],price=tr['price']))
 assert {s:q for s,q in held.items() if q}==b['quantities'], 'held split/writeoff needs explicit allocation; do not guess'
 records=[]
 for lid,z in layers.items():
  buy=buying[lid];qty=buy['shares'];cost=D(buy['gross_cny'])+D(buy['fees_cny']);parts=[];remaining=qty;allocated=Z
  for p in sales[lid]:
   assert p['shares']<=remaining
   basis=cost-allocated if p['shares']==remaining else cost*D(p['shares'])/qty
   allocated+=basis;remaining-=p['shares'];p=dict(p,buy_cost_allocated=basis,realized_trade_PNL=D(p['net_cash'])-basis);parts.append(p);sells.append(dict(p,sid=z['sid'],layer=lid))
  assert remaining==z['qty'], 'layer share allocation unsupported'
  realized=sum((p['realized_trade_PNL'] for p in parts),Z)
  unreal=D(z['qty'])*D(a['market_marks'].get(z['sid'],0))-(cost-allocated)
  meta=a['capital_meta'][str(lid)];div=D(z['dividend']);contrib=realized+unreal+div
  absdiff(contrib,D(z['cash'])+div+D(z['qty'])*D(a['market_marks'].get(z['sid'],0)))
  duties=[dict(id=eid,**duty) for eid,duty in a['exit_duties'].items() if duty['layer']==lid]
  first=min(duties,key=lambda duty:duty['requested_at']) if duties else None
  records.append(dict(layer=lid,sid=z['sid'],opened=z['opened'],signal_at=z['signal_at'],closed=z['closed'],role=meta['role'],pool=meta['pool'],purpose=meta['purpose'],sector=meta['sector'],source_context=meta['source_context'],entry_class=labels[lid],initial_qty=qty,remaining_qty=z['qty'],buy_gross=D(buy['gross_cny']),buy_fee=D(buy['fees_cny']),buy_cost=cost,fill_price=D(buy['gross_cny'])/qty,buy_receipt=buy['receipt_id'],actual_sell_parts=parts,realized_trade_PNL=realized,unrealized_net_buy_cost=unreal,booked_dividend_income=div,total_contribution=contrib,terminal_mark=a['market_marks'].get(z['sid']),actual_floor_signal_coordinate=z['floor'],current_factor=a['market_factors'].get(z['sid']),core_I_floor_signal_coordinate=a['facts_floors'].get(z['sid']),exit_duties=duties,first_exit_request=first,same_buy_day_exit_requested=bool(first and first['requested_at'][:10]==z['opened'][:10])))
 real=sum((z['realized_trade_PNL'] for z in records),Z);unreal=sum((z['unrealized_net_buy_cost'] for z in records),Z);income=sum((z['booked_dividend_income'] for z in records),Z)
 absdiff(D(b['nav'])-D(1000000),real+unreal+income)
 closed=[z for z in records if not z['remaining_qty']];opened=[z for z in records if z['remaining_qty']]
 return records,sells,dict(realized_actual_sales_net_buy_and_sell_fees=real,unrealized_mark_minus_remaining_net_buy_cost=unreal,booked_dividends=income,dividend_receivable=D(b['dividend_receivable']),cash_confirmed_dividends=income-D(b['dividend_receivable']),fractional_writeoff=Z,closed_layer_positive=sum((max(Z,z['total_contribution']) for z in closed),Z),closed_layer_negative=sum((min(Z,z['total_contribution']) for z in closed),Z),open_layer_contribution=sum((z['total_contribution'] for z in opened),Z),open_layer_realized_partials=sum((z['realized_trade_PNL'] for z in opened),Z),open_layer_dividends=sum((z['booked_dividend_income'] for z in opened),Z))
def grouped(records,keys):
 groups=defaultdict(list)
 for r in records:groups[tuple(r[k] for k in keys)].append(r)
 out=[]
 for key,rr in sorted(groups.items()):
  closed=[r for r in rr if not r['remaining_qty']];op=[r for r in rr if r['remaining_qty']]
  out.append(dict(**dict(zip(keys,key)),layers=len(rr),stocks=len({r['sid'] for r in rr}),buy_gross=sum((r['buy_gross'] for r in rr),Z),realized_trade_PNL=sum((r['realized_trade_PNL'] for r in rr),Z),unrealized=sum((r['unrealized_net_buy_cost'] for r in rr),Z),booked_dividends=sum((r['booked_dividend_income'] for r in rr),Z),closed_positive=sum((max(Z,r['total_contribution']) for r in closed),Z),closed_negative=sum((min(Z,r['total_contribution']) for r in closed),Z),open_contribution=sum((r['total_contribution'] for r in op),Z)))
 return out
def main():
 t=time.perf_counter();M.guard();OUT.mkdir(exist_ok=True);rows=[];eventchecks=[];restores=[];all_layers={};all_sells={};all_daily={};all_events={};causal={}
 for window in ('2022','2025_26'):
  inputs=M.MonthInputs(read(HERE/'POLICY_INPUT_IDENTITY.json')['inputs'][window]['path'])
  for mode in ('C10','C_BATCH20'):
   arm=window+'-'+mode;root=HERE/'runs'/arm;pp=read(root/'PROGRESS.json');assert pp['cursor'][:10]==END[window] and pp['phase']=='CLOSE'
   final=read(Path(pp['checkpoint']).with_suffix('.json'));a=final['account'];b=a['balance'];records,sells,pnl=accounting(final)
   all_layers[arm]=records;all_sells[arm]=sells;daily=[];events=[]
   for p in sorted(root.glob('20*-*.json')):
    phase=p.stem.split('-')[-1]
    if phase not in ('ACTION','OPEN','CLOSE'):continue
    day=p.name[:10];x=read(p);aa=x['account'];bb=aa['balance'];check=check_json(p)
    eventchecks.append(dict(arm=arm,file=str(p),sha256=sha(p),differences=check,newly_authorized=day>START[window]))
    flow=read(p.with_name(p.stem+'-FLOW.json'));ff=flow['fills'];bk=json.loads(flow['budget_after'])['body']['batch'];hf=flow['healthy_funding_sells'];buy=sum((D(f['gross_cny']) for f in ff if f['side']=='buy'),Z);sell=sum((D(f['gross_cny']) for f in ff if f['side']=='sell'),Z)
    events.append(dict(day=day,phase=phase,seconds=flow['seconds'],actual_buy_gross=buy,actual_sell_gross=sell,actual_fees=sum((D(f['fees_cny']) for f in ff),Z),buy_fill_count=sum(f['side']=='buy' for f in ff),sell_fill_count=sum(f['side']=='sell' for f in ff),healthy_funding_sell_gross=sum((D(f['gross_cny']) for f in hf),Z),other_sell_gross=sell-sum((D(f['gross_cny']) for f in hf),Z),before_available=flow['before_available'],after_available=flow['after_available'],sale_receivable=bb['sale_receivable'],order_reserved=bb['order_reserved'],planned_New=bk['new'],planned_Carry=bk['carry'],planned_limit=bk['limit'],plan_NAV=bk['NAV']))
    if phase=='CLOSE':
     industry=defaultdict(lambda:Z);role=defaultdict(lambda:Z);scope=defaultdict(lambda:Z)
     for z in aa['layers']:
      value=D(z['qty'])*D(aa['market_marks'].get(z['sid'],0));meta=aa['capital_meta'][str(z['id'])];industry[meta['sector']]+=value;role[meta['role']+'|'+meta['pool']]+=value;scope[meta['purpose']]+=value
     proj=x['results'][-1]['projection']; rr=[tr for tr in aa['trades'] if tr['at'][:10]==day];book=json.loads(x['budget'])['body']['batch']
     daily.append(dict(day=day,NAV=bb['nav'],exposure=D(bb['inventory'])/D(bb['nav']),cash_available=bb['available'],fees_cumulative=bb['fees_cny'],buy_gross=sum((D(tr['gross_cny']) for tr in rr if tr['side']=='buy'),Z),sell_gross=sum((D(tr['gross_cny']) for tr in rr if tr['side']=='sell'),Z),industry=[dict(sector=s,value=v,weight=v/D(bb['nav'])) for s,v in sorted(industry.items(),key=lambda q:-q[1]) if v],role_pool=dict(role),support_use=dict(scope),Q={s:q for s,q in proj['Q'].items() if q},D=proj['D'],planned_New=book['new'],planned_Carry=book['carry'],planned_limit=book['limit'],new_pending_intents=len(x['pending']),active_native_buy=len(aa['buys']),active_native_exit=len(aa['exits']),ACT=aa['policy']['act'],active_K=aa['policy']['k'],new_rejections=Counter(json.dumps(z.get('route',z).get('why',z.get('reason','UNKNOWN')),sort_keys=True) for z in aa['rejections'] if str(z.get('at',''))[:10]==day)))
   events.sort(key=lambda e:(e['day'],{'ACTION':0,'OPEN':1,'CLOSE':2}[e['phase']]))
   all_daily[arm]=daily;all_events[arm]=events
   old=read(root/(START[window]+'-CLOSE.json'));_,_,oldp=accounting(old)
   fills=a['fills']; buys=[f for f in fills if f['side']=='buy']; sales=[f for f in fills if f['side']=='sell'];fees=sum((D(f['fees_cny']) for f in fills),Z)
   turnover=sum((D(f['gross_cny']) for f in fills),Z);newrecords=[r for r in records if r['opened'][:10]>START[window]]
   startp=read(root/'STARTED.json');stopp=read(root/'STOPPED_AT_CUTOFF.json')
   rows.append(dict(arm=arm,cursor=pp['cursor'],checkpoint=pp['checkpoint'],checkpoint_sha256=pp['sha256'],NAV=D(b['nav']),cumulative_return=D(b['nav'])/D(1000000)-1,exposure=D(b['inventory'])/D(b['nav']),available=D(b['available']),inventory=D(b['inventory']),pnl=pnl,new_authorized_period_PNL_change={k:pnl[k]-oldp[k] for k in ('realized_actual_sales_net_buy_and_sell_fees','unrealized_mark_minus_remaining_net_buy_cost','booked_dividends')},cumulative_buy_gross=sum((D(f['gross_cny']) for f in buys),Z),cumulative_sell_gross=sum((D(f['gross_cny']) for f in sales),Z),two_sided_gross_turnover=turnover,turnover_vs_initial_NAV=turnover/D(1000000),fees=fees,buy_fill_receipts=len(buys),sell_fill_receipts=len(sales),actual_funded_stocks=len({f['security_id'] for f in buys}),all_layers=len(records),new_authorized_layers=len(newrecords),same_buy_day_exit_requested_layers=sum(r['same_buy_day_exit_requested'] for r in records),new_authorized_layer_groups=grouped(newrecords,['role','pool','entry_class']),full_history_groups=grouped(records,['role','pool','entry_class']),largest_industry=daily[-1]['industry'][0],terminal_Q=daily[-1]['Q'],terminal_D=daily[-1]['D'],active_native_buys=len(a['buys']),active_native_exits=len(a['exits']),pending_intents=len(final['pending']),actual_start=startp['actual_at'],actual_completed=stopp['actual_at'],runner_seconds=stopp['seconds'],new_event_seconds=sum(e['seconds'] for e in events if e['day']>START[window]),ACT=a['policy']['act']))
   selected=[r for r in records if (window=='2022' and r['sid'] in MED) or (window=='2025_26' and r['sid']=='601916.SH')]
   ranked=sorted(records,key=lambda r:r['total_contribution'])
   causal[arm]=dict(medicine_or_601916=selected,deterministic_worst3=ranked[:3],deterministic_best3=list(reversed(ranked[-3:])),sale_reasons=grouped_sell_reasons(sells),new_authorized_buy_cost=sum((r['buy_cost'] for r in newrecords),Z))
   r=M.MonthRunner.restore(pp['checkpoint']);expected=json.loads(json.dumps(r.observable(r.last_completed_event),default=M.E.encode));assert expected==final
   restores.append(dict(arm=arm,checkpoint=pp['checkpoint'],sha256=sha(pp['checkpoint']),full_observable_exact=True,identity_verified=True,grant=r.execution_grant_record,grant_history=r.execution_grant_history,financial_events_executed=0))
   print('ANALYZED',arm,'NAV',b['nav'],'realized',pnl['realized_actual_sales_net_buy_and_sell_fees'],'unrealized',pnl['unrealized_mark_minus_remaining_net_buy_cost'],flush=True)
 differences={}
 for window in ('2022','2025_26'):
  agg={}
  for mode in ('C10','C_BATCH20'):
   qq=defaultdict(lambda:dict(contribution=Z,realized=Z,unrealized=Z,buy_gross=Z,qty=0))
   for z in all_layers[window+'-'+mode]:
    q=qq[z['sid']]
    for to,fr in [('contribution','total_contribution'),('realized','realized_trade_PNL'),('unrealized','unrealized_net_buy_cost'),('buy_gross','buy_gross')]:q[to]+=z[fr]
    q['qty']+=z['remaining_qty']
   agg[mode]=qq
  differences[window]=sorted([dict(sid=s,C10=agg['C10'].get(s,{}),C20=agg['C_BATCH20'].get(s,{}),C20_minus_C10=agg['C_BATCH20'].get(s,{}).get('contribution',Z)-agg['C10'].get(s,{}).get('contribution',Z)) for s in set(agg['C10'])|set(agg['C_BATCH20'])],key=lambda z:(z['C20_minus_C10'],z['sid']))
  assert sum((z['C20_minus_C10'] for z in differences[window]),Z)==next(z['NAV'] for z in rows if z['arm']==window+'-C_BATCH20')-next(z['NAV'] for z in rows if z['arm']==window+'-C10')
 save('ALL_STOCK_ACCOUNTING_DIFFERENCES.json',dict(rows=differences,scope='all-stock accounting decomposition only; not holding-removal or individual-trade causal counterfactual'))
 save('RESULTS.json',dict(rows=rows,financial_events_executed_by_analysis=0,scope='same four continuous accounts; no Jan13 or later / no Jul10 or later',all_samples_retained=True,accounting='actual sale net less allocated original gross+buy fee; residual mark less remaining gross+buy fee; dividends separate; open-layer contribution is not unrealized'))
 save('DAILY.json',all_daily);save('EVENTS.json',all_events);save('ALL_LAYERS.json',all_layers);save('ALL_SALE_PARTS.json',all_sells);save('CAUSAL_CHAINS.json',causal)
 save('VERIFICATION.json',dict(passed=True,event_states=len(eventchecks),checks_per_event=7,independent_stock_share_bridge=True,PNL_reconciles_NAV_minus_initial=True,all_terminal_restores=restores,event_checks=eventchecks,analysis_seconds=time.perf_counter()-t,financial_events_executed=0))
def grouped_sell_reasons(sells):
 out=[]
 for reason in sorted({s['reason'] for s in sells}):
  rr=[s for s in sells if s['reason']==reason];out.append(dict(reason=reason,parts=len(rr),net_proceeds=sum((D(s['net_cash']) for s in rr),Z),realized_actual_sales_PNL=sum((s['realized_trade_PNL'] for s in rr),Z)))
 return out
if __name__=='__main__':main()
