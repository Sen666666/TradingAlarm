import time
START=time.monotonic()
from core import *
from dataclasses import replace
from collections import defaultdict,Counter
import signal,traceback
OUT=O/'full';OUT.mkdir(exist_ok=False);status='started'
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('120 second local compute budget')));signal.setitimer(signal.ITIMER_REAL,118)
try:
 assert read(O/'SYNTHETIC_TESTS.json')['passed'];facts=O.parent/'act-entry-path-diagnostics-20261031';cycles=S.csvrows(facts/'CYCLE_PATH_FACTS.csv');assert len(cycles)==153
 pdays=defaultdict(dict)
 for r in S.csvrows(facts/'DAILY_PATHS.csv'):
  if r['kind']=='holding_close':pdays[r['sector'],r['cycle_id']][r['day']]=r
 R=S.RR;sources={'TECH':(R/'pvr-local-finite-capital-20261029/baseline/accounts-v2/I__S0_base.json',R/'pvr-local-finite-capital-20261029/baseline/accounts-v2/daily.jsonl.gz','I__S0_base'),'DRUG':(R/'innovative-drug-local-recovery-20261028/S0/accounts-v2/ACT__S0_base.json',R/'innovative-drug-local-recovery-20261028/S0/accounts-v2/daily.jsonl.gz','ACT__S0_base')};ctx={};identity={str(p):sha(p) for p in [O/'PROTOCOL.txt',O/'core.py',Path(__file__),O/'SYNTHETIC_TESTS.json',facts/'INPUT_IDENTITY.json',facts/'CYCLE_PATH_FACTS.csv',facts/'DAILY_PATHS.csv',W/'partial-recovery-local-rgn-20261031/shared.py']}
 for sec,(ap,dp,aid) in sources.items():
  identity[str(ap)]=sha(ap);identity[str(dp)]=sha(dp);logs=read(ap)['audit_log'];cs=[c for c in cycles if c['sector']==sec];ids={c['symbol'] for c in cs};m=S.market(sec,ids)
  with gzip.open(dp,'rt') as f:ds={x['at'][:10]:x for line in f if (x:=json.loads(line))['account']==aid}
  ctx[sec]=dict(m=m,logs=logs,ds=ds,ids=ids)
 # The preceding diagnostic manifest pins cached prices/actions/signals; no metric or full-account recomputation.
 old=read(facts/'INPUT_IDENTITY.json');assert all(sha(p)==h for p,h in old['sha256'].items())
 identity.update(old['sha256']);save(O/'FREEZE.json',dict(at=str(datetime.now().astimezone()),before_B_economics=True,prior_path_information_seen=True,arms=['A','B10','B20','B30'],mother_ids=[(c['sector'],c['cycle_id']) for c in cycles],sha256=identity))
 results=[];flows=[];curves=[];controls=[]
 def replay(c,arm,b=None):
  sec=c['sector'];cid=c['cycle_id'];s=c['symbol'];m=ctx[sec]['m'];logs=ctx[sec]['logs'];entry=stamp(c['entry_at']);end=at(c['endpoint'][:10]);K=D(c['basis']);q0=int(c['initial_shares']);nextop=m.sessions['A'][bisect.bisect_right(m.sessions['A'],entry)];quote=m.quote(s,entry);assert quote
  a=L.SectorAccount(initial_cash=K,fractional_split_policy=m.protocol['fractional_split_policy']);a.available=Z;a.positions[s]=L.Position(s,quote.issuer_id,quote.sector_id,quote.currency,[L.InventoryLot(q0,nextop)]);book=Book(q0);ctrl=Budget(K,b) if b is not None else None
  original=[x['at'][:10] for x in logs if x['kind']=='exit_request' and x['sid']==s and entry<=stamp(x['at'])<=end];assert len(original)==int(c['closed']=='True');origday=original[0] if original else None;newday=None;newV=None;newNAV=None;submit=None;clear=None;clearNAV=None;wait=0;coincidence=False;unknown=[];execution=[];local=[];peak=K;dd=Z
  def snap(t,phase):
   # Only close snapshots enter risk decisions. Book validates gross fees and all equity, including receivables.
   bal=book.check(a,m,s,t);return bal
  for day in ctx[sec]['ds']:
   if day<entry.date().isoformat() or day>end.date().isoformat():continue
   op=at(day,9,30);cl=at(day)
   if day>entry.date().isoformat():
    for action in m.actions.get(s,[]):
     if action['effective_date']==day:H.action(a,m,s,action)
    H.pay(a,m,op)
    if s in a.exits:
     qb=a.quantity(s);w=m.window(s,op,'sell',1);fill=a.fill_exit(s,w) if w else None;execution.append(dict(at=op,shares_before=qb,shares_after=a.quantity(s),window_known=w is not None,sell_allowed=w.sell_allowed if w else None,capacity=w.capacity_shares if w else None,filled=fill is not None));wait+=int(newday is not None and clear is None)
     if fill and not a.quantity(s) and newday is not None:clear=str(op)
    H.pay(a,m,op)
    if clear==str(op):clearNAV=snap(op,'clear')['nav']
   H.pay(a,m,cl);bal=snap(cl,'close');q=a.quantity(s);mk=m.latest_mark(s,cl) if q else None;fee,slip=liquidation(m,s,q,mk.raw_price,cl) if q else (Z,Z);V=bal['nav']-fee-slip
   path=pdays[sec,cid].get(day);raw=m.raw[s];d=pd.Timestamp(day);known=bool(q and mk and mk.known_at.date()==cl.date() and d in raw.index and raw.loc[d,'valid_price'] and raw.loc[d,'observed_bar']);known=known and (path is None or path['price_observation_known']=='True')
   if q and not known:unknown.append(dict(day=day,kind='budget_price_or_observation_unknown'))
   original_now=day==origday
   if arm=='A':
    if original_now and q and s not in a.exits:
     qt=m.quote(s,cl);assert qt;a.request_exit(qt,A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()))
   elif q:
    if original_now and known and V<=(ONE-b)*K and not ctrl.locked:coincidence=True
    requested=ctrl.close(V=V if known else None,known=known,at=str(cl),original=original_now)
    if requested and ctrl.reason=='loss_budget':newday=day;newV=V;newNAV=bal['nav']
    if ctrl.locked and s not in a.exits:
     qt=m.quote(s,cl)
     if qt:
      a.request_exit(qt,A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()))
      if ctrl.reason=='loss_budget' and submit is None:submit=str(cl)
     else:unknown.append(dict(day=day,kind='exit_quote_unknown_locked_waiting'))
   if arm=='A' and path:
    assert a.quantity(s)==int(path['shares']);assert bal['nav']==K+D(path['net_pnl']),(sec,cid,day,bal['nav'],K+D(path['net_pnl']))
   v=bal['nav'];peak=max(peak,v);dd=max(dd,ONE-v/peak);local.append(dict(sector=sec,cycle_id=cid,arm=arm,at=cl,nav=v,liquidation_V=V,estimated_exit_fee=fee,estimated_exit_slippage=slip,shares=q,dividend=book.div,available=bal['available'],claim=bal['dividend_receivable'],sale_receivable=bal['sale_receivable'],known_price=known if q else None,exit_pending=s in a.exits))
  final=book.check(a,m,s,end);sf=a.fills;net=final['nav']-K
  if arm=='A':
   source=[x for x in logs if x['kind']=='fill' and x['receipt']['security_id']==s and x['receipt']['side']=='sell' and entry<=stamp(x['receipt']['at'])<=end];assert len(source)==len(sf)
   for x,f in zip(source,sf):assert stamp(x['receipt']['at'])==f.at and x['receipt']['shares']==f.shares and D(x['receipt']['gross_cny'])==f.gross_cny and D(x['receipt']['fees_cny'])==f.fees_cny
   assert net==D(c['final_net_pnl']),(sec,cid,net,c['final_net_pnl']);assert a.quantity(s)==int(c['exit_or_final_shares']) if c['closed']=='False' else a.quantity(s)==0
   controls.append(dict(sector=sec,cycle_id=cid,source_net=c['final_net_pnl'],reproduced_net=net,source_sell_count=len(source),reproduced_sell_count=len(sf),residual=Z))
  closed=c['closed']=='True';group=('open' if not closed else ('severe_loss' if D(c['final_net_return'])<=D('-.3') else ('other_loss' if D(c['final_net_pnl'])<0 else ('tail_profit_30pct' if D(c['final_net_return'])>=D('.3') else 'other_profit'))))
  result=dict(sector=sec,cycle_id=cid,symbol=s,name=c['name'],arm=arm,budget=b,original_group=group,closed=closed,basis=K,original_net=c['final_net_pnl'],full_cycle_net=net,final_equity=final['nav'],difference_vs_A=net-D(c['final_net_pnl']),new_trigger=newday,request_submitted=submit,trigger_NAV=newNAV,trigger_liquidation_V=newV,trigger_liquidation_return=newV/K-ONE if newV is not None else None,trigger_close_overshoot=max(Z,(ONE-b)*K-newV) if newV is not None else None,actual_cleared=clear,actual_clear_equity=clearNAV,actual_clear_return=clearNAV/K-ONE if clearNAV is not None else None,actual_budget_overshoot=max(Z,(ONE-b)*K-clearNAV) if clearNAV is not None else None,trigger_to_actual_change=clearNAV-newV if clearNAV is not None else None,waiting_execution_opens=wait,same_day_original_priority=coincidence,first_sell=str(sf[0].at) if sf else None,last_sell=str(sf[-1].at) if sf else None,sell_fills=len(sf),sold_quantity=sum(f.shares for f in sf),full_fees=D(c['basis'])-sum((D(x['receipt']['gross_cny']) for x in logs if x['kind']=='fill' and x['receipt']['security_id']==s and x['receipt']['side']=='buy' and stamp(x['receipt']['at'])==entry),Z)+book.fees,sell_fees=book.fees,dividend_equity=book.div,final_shares=a.quantity(s),terminal_claim=final['dividend_receivable'],terminal_sale_receivable=final['sale_receivable'],terminal_inventory=final['inventory'],source_unknown_dates=c['unknown_dates'],source_unknown_count=c['unknown_count'],runtime_unknown=json.dumps(unknown),max_close_drawdown=dd,max_accounting_residual=book.maxres)
  flows.append(dict(sector=sec,cycle_id=cid,arm=arm,requests=[x for x in a.audit_log if x['kind']=='exit_request'],execution=execution,fills=sf,audit=a.audit_log,initial_actual_shares=q0,initial_basis=K));curves.extend(local);return result
 for c in cycles:results.append(replay(c,'A'))
 assert len(controls)==153;save(OUT/'A_REPRODUCTION.json',dict(passed=True,cycles=153,all_daily_nav_exact=True,all_sell_fills_fees_exact=True,checks=controls));print('A_ALL153_EXACT',time.monotonic()-START,flush=True)
 for sec in ['TECH','DRUG']:
  for i,c in enumerate(x for x in cycles if x['sector']==sec):
   for arm,b in [('B10',D('.1')),('B20',D('.2')),('B30',D('.3'))]:results.append(replay(c,arm,b))
   if (i+1)%20==0:print('B_DONE',sec,i+1,time.monotonic()-START,flush=True)
 assert len(results)==612;export(OUT/'unit-ledgers.csv',results);pd.DataFrame(H.encoded(curves)).to_parquet(OUT/'equity.parquet',index=False)
 with gzip.open(OUT/'audit.jsonl.gz','wt') as f:
  for x in flows:f.write(json.dumps(H.encoded(x),ensure_ascii=False,allow_nan=False)+'\n')
 assert all(sha(p)==h for p,h in identity.items());save(OUT/'VERIFICATION.json',dict(passed=True,source_cycles=153,local_paths=612,A_exact=153,max_accounting_residual=max(x['max_accounting_residual'] for x in results),seconds=time.monotonic()-START,no_new_buys=True,no_portfolio_paths=True,parameters=['10%','20%','30%'],no_cost2_replay=True));status='complete';print('COMPLETE',time.monotonic()-START,flush=True)
except BaseException as e:
 save(OUT/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
finally:
 signal.setitimer(signal.ITIMER_REAL,0);save(O/'COMPUTATION_TIME.json',dict(status=status,seconds=time.monotonic()-START,synthetic_allowance=2,budget=120))
