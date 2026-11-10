"""Independent information/CP confirmation and donor chronology audit. No strategy rerun."""
from pathlib import Path
import sys,json,copy
from decimal import Decimal as D
from collections import defaultdict,Counter
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;run=Path(sys.argv[1]);read=lambda p:json.loads(Path(p).read_text())
# Reuse only our independent data/fee definitions. The audit trade loop is not executed.
src=(O/'reconcile_mainline.py').read_text().split('for row in ledger:')[0];exec(compile(src,str(O/'reconcile_mainline.py'),'exec'),globals())
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');K=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet');RT=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/RIGHT3.parquet');pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',columns=['sid','day','state']);pv=pv.pivot(index='day',columns='sid',values='state').reindex(index=K.index,columns=K.columns);known=K&pv.ge(0);right=known&RT;cal=K.index
facts={s:pd.read_parquet(manifest[s]['refs']['facts']) for s in raw};sourcecp={s:pd.read_parquet(manifest[s]['refs']['CP1']) for s in raw};evidence=pd.read_csv(O/(run.name+'_INDEPENDENT_M_EVIDENCE.csv')).set_index(['day','sector51']);confirm=read(run/'INFORMATION_CONFIRMATIONS.json');transfers=read(run/'TRANSFERS.json');cplog=read(run/'CP_EVENTS.json');proofs={x['proof_id']:x for x in confirm if x['phase']=='CLOSE'};hday=byday(holdings);tday=byday(transfers);cday=byday(confirm);CPday=byday(cplog)
def truth(x):return pd.notna(x) and x in (True,1)
def false(x):return pd.notna(x) and x in (False,0)
def stock(s,t):return int(right.at[pd.Timestamp(t),s]) if known.at[pd.Timestamp(t),s] else -1
def lin(z):return tuple(str(z[c]) for c in ['source_kind','source_path','segment_id'])
def nextday(t):return str(cal[cal.get_loc(pd.Timestamp(t))+1].date())
def applytr(st,flows,tr):
 rid=tr['round_id'];flows[rid]+=D(tr['cash_delta'])
 if tr['side'].startswith('BUY'):st[tr['lot_id']]=dict(sid=tr['sid'],rid=rid,q=tr['qty'],kind=tr['side'][4:],bought=tr['day'])
 else:
  qq=tr.get('lot_quantities') or {lid:st[lid]['q'] for lid in tr['lots']}
  for lid,q in qq.items():st[lid]['q']-=q
  st0={k:v for k,v in st.items() if v['q']};st.clear();st.update(st0)
def quantity(st,rid):return sum(x['q'] for x in st.values() if x['rid']==rid)
def net(st,flows,divs,rid,s,d,field):
 q=quantity(st,rid);p=price(s,d,field)*D('.9995');return flows[rid]+divs[rid]+q*p-fee(s,d,q,p,'sell')
def cpok(rid,cid,s,t,field,state,invalid):
 if state.get(rid)!=cid or cid in invalid:return False
 cp=cpcreated[cid];z=raw[s].loc[pd.Timestamp(t)];return lin(z)==lin(raw[s].loc[pd.Timestamp(cp['day'])]) and price(s,t,field)*price(s,t,'adjustment_factor')>D(cp['candidate'])
