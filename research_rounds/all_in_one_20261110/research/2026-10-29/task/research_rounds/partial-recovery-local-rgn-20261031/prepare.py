import time
T=time.monotonic()
from shared import *
eps=csvrows(W/'partial-action-ledger-attribution-20261030/RISK_TRIM_RECOVERY_EPISODES.csv');group=defaultdict(list)
for e in eps:group[e['sector'],e['stress'],e['symbol'],e['group'],e['cycle']].append(e)
units=[];proof=[];meta=[];allcases={(sec,st):loadcase(sec,st) for sec in ['TECH','DRUG'] for st in ['base','delay1']};repro_count=0
for sec in ['TECH','DRUG']:
 ids={r['sid'] for st in ['base','delay1'] for r in allcases[sec,st]['logs'] if r['kind']=='partial_input'};feed=Feed(sec,ids)
 for stress in ['base','delay1']:
  cc=allcases[sec,stress];logs=cc['logs'];buys={};contracts={x['order_id']:x for x in logs if x['kind']=='entry_contract'};rstate={};ctrl={};recs=[];caps={};claims=[];risktrades=[];splits=[];original_reqs={(x['detail']['sid'],x['at']) for x in logs if x['kind']=='partial_event' and x['detail']['kind']=='risk_trim_request'};accdiv={x['receivable']['event_id']:x['receivable'] for x in logs if x['kind']=='dividend_accrual'};checked=0
  for x in logs:
   k=x['kind']
   if k=='reserve':buys[x['order_id']]=x
   elif k in ['split','split_fraction_floor_proxy']:
    s=x['sid']
    if s in rstate:
     z=rstate[s];ratio=D(x['ratio']);total=int(D(z['K']+z['R'])*ratio);z['R']=int(D(z['R'])*ratio);z['K']=total-z['R'];z['cap']=int(D(z['cap'])*ratio);splits.append(dict(at=x['at'],sid=s,cycle=z['cycle'],ratio=x['ratio'],cap_after=z['cap']))
   elif k=='partial_event':
    e=x['detail'];s=e.get('sid');kind=e['kind']
    if kind=='actual_role_buy':
     f=e['receipt'];fr=next(y for y in logs if y['kind']=='fill' and y['receipt']['receipt_id']==f['receipt_id']);z=rstate.get(s)
     if e['action']=='initial':
      if z is None:z=dict(K=0,R=0,cap=0,group=e['group'],cycle=f['receipt_id'],floor=float(contracts[fr['order_id']]['floor_signal']));rstate[s]=z;ctrl[s]=None
     z.update(K=e['K'],R=e['R'],cap=e['cap'])
     if e['action']=='risk_restore' and (ctrl[s] is None or ctrl[s].phase=='CLOSED'):ctrl[s]=RB.RiskBoundary(cycle_id=f['receipt_id'],symbol=s,source_id=z['group'],unit_id=z['group'],shares=z['R'],e0_floor=float(contracts[fr['order_id']]['floor_signal']))
    elif kind=='risk_trim_request':
     z=rstate[s];caps[s,e['at']]=dict(q=z['R'],cap=z['cap'],group=z['group'],cycle=z['cycle'])
    elif kind=='actual_role_sell':
     f=e['receipt'];z=rstate[s];rq=z['R']-e['R'];risktrades.append(dict(at=e['at'],sid=s,cycle=z['cycle'],action=e['action'],q=rq,gross=D(f['gross_cny'])*D(rq)/f['shares'],fee=D(f['fees_cny'])*D(rq)/f['shares'],receipt=f['receipt_id']));z.update(K=e['K'],R=e['R'])
     if ctrl[s] is not None:ctrl[s].sync_execution(shares=z['R'],buy_pending=False,exit_order_pending=False)
     if z['K']+z['R']==0:rstate.pop(s);ctrl.pop(s,None)
    elif kind=='role_dividend':
     z=rstate[s];raw=accdiv[e['event_id']];claims.append(dict(raw,net_local=e['risk'],cycle=z['cycle'],sid=s))
   elif k=='partial_input':
    s=x['sid'];di=x['diagnostic']
    if 'cycle_id' not in di:continue
    z=rstate[s];assert z['R']==di['shares'];c=ctrl[s]
    if c is None:c=RB.RiskBoundary(cycle_id=z['cycle'],symbol=s,source_id=z['group'],unit_id=z['group'],shares=z['R'],e0_floor=z['floor']);ctrl[s]=c
    # Actual share/order flags are original external input snapshots, not copied decisions.
    c.sync_execution(shares=z['R'],buy_pending=di['buy_pending'],exit_order_pending=di['exit_order_pending']);day=x['at'][:10];ob=feed.obs(s,day,z['group']);fr=feed.row(s,day);full=(fr is not None and pd.notna(fr.i_target) and not bool(fr.i_target)) or not cc['act'][x['at']]['on'];neg=RB.NegativeReceipt(f'{s}|source={ob["segment"]}|confirmed={day}|native_event=-1',s,z['group'],stamp(x['at']).date().toordinal()) if ob['event']==-1 and ob['source_known'] else None;sig=feed.sigma(s,day,ob['segment']) if neg else None
    out=c.on_close(bar=stamp(x['at']).date().toordinal(),raw_close=ob['raw_close'],factor=ob['factor'],unit_id=z['group'],negative=neg,sigma=sig,updated_floor=ob['floor'],floor_known=ob['floor_known'],event_feed_known=ob['event_known'],original_exit=full)
    for field in ['cycle_id','phase','boundary','anchor','sigma','e0_floor','exit_locked','exit_reason','intent_count','episodes','note','protection_after']:
     assert out[field]==di[field],(sec,stress,s,x['at'],field,out[field],di[field])
    checked+=1
  proof.append(dict(sector=sec,stress=stress,recorded_state_closes_exact=checked,actual_budgets_and_fills_source=str(cc['root']/'accounts-v2'/f'{aid(sec,stress)}.json'),conditional_input_reproduction_not_new_account=True));print('ACTUAL_R_STATE_EXACT',proof[-1],flush=True);repro_count+=checked
  for key,ee in group.items():
   if key[:2]!=(sec,stress):continue
   first=min(ee,key=lambda e:e['request_at']);s=first['symbol'];start=first['request_at'];end=first['cycle_end'] or cc['ds'][-1]['at'];seed=first['flat_at'] or end;z=caps[s,start];pi=next(x for x in logs if x['kind']=='partial_input' and x['sid']==s and x['at']==start);B=pi['diagnostic']['boundary'];assert B is not None;cap=z['cap']
   for a in splits:
    if a['cycle']==z['cycle'] and start<a['at']<=seed:cap=a['cap_after']
   cl=[a for a in claims if a['cycle']==z['cycle'] and a['ex_at']<=seed and (a['ex_at']>start or not a.get('paid_at') or a['paid_at']>start)];initial_claim=sum((D(a['net_local']) for a in cl if a['ex_at']<=start),Z);cashdiv=sum((D(a['net_local']) for a in cl if a.get('paid_at') and a['paid_at']<=seed),Z);pending=[a for a in cl if not a.get('paid_at') or a['paid_at']>seed];sales=[a for a in risktrades if a['cycle']==z['cycle'] and start<=a['at']<=seed];sold=sum((a['gross']-a['fee'] for a in sales),Z);fees=sum((a['fee'] for a in sales),Z);r0=feed.row(s,start[:10]);initial=D(z['q'])*D(str(r0.raw_close))+initial_claim
   unit=dict(unit_id=f'{sec}|{stress}|{s}|{z["cycle"]}',sector=sec,stress=stress,symbol=s,name=first['name'],group=z['group'],cycle=z['cycle'],request_at=start,seed_at=seed,end_at=end,stop_signal=first['window_end'],old_B=B,risk_q_at_request=z['q'],target_cap_at_seed=cap,initial_equity=initial,initial_unpaid_claim=initial_claim,seed_cash=sold+cashdiv,seed_claims=pending,prefix_fees=fees,prefix_sales=sales,actionable=bool(first['flat_at']),source_request=first['order_id'],merged_requests=len(ee));units.append(unit)
assert len(units)==101
save(O/'ACTUAL_R_REPRODUCTION.json',dict(passed=True,closes=repro_count,receipts=proof));save(O/'UNITS.json',units);export(O/'FROZEN_101_UNITS.csv',[{k:v for k,v in u.items() if k not in ['seed_claims','prefix_sales']} for u in units]);save(O/'PREPARE_TIME.json',dict(seconds=time.monotonic()-T,units=len(units),active=sum(u['actionable'] for u in units)));print('PREPARED',len(units),time.monotonic()-T,flush=True)
