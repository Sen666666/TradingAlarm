"""Closed-form local cash diagnostics in a deliberately narrow simple domain.

Calls original market windows/fees; never constructs an Account, production
adapter, full event loop, synthetic fill, or new financial strategy path.
"""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D
from bisect import bisect_right
import sys,json,gzip,hashlib,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;E=O.parents[1];sys.path.insert(0,str(E/'trend_exit_controls_v1'))
import load_inputs as V
J=V.J;SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt')if gz else p.open())as f:return [json.loads(l)for l in f]if lines else json.load(f)
def clock(s):return J.M.N.iso(s.replace(' ','T'))
def fee(schedule,q,p,paid,accrued,par):
 x=schedule.incremental('sell',D(q)*p,paid,accrued,1,shares=q,par_value=par)
 for k,v in x.items():paid[k]=paid.get(k,D(0))+v
 for k,v in schedule.rate_accrual('sell',D(q)*p,1,shares=q,par_value=par).items():accrued[k]=accrued.get(k,D(0))+v
 return sum(x.values(),D(0))

def main():
 start=time.monotonic();protocol=read(O/'LOCAL_DIAGNOSTIC_PROTOCOL.json');annex=read(O/'COUNTERCASE_SCOPE_ANNEX.json')
 traces=read(O.parent/'chains/LOCAL_DIAGNOSTIC_TRIGGERS.json');chains=read(O.parent/'chains/COMPLETE_ORIGINAL_CHAINS.json')
 cases={r['campaign']['campaign_id']:r['campaign']for r in chains}
 wanted={tuple(x)for x in protocol['scope_pairs']+annex['additional_pairs']}
 traces=[r for r in traces if(r['sid'],r['campaign_id'].split('|')[-1][:10])in wanted];assert len(traces)==len(wanted)==13
 sm={r['symbol']:r for r in read(V.W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 assert J.LR.SLIP==D('.0005')
 # Exactly the original loader_2024 market constructor, restricted to queried
 # stock identities. It creates no Account; indicators/ranking are not recomputed.
 _,market,_=J.M.context('2024-12-31',ids=sorted({r['sid']for r in traces}))
 assert set(market.lines)=={r['sid']for r in traces}
 assert market.protocol['daily_execution']['A']['slippage_bps']=='5'
 for sid in market.lines:
  rr=market.bundle.series[sid].record['raw'];assert sha(rr['path'])==rr['sha256'];SRC[str(Path(rr['path']).resolve())]=rr['sha256']
 pair=E/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair'
 book=read(pair/'B.json.gz',True);daily=read(pair/'daily.jsonl.gz',True,True);days={r['at'][:10]:r for r in daily}
 receipt_order={x['receipt']['receipt_id']:x['order_id']for x in book['audit']if x.get('kind')=='fill'}
 buys={x['layer']:x for x in book['trades']if x['side']=='buy'}
 result=[]
 for t in traces:
  sid=t['sid'];c=cases[t['campaign_id']];T=clock(t['trigger_known_clock']);H=clock(c['closed']);ids=set(c['layer_ids']);df=days[str(T.date())]
  ep=Path(t['trigger_event_source']);assert sha(ep)==sm[sid]['source_sha256'][str(ep)];SRC[str(ep)]=sha(ep);events=pd.read_parquet(ep)
  ev=events.loc[c['opened'][:10]:c['closed'][:10]];ev=ev[ev.index<pd.Timestamp(H.date())];negative=ev.index[ev.event.eq(-1)];assert len(negative)and str(negative[0].date())==str(T.date())
  live=[r for r in df['layers']if r['sid']==sid and r['id']in ids];assert [r['id']for r in live]==t['T_inventory_layer_ids']
  inv={r['id']:int(r['qty'])for r in live};q=sum(inv.values());quote=market.quote(sid,T);assert quote and quote.known_at<=T;mark=quote.read_price(T)
  held_pending=set()
  for r in book['audit']:
   if r.get('kind')=='pilot_layer_exit'and r.get('sid')==sid and clock(r['at'])<=T:
    held_pending|=(set(r['layers'])&set(inv))
  # A live layer with any original request remains latched. Original partials
  # are not silently considered filled merely because a later reason changed.
  removed=[lid for lid in ids if clock(buys[lid]['signal_at'])>T and buys[lid]['kind']=='add']
  postbuys=[x for lid,x in buys.items()if lid in ids and clock(x['at'])>T]
  kept_postbuys=[x for x in postbuys if x['layer']not in removed]
  acts=[a for a in market.actions[sid]if str((T-pd.Timedelta(days=5)).date())<=a['effective_date']<=str(H.date())]
  row=dict(campaign_id=c['campaign_id'],sid=sid,trigger_at=str(T),horizon=str(H),trigger_is_confirmed_down_event_not_E0_off=True,T_units=q,T_layer_ids=list(inv),original_pending_layer_ids=sorted(held_pending),T_CORE_units=sum(int(r['qty'])for r in live if r['kind']=='core'),T_mobile_units=sum(int(r['qty'])for r in live if r['kind']=='add'),removed_post_T_mobile_ids=sorted(removed),same_T_or_prior_committed_future_buys=[x['layer']for x in kept_postbuys],actions_near_T_or_to_H=acts,A=None,B=None)
  if held_pending==set(inv):row['A']=dict(status='NO_INCREMENT_ALL_T_UNITS_ALREADY_LATCHED',local_delta='0')
  if not removed:row['B']=dict(status='NO_STRICT_POST_T_MOBILE_CONTRACT',local_delta='0')
  reasons=[]
  if held_pending:reasons.append('prior_or_same_CLOSE_pending_requires_order_state_reconstruction')
  if acts:reasons.append('near_T_or_future_corporate_action_outside_closed_form_scope')
  # A/B arithmetic can be exact only in this predeclared simple domain. Native
  # partial fill/state replay belongs to a separately reviewed future experiment.
  try:
   if reasons:raise ValueError(';'.join(reasons))
   chosen=set(inv);groups=[];sold=defaultdict(int)
   for tr in book['trades']:
    if tr['side']!='sell'or tr['security_id']!=sid or not(T<clock(tr['at'])<=H):continue
    parts=[p for p in tr['parts']if p['layer']in chosen];n=sum(p['shares']for p in parts)
    if not n:continue
    at=clock(tr['at']);w=market.window(sid,at,'sell',1);assert w and w.sell_allowed is True and w.execution_price==D(tr['price'])
    assert w.capacity_shares>=n
    groups.append((at,receipt_order[tr['receipt_id']],n,w))
    for p in parts:sold[p['layer']]+=p['shares']
   assert dict(sold)==inv,('not_all_T_units_reconciled',dict(sold),inv)
   paid={};accrued={};base_net=D(0);remaining=q;base_parts=[]
   for at,oid,n,w in groups:
    assert w.quantity.sell_floor(n,remaining)>=n and n%w.quantity.fill_step==0
    f=fee(w.fees,n,w.execution_price,paid.setdefault(oid,{}),accrued.setdefault(oid,{}),w.par_value)
    net=D(n)*w.execution_price-f;base_net+=net;remaining-=n
    base_parts.append(dict(at=str(at),native_order_id=oid,shares=n,price=str(w.execution_price),fee=str(f),net=str(net)))
   assert remaining==0
   row['isolated_T_inventory_control']=dict(mark_at_T=str(D(q)*mark),later_exit_net=str(base_net),wealth_from_T=str(base_net-D(q)*mark),parts=base_parts,buy_cost_before_T_sunk=True,no_post_T_buys=True)
   if row['A']is None:
    early=None;failed=[]
    for at in market.sessions['A'][bisect_right(market.sessions['A'],T):]:
     if at>H:break
     w=market.window(sid,at,'sell',1)
     if w is None or w.sell_allowed is not True:failed.append(str(at));continue
     # All original buys precede T CLOSE, so original A T+1 matures no later
     # than this next A OPEN; recent bonus/share actions were excluded above.
     assert all(clock(buys[lid]['at'])<at for lid in chosen)
     if w.capacity_shares<q:raise ValueError('first_legal_window_requires_partial_replay')
     if w.quantity.sell_floor(q,q)<q or q%w.quantity.fill_step:raise ValueError('integer_full_exit_outside_simple_domain')
     f=fee(w.fees,q,w.execution_price,{}, {},w.par_value);net=D(q)*w.execution_price-f
     early=dict(status='EXACT_SIMPLE_ISOLATED_T_UNITS_CONDITIONAL_ON_ORIGINAL_CONTEXT',at=str(at),shares=q,price=str(w.execution_price),fee=str(f),exit_net=str(net),wealth_from_T=str(net-D(q)*mark),local_delta=str(net-base_net),prior_ineligible_windows=failed)
     break
    if early is None:raise ValueError('no_legal_full_exit_window_before_evaluation_H')
    row['A']=early
   if row['B']is None:
    if kept_postbuys:raise ValueError('same_T_or_prior_committed_post_T_buy_requires_more_contract_state')
    baseline_cash=D(0)
    for tr in book['trades']:
     if tr['security_id']!=sid or not(T<clock(tr['at'])<=H):continue
     if tr['side']=='buy'and tr['layer']in ids:baseline_cash-=D(tr['gross_cny'])+D(tr['fees_cny'])
     elif tr['side']=='sell':
      relevant=[p for p in tr['parts']if p['layer']in ids]
      if relevant:
       assert len(relevant)==len(tr['parts'])
       baseline_cash+=D(tr['gross_cny'])-D(tr['fees_cny'])
    row['B']=dict(status='EXACT_SIMPLE_POST_T_MOBILE_REJECTION_CONDITIONAL_ON_ORIGINAL_CONTEXT',original_post_T_cash=str(baseline_cash),retained_old_units_exit_net=str(base_net),avoided_mobile_actual_buycash=str(sum((D(buys[i]['gross_cny'])+D(buys[i]['fees_cny'])for i in removed),D(0))),local_delta=str(base_net-baseline_cash),cash_segregated_not_reinvested=True)
  except (ValueError,AssertionError)as e:
   why=str(e)
   if row['A']is None:row['A']=dict(status='UNCOMPUTED_SIMPLE_SCOPE_LIMIT',reason=why,local_delta=None)
   if row['B']is None:row['B']=dict(status='UNCOMPUTED_SIMPLE_SCOPE_LIMIT',reason=why,local_delta=None)
  result.append(row)
 SRC[str(Path(__file__).resolve())]=sha(__file__)
 out=dict(status='LOCAL_SIMPLE_DOMAIN_DIAGNOSTICS_NOT_PORTFOLIO_RETURNS',cases=result,new_financial_accounts=0,new_financial_events=0,original_native_market_construction_only=True,source_sha256=SRC,limitations=['Original ACT/account context held fixed; no cash reallocation or changed role/PVR competition is modeled.','A isolated T inventory control is repriced, not original whole campaign PnL. B is local conditional cash difference, not a deployable live reset rule.','UNKNOWN/uncomputed cases were not assigned zero and were not replaced with future best fills.','All selected losers and attached winners retained. No picking A or B per case.'],seconds=time.monotonic()-start)
 with (O/'SIMPLE_LOCAL_CASH_RESULTS.json').open('x')as f:json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({'status':out['status'],'cases':len(result),'A':[{k:r[k]for k in ['sid','A']}for r in result],'B':[{k:r[k]for k in ['sid','B']}for r in result],'seconds':out['seconds']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
