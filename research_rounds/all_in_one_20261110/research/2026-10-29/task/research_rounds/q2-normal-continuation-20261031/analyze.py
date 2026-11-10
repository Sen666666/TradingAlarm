"""Saved-book Q2 attribution/behavior; canonical original marks, no orders/run."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip,collections,time,math
import pandas as pd
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import continuation as E
J=E.J;L=E.L;Z=D(0);START='2026-04-01';OLD='2026-03-31';END=E.END
META=L.read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):
 def unknown(v):
  if isinstance(v,float) and not math.isfinite(v):return None
  if isinstance(v,dict):return {k:unknown(z) for k,z in v.items()}
  if isinstance(v,list):return [unknown(z) for z in v]
  return v
 E.IO.write_json(p,unknown(J.W.canon(x)))
def date(x):return str(x)[:10]
def num(x):return D(str(x))
def main():
 begun=time.monotonic();books={};oldbooks={};dailies={};ids=set()
 for ref,parent in [('B3',J.O/'run-universe'),('B_diag',E.BASE.O/'run')]:
  assert L.read(O/'runs'/ref/'DONE.json')['completed']
  a=obj(O/'runs'/ref/'pair/B.json.gz');old=obj(parent/'pair/B.json.gz');daily=rows(O/'runs'/ref/'pair/daily.jsonl.gz');books[ref]=a;oldbooks[ref]=old;dailies[ref]=daily
  start=next(x for x in daily if date(x['at'])==OLD);ids.update(start['positions']);ids.update(daily[-1]['positions']);ids.update(t['security_id'] for t in a['trades'] if date(t['at'])>=START)
 # This subset is a pricing-only view of the same raw/rights sources. The
 # strategy's fixed1709/90 market clock was not replaced or recomputed.
 _,market,facts=J.M.context(END,ids=sorted(ids));cache={}
 def price(sid,day):
  key=sid,day
  if key not in cache:
   at=J.M.N.iso(day+'T15:10:00+08:00');cache[key]=market.latest_mark(sid,at).cny_price(at)
  return cache[key]
 state_manifest={x['series']:x for x in L.read(L.U/'INDUSTRY_MANIFEST.json')};states={}
 for g,r in state_manifest.items():
  frame=pd.read_parquet(r['refs']['state']);states[g]={x['day']:x for x in frame.to_dict('records') if OLD<=x['day']<=END}
 results=[];case_outputs=[];top_outputs=[]
 for ref,a in books.items():
  out=O/'analysis'/ref;old=oldbooks[ref];daily=dailies[ref];q=[r for r in daily if START<=date(r['at'])<=END];initial=next(r for r in daily if date(r['at'])==OLD);nav0=num(initial['nav']);nav1=num(a['ending_NAV']);tr=[x for x in a['trades'] if date(x['at'])>=START];journal={x['layer']:x for x in a['journal'] if x['kind']=='real_buy_fill'}
  values={};sector_values={};stock_flows=collections.defaultdict(lambda:Z);divs=collections.defaultdict(lambda:Z)
  for day,r in [(OLD,initial)]+[(date(x['at']),x) for x in q]:
   vv={s:D(n)*price(s,day) for s,n in r['positions'].items() if n};assert abs(sum(vv.values(),Z)-num(r['inventory']))<D('.00000001'),('canonical mark mismatch',ref,day)
   values[day]=vv;sv=collections.defaultdict(lambda:Z)
   for s,v in vv.items():sv[META[s]['sector_id']]+=v
   sector_values[day]=dict(sv)
  for t in tr:stock_flows[t['security_id']]+=(num(t['gross_cny']) if t['side']=='sell' else -num(t['gross_cny']))-num(t['fees_cny'])
  for x in a['audit']:
   if x['kind']=='dividend_accrual' and START<=date(x['receivable']['ex_at'])<=END:
    v=x['receivable'];divs[v['security_id']]+=num(v['net_local'])
  stocks=set(values[OLD])|set(values[END])|set(stock_flows)|set(divs)
  contribution={s:stock_flows[s]+divs[s]+values[END].get(s,Z)-values[OLD].get(s,Z) for s in stocks}
  assert abs(sum(contribution.values(),Z)-(nav1-nav0))<D('.00000001')
  oldlayers={x['id']:x for x in old['layers']};old_stock_net=collections.defaultdict(lambda:Z)
  for x in old['layers']:old_stock_net[x['sid']]+=num(x['cash'])+num(x['dividend'])+(D(x['qty'])*price(x['sid'],OLD) if x['qty'] else Z)
  observed_layer_max={}
  for r in q:
   day=date(r['at'])
   for x in r['layers']:
    net=num(x['cash'])+num(x['dividend'])+D(x['qty'])*price(x['sid'],day)
    observed_layer_max[x['id']]=max(observed_layer_max.get(x['id'],net),net)
  cohorts=collections.defaultdict(lambda:Z);layer_table=[];negative_closed_new_probe=Z;probe_loss_groups=collections.defaultdict(lambda:Z)
  for x in a['layers']:
   sid=x['sid'];end=num(x['cash'])+num(x['dividend'])+(D(x['qty'])*price(sid,END) if x['qty'] else Z);prior=oldlayers.get(x['id']);start=Z
   if prior:
    start=num(prior['cash'])+num(prior['dividend'])+(D(prior['qty'])*price(sid,OLD) if prior['qty'] else Z);cohort='inherited_winner_stock_layers' if old_stock_net[sid]>0 else 'inherited_nonpositive_stock_layers'
   else:cohort='March31_pending_intent_fill' if date(x['signal_at'])<=OLD else 'Q2_new_evidence_layer'
   delta=end-start;cohorts[cohort]+=delta
   if not prior and not x['qty'] and journal[x['id']]['pool']=='probe':
    negative_closed_new_probe-=min(Z,end)
    if end<0:probe_loss_groups['positive_then_closed_loss' if observed_layer_max.get(x['id'],Z)>0 else 'never_positive_at_saved_closes' if x['id'] in observed_layer_max else 'no_saved_close_unknown']-=end
   layer_table.append(dict(layer=x['id'],sid=sid,name=META[sid]['name'],cohort=cohort,role=a['metadata'][str(x['id'])]['role'],pool_at_fill=journal[x['id']]['pool'],Q2_net_contribution=delta,end_quantity=x['qty'],opened=x['opened'],closed=x['closed']))
  assert abs(sum(cohorts.values(),Z)-(nav1-nav0))<D('.00000001')
  ranked=sorted(contribution,key=contribution.get,reverse=True);chosen=list(dict.fromkeys(ranked[:3]+ranked[-3:]));flows=collections.defaultdict(lambda:Z);accrued=collections.defaultdict(lambda:Z);curves={s:[] for s in stocks};daily_behavior=[]
  for r in q:
   day=date(r['at']);nav=num(r['nav'])
   for t in tr:
    if date(t['at'])==day:flows[t['security_id']]+=(num(t['gross_cny']) if t['side']=='sell' else -num(t['gross_cny']))-num(t['fees_cny'])
   for x in a['audit']:
    if x['kind']=='dividend_accrual' and date(x['receivable']['ex_at'])==day:accrued[x['receivable']['security_id']]+=num(x['receivable']['net_local'])
   for s in stocks:curves[s].append(dict(day=day,contribution=flows[s]+accrued[s]+values[day].get(s,Z)-values[OLD].get(s,Z),weight=values[day].get(s,Z)/nav))
   stage_inactive=sum((v for g,v in sector_values[day].items() if not states[g][day]['E0_valid'] or states[g][day]['attempt_id'] is None),Z)
   top3=sum(sorted(sector_values[day].values(),reverse=True)[:3],Z)
   daily_behavior.append(dict(day=day,NAV=nav,exposure_pct=num(r['inventory'])/nav*100,cash_available_pct=num(r['available'])/nav*100,confirmed_committed_pct=num(r['pool_confirmed'][0])/nav*100,probe_committed_pct=num(r['pool_probe'][0])/nav*100,held_industries=len(sector_values[day]),top3_industry_share_of_inventory=top3/num(r['inventory']) if num(r['inventory']) else None,industry_no_new_attempt_but_still_held_pct=stage_inactive/nav*100))
  exit_requests={x['event_id']:x for x in a['audit'] if x['kind']=='exit_request'};fillgroups=collections.defaultdict(list)
  for x in a['audit']:
   if x['kind']=='fill' and x['receipt']['side']=='sell' and date(x['receipt']['at'])>=START:fillgroups[x['order_id']].append(x['receipt'])
  calendar=list(market.sessions['A']);idx={x.date().isoformat():n for n,x in enumerate(calendar)};latencies=[]
  for event,fs in fillgroups.items():
   req=exit_requests[event];first=min(fs,key=lambda z:z['at']);lag=idx[date(first['at'])]-idx[date(req['at'])]-1
   latencies.append(dict(sid=req['sid'],event=event,request=req['at'],first_fill=first['at'],last_observed_fill=max(x['at'] for x in fs),source_sessions_after_earliest=lag,pending_at_end=any(o['event_id']==event for o in a['exits'].values())))
  reentries=[];seen=set()
  for t in tr:
   if t['side']!='buy':continue
   j=journal[t['layer']]
   if j['budget_order'] in seen:continue
   seen.add(j['budget_order']);prior=[x for x in a['layers'] if x['sid']==t['security_id'] and x['opened']<t['at']]
   if prior and any(x['closed'] is not None and x['closed']<=t['at'] for x in prior) and not any(x['closed'] is None or x['closed']>t['at'] for x in prior):
    meta=a['metadata'][str(t['layer'])];reentries.append(dict(sid=t['security_id'],at=t['at'],shares=t['shares'],role=j['role'],pool=j['pool'],canonical_receipt=j['CP1_id'],stock_structure=meta.get('stock_structure'),industry_episode=meta['episode'],industry_attempt=meta['attempt'],previous_exit=max(x['closed'] for x in prior if x['closed'])))
  for s in chosen:
   curve=curves[s];worst=min(curve,key=lambda x:x['contribution']);held=[x for x in [initial]+q if date(x['at'])<=worst['day'] and x['positions'].get(s,0)>0];r=held[-1] if held else next(x for x in q if date(x['at'])==worst['day']);snapshot=date(r['at']);row=facts.row(s,J.M.N.iso(snapshot+'T15:10:00+08:00'));factor=facts.factor(s,J.M.N.iso(snapshot+'T15:10:00+08:00'));protection=[]
   for x in r['layers']:
    if x['sid']!=s:continue
    line=num(x['last_core_line']) if x['role']=='core' else num(x['floor'])
    protection.append(dict(layer=x['id'],role=x['role'],pool=x['pool'],qty=x['qty'],raw_mark=price(s,snapshot),raw_line=line/factor,mark_above_line_pct=(price(s,snapshot)/(line/factor)-1)*100 if line>0 else None,pending_I_exit_reference=x.get('pending_I_exit_reference',False),core_line_matches_current_I_floor=(line==num(row.i_floor)) if x['role']=='core' and not x.get('pending_I_exit_reference',False) and pd.notna(row.i_floor) else None,original_attempt=x['attempt']))
   entry=dict(reference=ref,sid=s,name=META[s]['name'],industry=META[s]['industry'],Q2_net_contribution=contribution[s],initial_marked_value=values[OLD].get(s,Z),terminal_marked_value=values[END].get(s,Z),Q2_new_buy_cash=sum((num(t['gross_cny'])+num(t['fees_cny']) for t in tr if t['security_id']==s and t['side']=='buy'),Z),Q2_fees=sum((num(t['fees_cny']) for t in tr if t['security_id']==s),Z),peak_weight_pct=max(x['weight'] for x in curve)*100,worst_observed_Q2_contribution=worst,protection_snapshot_day=snapshot,I_valid_at_protection_snapshot=bool(row.i_target),pending_sell_at_protection_snapshot=s in r['pending_sells'],protection_at_snapshot=protection,initial_held_layers=[x for x in old['layers'] if x['sid']==s and x['qty']],historical_trade_context=[t for t in old['trades'] if t['security_id']==s],trades=[t for t in tr if t['security_id']==s],daily_Q2_stock_path=curve,exit_requests_and_fills=[x for x in latencies if x['sid']==s],layer_books=[x for x in layer_table if x['sid']==s],reentries=[x for x in reentries if x['sid']==s]);top_outputs.append(entry)
  cases=[]
  for g in ('URFI881172','URFI881270','URFI881121'):
   gs={s for s in stocks if META[s]['sector_id']==g};weights=[(date(r['at']),sector_values[date(r['at'])].get(g,Z)/num(r['nav'])) for r in q];peak=max(weights,key=lambda x:x[1]);industry_prices=pd.read_parquet(J.M.O/'industry-facts'/f'{g}.parquet',columns=['raw_close']).raw_close.loc[START:END];pday=str(industry_prices.idxmax().date());buys=[t for t in tr if t['side']=='buy' and META[t['security_id']]['sector_id']==g];adds=[]
   for t in buys:
    if any(x['sid']==t['security_id'] and x['opened']<t['at'] and (x['closed'] is None or x['closed']>t['at']) for x in a['layers']):adds.append(t)
   case=dict(reference=ref,sector=g,industry=next(x['industry'] for x in META.values() if x['sector_id']==g),initial_industry_value=sector_values[OLD].get(g,Z),first_actual_buy=buys[0] if buys else None,first_same_stock_add=adds[0] if adds else None,Q2_actual_buy_cash=sum((num(t['gross_cny'])+num(t['fees_cny']) for t in buys),Z),peak_actual_weight_pct=peak[1]*100,peak_weight_day=peak[0],posterior_industry_price_peak_day=pday,weight_at_price_peak_pct=dict(weights).get(pday,Z)*100,Q2_net_contribution=sum((contribution[s] for s in gs),Z),inherited_market_stage=states[g][OLD]['stage_name'],industry_evidence_events=[dict(day=d,stage=x['stage_name'],receipt=x['receipt_id'],action=x['action']) for d,x in states[g].items() if START<=d<=END and (x['receipt'] or x['action']=='end_attempt')],actual_trades=[t for t in tr if META[t['security_id']]['sector_id']==g],evaluation_only_no_whitelist=True);cases.append(case);case_outputs.append(case)
  stocktable=[dict(sid=s,name=META[s]['name'],industry=META[s]['industry'],Q2_contribution=contribution[s],initial_marked=values[OLD].get(s,Z),terminal_marked=values[END].get(s,Z)) for s in ranked]
  oldloss=sum((num(x) for x in old['budget']['losses'].values()),Z);newloss=sum((num(x) for x in a['budget']['losses'].values()),Z)
  result=dict(reference=ref,Q2_strict_NAV_difference=nav1-nav0,sum_stock_contributions=sum(contribution.values(),Z),stock_bridge_residual=sum(contribution.values(),Z)-(nav1-nav0),cohort_contributions=dict(cohorts),cohort_residual=sum(cohorts.values(),Z)-(nav1-nav0),new_probe_origin_closed_negative_layer_loss=negative_closed_new_probe,new_probe_origin_loss_groups=dict(probe_loss_groups),intraday_unobserved_positive_unknown=True,record_only_negative_realization_plus_fee_increase=newloss-oldloss,Q2_actual_flat_reentries=len(reentries),exit_first_fill_source_session_latency=dict(collections.Counter(x['source_sessions_after_earliest'] for x in latencies)),Q2_exit_orders_with_fills=len(latencies),pending_sell_orders=len(a['exits']),actual_company_actions=dict(collections.Counter(x['kind'] for x in a['audit'] if x['kind'] in ('split','dividend_accrual') and START<=date(x.get('at',x.get('receivable',{}).get('ex_at','')))<=END)),no_single_mechanism_causal_attribution=True)
  save(out/'ATTRIBUTION_SUMMARY.json',result);save(out/'STOCK_CONTRIBUTIONS.json',stocktable);save(out/'LAYER_COHORTS.json',layer_table);save(out/'DAILY_CAPITAL_BEHAVIOR.json',daily_behavior);save(out/'EXIT_LATENCIES.json',latencies);save(out/'ACTUAL_REENTRIES.json',reentries);results.append(result)
  print('ATTRIBUTION',ref,'cohorts',J.W.canon(cohorts),'top+',[(META[s]['name'],str(contribution[s])) for s in ranked[:3]],'top-',[(META[s]['name'],str(contribution[s])) for s in ranked[-3:]],flush=True)
 save(O/'ATTRIBUTION_SUMMARY.json',results);save(O/'THREE_POSTERIOR_CASES.json',case_outputs);save(O/'TOP3_POSITIVE_AND_NEGATIVE_FULL_PATHS.json',top_outputs);save(O/'ANALYSIS_COMPLETION.json',dict(seconds=time.monotonic()-begun,pricing_only_subset=len(ids),new_account_paths=0,strict_stock_and_layer_NAV_bridges=True,original_market_marks_with_stale_corporate_action_handling=True))
if __name__=='__main__':
 try:main()
 except BaseException as e:save(O/'ANALYSIS_ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