st={};flows=defaultdict(lambda:D(0));divs=defaultdict(lambda:D(0));hist=defaultdict(bool);adds=Counter();latest={};invalid=set();pending={};previous_h={};states_by_close={};actual_open={};actual_close={};unfunded=[]
for d in sorted(ld):
 today=od.get(d,[]);mandatory=[x for x in today if x['side'].startswith('SELL') and not x.get('transfer_rank')]
 for tr in mandatory:applytr(st,flows,tr)
 for x in ed.get(d,[]):
  if x['event']=='ACCRUE_NET80':divs[x['round_id']]+=D(x['receivable_delta'])
 for x in CPday.get(d,[]):
  if x['phase']=='OPEN' and x['event']=='INVALIDATED':equal('OPEN_CP_invalidation_current',latest.get(x['round_id']),x['cp_id'],x['cp_id']);invalid.add(x['cp_id'])
 openc={x['proof_id']:x for x in cday.get(d,[]) if x['phase']=='OPEN'}
 equal('next_OPEN_confirms_every_prior_proof',set(openc),set(pending),d)
 for pid,proof in pending.items():
  x=openc.get(pid)
  if x is None:continue
  rid=proof['round_id'];s=proof['sid'];cid=proof['cp_id'];q=quantity(st,rid);left=[h for lid,h in previous_h.items() if lid in st and h['round_id']==rid];reason='PASS';ifloor=next((D(h['protection_signal']) for h in left if h['kind']=='SEED'),D(0));n=net(st,flows,divs,rid,s,d,'raw_open')
  if not q or any(h['locked_exit'] for h in left):reason='EXIT_OR_NO_POSITION'
  elif not cpok(rid,cid,s,d,'raw_open',latest,invalid):reason='CP_INVALID_OR_REPLACED'
  elif price(s,d,'raw_open')*price(s,d,'adjustment_factor')<=max(ifloor,D(cpcreated[cid]['candidate'])):reason='OPEN_BELOW_PROTECTION'
  elif n<=0:reason='OPEN_NET_NOT_POSITIVE'
  equal('OPEN_confirmation_exact_reason',x['reason'],reason,[d,rid]);equal('OPEN_same_proof_and_CP',x['cp_id'],cid,[d,rid]);equal('OPEN_next_common_date',d,nextday(proof['day']),rid)
  if reason=='PASS':hist[rid]=True
  equal('confirmed_history_monotone_and_no_resurrection',x['confirmed_history'],hist[rid],[d,rid]);equal('confirmation_independent_actual_ADD_count',x['actual_add_count'],adds[rid],[d,rid]);equal('confirmation_does_not_require_funding',x['capacity_or_funding_required'],False,[d,rid])
  if reason=='PASS' and not any(t['round_id']==rid and t['side']=='BUY_ADD' for t in today):unfunded.append(dict(day=d,round_id=rid,net=str(n),had_prior_ADD=adds[rid]>0))
 actual_open[d]=dict(st=copy.deepcopy(st),flows=dict(flows),div=dict(divs),hist=dict(hist),adds=dict(adds),latest=dict(latest),invalid=set(invalid))
 for tr in today:
  if tr in mandatory:continue
  if tr['side']=='BUY_ADD':equal('ADD_after_history_confirmation',hist[tr['round_id']],True,tr['order_seq']);adds[tr['round_id']]+=1
  applytr(st,flows,tr)
 for x in CPday.get(d,[]):
  rid=x['round_id'];cid=x['cp_id'];event=x['event']
  if x['phase']=='OPEN' and event=='INVALIDATED':continue
  if event=='CONSUMED_ON_FILL':
   equal('consume_exactly_actual_ADD',sum(t['side']=='BUY_ADD' and t['cp_id']==cid for t in today),1,cid);equal('consume_latest_CP',latest.get(rid),cid,cid);latest[rid]=None
  elif event=='INVALIDATED':equal('CLOSE_CP_invalidation_current',latest.get(rid),cid,cid);invalid.add(cid)
  elif event=='SUPERSEDED':equal('CP_supersedes_current',latest.get(rid),cid,cid);latest[rid]=None
  elif event=='CREATED_AFTER_SEED':
   s=x['sid'];ts=pd.Timestamp(x['day']);equal('CP_source_receipt',truth(sourcecp[s].at[ts,'receipt']),True,cid);equal('CP_source_floor',D(x['candidate']),D(str(sourcecp[s].at[ts,'candidate'])),cid);equal('CP_post_actual_seed',x['day']>=seed[rid]['day'],True,cid);latest[rid]=cid
 hs={h['lot_id']:h for h in hday.get(d,[])};rr=defaultdict(list)
 for h in hs.values():rr[h['round_id']].append(h)
 closec={x['round_id']:x for x in cday.get(d,[]) if x['phase']=='CLOSE'};expected=set()
 for rid,ll in rr.items():
  s=ll[0]['sid'];f=facts[s].loc[pd.Timestamp(d)];c=sourcecp[s].loc[pd.Timestamp(d)];ev=evidence.loc[(d,mapping[s])];cid=latest.get(rid);n=net(st,flows,divs,rid,s,d,'raw_close');legal=not any(h['locked_exit'] for h in ll) and truth(f.get('i_target')) and pd.notna(f.get('i_floor')) and f.i_floor>0 and ev.state!=-1 and ev.M==1 and (truth(c.get('receipt')) or false(c.get('receipt'))) and cid is not None and cpok(rid,cid,s,d,'raw_close',latest,invalid) and n>0
  if legal:
   expected.add(rid);x=closec.get(rid);equal('every_CLOSE_nonfunding_pass_gets_proof',x is not None,True,[d,rid])
   if x:
    equal('CLOSE_CP_matches_current',x['cp_id'],cid,[d,rid]);equal('CLOSE_net_independent',D(x['close_net']),n,[d,rid]);equal('CLOSE_history_not_provisionally_promoted',x['confirmed_history'],hist[rid],[d,rid]);equal('CLOSE_actual_ADD_count',x['actual_add_count'],adds[rid],[d,rid])
  else:equal('no_proof_without_all_nonfunding_conditions',rid in closec,False,[d,rid])
 equal('CLOSE_proof_population_exact',set(closec),expected,d);pending={x['proof_id']:x for x in closec.values()};actual_close[d]=dict(st=copy.deepcopy(st),flows=dict(flows),div=dict(divs),hist=dict(hist),adds=dict(adds),latest=dict(latest),invalid=set(invalid));states_by_close[d]=dict(proofs=set(closec),holdings=hs);previous_h=hs
