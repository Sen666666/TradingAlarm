import time
START=time.monotonic()
from core import *
import ast,signal,traceback
OUT=O/'full';OUT.mkdir(exist_ok=False);status='started';signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('120-second compute budget')));signal.setitimer(signal.ITIMER_REAL,118)
try:
 assert read(O/'STATE_TESTS.json')['passed'];prior=W/'entry-loss-budget-local153-20261031';pf=read(prior/'FREEZE.json');assert all(sha(p)==h for p,h in pf['sha256'].items());diag=W/'act-entry-path-diagnostics-20261031';cycles=S.csvrows(diag/'CYCLE_PATH_FACTS.csv');pdays=defaultdict(dict)
 for r in S.csvrows(diag/'DAILY_PATHS.csv'):
  if r['kind']=='holding_close':pdays[r['sector'],r['cycle_id']][r['day']]=r
 ctx={};feeds={};qproof=[];sources={'TECH':(S.RR/'pvr-local-finite-capital-20261029/baseline','I__S0_base'),'DRUG':(S.RR/'innovative-drug-local-recovery-20261028/S0','ACT__S0_base')};identity={str(p):sha(p) for p in [O/'PROTOCOL.txt',O/'core.py',Path(__file__),O/'STATE_TESTS.json',prior/'full/unit-ledgers.csv',prior/'full/VERIFICATION.json',prior/'run.py']};identity.update(pf['sha256'])
 for sec,(root,aid) in sources.items():
  ap=root/'accounts-v2'/f'{aid}.json';dp=root/'accounts-v2/daily.jsonl.gz';qp=root/'accounts-v2/decisions.jsonl.gz'
  for p in [ap,dp,qp]:identity[str(p)]=sha(p)
  logs=read(ap)['audit_log'];ids={c['symbol'] for c in cycles if c['sector']==sec};m=S.market(sec,ids);feeds[sec]=S.Feed(sec,ids)
  with gzip.open(dp,'rt') as f:ds={x['at'][:10]:x for line in f if (x:=json.loads(line))['account']==aid}
  with gzip.open(qp,'rt') as f:de={x['at'][:10]:x for line in f if (x:=json.loads(line))['account']==aid}
  assert set(ds)==set(de)
  updates=[]
  for i,x in enumerate(logs):
   if x['kind']=='reserve':updates.append((stamp(x['at']),i,'reserve',x))
   elif x['kind']=='fill' and x['receipt']['side']=='buy':updates.append((stamp(x['receipt']['at']),i,'fill',x))
   elif x['kind']=='release_buy':updates.append((stamp(x['at']),i,'release',x))
  updates.sort(key=lambda x:(x[0],x[1]));j=0;pending={};gross={}
  for day,d in ds.items():
   cl=stamp(d['at'])
   while j<len(updates) and updates[j][0]<=cl:
    _,_,kind,x=updates[j];oid=x['order_id']
    if kind=='reserve':pending[oid]=(x['sid'],D(x['gross_budget_cny']))
    elif kind=='fill':pending[oid]=(x['receipt']['security_id'],D(x['gross_budget_remaining']))
    else:pending.pop(oid,None)
    j+=1
   by=defaultdict(lambda:Z)
   for s,v in pending.values():by[s]+=v
   assert sum(by.values(),Z)<=D(d['order_reserved']);assert set(by)==set(d['pending_buys']),(sec,day,set(by),d['pending_buys']);gross[day]=dict(by)
  cp={x['at'][:10]:x for x in logs if x['kind']=='risk_checkpoint'};assert set(cp)==set(ds);ctx[sec]=dict(m=m,logs=logs,ds=ds,de=de,gross=gross,cp=cp,ids=ids)
  heldQ=[(day,s) for day,d in ds.items() for s in d['positions'] if s in de[day]['eligible']];qproof.append(dict(sector=sec,days=len(ds),held_and_external_Q_true=len(heldQ),first_examples=heldQ[:5],pending_gross_checked=len(gross),Q_function_excludes_occupancy_cash=True))
 save(O/'Q_INTERFACE_CHECK.json',dict(passed=True,records=qproof,source=str(S.RR/'rs-h1-execution-20261025/code/sector_stock_admission.py'),Q_lines=[185,220],external_false_unknown_reason_not_separated_in_original_eligible_list=True))
 save(O/'FREEZE.json',dict(at=str(datetime.now().astimezone()),before_C_economics=True,prior_path_information_seen=True,arms=['C10','C20','C30'],mother=[(c['sector'],c['cycle_id']) for c in cycles],sha256=identity))
 # Exact, unchanged original B replay function; it keeps its original Book/Budget globals.
 import datetime as datetime_module
 globals()['datetime']=datetime_module.datetime
 flows=[];curves=[];controls=[]
 tree=ast.parse((prior/'run.py').read_text());node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='replay');exec(compile(ast.Module(body=[node],type_ignores=[]),str(prior/'run.py'),'exec'),globals())
 oldrows=S.csvrows(prior/'full/unit-ledgers.csv');oldmap={(x['sector'],x['cycle_id'],x['arm']):x for x in oldrows};brepro=[]
 for c in cycles:
  for arm,b in [('B10',D('.1')),('B20',D('.2')),('B30',D('.3'))]:
   r=replay(c,arm,b);old=oldmap[c['sector'],c['cycle_id'],arm]
   for k in ['full_cycle_net','final_equity','difference_vs_A','full_fees','dividend_equity','terminal_claim','terminal_inventory']:assert D(r[k])==D(old[k])
   for k in ['new_trigger','request_submitted','actual_cleared','first_sell','last_sell']:assert str(r[k] or '')==old[k]
   brepro.append(dict(sector=c['sector'],cycle_id=c['cycle_id'],arm=arm,passed=True))
 save(OUT/'B_REPRODUCTION.json',dict(passed=True,rows=len(brepro),exact_money_and_dates=True));print('B_ALL459_EXACT',time.monotonic()-START,flush=True);flows.clear();curves.clear();results=[];attempts=[];legrows=[]
 def resources(a,sec,c,day,quote):
  cc=ctx[sec];d=cc['ds'][day];s=c['symbol'];oc=[x for x in cc['de'][day]['occupancy'] if x['security_id']!=s];issuers={x['issuer_id'] for x in oc};sectors=Counter(x['sector_id'] for x in oc)
  if quote.issuer_id in issuers:return Z,'other_original_issuer_occupied',{}
  if len(issuers)>=6:return Z,'other_original_capacity_full',{}
  if quote.sector_id not in sectors and len(sectors)>=3:return Z,'other_original_three_industries',{}
  if sectors[quote.sector_id]>=2:return Z,'other_original_same_industry_two',{}
  originalold=D(int(d['positions'].get(s,0)))*cc['m'].latest_mark(s,at(day)).raw_price;others=D(d['inventory'])-originalold;pending=sum((v for sid,v in cc['gross'][day].items() if sid!=s),Z);own=D(a.quantity(s))*cc['m'].latest_mark(s,at(day)).raw_price;ownpending=sum((o.remaining_budget_cny for o in a.buys.values()),Z);nav=D(d['nav']);head=max(Z,D('.9')*nav-others-pending-own-ownpending);budget=min(a.available,D('.15')*nav,head)
  assert others>=0;return budget,None,dict(original_NAV=nav,other_original_inventory=others,other_pending_gross=pending,headroom=head,private_available=a.available,per_order_cap=D('.15')*nav,selected_budget=budget)
 def runC(c,arm,b):
  sec=c['sector'];cid=c['cycle_id'];s=c['symbol'];m=ctx[sec]['m'];feed=feeds[sec];entry=stamp(c['entry_at']);end=at(c['endpoint'][:10]);K0=D(c['basis']);logs=ctx[sec]['logs'];quote=m.quote(s,entry);a=Wallet(symbol=s,cycle_id=cid,b=b,K=K0,q=int(c['initial_shares']),quote=quote,sellable=m.sessions['A'][bisect.bisect_right(m.sessions['A'],entry)],fractional=m.protocol['fractional_split_policy']);book=CycleBook(int(c['initial_shares']));orig=[x['at'][:10] for x in logs if x['kind']=='exit_request' and x['sid']==s and entry<=stamp(x['at'])<=end];assert len(orig)==int(c['closed']=='True');origday=orig[0] if orig else None;peak=K0;minnav=K0;dd=Z;local=[];requests=[];closes=[];budget_requests=0;application=accepted=0;unknown=[]
  for day,d in ctx[sec]['ds'].items():
   if day<entry.date().isoformat() or day>end.date().isoformat():continue
   op=at(day,9,30);cl=at(day)
   if day>entry.date().isoformat():
    for act in m.actions.get(s,[]):
     if act['effective_date']==day:H.action(a,m,s,act)
    H.pay(a,m,op)
    if s in a.exits:
     w=m.window(s,op,'sell',1)
     if w:a.fill_exit(s,w)
    H.pay(a,m,op);bal=book.check(a,m,s,op)
    if a.last_flat==op and not a.leg.closed:
     a.leg.closed=True;lr=dict(sector=sec,cycle_id=cid,arm=arm,leg=a.leg.number,K=a.leg.K,buy_at=a.leg.buy_at or c['entry_at'],clear_at=str(op),reason=a.leg.controller.reason,dividend=a.leg.dividend,sale_net=a.leg.sales,net=a.leg.sales+a.leg.dividend-a.leg.K);legrows.append(lr);closes.append(lr)
    if s in a.buys:
     w=m.window(s,op,'buy',1);r=feed.row(s,day);factor=D(str(r.factor)) if r is not None and pd.notna(r.factor) else None
     if w:a.fill_buy(s,w,factor)
    H.pay(a,m,op);book.check(a,m,s,op)
   H.pay(a,m,cl);a.expire_day_buys(cl);bal=book.check(a,m,s,cl);q=a.quantity(s);r=feed.row(s,day);native=pd.Timestamp(day) in feed.f[s].index;raw=m.raw[s];t=pd.Timestamp(day);mk=m.latest_mark(s,cl) if q else None;path=pdays[sec,cid].get(day);known=bool(q and mk and mk.known_at.date()==cl.date() and t in raw.index and raw.loc[t,'observed_bar'] and raw.loc[t,'valid_price']);known=known and (path is None or path['price_observation_known']=='True');same_epoch=not(native and path is not None and path['market_epoch'] and path['market_epoch']!=c['economic_epoch']);endstructure=native and r is not None and not bool(r.e0_target);original_now=day==origday or not ctx[sec]['cp'][day]['on'] or endstructure or not same_epoch
   if original_now:a.ended=True;a.cancel_buy(s)
   if q:
    if not known:unknown.append(dict(day=day,kind='leg_budget_price_unknown'))
    fee,slip=liquidation(m,s,q,mk.raw_price,cl);legV=D(q)*mk.raw_price+a.leg.dividend+a.leg.sales-fee-slip;hit=a.leg.controller.close(V=legV if known else None,known=known,at=str(cl),original=original_now)
    if hit:
     reason=a.leg.controller.reason;requests.append(dict(at=str(cl),leg=a.leg.number,reason=reason,K=a.leg.K,V=legV));budget_requests+=int(reason=='loss_budget')
    if a.leg.controller.locked and s not in a.exits:
     qt=m.quote(s,cl)
     if qt:a.request_exit(qt,A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()))
     else:unknown.append(dict(day=day,kind='exit_quote_unknown'))
   fresh=bool(native and bool(r.i_buy));externalQ=s in ctx[sec]['de'][day]['eligible']
   if not a.ended and a.last_flat is not None and not a.quantity(s) and s not in a.buys and s not in a.exits and fresh and cl>a.last_flat:
    application+=1;why=None;budget=Z;rd={};ok=False;qt=m.quote(s,cl)
    if not externalQ:why='recorded_external_Q_not_true_false_or_unknown'
    elif qt is None:why='quote_unknown'
    elif r is None or not pd.notna(r.i_floor):why='floor_unknown'
    else:
     budget,why,rd=resources(a,sec,c,day,qt)
     if why is None:ok,why=a.reserve_restore(clock=A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()),quote=qt,floor=D(str(r.i_floor)),budget=budget,fresh=True,Q=True)
    accepted+=int(ok);attempts.append(dict(sector=sec,cycle_id=cid,arm=arm,at=str(cl),native_i_buy=fresh,external_Q_true=externalQ,ok=ok,why=why,**rd))
   a.daily_delay_credit.clear();bal=book.check(a,m,s,cl);peak=max(peak,bal['nav']);minnav=min(minnav,bal['nav']);dd=max(dd,ONE-bal['nav']/peak);local.append(dict(sector=sec,cycle_id=cid,arm=arm,at=str(cl),nav=bal['nav'],shares=a.quantity(s),private_cash=bal['available'],reserved=bal['order_reserved'],claim=bal['dividend_receivable'],sale_receivable=bal['sale_receivable'],leg=a.leg.number,legK=a.leg.K,ended=a.ended))
  final=book.check(a,m,s,end);mv=final['inventory'];legvalue=mv+a.leg.dividend+a.leg.sales;unrealized=Z if a.leg.closed else legvalue-a.leg.K;totalleg=sum((x['net'] for x in closes),Z)+unrealized;net=final['nav']-K0;assert totalleg==net,(sec,cid,arm,totalleg,net);buys=[f for f in a.fills if f.side=='buy'];sells=[f for f in a.fills if f.side=='sell'];oldB=oldmap[sec,cid,'B'+arm[1:]];result=dict(sector=sec,cycle_id=cid,symbol=s,name=c['name'],arm=arm,budget=b,original_group=oldB['original_group'],basis=K0,original_net=c['final_net_pnl'],B_net=oldB['full_cycle_net'],C_net=net,C_minus_A=net-D(c['final_net_pnl']),C_minus_B=net-D(oldB['full_cycle_net']),budget_requests=budget_requests,restore_applications=application,accepted_orders=accepted,restore_buy_fills=len(buys),sell_fills=len(sells),legs=a.leg.number,full_fees=K0-sum((D(x['receipt']['gross_cny']) for x in logs if x['kind']=='fill' and x['receipt']['security_id']==s and x['receipt']['side']=='buy' and stamp(x['receipt']['at'])==entry),Z)+book.fees,dividend=book.div,final_shares=a.quantity(s),terminal_claim=final['dividend_receivable'],terminal_sale_receivable=final['sale_receivable'],minimum_cycle_return=minnav/K0-ONE,max_close_drawdown=dd,source_unknown_count=c['unknown_count'],source_unknown_dates=c['unknown_dates'],runtime_unknown=json.dumps(unknown),final_unrealized_leg_net=unrealized,leg_net_sum=totalleg,max_residual=book.maxres,reused=False)
  flows.append(dict(sector=sec,cycle_id=cid,arm=arm,requests=requests,fills=a.fills,audit=a.audit_log,notes=a.notes));curves.extend(local);return result
 for sec in ['TECH','DRUG']:
  for c in [x for x in cycles if x['sector']==sec]:
   for arm,b in [('C10',D('.1')),('C20',D('.2')),('C30',D('.3'))]:
    oldB=oldmap[sec,c['cycle_id'],'B'+arm[1:]]
    if oldB['new_trigger']:result=runC(c,arm,b)
    else:result=dict(sector=sec,cycle_id=c['cycle_id'],symbol=c['symbol'],name=c['name'],arm=arm,budget=b,original_group=oldB['original_group'],basis=c['basis'],original_net=c['final_net_pnl'],B_net=oldB['full_cycle_net'],C_net=oldB['full_cycle_net'],C_minus_A=Z,C_minus_B=Z,budget_requests=0,restore_applications=0,accepted_orders=0,restore_buy_fills=0,sell_fills=oldB['sell_fills'],legs=1,full_fees=oldB['full_fees'],dividend=oldB['dividend_equity'],final_shares=oldB['final_shares'],terminal_claim=oldB['terminal_claim'],terminal_sale_receivable=oldB['terminal_sale_receivable'],minimum_cycle_return=None,max_close_drawdown=oldB['max_close_drawdown'],source_unknown_count=c['unknown_count'],source_unknown_dates=c['unknown_dates'],runtime_unknown=oldB['runtime_unknown'],final_unrealized_leg_net=None,leg_net_sum=oldB['full_cycle_net'],max_residual=Z,reused=True)
    results.append(result)
  print('C_SECTOR_DONE',sec,len(results),time.monotonic()-START,flush=True)
 assert len(results)==459;export(OUT/'unit-results.csv',results);export(OUT/'restoration-attempts.csv',attempts);export(OUT/'leg-ledgers.csv',legrows);pd.DataFrame(H.encoded(curves)).to_parquet(OUT/'equity.parquet',index=False)
 with gzip.open(OUT/'audit.jsonl.gz','wt') as f:
  for x in flows:f.write(json.dumps(H.encoded(x),ensure_ascii=False,allow_nan=False)+'\n')
 assert all(sha(p)==h for p,h in identity.items());save(OUT/'VERIFICATION.json',dict(passed=True,C_rows=459,B_exact=459,replayed_C=sum(not x['reused'] for x in results),identical_C_reused=sum(x['reused'] for x in results),maximum_residual=max(x['max_residual'] for x in results),seconds=time.monotonic()-START,no_external_funding=True,no_portfolio_paths=True));status='complete';print('COMPLETE',time.monotonic()-START,flush=True)
except BaseException as e:
 save(OUT/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
finally:
 signal.setitimer(signal.ITIMER_REAL,0);save(O/'COMPUTATION_TIME.json',dict(status=status,seconds=time.monotonic()-START,synthetic_allowance=2,budget=120))
