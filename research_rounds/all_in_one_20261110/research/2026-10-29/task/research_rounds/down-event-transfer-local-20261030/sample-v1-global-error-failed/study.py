"""32 frozen local attempts, three inventory/cash arms, two costs, two common endpoints."""
from pathlib import Path
from datetime import datetime,time as dt,timedelta,timezone
from decimal import Decimal as D,getcontext
from dataclasses import replace
from collections import defaultdict,Counter
import sys,json,gzip,csv,time,hashlib,importlib.util,bisect
import pandas as pd

T=time.monotonic();O=Path(__file__).resolve().parent;P=O.parent/'down-event-transfer-exposure-20261030';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');B=R/'pvr-local-finite-capital-20261029/baseline';S=R/'s-entry-mechanism-audit-20261029';Z=D(0);ONE=D(1)
stage=sys.argv[1];assert stage in ('sample','full');dest=O/stage;dest.mkdir(exist_ok=False)
sp=importlib.util.spec_from_file_location('negative_event_existing_helpers',S/'code/audit.py');H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(H.encoded(x),ensure_ascii=False,indent=2,allow_nan=False))
def export(p,x):pd.DataFrame(H.encoded(x)).to_csv(p,index=False)
def stamp(x):return datetime.fromisoformat(x)
def near(a,b,n=1):
 bound=ONE.scaleb(max(abs(a),abs(b),ONE).adjusted()-getcontext().prec+1)*max(1,n)*64
 assert abs(a-b)<=bound,('money_identity',str(a),str(b),str(bound));return abs(a-b)