# Independently reconstruct eligible donor universe and frozen ordering for every CLOSE.
plans={};details=[]
for d in sorted(ld):
 hs=states_by_close[d]['holdings'];snap=actual_close[d];groups=defaultdict(list)
 for h in hs.values():groups[h['round_id']].append(h)
 universe=[]
 for rid,ll in groups.items():
  s=ll[0]['sid'];ev=evidence.loc[(d,mapping[s])];stt=stock(s,d)
  if any(h['locked_exit'] for h in ll) or ev.M==1:continue
  seedok=not snap['hist'].get(rid,False) and rid not in states_by_close[d]['proofs'] and not snap['adds'].get(rid,0) and ev.M==0 and ev.state in [0,1] and stt in [0,1] and pd.notna(ev.E)
  for h in ll:
   if nextday(d)<=h['bought']:continue
   if seedok and h['kind']=='SEED':universe.append(((0,stt!=0,float(ev.E),seed[rid]['day'],s,h['lot_id']),h,'UNCONFIRMED_NON_MAINLINE_SEED'))
   elif ev.W and h['kind']=='ADD':universe.append(((1,False,0,h['bought'],s,h['lot_id']),h,'WEAK_SECTOR_ADD_LAYER'))
 universe.sort(key=lambda x:x[0]);rows=[x for x in tday[d] if x['event']=='DONOR_PLANNED'];dp=next(x for x in tday[d] if x['event']=='DEMAND_PLAN');gap=D(dp['initial_gap']);equal('donors_only_positive_M_demand_and_gap',not rows or (D(dp['M_desired_cost'])>0 and gap>0),True,d);equal('CLOSE_gap_cash_reserve_formula',gap,max(D(0),D(dp['M_desired_cost'])+D(dp['reserve'])-D(dp['cash_after_known_protection'])) if D(dp['M_desired_cost'])>0 else D(0),d)
 for i,x in enumerate(rows):
  equal('frozen_donor_rank',x['rank'],i+1,[d,x['sid']]);equal('eligible_donor_order',x['lot_id'],universe[i][1]['lot_id'],[d,i]);h=hs[x['lot_id']];equal('donor_reason_matches_source',x['reason'],universe[i][2],[d,x['sid']]);equal('donor_max_within_lot',0<x['max_q']<=h['qty'],True,[d,x['sid']]);equal('donor_prior_gap',D(x['gap_before']),gap,[d,x['sid']]);p=price(x['sid'],d,'raw_close')*D('.9995');pro=x['max_q']*p-fee(x['sid'],nextday(d),x['max_q'],p,'sell');equal('CLOSE_net_sale_estimate',D(x['close_estimated_net']),pro,[d,x['sid']]);gap=max(D(0),gap-pro);equal('CLOSE_gap_after_donor',D(x['remaining_gap']),gap,[d,x['sid']]);plans[(d,x['lot_id'])]=x
 equal('CLOSE_gap_after_all_donors',D(dp['remaining_gap']),gap,d)
 for x in [x for x in tday[d] if x['event']=='DONOR_EXECUTION']:
  key=(x['signal_day'],x['lot_id']);plan=plans.get(key);equal('donor_execution_preplanned',plan is not None,True,[d,x['sid']]);equal('donor_next_common_OPEN',d,nextday(x['signal_day']),[d,x['sid']]);equal('OPEN_donor_cannot_expand',0<=x['executed_q']<=plan['max_q'],True,[d,x['sid']]);tr=[t for t in od.get(d,[]) if t.get('transfer_rank')==x['rank']]
  equal('donor_trade_exists_iff_execution',len(tr),int(x['executed_q']>0),[d,x['sid']])
  if tr:equal('donor_exact_trade_qty',tr[0]['qty'],x['executed_q'],[d,x['sid']]);equal('donor_exact_trade_lot',tr[0]['lots'],[x['lot_id']],[d,x['sid']])
 tc=next(x for x in tday[d] if x['event']=='TRANSFER_CASH');fund=next(x for x in tday[d] if x['event']=='RECEIVER_FUNDING');trs=[x for x in od.get(d,[]) if x.get('transfer_rank')];released=sum((D(x['cash_delta']) for x in trs),D(0));equal('transfer_net_proceeds_actual_fees',D(tc['net_cash_released']),released,d);equal('receiver_released_cash_same',D(fund['released_cash']),released,d);equal('released_cash_only_when_M_demand',not trs or D(tc['M_desired_cost'])>0,True,d);equal('OPEN_gap_reduction_exact',D(tc['remaining_gap']),max(D(0),D(tc['initial_gap'])-released),d)
 details.append(dict(day=d,planned_donors=len(rows),executed_donors=len(trs),net_released=str(released),main_buy_cost=fund['M_actual_buy_cost'],remaining_frozen_reserve=fund['cash_above_frozen_reserve']))
