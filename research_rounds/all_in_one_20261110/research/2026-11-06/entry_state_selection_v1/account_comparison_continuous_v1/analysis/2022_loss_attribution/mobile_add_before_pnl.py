"""Read-only event-time MOBILE adding-to-held-stock diagnosis. No daily close inputs."""
from pathlib import Path
import sys,json,pickle,hashlib
from decimal import Decimal as D
from collections import Counter
import pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parents[1];sys.path.insert(0,str(ROOT/'inputs'));import continuous_inputs as C
P=ROOT/'run_1200000/latest_checkpoint/checkpoint-2022-12-30.pkl';Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def status(p):return 'UNKNOWN'if p is None else 'LOSS'if p<0 else 'PROFIT'if p>0 else 'FLAT'
def save(n,v):(O/n).write_text(json.dumps(v,indent=2,default=str,allow_nan=False))
def main():
 b=P.read_bytes();m=json.loads(P.with_suffix('.json').read_text());h=hashlib.sha256(b).hexdigest();assert h==m['sha256']==json.loads(P.with_suffix('.provenance.json').read_text())['checkpoint_sha256'];x=pickle.loads(b);del b
 assert str(x['last_completed_event'])[:10]=='2022-12-30'
 _,market,_=C.J.M.context('2022-12-30',ids=C.read(C.U/'FREEZE.json')['stocks'])
 allrows=[];summaries={};examples=[]
 for a,v in x['accounts'].items():
  assert v['initial_cash']==D(1200000)
  # All actual sell receipts must have same-event cash settlement. Otherwise do not substitute fill for received proceeds.
  settled={r['settlement'].settlement_id:r for r in v['audit_log']if r['kind']=='settle'}
  for t in v['trades']:
   if t['side']=='sell':
    sr=settled[t['settlement_id']];assert sr['at']==t['at'];assert sr['settlement'].cny_amount==t['gross_cny']-t['fees_cny'];assert not sr['settlement'].debit
  assert not v['paid_dividends'],'This dataset has no dividend payments; explicit update needed if payments appear'
  active={};seq=Counter();layers={};rows=[];closed=[];events=[]
  for i,t in enumerate(v['trades']):events.append((t['at'],2,i,'trade',t))
  for i,r in enumerate(v['journal']):
   if r['kind']=='actual_split':events.append((r['at'],1,i,'split',r))
  for i,r in enumerate(v['audit_log']):
   if r['kind']=='dividend_accrual':events.append((r['receivable'].ex_at,0,i,'dividend',r['receivable']))
  for at,_,idx,kind,t in sorted(events,key=lambda e:e[:3]):
   if kind=='dividend':
    s=t.security_id;assert s in active;active[s]['unpaid_dividend']+=t.net_local;continue
   if kind=='split':
    s=t['sid'];ks=[k for k,z in layers.items()if z['sid']==s and z['qty']>0];old=sum(layers[k]['qty']for k in ks)
    if not old:continue
    ratio=D(str(t['ratio']));target=int(D(old)*ratio);qs=[int(D(layers[k]['qty'])*ratio)for k in ks]
    for i in range(target-sum(qs)):qs[i%len(qs)]+=1
    for k,q in zip(ks,qs):layers[k]['qty']=q
    active[s]['Q']=target;active[s]['actions'].append(dict(at=str(at),ratio=str(ratio),old_qty=old,new_qty=target));assert target>0;continue
   s=t['security_id'];qty=t['shares']
   if t['side']=='buy':
    if s not in active:
     seq[s]+=1;active[s]=dict(Q=0,K=Z,K_remaining=Z,paid_dividend=Z,unpaid_dividend=Z,buy_paid=Z,sell_received=Z,actions=[],opened=at,round_id=f'{s}:{seq[s]}')
    z=active[s];assert sum(l['qty']for l in layers.values()if l['sid']==s)==z['Q']
    if t['kind']=='add'and z['Q']>0:
     Q=z['Q'];op=t.get('raw_open');px=t.get('price');sellpx=op*D('.9995')if op is not None and op>0 else None
     live=[l for l in layers.values()if l['sid']==s and l['qty']>0];surviving_cost=sum((l['remaining_cost']for l in live),Z)
     pnl_raw=D(Q)*op-z['K']if op is not None else None;pnl_sell=D(Q)*sellpx-z['K']if sellpx is not None else None
     r=dict(account=a,at=str(at),sid=s,round_id=z['round_id'],round_opened=str(z['opened']),buy_layer=t['layer'],add_shares=qty,add_gross=t['gross_cny'],add_fees=t['fees_cny'],add_paid=t['gross_cny']+t['fees_cny'],pre_Q=Q,pre_K=z['K'],round_net_cost_per_share=z['K']/D(Q),prior_buy_paid=z['buy_paid'],prior_sell_received=z['sell_received'],paid_dividend=z['paid_dividend'],unpaid_dividend_excluded_from_K=z['unpaid_dividend'],prior_actions=z['actions'].copy(),known_raw_open=op,actual_add_price=px,sell_proxy_mark_before_hypothetical_fee=sellpx,round_pnl_at_raw_open=pnl_raw,round_pnl_at_actual_add_price=D(Q)*px-z['K']if px is not None else None,round_pnl_at_sell_proxy=pnl_sell,round_status_raw_open=status(pnl_raw),round_status_sell_proxy=status(pnl_sell),surviving_layer_cost=surviving_cost,surviving_layer_weighted_cost=surviving_cost/D(Q),surviving_layer_unrealized_at_raw_open=D(Q)*op-surviving_cost if op is not None else None,live_layers=len(live),losing_layers_at_raw_open=sum(D(l['qty'])*op<l['remaining_cost']for l in live)if op is not None else None,winning_layers_at_raw_open=sum(D(l['qty'])*op>l['remaining_cost']for l in live)if op is not None else None)
     schedule=market.fees(s,at);par=market.rules.get('security_metadata',{}).get(s,{}).get('par_value')
     estimated_sell_fee=sum(schedule.incremental('sell',D(Q)*sellpx,{}, {},1,shares=Q,par_value=par).values(),Z)
     V=D(Q)*sellpx-estimated_sell_fee
     r.update(primary_K_remaining=z['K_remaining'],primary_average_cost=z['K_remaining']/D(Q),estimated_full_position_sell_fee=estimated_sell_fee,primary_net_liquidation_V=V,primary_V_minus_K=V-z['K_remaining'],primary_reject_add=V<=z['K_remaining'],primary_gate='Q_positive_and_V_le_remaining_average_cost',primary_mark='raw_open_minus_5bp_minus_dated_sell_fee',average_cost_pnl_rawO=D(Q)*op-z['K_remaining'],average_cost_pnl_buy_proxy=D(Q)*px-z['K_remaining'])
     rows.append(r)
    paid=t['gross_cny']+t['fees_cny'];z['Q']+=qty;z['K']+=paid;z['K_remaining']+=paid;z['buy_paid']+=paid;layers[t['layer']]=dict(sid=s,qty=qty,remaining_cost=paid)
   else:
    z=active[s];net=t['gross_cny']-t['fees_cny'];z['K']-=net;z['sell_received']+=net;z['Q']-=qty;z['K_remaining']*=D(z['Q'])/D(z['Q']+qty)
    for part in t['parts']:
     l=layers[part['layer']];sold=part['shares'];l['remaining_cost']-=l['remaining_cost']*D(sold)/D(l['qty']);l['qty']-=sold
    assert z['Q']==sum(l['qty']for l in layers.values()if l['sid']==s)
    if z['Q']==0:closed.append(dict(sid=s,**z,closed=str(at)));del active[s]
  for layer in v['layers']:assert layers[layer['id']]['qty']==layer['qty']
  assert {s:z['Q']for s,z in active.items()}=={s:p.shares for s,p in v['positions'].items()}
  # Full-round K plus receivables and endpoint value recovers the saved account, independently of unrealized-layer cost.
  end=next(r for r in reversed(x['runner']['daily'])if r['account']==a)
  pnl=-sum((z['K']for z in closed),Z)-sum((z['K']for z in active.values()),Z)+end['inventory']+sum((z['unpaid_dividend']for z in closed),Z)+sum((z['unpaid_dividend']for z in active.values()),Z)
  assert abs(pnl-(end['nav']-v['initial_cash']))<D('1e-8')
  allrows.extend(rows);sums={}
  for st in ['LOSS','PROFIT','FLAT','UNKNOWN']:
   rr=[r for r in rows if r['round_status_raw_open']==st];sums[st]=dict(count=len(rr),gross=str(sum((r['add_gross']for r in rr),Z)),paid_including_fees=str(sum((r['add_paid']for r in rr),Z)))
  summaries[a]=dict(held_stock_mobile_adds=len(rows),status_at_raw_open=sums,status_at_sell_proxy=dict(Counter(r['round_status_sell_proxy']for r in rows)),round_profitable_but_some_layer_losing=sum(r['round_status_raw_open']=='PROFIT'and r['losing_layers_at_raw_open']>0 for r in rows),round_loss_but_surviving_layers_profitable=sum(r['round_status_raw_open']=='LOSS'and r['surviving_layer_unrealized_at_raw_open']>0 for r in rows),same_event_sell_settlements_verified=True,no_dividend_payments=True,endpoint_quantity_and_account_K_bridge_pass=True)
  positive=[r for r in rows if r['primary_reject_add']]
  summaries[a].update(primary_historical_adds_rejected=len(positive),primary_rejected_add_gross=str(sum((r['add_gross']for r in positive),Z)),primary_rejected_add_paid=str(sum((r['add_paid']for r in positive),Z)),primary_historical_adds_allowed=len(rows)-len(positive),primary_unknown=0,primary_definition='Current whole-stock average fee-inclusive remaining cost, no sale-profit/dividend deduction; V uses O minus5bp and original dated sell fee.')
  picks=[r for r in rows if r['sid']=='600675.SH'and r['at'].startswith('2022-12-02')]
  picks += [r for r in rows if r['round_status_raw_open']=='LOSS'and r['sid']!='600675.SH'][:2]
  picks += [r for r in rows if r['round_status_raw_open']=='PROFIT'and r['losing_layers_at_raw_open']>0][:1]
  examples+=picks
  print(a,json.dumps(summaries[a]),flush=True)
 pd.DataFrame(allrows).to_csv(O/'MOBILE_HELD_STOCK_PRE_ADD_2022.csv',index=False)
 save('MOBILE_PRE_ADD_SUMMARY.json',dict(status='PASS_EVENT_TIME_K_REPLAY',checkpoint_sha256=h,accounts=summaries,examples=examples,definitions=['K = cumulative actual buy gross+fees minus actual settled sell net minus actually paid dividends within a continuous stock 0-to-0 round. Partial exits do not reset K; pool migration has no effect.','All2022 sell proceeds settled at the same event; no dividend payments exist. Accrued unpaid dividends are excluded from K and reported separately.','PRIMARY gate uses whole-stock average remaining buy cost inclusive of buy fees; sale quantity reduces cost proportionally, dividends and realized sale profit do not reduce it. Reject if Q>0 and Q*raw_open*.9995 minus original dated sell fee <= this cost. Other status_at_raw_open fields refer only to the secondary continuous-round K definition.','Remaining layer cost includes allocated buy fees and adjusts shares for corporate actions; it is not the round net K after prior realized profits/losses.','Only MOBILE buys when pre-event Q>0 are counted, not initial MOBILE entries from zero.','No current-day close used. Proxy executable mark is a research assumption, not actual tradability proof.']))
 save('MOBILE_EXAMPLES.json',examples)
 print('EXAMPLES',json.dumps(examples,default=str),flush=True)
if __name__=='__main__':main()
