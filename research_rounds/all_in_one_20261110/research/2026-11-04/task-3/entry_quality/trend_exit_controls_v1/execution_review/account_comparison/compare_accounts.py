"""Read finished native outputs only. No Runner, Account, order or replay imports.

Refuses partial runs and unknown accounting splits. All cross-arm matching uses
full causal entry keys; a layer ID is only an intra-book locator.
"""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D,getcontext
import argparse,bisect,csv,gzip,hashlib,importlib.util,json
import pandas as pd
import numpy as np

getcontext().prec=60
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ENTRY=ROOT.parent
OLD=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
Z=D(0);INITIAL=D(1000000)
ARMS=['BASELINE','EARLY_EMA20','EARLY_EMA60','EARLY_BOLL20_MID','EARLY_BOLL20_LOWER']
INDICATORS={a:a.removeprefix('EARLY_') for a in ARMS[1:]}
NATIVE_REASONS={'ACT_pause','I_structure_exit','CP1_add_protection'}
SRC={};FRAMES={};MARK_CACHE={}
PERIODS={'2022_2024':[('full_2022_2024','2022-01-01','2024-12-31'),('2022','2022-01-01','2022-12-31'),
 ('2023','2023-01-01','2023-12-31'),('2024','2024-01-01','2024-12-31'),
 ('from_2024_09_24','2024-09-24','2024-12-31'),('after_2024_10_08','2024-10-09','2024-12-31')],
 'strong':[('strong','2025-07-01','2026-06-30')]}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(out,name,value):
 with (out/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def eq(a,b,why,tolerance='0.000001'):
 assert abs(D(str(a))-D(str(b)))<D(tolerance),(why,a,b)
def ts(x):return pd.Timestamp(x).isoformat()
def entry_key(sid,role,receipt,decision_at,opened):
 assert role in ('core','mobile')
 if role=='mobile':assert receipt,'missing mobile receipt'
 return json.dumps([sid,role,receipt,ts(decision_at),ts(opened)],ensure_ascii=False,separators=(',',':'))
def old_key(x):return entry_key(x['sid'],x['role'],x.get('receipt'),x['decision_at'],x['opened'])
def facts(sid):
 if sid not in FRAMES:
  r=SM[sid];p=Path(r['refs']['facts']);h=sha(p);assert h==r['output_sha256'][str(p)];SRC[str(p)]=h
  FRAMES[sid]=pd.read_parquet(p,columns=['raw_close','factor','close','i_target','segment_id'])
 return FRAMES[sid]
def quote(sid,day):
 key=(sid,day)
 if key not in MARK_CACHE:
  f=facts(sid);ix=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert ix>=0
  r=f.iloc[ix];qd=str(f.index[ix].date());assert qd<=day and r.raw_close>0
  MARK_CACHE[key]=(D(str(r.raw_close)),D(str(r.factor)),qd)
 return MARK_CACHE[key]
def sumfield(rows,key):return sum((D(x[key]) for x in rows),Z)
def layer_totals(rows):
 return dict(layers=len(rows),stocks=len({x['sid'] for x in rows}),cost=sumfield(rows,'cost'),net=sumfield(rows,'net'),
  positive=sum((max(Z,D(x['net'])) for x in rows),Z),negative=sum((min(Z,D(x['net'])) for x in rows),Z),
  strict_realized=sumfield(rows,'strict_realized'),open_unrealized=sumfield(rows,'open_unrealized'),AR=sumfield(rows,'AR'),
  closed=sum(x['closed'] is not None for x in rows),open=sum(x['closed'] is None for x in rows))
def group_layers(rows,key):
 g=defaultdict(list)
 for x in rows:g[str(x[key])].append(x)
 return {k:layer_totals(v) for k,v in sorted(g.items())}
def tool_fact(provider,sid,at,indicator):
 r=provider.at(sid,at,indicator)
 return dict(r,below=(r['causal_close']<r['line']) if r['status']=='READY' else None)

def analyze_run(arm,window,run,provider,original_calendar):
 timing=read(run/'TIMING.json');assert timing['completed'] is True,('unfinished run',run)
 meta=read(run/'RUN_METADATA.json');assert meta['arm']==arm and meta['window']==window
 assert meta['fresh_cash']==1000000 and meta['yearly_reset'] is False
 book=read(run/'pair/B.json.gz',gz=True);daily=read(run/'pair/daily.jsonl.gz',gz=True,lines=True)
 assert [x['at'] for x in daily]==original_calendar,('calendar drift',arm,window)
 buy={x['layer']:x for x in book['trades'] if x['side']=='buy'};native={x['id']:x for x in book['layers']};assert set(buy)==set(native)
 journal={x['layer']:x for x in book['journal'] if x['kind']=='real_buy_fill'};assert set(journal)==set(buy)
 parts=defaultdict(list);requests={x['event_id']:x for x in book['audit'] if x['kind']=='exit_request'}
 fills={x['receipt']['receipt_id']:x for x in book['audit'] if x['kind']=='fill'}
 for t in book['trades']:
  if t['side']=='sell':
   req=requests[fills[t['receipt_id']]['order_id']]
   for p in t['parts']:parts[p['layer']].append(dict(at=t['at'],reason=p['reason'],net_cash=p['net_cash'],shares=p['shares'],order_created_at=req['at']))
 assert not any(x['kind']=='dividend_payment' for x in book['audit']),'Paid dividend present: extend explicit paid/AR split before publishing; never relabel paid cash as AR.'
 days=[x['at'] for x in daily];days_iso=[ts(x) for x in days];cutoff=days[-1];rows=[];bykey={}
 # Only the two audited nontrivial partial layers need a sold-basis sidecar.
 # Replay their recorded buy/split/sell.parts arithmetic, never an account.
 partial_ids={lid for lid,pp in parts.items() if len(pp)>1 or native[lid]['qty']>0}
 partial_states={}
 for lid in partial_ids:
  b=buy[lid];x=native[lid];sid=x['sid'];q=b['shares'];basis=D(b['gross_cny'])+D(b['fees_cny']);real=Z
  ee=[(b['at'],'buy',None)]+[(p['at'],'sell',p) for p in parts[lid]]
  ee += [(a['at'],'split',a) for a in book['audit'] if a['kind'] in ('split','split_fraction_floor_proxy') and a['sid']==sid and b['at']<a['at'] and (x['closed'] is None or a['at']<x['closed'])]
  states=[]
  for atp,kind,p in sorted(ee,key=lambda z:z[0]):
   if kind=='split':
    exact=D(q)*D(p['ratio']);assert exact==int(exact),('Unknown fractional partial-layer basis boundary',arm,window,lid,atp);q=int(exact)
   elif kind=='sell':
    sold=p['shares'];assert 0<sold<=q;allocated=basis*D(sold)/D(q);real+=D(p['net_cash'])-allocated;basis-=allocated;q-=sold
   states.append(dict(at=atp,quantity=q,basis=basis,strict_realized=real))
  assert q==x['qty'];eq(real-basis,x['cash'],'partial final cash/basis identity');partial_states[lid]=states
 def partial_at(lid,atp):
  ss=partial_states[lid];j=bisect.bisect_right([s['at'] for s in ss],atp)-1;assert j>=0;return ss[j]
 for lid,x in native.items():
  b=buy[lid];j=journal[lid];m=book['metadata'][str(lid)];decision=m['budget_order'].split('|')[1]
  assert ts(decision)==ts(j['signal_at'])==ts(b['signal_at'])
  role=m['role'];receipt=j.get('CP1_id');key=entry_key(x['sid'],role,receipt,decision,x['opened']);assert key not in bykey,('ambiguous full entry key',key)
  cost=D(b['gross_cny'])+D(b['fees_cny']);value=Z if not x['qty'] else D(x['qty'])*quote(x['sid'],cutoff[:10])[0]
  if lid in partial_ids:
   ps=partial_at(lid,cutoff);realized=ps['strict_realized'];unreal=value-ps['basis']
  elif x['qty']:realized=Z;unreal=value-cost
  else:realized=D(x['cash']);unreal=Z
  ar=D(x['dividend']);net=realized+unreal+ar
  rr=dict(arm=arm,window=window,key=key,layer_in_this_book=lid,sid=x['sid'],role=role,receipt=receipt,decision_at=ts(decision),
   opened=ts(x['opened']),closed=None if x['closed'] is None else ts(x['closed']),qty=x['qty'],initial_qty=x['initial_qty'],
   buy_price=b['price'],cost=cost,net=net,strict_realized=realized,open_unrealized=unreal,AR=ar,value=value,
   actual_sale_parts=parts.get(lid,[]),actual_exit_reasons=sorted({p['reason'] for p in parts.get(lid,[])}),
   actual_exit_has_tool_reason=any(p['reason'] not in NATIVE_REASONS for p in parts.get(lid,[])),watch_epoch=b.get('epoch'),budget_order=m['budget_order'],
   held_close_observations=(bisect.bisect_left(days_iso,ts(x['closed'])) if x['closed'] is not None else len(days))-bisect.bisect_left(days_iso,ts(x['opened'])))
  if arm!='BASELINE':
   indicator=INDICATORS[arm];df=tool_fact(provider,x['sid'],decision,indicator);bf=tool_fact(provider,x['sid'],x['opened'],indicator)
   opcoord=D(b['raw_open'])*quote(x['sid'],x['opened'][:10])[1]
   rr.update(entry_decision_tool=df,entry_day_CLOSE_tool=bf,
    buy_OPEN_vs_prior_decision_line_below=(opcoord<D(str(df['line']))) if df['status']=='READY' else None,
    entry_day_CLOSE_is_after_buy_and_not_known_at_OPEN=True)
  rows.append(rr);bykey[key]=rr
 # Aggregate marks are checked against the actual native inventory; no
 # synthetic account or forced fills are created by this reader.
 by_stock_entries=defaultdict(list)
 for r in sorted(rows,key=lambda x:(x['opened'],x['layer_in_this_book'])):
  previous=by_stock_entries[r['sid']]
  r['actual_entry_action']='first' if not previous else 'add' if any(x['closed'] is None or x['closed']>r['opened'] for x in previous) else 'reentry'
  previous.append(r)
 core_orders=defaultdict(set)
 for r in rows:
  if r['role']=='core':core_orders[r['sid'],json.dumps(r['watch_epoch'])].add(r['budget_order'])
 assert all(len(v)==1 for v in core_orders.values()),'Repeated core order in same original watch epoch: inspect native contract before publishing.'
 led=[];closed_sorted=sorted((x for x in native.values() if x['closed'] is not None and x['id'] not in partial_ids),key=lambda x:x['closed']);ci=0;real=Z;maxdiff=Z;global_peak=INITIAL
 for d in daily:
  atd=d['at'];day=atd[:10]
  while ci<len(closed_sorted) and closed_sorted[ci]['closed']<=atd:real+=D(closed_sorted[ci]['cash']);ci+=1
  heldcost=Z;mark=Z
  for x in d['layers']:
   b=buy[x['id']];cost=D(b['gross_cny'])+D(b['fees_cny'])
   if x['id'] in partial_ids:
    ps=partial_at(x['id'],atd);assert ps['quantity']==x['qty'];eq(x['cash'],ps['strict_realized']-ps['basis'],'partial held cash');cost=ps['basis']
   else:eq(x['cash'],-cost,('Held nonpartial cash',arm,window,atd,x['id']))
   heldcost+=cost;mark+=D(x['qty'])*quote(x['sid'],day)[0]
  eq(mark,d['inventory'],('native inventory mark',arm,window,atd));unreal=D(d['inventory'])-heldcost;ar=D(d['dividend_receivable'])
  currentreal=real+sum((partial_at(lid,atd)['strict_realized'] for lid in partial_ids if buy[lid]['at']<=atd),Z)
  diff=D(d['nav'])-INITIAL-currentreal-unreal-ar;maxdiff=max(maxdiff,abs(diff));eq(diff,Z,('wealth split',arm,window,atd))
  global_peak=max(global_peak,D(d['nav']))
  led.append(dict(at=atd,day=day,NAV=D(d['nav']),strict_realized=currentreal,open_unrealized=unreal,AR=ar,inventory=D(d['inventory']),
   drawdown_from_full_path_peak=1-D(d['nav'])/global_peak,
   held_basis=heldcost,available=D(d['available']),exposure=D(d['inventory'])/D(d['nav']),ACT_on=d['on'],held_layers=len(d['layers']),held_stocks=len(d['positions'])))
 eq(sumfield(rows,'net'),D(book['ending_NAV'])-INITIAL,'all-layer endpoint wealth');eq(led[-1]['NAV'],book['ending_NAV'],'terminal NAV')
 # Actual interval union identifies flat-to-flat stock campaigns. This uses
 # recorded opens/closes only, without simulating a decision or an inventory.
 campaigns=[];by_sid=defaultdict(list)
 for r in rows:by_sid[r['sid']].append(r)
 for sid,rr in by_sid.items():
  rr.sort(key=lambda x:x['opened']);g=[];end=None
  def flush(group):
   if not group:return
   closed=all(x['closed'] is not None for x in group);last=max((x['closed'] for x in group if x['closed']),default=None) if closed else None
   reasons=sorted({p['reason'] for x in group for p in x['actual_sale_parts'] if last is not None and ts(p['at'])==last})
   campaigns.append(dict(sid=sid,opened=group[0]['opened'],closed=last,entry_keys=[x['key'] for x in group],
    roles=[x['role'] for x in group],exit_has_tool_reason=any(x['actual_exit_has_tool_reason'] for x in group),
    final_liquidation_reasons=reasons,final_liquidation_has_tool_reason=any(r not in NATIVE_REASONS for r in reasons),
    closed_layers=sum(x['closed'] is not None for x in group),**{k:v for k,v in layer_totals(group).items() if k!='closed'}))
  for r in rr:
   if g and end is not None and end<=r['opened']:flush(g);g=[]
   g.append(r);end=None if any(x['closed'] is None for x in g) else max(x['closed'] for x in g)
  flush(g)
 repeated=[]
 for sid in by_sid:
  cc=sorted([c for c in campaigns if c['sid']==sid],key=lambda c:c['opened'])
  for prev,nxt in zip(cc,cc[1:]):
   assert prev['closed'] is not None and prev['closed']<=nxt['opened']
   if prev['final_liquidation_has_tool_reason']:
    repeated.append(dict(sid=sid,previous_closed=prev['closed'],previous_net=prev['net'],next_opened=nxt['opened'],next_net=nxt['net'],
     next_roles=nxt['roles'],next_entry_keys=nxt['entry_keys'],next_campaign_also_tool_exit=nxt['final_liquidation_has_tool_reason']))
 events=[x for x in book['audit'] if x['kind']=='risk_checkpoint']
 audit=read(ROOT/'independent_review'/f'{arm}_{window}_ACCOUNT_AUDIT.json');assert audit['status']=='PASS_COMPLETED_ACCOUNT_WITH_LIMITS';eq(audit['corporate_zero_qty_basis_writeoff'],Z,'No unhandled zero-unit basis writeoff')
 eq(led[-1]['strict_realized'],audit['trade_realized'],'independent audited realized');eq(led[-1]['open_unrealized'],audit['open_unrealized'],'independent audited unrealized')
 cutoff_split=None
 if window=='2022_2024':
  cut=next(d for d in daily if d['at'][:10]=='2024-10-08');oldids={x['id'] for x in cut['layers']};rm={r['layer_in_this_book']:r for r in rows}
  olddetails=[]
  for x in cut['layers']:
   startwealth=D(x['cash'])+D(x['qty'])*quote(x['sid'],'2024-10-08')[0]+D(x['dividend']);r=rm[x['id']]
   olddetails.append(dict(key=r['key'],sid=x['sid'],cutoff_quantity=x['qty'],cutoff_layer_wealth=startwealth,ending_layer_wealth=r['net'],period_wealth_change=r['net']-startwealth))
  newrows=[r for r in rows if r['opened']>ts(cut['at'])];oldchange=sum((x['period_wealth_change'] for x in olddetails),Z);newchange=sumfield(newrows,'net');total=D(book['ending_NAV'])-D(cut['nav']);residual=total-oldchange-newchange;eq(residual,Z,'Oct8 old/new wealth bridge')
  cutoff_split=dict(cutoff_at=cut['at'],cutoff_NAV=cut['nav'],ending_NAV=book['ending_NAV'],net_wealth_change=total,old_inventory_layers=len(oldids),old_inventory_period_wealth_change=oldchange,
   post_cutoff_new_actual_layers=layer_totals(newrows),old_previously_flat_layer_change_residual=residual,old_inventory_details=olddetails,new_layers=newrows,
   interpretation='Each arm own Oct8 actual inventory and own later new layers. Old inventory change starts from Oct8 marked wealth; new-layer endpoint P&L starts from actual entry. This is not all original303 or pure exit attribution.')
 result=dict(arm=arm,window=window,run=str(run),daily=led,layers=rows,bykey=bykey,campaigns=campaigns,cutoff_split=cutoff_split,
  tool_exit_reentries=repeated,periods=[],validation=dict(native_daily_mark_and_wealth_checks=len(led),maximum_wealth_residual=maxdiff,
   partial_layer_ids=sorted(partial_ids),partial_basis_state_points=partial_states,partial_basis_matches_independent_final=True,paid_dividends=0,maximum_distinct_core_orders_same_watch_epoch=max((len(v) for v in core_orders.values()),default=0),new_accounts=0))
 for label,start,end in PERIODS[window]:
  ix=[i for i,d in enumerate(led) if start<=d['day']<=end];assert ix
  first,last=ix[0],ix[-1];prior=led[first-1] if first else dict(NAV=INITIAL,strict_realized=Z,open_unrealized=Z,AR=Z)
  endd=led[last];selected=[led[i] for i in ix];peak=prior['NAV'];dd=Z
  for x in selected:peak=max(peak,x['NAV']);dd=max(dd,Z if peak==0 else 1-x['NAV']/peak)
  tsell=[t for t in book['trades'] if start<=t['at'][:10]<=end];fees=sum((D(t['fees_cny']) for t in tsell),Z);turn=sum((D(t['gross_cny']) for t in tsell),Z)
  risk=[x for x in events if start<=x['at'][:10]<=end]
  p=dict(arm=arm,window=window,period=label,calendar_start=start,calendar_end=end,first_observed_day=selected[0]['day'],last_observed_day=selected[-1]['day'],
   observations=len(ix),NAV_begin=prior['NAV'],NAV_end=endd['NAV'],net_wealth_change=endd['NAV']-prior['NAV'],return_fraction=endd['NAV']/prior['NAV']-1,
   strict_realized_change=endd['strict_realized']-prior['strict_realized'],open_unrealized_change=endd['open_unrealized']-prior['open_unrealized'],
   AR_change=endd['AR']-prior['AR'],period_rebased_max_drawdown=dd,
   maximum_account_drawdown_from_full_path_peak=max(x['drawdown_from_full_path_peak'] for x in selected),
   mean_close_exposure=sum((x['exposure'] for x in selected),Z)/len(selected),end_exposure=selected[-1]['exposure'],
   mean_available=sum((x['available'] for x in selected),Z)/len(selected),fees=fees,turnover_gross=turn,turnover_over_period_begin_NAV=turn/prior['NAV'],
   buy_fills=sum(t['side']=='buy' for t in tsell),sell_fills=sum(t['side']=='sell' for t in tsell),
   actual_buycash=sum((D(t['gross_cny'])+D(t['fees_cny']) for t in tsell if t['side']=='buy'),Z),
   actual_sell_net=sum((D(t['gross_cny'])-D(t['fees_cny']) for t in tsell if t['side']=='sell'),Z),
   ACT_paused_closes=sum(not x['ACT_on'] for x in selected),ACT_pause_events=sum(x.get('event')=='pause' for x in risk),ACT_resume_events=sum(x.get('event')=='resume' for x in risk))
  eq(p['net_wealth_change'],p['strict_realized_change']+p['open_unrealized_change']+p['AR_change'],'period split');result['periods'].append(p)
 return result

def matching(base,arm):
 common=base['bykey'].keys()&arm['bykey'].keys();removed=base['bykey'].keys()-arm['bykey'].keys();new=arm['bykey'].keys()-base['bykey'].keys()
 matched=[]
 for k in sorted(common):
  b=base['bykey'][k];a=arm['bykey'][k]
  relation='both_open' if a['closed'] is None and b['closed'] is None else 'candidate_still_open_baseline_closed' if a['closed'] is None else 'candidate_closed_baseline_open' if b['closed'] is None else 'earlier' if a['closed']<b['closed'] else 'later' if a['closed']>b['closed'] else 'same'
  matched.append(dict(key=k,sid=b['sid'],role=b['role'],baseline_cost=b['cost'],candidate_cost=a['cost'],baseline_net=b['net'],candidate_net=a['net'],
   net_delta=a['net']-b['net'],entry_quantity_price_fees_equal=(b['initial_qty']==a['initial_qty'] and D(b['buy_price'])==D(a['buy_price']) and b['cost']==a['cost']),
   baseline_closed=b['closed'],candidate_closed=a['closed'],exit_relation=relation,baseline_exit_reasons=b['actual_exit_reasons'],candidate_exit_reasons=a['actual_exit_reasons']))
 rem=[base['bykey'][k] for k in sorted(removed)];newr=[arm['bykey'][k] for k in sorted(new)];delta=sum((x['net_delta'] for x in matched),Z)+sumfield(newr,'net')-sumfield(rem,'net')
 eq(delta,sumfield(arm['layers'],'net')-sumfield(base['layers'],'net'),'path decomposition')
 changed=[]
 for b,a in zip(base['daily'],arm['daily']):
  assert b['at']==a['at']
  if b['ACT_on']!=a['ACT_on']:changed.append(dict(at=a['at'],baseline_ACT_on=b['ACT_on'],candidate_ACT_on=a['ACT_on'],baseline_NAV=b['NAV'],candidate_NAV=a['NAV'],
   baseline_exposure=b['exposure'],candidate_exposure=a['exposure'],baseline_available=b['available'],candidate_available=a['available']))
 return dict(summary=dict(matched_entries=len(common),removed_baseline_entries=len(removed),new_candidate_entries=len(new),
  matched_entry_net_delta=sum((x['net_delta'] for x in matched),Z),removed_baseline=layer_totals(rem),new_candidate=layer_totals(newr),
  account_net_delta=delta,matched_exit_relations=dict(Counter(x['exit_relation'] for x in matched)),ACT_changed_closes=len(changed),
  attribution='Exact endpoint identity for executed paths; quantity, freed cash, later selection/reentry and ACT feedback are endogenous. Matched/static deltas are not pure causal exit effects.'),
  matched=matched,removed=rem,new=newr,ACT_changes=changed)

def tails_for(window,frozen,base,arm):
 rr=[]
 for t in frozen:
  original=t['original'];k=old_key(original);b=base['bykey'].get(k);a=arm['bykey'].get(k)
  start=ts(original['opened']);end=ts(original['closed']) if original['closed'] else ts(base['daily'][-1]['at'])
  overlap=[x for x in arm['layers'] if x['sid']==original['sid'] and x['opened']<end and (x['closed'] is None or x['closed']>start)]
  after_exit=[];early_exit=False
  if b is not None and a is not None and a['closed'] is not None:
   bend=b['closed'] or ts(base['daily'][-1]['at'])
   early_exit=a['closed']<bend
   if early_exit:after_exit=[x for x in arm['layers'] if x['sid']==a['sid'] and x['key']!=k and x['opened']<bend and (x['closed'] is None or x['closed']>a['closed'])]
  status='matched_baseline_and_candidate' if b and a else 'same_entry_not_participated_candidate' if b else 'baseline_unmatched_candidate_entry_present' if a else 'baseline_unmatched_both_absent'
  rr.append(dict(window=window,original_fixed_member=original,entry_key=k,status=status,baseline_current_exact_match=b,
   candidate_exact_entry_match=a,candidate_holding_overlap_original_tail_interval_keys=[x['key'] for x in overlap],
   candidate_no_actual_holding_during_original_tail_interval=not overlap,
   candidate_other_holding_after_exact_layer_exit_before_baseline_end_keys=[x['key'] for x in after_exit],
   candidate_new_entries_after_exact_layer_exit_before_baseline_end_keys=[x['key'] for x in after_exit if x['opened']>=a['closed']] if a is not None and a['closed'] is not None else [],
   matched_entry_exited_earlier=early_exit,candidate_no_further_holding_after_early_exit=(not after_exit) if early_exit else None,
   raw_contribution_delta=None if b is None else (Z if a is None else a['net'])-b['net'],
   raw_contribution_is_not_exit_only_counterfactual=True))
 return dict(summary=dict(original_frozen_members=len(rr),baseline_current_matches=sum(r['baseline_current_exact_match'] is not None for r in rr),
  candidate_exact_matches=sum(r['candidate_exact_entry_match'] is not None for r in rr),statuses=dict(Counter(r['status'] for r in rr)),
  completely_no_holding_in_original_tail_interval=sum(r['candidate_no_actual_holding_during_original_tail_interval'] for r in rr),
  baseline_matched_cohort_completely_no_holding_in_original_tail_interval=sum(r['candidate_no_actual_holding_during_original_tail_interval'] for r in rr if r['baseline_current_exact_match'] is not None),
  matched_tail_earlier_exit_then_no_further_holding=sum(r['candidate_no_further_holding_after_early_exit'] is True for r in rr),
  baseline_matched_cohort_net=sum((r['baseline_current_exact_match']['net'] for r in rr if r['baseline_current_exact_match'] is not None),Z),
  candidate_same_entry_contribution_for_baseline_matched_cohort=sum((r['candidate_exact_entry_match']['net'] for r in rr if r['baseline_current_exact_match'] is not None and r['candidate_exact_entry_match'] is not None),Z)),rows=rr)

def main():
 global SM
 p=argparse.ArgumentParser();p.add_argument('--runs-root',type=Path,default=ROOT/'runs');p.add_argument('--out',type=Path,default=HERE/'results_v1');args=p.parse_args()
 # All inputs must be complete before any financial result is written.
 for arm in ARMS:
  for win in PERIODS:
   run=args.runs_root/arm/win
   for name in ['TIMING.json','RUN_METADATA.json','pair/B.json.gz','pair/daily.jsonl.gz']:assert (run/name).exists(),('waiting for complete output',run/name)
   assert json.loads((run/'TIMING.json').read_text())['completed'] is True
 assert not args.out.exists(),'Preserve existing analysis: use a fresh --out for an approved correction.'
 frozen=read(ROOT/'STATE_MACHINE_FREEZE.json');assert frozen['active_arms']==ARMS
 SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 fixed=read(ENTRY/'entry_exit_scale/analysis_summary/FIXED_ORIGINAL_TAILS.json');assert [len(fixed[k]) for k in PERIODS]==[83,94]
 providerfile=ROOT/'indicator_provider.py';SRC[str(providerfile)]=sha(providerfile)
 spec=importlib.util.spec_from_file_location('exit_comparison_readonly_indicator_provider',providerfile);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);provider=mod.IndicatorProvider()
 im=read(ROOT/'indicators/MANIFEST.json');SRC[im['data_file']]=sha(im['data_file']);assert SRC[im['data_file']]==im['data_sha256']
 calendars={};oldrows={}
 for win,path in [('2022_2024',OLD/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair'),('strong',OLD/'pvr_pool_feasibility/runs/2025_26/pair')]:
  calendars[win]=[x['at'] for x in read(path/'daily.jsonl.gz',gz=True,lines=True)]
  oldrows[win]=read(ENTRY/'entry_exit_scale/holding_exit'/f'{win}_LAYERS.json')
 args.out.mkdir(parents=True);allruns={};matrix=[];validation={};comparisons={};tails={};entryfeedback={};layer_summaries={};post_summaries={};original303={}
 try:
  for win in PERIODS:
   base=analyze_run('BASELINE',win,args.runs_root/'BASELINE'/win,provider,calendars[win]);allruns[('BASELINE',win)]=base
   expected={old_key(x):x for x in oldrows[win]};assert set(base['bykey'])==set(expected),('baseline old full entry identity drift',win)
   for k,b in base['bykey'].items():eq(b['cost'],expected[k]['cost'],'old baseline cost');eq(b['net'],expected[k]['net'],'old baseline net')
   assert sum(old_key(t['original']) in base['bykey'] for t in fixed[win])=={'2022_2024':45,'strong':67}[win]
   for arm in ARMS:
    r=base if arm=='BASELINE' else analyze_run(arm,win,args.runs_root/arm/win,provider,calendars[win]);allruns[arm,win]=r;matrix.extend(r['periods']);validation[arm+'|'+win]=r['validation']
    layer_summaries[arm+'|'+win]=dict(all=layer_totals(r['layers']),by_role=group_layers(r['layers'],'role'),by_actual_action=group_layers(r['layers'],'actual_entry_action'))
    save(args.out,arm+'_'+win+'_LAYERS.json',r['layers']);save(args.out,arm+'_'+win+'_DAILY_WEALTH_SPLIT.json',r['daily']);save(args.out,arm+'_'+win+'_STOCK_CAMPAIGNS.json',r['campaigns'])
    if win=='2022_2024':
     save(args.out,arm+'_POST_OCT8_OLD_NEW_WEALTH.json',r['cutoff_split']);post_summaries[arm]={k:v for k,v in r['cutoff_split'].items() if k not in ['old_inventory_details','new_layers']}
     f303=[dict(original=x) for x in oldrows[win] if '2024-10-09'<=x['opened'][:10]<='2024-12-31'];assert len(f303)==303
     post=tails_for(win,f303,base,r);save(args.out,arm+'_ORIGINAL303_FULL_ENTRY_MATCH.json',post);original303[arm]=post['summary']
    tf=tails_for(win,fixed[win],base,r);tails[arm+'|'+win]=tf['summary'];save(args.out,arm+'_'+win+'_FIXED_ORIGINAL_TAILS.json',tf)
    if arm!='BASELINE':
     c=matching(base,r);comparisons[arm+'|'+win]=c['summary'];save(args.out,arm+'_'+win+'_ENTRY_PATH_COMPARISON.json',c)
     below=[x for x in r['layers'] if x['entry_decision_tool']['below'] is True]
     buyclose=[x for x in r['layers'] if x['entry_day_CLOSE_tool']['below'] is True]
     entryfeedback[arm+'|'+win]=dict(all=layer_totals(r['layers']),decision_CLOSE_already_below=layer_totals(below),buy_day_CLOSE_below_post_fill=layer_totals(buyclose),
      buy_OPEN_below_prior_decision_line=layer_totals([x for x in r['layers'] if x['buy_OPEN_vs_prior_decision_line_below'] is True]),
      decision_below_role_groups=group_layers(below,'role'),decision_below_action_groups=group_layers(below,'actual_entry_action'),decision_below_exited_within_one_held_close=layer_totals([x for x in below if x['closed'] is not None and x['held_close_observations']<=1]),
      decision_below_exited_within_five_held_closes=layer_totals([x for x in below if x['closed'] is not None and x['held_close_observations']<=5]),
      actual_tool_exit_then_new_stock_campaigns=len(r['tool_exit_reentries']),next_campaign_also_tool_exit=sum(x['next_campaign_also_tool_exit'] for x in r['tool_exit_reentries']),
      reentries=r['tool_exit_reentries'],no_entry_indicator_gate_added=True,
      interpretation='Original core epoch consumption is preserved by the runner; mobile fresh CP can reenter while tool is already below. Descriptive quick exits and repeats do not authorize entry filtering.')
   # Exact same original dates; no arm-specific favorable window selection.
  save(args.out,'PERIOD_ACCOUNT_MATRIX.json',matrix);save(args.out,'FULL_PATH_COMPARISON_SUMMARY.json',comparisons);save(args.out,'FIXED_ORIGINAL_TAIL_SUMMARY.json',tails);save(args.out,'ENTRY_AND_REENTRY_FEEDBACK.json',entryfeedback);save(args.out,'ACCOUNT_LAYER_TOTALS.json',layer_summaries);save(args.out,'POST_OCT8_OLD_NEW_SUMMARY.json',post_summaries);save(args.out,'ORIGINAL303_MATCH_SUMMARY.json',original303)
  with (args.out/'PERIOD_ACCOUNT_MATRIX.csv').open('x',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=list(matrix[0]));writer.writeheader();writer.writerows(matrix)
  save(args.out,'VALIDATION.json',dict(status='PASS',runs=validation,old_baseline_entry_keys_and_cost_net_exact=True,original_fixed_tails=[83,94],current_baseline_tail_matches=[45,67],new_accounts=0,new_account_steps=0,
   constraints='No account/ledger imports. Actual native snapshots, fills, cash, AR and exact frozen marks only. If partial realization/paid dividends need extra basis treatment, stop instead of guessing.'))
 except BaseException as e:
  save(args.out,'FAILURE.json',dict(error=repr(e),partial_analysis_preserved=True,new_accounts=0));raise
 finally:
  SRC[str(Path(__file__).resolve())]=sha(__file__);save(args.out,'SOURCE_SHA256.json',SRC)
  save(args.out,'DELIVERABLE_SHA256.json',{str(f):sha(f) for f in args.out.iterdir() if f.is_file() and f.name!='DELIVERABLE_SHA256.json'})
 print('COMPARISON_COMPLETE',args.out,len(matrix),'fixed period rows; no account execution')

if __name__=='__main__':main()