# Rebuild legal receiver demand, before cash, from actual previous-CLOSE requests.
requestday=byday(read(run/'FUNDING_REQUESTS.json'));days=sorted(ld)
def demand_independent(reqs,d,field,snap,nav,sv,hold):
 total=D(0);details=[];sv=dict(sv)
 for r in reqs:
  if r['M']!=1:continue
  sid=r['sid'];rid=r.get('round_id');q=0;reason='PASS';rawp=price(sid,d,field);p=rawp*D('1.0005');plan=r['plan_day'];qq=quantity(snap['st'],rid) if rid else 0;rr=[h for h in hold.values() if h['round_id']==rid and h['lot_id'] in snap['st']];fl=next((D(h['protection_signal']) for h in rr if h['kind']=='SEED'),D(0));netv=None
  if r['event']=='ADD':
   if not qq or any(h['locked_exit'] for h in rr):reason='LOCKED_EXIT'
   elif not cpok(rid,r['cp_id'],sid,d,field,snap['latest'],snap['invalid']):reason='CP_INVALID_OR_REPLACED'
   else:
    netv=net(snap['st'],defaultdict(lambda:D(0),snap['flows']),defaultdict(lambda:D(0),snap['div']),rid,sid,d,field)
    if netv<=0:reason='OPEN_NET_NOT_POSITIVE' if field=='raw_open' else 'CLOSE_NET_NOT_POSITIVE'
    elif rawp*price(sid,d,'adjustment_factor')<=max(fl,D(cpcreated[r['cp_id']]['candidate'])):reason='BELOW_PROTECTION'
   n0=D(attempts[rid]['nav0']);qprev=quantity(actual_close[plan]['st'],rid);closebudget=min(D('.02')*n0,max(D(0),D('.04')*n0-qprev*price(sid,plan,'raw_close')));budget=min(closebudget,max(D(0),D('.04')*n0-qq*rawp))
  else:
   if any(x['sid']==sid for x in snap['st'].values()):reason='ALREADY_HELD'
   ff=facts[sid].loc[pd.Timestamp(r['signal_day']):pd.Timestamp(plan)];floors=[D(str(v.i_floor)) for _,v in ff.iterrows() if truth(v.get('i_target')) and pd.notna(v.get('i_floor')) and v.i_floor>0];floor=max(floors)
   if reason=='PASS' and rawp*price(sid,d,'adjustment_factor')<=floor:reason='OPEN_BELOW_PROTECTION'
   budget=D('.02')*D(ld[r['signal_day']]['NAV'])
  caps={'attempt_budget':budget,'stock_cap':max(D(0),D('.1')*nav-sv.get(sid,D(0)))};capacity=int(raw[sid].raw_volume[raw[sid].raw_volume.gt(0)].loc[:pd.Timestamp(plan)].tail(20).mean()*.01);qr=version(rules['quantity_versions'][sid],d)['rule']
  if reason=='PASS':
   if r['event']=='SEED':
    q=qr['buy_minimum']
    if q>r['planned_q'] or q>capacity:reason='DATED_LOT_OR_CAPACITY_CHANGED'
    elif q*p+fee(sid,d,q,p,'buy')>min(caps.values()):reason='MIN_LOT_CAPITAL_REJECT:'+min(caps,key=caps.get)
   else:
    q=size(sid,d,p,min(caps.values()),min(r['planned_q'],capacity))
    if not q:reason='ADD_NO_LEGAL_Q:'+min(caps,key=caps.get)
  if reason!='PASS':q=0
  cost=q*p+fee(sid,d,q,p,'buy') if q else D(0);total+=cost;sv[sid]=sv.get(sid,D(0))+cost;details.append(dict(sid=sid,kind=r['event'],q=q,cost=str(cost),reason=reason))
 return total,details
