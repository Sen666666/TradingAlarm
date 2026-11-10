"""Match isolated candidate labels to actual existing same-sector wealth.
No portfolio policy, order, or donor selection is implemented here.
"""
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
from decimal import Decimal as D
import argparse, gzip, hashlib, json, sys, time
import pandas as pd

O=Path(__file__).resolve().parent; OUT=O; W=O.parent; SOURCES={}; ZERO=D(0)
sys.path.insert(0,str(W/'new_price_trend_v1'))
import native_mark_reader as MARK
LR=MARK.E.J.LR
RULES=MARK.rules; RULECACHE={}; OPENMARK={}

def bind(p):
 p=Path(p);SOURCES[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def load(p,lines=False):
 with gzip.open(bind(p),'rt')as h:return list(map(json.loads,h))if lines else json.load(h)
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def num(x):return D(str(x))
def effective(xs,day):return next(x for x in reversed(xs)if x['from']<=day and(x.get('to')is None or day<x['to']))
def fees(sid,day,qty,price):
 venue=effective(RULES['venue_versions'][sid],day)['venue'];z=effective(RULES['fee_versions'][venue],day)['schedule']
 if z['schedule_id']not in RULECACHE:
  RULECACHE[z['schedule_id']]=LR.L.FeeSchedule(z['schedule_id'],tuple(LR.L.FeeComponent(**c)for c in z['components']))
 return LR.fees(qty,price,RULECACHE[z['schedule_id']],'sell',num(RULES['security_metadata'][sid]['par_value']))if qty else ZERO
def open_mark(sid,day):
 key=sid,day
 if key not in OPENMARK:
  if sid not in MARK.views:MARK.price(sid,day)
  at=datetime.fromisoformat(day+'T09:30:00+08:00');m=MARK.F.latest_mark(MARK.views[sid],sid,at)
  is_current=m.known_at==at and ':derived_ex_reference:'not in m.source_id
  if is_current:
   raw=MARK.views[sid].raw[sid].loc[pd.Timestamp(day),'open']
   assert m.cny_price(at)==num(raw),(sid,day,'OPEN mark must equal actual raw OPEN')
  OPENMARK[key]=(m.cny_price(at),str(m.known_at),m.source_id,is_current)
 return OPENMARK[key]
def net_liquidation(sid,day,qty,mark):
 px=mark*(D(1)-LR.SLIP)
 return qty*px-fees(sid,day,qty,px)if qty else ZERO
def quadrant(new,old):
 if new==0 or old==0:return 'zero_boundary'
 return ('new_profit'if new>0 else'new_loss')+'_'+('old_profit'if old>0 else'old_loss')

class OriginalHoldings:
 def __init__(self):
  self.final={};self.live={};self.cache={};self.pending={};self.exit_requests={};self.sell_fills={}
  for w in ['long','strong']:
   root=W/'new_price_trend_v1/funding/runs'/(w+'_OFF')/'pair'
   b=load(root/'B.json.gz');self.final[w]={int(x['id']):x for x in b['layers']}
   ds=load(root/'daily.jsonl.gz',True)
   self.live[w]={r['at'][:10]:{int(x['id']):x for x in r['layers']}for r in ds}
   self.pending[w]={r['at'][:10]:set(r['pending_sells'])for r in ds}
   requests=defaultdict(list);fills=defaultdict(list)
   for a in b['audit']:
    if a['kind']=='exit_request':requests[a['sid']].append(a)
    if a['kind']=='fill'and a['receipt']['side']=='sell':fills[a['order_id']].append(a)
   self.exit_requests[w]=requests;self.sell_fills[w]=fills
 def partial_exit_fee_unknown(self,w,sid,end):
  if sid not in self.pending[w][end]:return False
  requests=[r for r in self.exit_requests[w][sid]if r['at'][:10]<=end]
  if not requests:return True
  oid=requests[-1]['event_id']
  return any(r['receipt']['at'][:10]<=end for r in self.sell_fills[w][oid])
 def at(self,w,lid,day):
  if lid in self.live[w][day]:return self.live[w][day][lid]
  x=self.final[w][lid]
  assert num(x['qty'])==0,(w,lid,day,'old anchor layer absent before its final live end')
  assert x['closed']is None or x['closed'][:10]<=day,(w,lid,day,'future closed cash forbidden')
  return x
 def basket(self,snap,end,unlocked=False):
  ck=(snap['window'],snap['signal_day'],snap['OPEN'],snap['sector'],end,unlocked)
  if ck in self.cache:return self.cache[ck]
  w=snap['window'];start=snap['OPEN'];ls=snap['surviving_existing_layers_at_S0']
  locked=set(snap['CLOSE_account']['pending_sells'])
  if unlocked:ls=[x for x in ls if x['sid']not in locked and not x['previous_CLOSE_raw_layer'].get('reason')and not x['previous_CLOSE_raw_layer'].get('pending_I_exit_reference')]
  if not ls:
   result=dict(status='no_existing_unlocked_inventory'if unlocked else'no_existing_inventory',layers=0,stocks=0)
   self.cache[ck]=result;return result
  initialq=defaultdict(lambda:ZERO);endq=defaultdict(lambda:ZERO);cash=div=ZERO;details=[]
  for r in ls:
   lid=int(r['layer']);sid=r['sid'];a=r['next_CLOSE_raw_layer'];z=self.at(w,lid,end)
   q0=num(r['qty_after_original_actions_and_protection_exits']);qh=num(z['qty'])
   assert q0==num(a['qty']) and q0>0
   # Same-day00:00 entitlement and all existing OPEN protection sales are in a.
   # They are excluded by subtracting the S0 cumulative cash/dividend basis.
   dc=num(z['cash'])-num(a['cash']);dd=num(z['dividend'])-num(a['dividend'])
   initialq[sid]+=q0;endq[sid]+=qh;cash+=dc;div+=dd
   details.append(dict(layer=lid,sid=sid,qty_S0=q0,qty_terminal=qh,actual_sale_net_wealth_after_anchor=dc,new_dividend_entitlement_after_anchor=dd,closed=z['closed']))
  g0=l0=ending=ZERO;refs=[];stale_anchor=False;partial_fee_unknown=False
  for sid,q0 in initialq.items():
   mark,known,source,current=open_mark(sid,start);stale_anchor|=not current;g0+=q0*mark;l0+=net_liquidation(sid,start,q0,mark)
   qh=endq[sid];mh=MARK.price(sid,end)if qh else ZERO
   ending+=net_liquidation(sid,end,qh,mh)
   partial_fee_unknown|=bool(qh and self.partial_exit_fee_unknown(w,sid,end))
   refs.append(dict(sid=sid,initial_qty=q0,OPEN_mark=mark,known_at=known,source=source,exact_current_raw_OPEN=current,terminal_qty=qh,terminal_mark=mh,
                    current_quote_and_FIFO_sellability='NOT_VERIFIED_CONDITIONAL_LIQUIDATION_VALUE'))
  vh=cash+div+ending
  status='anchor_OPEN_reference_only_unknown'if stale_anchor else'terminal_partial_order_fee_unknown_conservative_value'if partial_fee_unknown else'known_actual_wealth_conditional_liquidation'
  result=dict(status=status,layers=len(ls),stocks=len(initialq),G0=g0,L0=l0,Vh=vh,
              actual_net_sale_wealth_after_anchor=cash,new_dividend_entitlement_after_anchor=div,terminal_net_liquidation=ending,
              old_net_return_from_current_gross_mark_pct=(vh/g0-1)*100 if g0>0 else None,
              old_keep_value_relative_to_sell_now_pct=(vh/l0-1)*100 if l0>0 else None,
              prior_CLOSE_locked_stock_count=len(set(initialq)&locked),unlocked_by_prior_CLOSE_only=unlocked,
              actual_tradability_and_bonus_share_unlock='NOT_COMPLETELY_KNOWN_NO_DONOR_ACTION',layers_detail=details,mark_references=refs)
  self.cache[ck]=result;return result
 def committed(self,event,commitments,end):
  keys=event['original_sameOPEN_prior_commitments']['same_sector_prior_order_keys'];fills=[]
  for key in keys:fills.extend(commitments[key]['actual_fills_after_all_funding'])
  if not fills:return dict(status='no_filled_prior_same_sector_commitment',reserved_orders=len(keys))
  cost=cash=div=ZERO;endq=defaultdict(lambda:ZERO)
  for f in fills:
   sid=f['sid'];lid=int(f['layer']);z=self.at(event['window'],lid,end)
   c=num(f['shares'])*num(f['price'])+num(f['fees']);cost+=c;cash+=num(z['cash']);div+=num(z['dividend']);endq[sid]+=num(z['qty'])
  remaining=sum((net_liquidation(s,end,q,MARK.price(s,end))for s,q in endq.items()if q),ZERO)
  value=cost+cash+div+remaining
  ambiguous=any(q and self.partial_exit_fee_unknown(event['window'],s,end)for s,q in endq.items())
  return dict(status='partial_exit_fee_unknown_conservative_committed_value'if ambiguous else'actual_committed_new_fills_Tplus1_not_rotation_donors',reserved_orders=len(keys),filled_layers=len(fills),actual_buy_cash=cost,
              terminal_wealth_from_that_buy_cash=value,net_return_from_actual_buy_cash_pct=(value/cost-1)*100 if cost else None,
              scope='Actual sameOPEN committed alternatives, not old mark/L0 comparison; all fills occur after candidate funding decision.')

def summary(rows,feature):
 groups=defaultdict(list)
 for r in rows:groups[feature(r)].append(r)
 result=[]
 for key,a in sorted(groups.items(),key=lambda x:str(x[0])):
  known=[r for r in a if r.get('matched_status')=='known_conditional_match'];gaps=[num(r['equal_cash_gap'])for r in known]
  adjusted=[num(r['release_adjusted_conditional_gap'])for r in known if r.get('release_adjusted_conditional_gap')is not None]
  newret=[num(r['new_net_return_pct'])for r in known];oldret=[num(r['old_all']['old_net_return_from_current_gross_mark_pct'])for r in known]
  def dist(v):
   v=sorted(v);n=len(v)
   return dict(n=n,mean=sum(v,ZERO)/n if n else None,median=v[n//2]if n%2 else(v[n//2-1]+v[n//2])/2 if n else None,
               p10=v[int((n-1)*.1)]if n else None,p90=v[int((n-1)*.9)]if n else None,minimum=v[0]if n else None,maximum=v[-1]if n else None)
  result.append(dict(group=key,events=len(a),matched=len(known),unmatched=dict(Counter(r.get('matched_status','missing')for r in a if r.get('matched_status')!='known_conditional_match')),
   quadrants=dict(Counter(r['quadrant']for r in known)),new_net_return_pct=dist(newret),old_net_return_pct=dist(oldret),equal_cash_gap=dist(gaps),
   required_relief_scenario_gap=dist(adjusted),required_relief_scenario_gap_positive=sum(v>0 for v in adjusted),
   matched_not_ruled_out_by_capital_bound=sum(bool(r.get('not_ruled_out_by_capital_bound'))for r in known),
   note='Descriptive repeated/overlapping experiments; money differences cannot be summed as portfolio gains.'))
 return result

def main():
 global OUT
 parser=argparse.ArgumentParser();parser.add_argument('--labels',type=Path,required=True);parser.add_argument('--out-dir',type=Path,default=O);args=parser.parse_args()
 OUT=args.out_dir.resolve();OUT.mkdir(parents=True,exist_ok=True)
 start=time.monotonic();bind(__file__);bind(O/'MATCHED_PROTOCOL.txt')
 bind(O/'RELEASE_ADJUSTED_EVALUATION_ADDENDUM.txt')
 cached=O/'release_bound/OPEN_MARK_STATUS.json'
 if cached.exists():
  for x in read(cached):
   if x.get('mark')is None:continue
   current=x['strict_OPEN_identity']
   if current:
    assert num(x['mark'])==num(x['raw_OPEN'])and datetime.fromisoformat(x['known_at'])==datetime.fromisoformat(x['OPEN']+'T09:30:00+08:00')
   OPENMARK[x['sid'],x['OPEN']]=(num(x['mark']),x['known_at'],x['source_id'],current)
  bind(O/'release_bound/SOURCE_SHA256.json')
 events={r['key']:r for r in load(O/'events/CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz',True)}
 bounds={r['key']:r for r in load(O/'release_bound/RELEASE_BOUND_EVENTS.jsonl.gz',True)}
 snaps=read(O/'events/ORIGINAL_EXISTING_LAYER_SNAPSHOTS.json');commit=read(O/'events/ACTUAL_SAMEOPEN_RESERVE_COMMITMENTS.json')
 labels=load(args.labels,True);book=OriginalHoldings();rows=[]
 for i,label in enumerate(labels):
  if time.monotonic()-start>120:
   save('MATCHED_PARTIAL_STATUS.json',dict(complete=False,rows=len(rows),total=len(labels),seconds=time.monotonic()-start,new_portfolio_policy_accounts=0));break
  event=events[label['key']];row=dict(key=label['key'],window=event['window'],sid=event['sid'],signal_day=event['signal_day'],OPEN=event['OPEN'],industry=event['industry'],
   classification=event['classification'],failure_tags=event['failure_tags'],inventory_context=event['inventory_vs_new_commitment_class'],new=label,release_bound=bounds[label['key']])
  cost=label.get('entry_cash_actual');end=label.get('horizon_CLOSE_day')
  if not label.get('known_net')or cost is None or not end or label.get('unknown_reason'):
   row['matched_status']='candidate_unfilled_or_unknown';rows.append(row);continue
  cn=num(cost)
  if cn<=0:
   row['matched_status']='candidate_unfilled_or_unknown';rows.append(row);continue
  try:
   old=book.basket(snaps[event['snapshot_key']],end);row['old_all']=old
   row['old_prior_CLOSE_unlocked']=book.basket(snaps[event['snapshot_key']],end,True)
  except MARK.native.RuleUnavailable as exc:
   row.update(matched_status='old_source_unavailable',unknown_reason=str(exc));rows.append(row);continue
  try:row['same_batch_filled_alternatives']=book.committed(event,commit,end)
  except MARK.native.RuleUnavailable as exc:
   row['same_batch_filled_alternatives']=dict(status='auxiliary_source_unavailable',unknown_reason=str(exc))
  vn=label.get('wealth_from_invested_Cn_net_liquidation')
  if old.get('status')=='known_actual_wealth_conditional_liquidation'and old.get('L0',ZERO)>0 and vn is not None:
   vn=num(vn);nr=(vn/cn-1)*100;orr=old['old_net_return_from_current_gross_mark_pct']
   row.update(matched_status='known_conditional_match',new_net_return_pct=nr,
    equal_cash_old_terminal=cn*old['Vh']/old['L0'],equal_cash_gap=vn-cn*old['Vh']/old['L0'],quadrant=quadrant(nr,orr),
    equal_cash_scaling_exceeds_entire_old_basket=cn>old['L0'],trade_feasibility='NOT_GRANTED_Normalized_basket_is_not_FIFO_sale')
   bound=bounds[label['key']]
   if bound['release_amount_status']=='KNOWN_NECESSARY_BOUND':
    assert abs(old['G0']-num(bound['old_inventory_gross']))<D('.000001'),(label['key'],'OPEN old capital identity')
    relief=num(bound['required_sector_relief_lower_bound_SAFE'])
    row.update(required_release_lower_bound=relief,
      release_adjusted_conditional_gap=(vn-cn)-(relief/old['G0'])*(old['Vh']-old['L0']),
      not_ruled_out_by_capital_bound=not(bound['relief_exceeds_nonlocked_old_upper_SAFE']or bound['qmin_itself_exceeds_sector_allowance_SAFE']),
      release_scenario_scope='Proportional basket at necessary gross-relief lower bound; not executable FIFO or portfolio gain')
  else:row['matched_status']=old.get('status','no_old_inventory_or_nonpositive_conditional_L0')
  rows.append(row)
  if(i+1)%1000==0:save('MATCHED_PROGRESS.json',dict(rows=i+1,total=len(labels),seconds=time.monotonic()-start))
 with gzip.open(OUT/'MATCHED_HOLDINGS.jsonl.gz','wt')as h:
  for r in rows:h.write(json.dumps(r,ensure_ascii=False,default=str,allow_nan=False)+'\n')
 save('MATCHED_SUMMARY.json',summary(rows,lambda r:(r['window'],r['classification'])))
 save('MATCHED_PERIOD_SUMMARY.json',summary(rows,lambda r:(r['window'],r['signal_day'][:4]if r['window']=='long'else('2026H1'if r['signal_day']>='2026-01-01'else'2025H2'))))
 save('OLD_BASKET_VALUES.json',list(book.cache.values()))
 SOURCES.update(MARK.sources);save('MATCHED_SOURCE_SHA256.json',SOURCES)
 save('MATCHED_SCOPE.json',dict(complete=len(rows)==len(labels),seconds=time.monotonic()-start,rows=len(rows),total=len(labels),new_portfolio_policy_accounts=0,new_shadow_paths_constructed_here=0,
  baseline='Actual original layers, cumulative cash/dividend differences after S0, surviving old qty and native marks; no future new layers in existing basket.',
  conditional='Net liquidation is estimated with original fees/5bps; donor FIFO/tradability/new-share unlock not fully proven. Actual old exit proceeds may be receivables; wealth is not immediately spendable cash.',
  no_portfolio_gain_claim=True))
 print(json.dumps(dict(rows=len(rows),total=len(labels),seconds=time.monotonic()-start),ensure_ascii=False))

if __name__=='__main__':main()