for p,h in read(P/'SELECTION_FREEZE.json')['sha256'].items():assert sha(p)==h,p
mother=list(csv.DictReader((P/'selected-events-before-labels.csv').open()));assert len(mother)==32
obj=read(B/'accounts-v2/I__S0_base.json');audit=obj['audit_log'];actualfills=[x for x in audit if x['kind']=='fill'];cycles={f"{x['symbol']}|{x['entry_at'][:10]}":x for x in csv.DictReader((B/'analysis/campaigns.csv').open()) if x['scenario']=='base'}
cache=pd.read_parquet(S/'market-cache.parquet');cc={(x.symbol,str(x.date.date())):x for x in cache.itertuples(index=False)};calendar=sorted(set(k[1] for k in cc));cp={x['at'][:10]:x for x in audit if x['kind']=='risk_checkpoint'};pauses=[stamp(x['at']) for x in audit if x['kind']=='risk_checkpoint' and x.get('event')=='pause']
ids={x[k] for x in mother for k in ['old','new']};_,m,_,_=H.context(ids,False)
olddiv=[x['receivable'] for x in audit if x['kind']=='dividend_accrual']
samples=[mother[0]['cycle_id'],next(x['cycle_id'] for x in mother if float(cycles[x['cycle_id']]['net_return'])>=.30)]
inputfiles=[P/'selected-events-before-labels.csv',P/'SELECTION_FREEZE.json',B/'accounts-v2/I__S0_base.json',B/'analysis/campaigns.csv',S/'market-cache.parquet',O/'PROTOCOL.txt',Path(__file__)]
if stage=='sample':save(O/'INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),mother_cycle_ids=[x['cycle_id'] for x in mother],samples=samples,sha256={str(p):sha(p) for p in inputfiles},before_new_pair_returns=True,supplementary_full_endpoint_added_after_winner_exposure=True))
identity=read(O/'INPUT_IDENTITY.json');assert identity['mother_cycle_ids']==[x['cycle_id'] for x in mother]
for p,h in identity['sha256'].items():assert sha(p)==h,p
events=mother if stage=='full' else [x for x in mother if x['cycle_id'] in samples]
loadsec=time.monotonic()-T;results=[];curves=[];flowlogs=[];baselinechecks=[];checks=Counter();maxres=Z

def endpoints(e):
 t=H.at(e['date'],dt(15,10));first=m.sessions['A'][bisect.bisect_right(m.sessions['A'],t)];firstidx=calendar.index(str(first.date()));targetidx=firstidx+20
 h21=H.at(calendar[min(targetidx,len(calendar)-1)],dt(15,10));why='21_market_days' if targetidx<len(calendar) else 'data_cutoff'
 future=[m.sessions['A'][bisect.bisect_right(m.sessions['A'],p)] for p in pauses if p>t]
 if future and min(future)<h21:h21=min(future);why='fixed_original_ACT_execution'
 c=cycles[e['cycle_id']];hfull=H.at(c['exit_at'][:10],dt(15,10)) if c['closed']=='True' else H.at(calendar[-1],dt(15,10))
 return t,first,h21,hfull,why
def seed(e,cost,arm):
 s=e['old'];t,first,*_=endpoints(e);q=int(e['old_quantity']);quote=m.quote(s,t);stock=D(q)*m.latest_mark(s,t).raw_price;c=cycles[e['cycle_id']]
 carry=[x for x in olddiv if x['security_id']==s and c['entry_at'][:10]<=x['ex_at'][:10]<=e['date'] and (x.get('paid_at') is None or stamp(x['paid_at'])>t)]
 carryval=sum((D(x['net_local']) for x in carry),Z);I0=stock+carryval
 a=H.L.SectorAccount(initial_cash=I0,cost_multiplier=cost,fractional_split_policy=m.protocol['fractional_split_policy']);a.available=Z;a.positions[s]=H.L.Position(s,quote.issuer_id,quote.sector_id,quote.currency,[H.L.InventoryLot(q,first)])
 for x in sorted(carry,key=lambda x:x['ex_at']):
  a.accrue_dividend(event_id=x['event_id'],sid=s,currency=x['currency'],net_local=D(x['net_local']),ex_at=stamp(x['ex_at']),paid_at=stamp(x['paid_at']) if x.get('paid_at') else None,source_id=x['source_id'],entitlement_basis=x['entitlement_basis'])
 if arm!='A':a.request_exit(quote,H.A.Clock(t,first,t.date()))
 return dict(a=a,arm=arm,cost=cost,q={s:q},flow=Z,div=Z,cursor=0,fee_state={},fees=Z,slippage=Z,I0=I0,stock0=stock,carry=carryval,prior_pnl=I0-D(c['buy_gross'])-D(c['buy_fees']),snapshots=[],fills=[],requests=[],attempt_status='no_active_exit_A' if arm=='A' else 'pending_active_exit',new_status='not_applicable' if arm!='C' else 'not_attempted',old_sale_net=Z,buy_spend=Z,new_initial_qty=0,unknowns=[],maxres=Z)
def consume(st,e):
 a=st['a']
 for x in a.audit_log[st['cursor']:]:
  k=x['kind']
  if k=='fill':
   f=x['receipt'];assert f.gross_cny==D(f.shares)*x['price'];components=x['fee_components'];assert sum(components.values(),Z)==f.fees_cny
   paid,acc=st['fee_state'].get(x['order_id'],({},{}));fs=m.fees(f.security_id,f.at);kw=dict(shares=f.shares,par_value=m.rules.get('security_metadata',{}).get(f.security_id,{}).get('par_value'));expected=fs.incremental(f.side,f.gross_cny,paid,acc,st['cost'],**kw);assert expected==components
   ra=fs.rate_accrual(f.side,f.gross_cny,st['cost'],**kw);st['fee_state'][x['order_id']]=({k:paid.get(k,Z)+v for k,v in expected.items()},{k:acc.get(k,Z)+v for k,v in ra.items()});checks['independent_fee_fills']+=1
   st['q'][f.security_id]=st['q'].get(f.security_id,0)+(f.shares if f.side=='buy' else -f.shares);st['flow']+=(-f.gross_cny-f.fees_cny) if f.side=='buy' else f.gross_cny-f.fees_cny;st['fees']+=f.fees_cny;st['slippage']+=abs(x['price']-x['raw_open'])*f.shares
   st['fills'].append(dict(sid=f.security_id,side=f.side,at=f.at,shares=f.shares,raw_open=x['raw_open'],price=x['price'],gross=f.gross_cny,fees=f.fees_cny,components=components,net=(-f.gross_cny-f.fees_cny) if f.side=='buy' else f.gross_cny-f.fees_cny))
   if f.side=='buy':assert st['arm']=='C' and f.security_id==e['new'];st['buy_spend']+=f.gross_cny+f.fees_cny;st['new_initial_qty']+=f.shares
  elif k in ('split','split_fraction_floor_proxy'):st['q'][x['sid']]=int(D(st['q'].get(x['sid'],0))*x['ratio'])
  elif k=='dividend_accrual':st['div']+=x['receivable'].net_local
 st['cursor']=len(a.audit_log)
 for s in ids:assert st['q'].get(s,0)==a.quantity(s)
 assert a.available>=0
def marks_at(a,tm):
 marks={}
 for s in a.positions:
  mk=m.latest_mark(s,tm)
  if tm.time()<dt(15,0):
   f=m.raw[s];day=pd.Timestamp(tm.date())
   if day in f.index and bool(f.loc[day,'valid_price']) and bool(f.loc[day,'observed_bar']):mk=replace(mk,raw_price=D(str(f.loc[day,'open'])),known_at=tm,source_id=mk.source_id+':known_open_proxy')
  marks[s]=mk
 return marks
def snapshot(st,e,tm,phase):
 consume(st,e);a=st['a'];marks=marks_at(a,tm);bal=a.balance(tm,marks);mv=sum((D(a.quantity(s))*mk.cny_price(tm) for s,mk in marks.items()),Z);expected=st['flow']+st['div']+mv
 st['maxres']=max(st['maxres'],near(bal['nav'],expected,len(a.audit_log)+1));checks['nav_snapshots']+=1
 estf=ests=Z
 for s,mk in marks.items():
  gross=D(a.quantity(s))*mk.raw_price*(ONE-D('.0005')*st['cost']);ests+=D(a.quantity(s))*mk.raw_price-gross;estf+=sum(m.fees(s,tm).incremental('sell',gross,{}, {},st['cost'],shares=a.quantity(s),par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value')).values(),Z)
 r=dict(cycle_id=e['cycle_id'],trigger=e['date'],old=e['old'],new=e['new'],cost=st['cost'],arm=st['arm'],at=tm,phase=phase,nav=bal['nav'],cash=bal['available'],inventory=mv,claim=bal['dividend_receivable'],sale_receivable=bal['sale_receivable'],settlement_locked=bal['settlement_locked'],payable=bal['payable'],reserved=bal['order_reserved'],shares=json.dumps({s:a.quantity(s) for s in a.positions}),fees=st['fees'],slippage=st['slippage'],dividend=st['div'],estimated_liquidation_fee=estf,estimated_liquidation_slippage=ests)
 st['snapshots'].append(r);return r
def active_attempt(st,e,op):
 a=st['a'];s=e['old'];w=m.window(s,op,'sell',st['cost']);q=a.quantity(s)
 allowed=bool(w is not None and w.sell_allowed and w.capacity_shares>=q and sum(l.shares for l in a.positions[s].lots if l.sellable_at<=op)>=q and w.quantity.sell_floor(q,q)==q)
 if not allowed:
  a.exits.pop(s,None);st['attempt_status']='old_full_sale_blocked_keep_original';return
 f=a.fill_exit(s,w);assert f is not None and a.quantity(s)==0;H.pay(a,m,op);st['old_sale_net']=f.gross_cny-f.fees_cny;st['attempt_status']='old_sold';consume(st,e)
 if st['arm']=='B':return
 n=e['new'];bw=m.window(n,op,'buy',st['cost']);nq=m.quote(n,op);floor=D(str(cc[n,e['date']].i_floor))/D(str(cc[n,str(op.date())].factor))
 why=None
 if bw is None or not bw.buy_allowed:why='buy_market_proxy_unavailable'
 elif bw.raw_open<=floor:why='open_not_above_frozen_support'
 elif nq is None:why='buy_quote_unknown'
 if why:st['new_status']='sold_but_buy_failed:'+why;return
 cap=int(e['new_projected_shares'])
 for x in m.actions.get(n,[]):
  if e['date']<x['effective_date']<=str(op.date()):cap=int(D(cap)*D(x['split_ratio']))
 budget=min(D(e['new_gross_cap']),st['old_sale_net'],a.available);when=op+timedelta(seconds=1);ok,oid=a.reserve_budget(quote=nq,clock=H.A.Clock(op,when,op.date()),gross_budget_cny=budget,target_shares_cap=cap,candidate_id=e['cycle_id']+'|frozen_transfer')
 if not ok:st['new_status']='sold_but_buy_failed:'+str(oid);return
 bw=replace(bw,event_id=bw.event_id+':local_after_sale',at=when,cash_due_at=max(when,bw.cash_due_at),execution_basis='daily_open_proxy_after_sale_1s_not_observed_tick');bf=a.fill_buy(n,bw);H.pay(a,m,when)
 if n in a.buys:a.cancel_buy(n)
 st['new_status']='new_filled' if bf else 'sold_but_buy_failed:quantity_capacity_or_budget';consume(st,e);assert st['buy_spend']<=st['old_sale_net'];checks['sealed_sale_cash_checks']+=1
def run(e):
 global maxres
 t,first,h21,hfull,hwhy=endpoints(e);last=max(h21,hfull);states=[seed(e,c,a) for c in [1,2] for a in ['A','B','C']];endpoint_rows={};c=cycles[e['cycle_id']]
 for st in states:snapshot(st,e,t,'trigger_close')
 for day in calendar[calendar.index(str(first.date())):]:
  op=H.at(day,dt(9,30));cl=H.at(day,dt(15,10))
  if op>last:break
  for st in states:
   a=st['a']
   for s in [e['old'],e['new']]:
    for act in m.actions.get(s,[]):
     if act['effective_date']==day:H.action(a,m,s,act)
   H.pay(a,m,op)
   if op==first and st['arm']!='A':active_attempt(st,e,op)
   else:
    for s in tuple(a.exits):
     w=m.window(s,op,'sell',st['cost'])
     if w:a.fill_exit(s,w)
   now=op+timedelta(seconds=1) if op==first else op;H.pay(a,m,now);sr=snapshot(st,e,now,'open')
   if h21==op:endpoint_rows[st['arm'],st['cost'],'H21']=sr
  if cl>last:break
  for st in states:
   a=st['a'];H.pay(a,m,cl)
   for s in tuple(a.positions):
    if s in a.exits:continue
    r=cc[s,day]
    if pd.isna(r.i_target):st['unknowns'].append(day+':I_unknown');continue
    if not bool(r.i_target) or not cp[day]['on']:
     quote=m.quote(s,cl)
     if quote is None:st['unknowns'].append(day+':exit_quote_unknown');continue
     a.request_exit(quote,H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()));st['requests'].append(dict(sid=s,at=cl,reason='ACT' if not cp[day]['on'] else 'I_structure'))
   sr=snapshot(st,e,cl,'close')
   if cl==h21:endpoint_rows[st['arm'],st['cost'],'H21']=sr
   if cl==hfull:endpoint_rows[st['arm'],st['cost'],'Hfull']=sr
  if cl==last:break
 for st in states:
  for view,end in [('H21',h21),('Hfull',hfull)]:
   sr=endpoint_rows[st['arm'],st['cost'],view];part=[x for x in st['snapshots'] if x['at']<=end];assert part and part[0]['nav']==st['I0'];peak=st['I0'];dd=Z
   for x in part:peak=max(peak,x['nav']);dd=max(dd,ONE-x['nav']/peak)
   held=[x for x in part if x['phase']=='close'];I0=st['I0'];res=dict(cycle_id=e['cycle_id'],trigger=e['date'],old=e['old'],new=e['new'],old_name=e['old_name'],new_name=e['new_name'],cost=st['cost'],arm=st['arm'],view=view,endpoint=end,endpoint_kind=hwhy if view=='H21' else 'original_old_exit_day_close_added_endpoint',initial_equity=I0,initial_stock=st['stock0'],initial_carry_claim=st['carry'],original_pretrigger_pnl=st['prior_pnl'],final_equity=sr['nav'],post_trigger_pnl=sr['nav']-I0,post_trigger_return=(sr['nav']-I0)/I0,fees=sr['fees'],slippage=sr['slippage'],dividend=sr['dividend'],inventory=sr['inventory'],claim=sr['claim'],sale_receivable=sr['sale_receivable'],cash=sr['cash'],estimated_liquidation_fee=sr['estimated_liquidation_fee'],estimated_liquidation_slippage=sr['estimated_liquidation_slippage'],estimated_net_liquidation_equity=sr['nav']-sr['estimated_liquidation_fee']-sr['estimated_liquidation_slippage'],min_trigger_return=min(x['nav'] for x in part)/I0-ONE,max_local_drawdown=dd,holding_close_observations=sum(x['inventory']>0 for x in held),cash_only_close_observations=sum(x['inventory']==0 for x in held),inventory_yuan_observations=sum((x['inventory'] for x in held),Z),original_tail30=float(c['net_return'])>=.30,original_cycle_net=c['net_pnl'],original_cycle_return=c['net_return'],attempt_status=st['attempt_status'],new_status=st['new_status'],old_sale_net=st['old_sale_net'],new_buy_spend=st['buy_spend'],new_initial_qty=st['new_initial_qty'],unknown='|'.join(st['unknowns']))
   results.append(res)
  if st['arm']=='A' and st['cost']==1:
   sr=endpoint_rows['A',1,'Hfull'];sells=[x for x in st['fills'] if x['side']=='sell'];orig=[x for x in actualfills if x['receipt']['security_id']==e['old'] and x['receipt']['side']=='sell' and x['receipt']['at']==c['exit_at']];assert len(orig)==len(sells)==1
   f=orig[0];ss=sells[0];assert ss['at']==stamp(c['exit_at']) and ss['shares']==f['receipt']['shares'] and ss['gross']==D(c['sell_gross']) and ss['fees']==D(c['sell_fees'])
   residue=near(sr['nav']-D(c['buy_gross'])-D(c['buy_fees']),D(c['net_pnl']),len(st['a'].audit_log)+1);baselinechecks.append(dict(cycle_id=e['cycle_id'],original_net=c['net_pnl'],reproduced_net=sr['nav']-D(c['buy_gross'])-D(c['buy_fees']),residual=residue,shares=ss['shares'],sale_at=ss['at'],dividend=sr['dividend']));checks['A_full_actual_cashflow_identity']+=1
  maxres=max(maxres,st['maxres']);curves+=st['snapshots'];flowlogs.append(dict(cycle_id=e['cycle_id'],cost=st['cost'],arm=st['arm'],I0=st['I0'],fills=st['fills'],requests=st['requests'],audit=st['a'].audit_log))
 for cost in [1,2]:
  bstate=next(st for st in states if st['arm']=='B' and st['cost']==cost);cstate=next(st for st in states if st['arm']=='C' and st['cost']==cost);assert bstate['old_sale_net']==cstate['old_sale_net']
 return states

for i,e in enumerate(events):
 run(e)
 if stage=='sample' or (i+1)%8==0:print(json.dumps(dict(stage=stage,events=i+1,total=len(events),seconds=time.monotonic()-T),ensure_ascii=False),flush=True)
 if time.monotonic()-T+float(identity.get('sample_seconds',0) if stage=='full' else 0)>300:raise TimeoutError('300s cumulative sample/full budget')
export(dest/'arm-endpoints.csv',results);export(dest/'A-actual-cycle-checks.csv',baselinechecks);pd.DataFrame(H.encoded(curves)).to_parquet(dest/'local-equity.parquet',index=False)
with gzip.open(dest/'audit.json.gz','wt') as f:json.dump(H.encoded(flowlogs),f,ensure_ascii=False,allow_nan=False)
if stage=='full':
 sm=pd.read_csv(O/'sample/arm-endpoints.csv',dtype=str).fillna('').set_index(['cycle_id','cost','arm','view']);fu=pd.read_csv(dest/'arm-endpoints.csv',dtype=str).fillna('').set_index(['cycle_id','cost','arm','view']);pd.testing.assert_frame_equal(sm,fu.loc[sm.index],check_exact=True)
for p,h in identity['sha256'].items():assert sha(p)==h,p
elapsed=time.monotonic()-T;save(dest/'VERIFICATION.json',dict(passed=True,stage=stage,events=len(events),arm_endpoint_rows=len(results),A_full_fact_checks=len(baselinechecks),max_NAV_residual=maxres,checks=dict(checks),sample_full_equal=stage=='full',load_seconds=loadsec,seconds=elapsed,new_account_portfolio_paths=0,no_external_cash=True,single_attempt_per_event=True))
if stage=='sample':identity['sample_seconds']=elapsed;save(O/'INPUT_IDENTITY.json',identity)
print(json.dumps(dict(stage=stage,complete=True,seconds=elapsed,endpoint_rows=len(results))),flush=True)