for idx,d in enumerate(days):
 if idx==0:priorcash=D(1200000);priorrecv=D(0)
 else:priorcash=D(ld[days[idx-1]]['cash']);priorrecv=D(ld[days[idx-1]]['receivable'])
 mandatory=[x for x in od.get(d,[]) if x['side'].startswith('SELL') and not x.get('transfer_rank')];cash0=priorcash+sum((D(x['cash_delta']) for x in mandatory),D(0));recv0=priorrecv+sum((D(x['receivable_delta']) for x in ed.get(d,[]) if x['event']=='ACCRUE_NET80'),D(0));snap=actual_open[d];sv=defaultdict(lambda:D(0))
 for l in snap['st'].values():sv[l['sid']]+=l['q']*price(l['sid'],d,'raw_open')
 nav=cash0+recv0+sum(sv.values());hold=states_by_close[days[idx-1]]['holdings'] if idx else {};desired,detail=demand_independent(requestday.get(d,[]),d,'raw_open',snap,nav,sv,hold);tc=next(x for x in tday[d] if x['event']=='TRANSFER_CASH')
 equal('OPEN_legal_M_demand_exact',D(tc['M_desired_cost']),desired,d);equal('OPEN_all_receiver_details',[(x['sid'],x['kind'],x['q'],D(x['cost']),x['reason']) for x in tc['receivers']],[(x['sid'],x['kind'],x['q'],D(x['cost']),x['reason']) for x in detail],d);equal('OPEN_gap_includes_existing_reserve_deficit',D(tc['initial_gap']),max(D(0),desired+D('.1')*nav-cash0) if desired>0 else D(0),d)
 # Last CLOSE's receiver request has not executed yet; its eligibility was audited above.
 if idx==len(days)-1:continue
 snap=actual_close[d];sv=defaultdict(lambda:D(0));cash0=D(ld[d]['cash']);nav=D(ld[d]['NAV']);hold=states_by_close[d]['holdings'];bysid=defaultdict(list)
 for h in hold.values():sv[h['sid']]+=h['qty']*price(h['sid'],d,'raw_close');bysid[h['sid']].append(h)
 for sid,ll in bysid.items():
  qty=sum(h['qty'] for h in ll if h['locked_exit'] and nextday(d)>h['bought'])
  if qty:p=price(sid,d,'raw_close')*D('.9995');cash0+=qty*p-fee(sid,nextday(d),qty,p,'sell');sv[sid]-=qty*price(sid,d,'raw_close')
 desired,detail=demand_independent(requestday.get(days[idx+1],[]),d,'raw_close',snap,nav,sv,hold);dp=next(x for x in tday[d] if x['event']=='DEMAND_PLAN');equal('CLOSE_receiver_demand_independent',D(dp['M_desired_cost']),desired,d);equal('CLOSE_cash_includes_PAY_and_known_protection',D(dp['cash_after_known_protection']),cash0,d);equal('CLOSE_reserve_independent',D(dp['reserve']),D('.1')*nav,d)
# Incremental known-floor arithmetic is not a stop-fill guarantee.
risk_rows=[];risk_source={x['cp_id']:x for x in read(run/'ADD_FLOOR_RISK.json')}
for tr in orders:
 if tr['side']!='BUY_ADD':continue
 d=tr['day'];prev=str(cal[cal.get_loc(pd.Timestamp(d))-1].date());h=next(x for x in hday[prev] if x['round_id']==tr['round_id'] and x['kind']=='SEED');floor=max(D(h['protection_signal']),D(cpcreated[tr['cp_id']]['candidate']));p=floor/price(tr['sid'],d,'adjustment_factor')*D('.9995');loss=D(tr['all_in_cost'])-(tr['qty']*p-fee(tr['sid'],d,tr['qty'],p,'sell'));x=risk_source[tr['cp_id']];equal('ADD_known_floor_loss_independent',D(x['incremental_known_floor_loss']),loss,tr['order_seq']);risk_rows.append(dict(day=d,sid=tr['sid'],round_id=tr['round_id'],buy_cost=tr['all_in_cost'],open_profit=tr['open_net'],incremental_floor_loss=str(loss),not_profit_covered=loss>D(tr['open_net'])))
(O/(run.name+'_INDEPENDENT_ADD_FLOOR_RISK.json')).write_text(json.dumps(dict(actual_ADD_count=len(risk_rows),not_profit_covered=sum(x['not_profit_covered'] for x in risk_rows),rows=risk_rows,limitations='Exact-known-floor hypothetical cost only. T+1, opening gaps and unverified auction matching may make actual losses larger.'),ensure_ascii=False,indent=2)+'\n')
final_attempts=read(run/'ATTEMPTS.json')
for a in final_attempts:equal('final_confirmed_history_matches_timeline',a.get('confirmed_history',False),hist[a['id']],a['id'])
rep=dict(status='PASS' if not errors else 'FAIL',run=str(run),checks=dict(checks),check_count=sum(checks.values()),error_count=len(errors),errors=errors,confirmed_OPEN_records=sum(x['decision']=='INFORMATION_CONFIRMED' for x in confirm),withdrawn_OPEN_records=sum(x['decision']=='PROVISIONAL_WITHDRAWN' for x in confirm),confirmed_without_same_OPEN_ADD=len(unfunded),zero_actual_ADD_confirmation_without_same_OPEN_ADD=sum(not x['had_prior_ADD'] for x in unfunded),distinct_confirmed_rounds=len({x['round_id'] for x in confirm if x['decision']=='INFORMATION_CONFIRMED'}),distinct_zero_actual_ADD_unfunded_rounds=len({x['round_id'] for x in unfunded if not x['had_prior_ADD']}),unfunded_confirmation_records=unfunded,daily_transfer_bridge=details,limitations=['This verifies frozen conditional accounting and evidence chronology, not real auction liquidity.','Information confirmation still uses the weak positive-whole-round-profit gate, not robust downside coverage.'])
(O/(run.name+'_CONFIRMATION_TRANSFER_AUDIT.json')).write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in rep.items() if k not in ['checks','unfunded_confirmation_records','daily_transfer_bridge']},ensure_ascii=False,indent=2))
