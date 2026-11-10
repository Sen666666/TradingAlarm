"""One market-conditioned TOTAL gross admission factor; no cost ledger."""
from pathlib import Path
from decimal import Decimal as D
import copy,sys
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'pvr_pool_feasibility'))
import native_adapter as A
N,J,L,IO,P=A.N,A.J,A.L,A.IO,A.P
Z=D(0);ALPHA=D('.10');POLICY='NO60_MARKET_DOWN_TOTAL_GROSS10_V1'

def context(a,at):
 bal=a.balance(at,a.market.marks(at,a.positions));orders={};gross=drag=Z
 for sid,o in a.buys.items():
  d=o.fee_reserved_cny+o.remaining_budget_cny*J.LR.SLIP/(1+J.LR.SLIP)
  orders[sid]=dict(order_id=o.order_id,gross=o.remaining_budget_cny,fee=o.fee_reserved_cny,qty=o.remaining_shares,drag=d)
  gross+=o.remaining_budget_cny;drag+=d
 return dict(at=at,NAV=bal['nav'],inventory=bal['inventory'],pending_gross=gross,pending_drag=drag,orders=orders,info=a.gross_info.state(at))

def decision(c,q,exec_price,mark,fee):
 numerator=c['inventory']+c['pending_gross']+D(q)*exec_price
 nav=c['NAV']-c['pending_drag']-fee-D(q)*max(Z,exec_price-mark)
 known=c['info']['state']!='UNKNOWN'
 allowed=known and(c['info']['state']!='DOWN'or(nav.is_finite()and nav>0 and numerator<=ALPHA*nav))
 return dict(allowed=allowed,projected_gross=numerator,projected_NAV=nav)

def snapshot(a,c,kind,**kw):
 r=dict(c,kind=kind,sequence=len(a.gross_events),native_audit_count=len(a.audit_log),native_trade_count=len(a.trades),native_journal_count=len(a.journal),**kw);a.gross_events.append(r);return r

class GrossAccount(J.Account):
 def gross_allowed(self,c,q,x,intent):
  fee=J.LR.fees(q,x['price'],x['schedule'],'buy',intent['quote'].par_value)
  return decision(c,q,x['price'],x['known_open'],fee)['allowed']
 def reserve_quantity(self,intent,q,price,schedule,at):
  c=context(self,at);mark=self.market.marks(at,[intent['sid']])[intent['sid']].cny_price(at);fee=J.LR.fees(q,price,schedule,'buy',intent['quote'].par_value);v=decision(c,q,price,mark,fee)
  assert v['allowed'],'non-atomic gross reserve'
  snapshot(self,c,'reserve_pre',sid=intent['sid'],q=q,fee=fee,execution_price=price,mark=mark,**v)
  oid=super().reserve_quantity(intent,q,price,schedule,at);post=context(self,at)
  if post['info']['state']=='DOWN':assert post['inventory']+post['pending_gross']<=ALPHA*(post['NAV']-post['pending_drag'])
  snapshot(self,post,'reserve_post',sid=intent['sid'],order_id=oid,q=q)
  return oid
 def fill_buy(self,sid,w):
  o=self.buys.get(sid)
  if o is None:return
  c=context(self,w.at);assert w.fx.read(w.at)==D(1)
  q=min(o.remaining_shares,int(o.remaining_budget_cny/w.execution_price));fees=self._fee(o,w.fees,'buy',D(q)*w.execution_price,shares=q,par_value=w.par_value);fullfee=sum(fees.values(),Z)
  mark=self.market.marks(w.at,[sid])[sid].cny_price(w.at)
  slip=max(o.remaining_budget_cny*J.LR.SLIP/(1+J.LR.SLIP),D(q)*max(Z,w.execution_price-mark))
  nav=c['NAV']-(c['pending_drag']-c['orders'][sid]['drag'])-(max(o.fee_reserved_cny,fullfee)+slip)
  gross=c['inventory']+c['pending_gross'];state=c['info']['state']
  allowed=state!='UNKNOWN'and(state!='DOWN'or(nav.is_finite()and nav>0 and gross<=ALPHA*nav))
  snapshot(self,c,'fill_pre',sid=sid,q_bound=q,fullfee_bound=fullfee,execution_price=w.execution_price,mark=mark,projected_NAV=nav,projected_gross=gross,allowed=allowed)
  if not allowed:
   self.cancel_buy(sid);snapshot(self,context(self,w.at),'fill_cancelled',sid=sid);return
  r=super().fill_buy(sid,w)
  if r:
   post=context(self,w.at)
   if state=='DOWN':assert post['inventory']+post['pending_gross']<=ALPHA*(post['NAV']-post['pending_drag']),'actual gross fill failed cap'
   snapshot(self,post,'fill_post',sid=sid,actual_gross=r.gross_cny,actual_fee=r.fees_cny,actual_shares=r.shares)
  return r

OLD_ROUTE=P.NEW_ROUTE
NEW_ROUTE=OLD_ROUTE.replace('results=[];reasons={}','results=[];reasons={};gross_context=context(a,at);gross_routes=[]')
NEW_ROUTE=NEW_ROUTE.replace('def allowed(q,detail=False):','def allowed(q,detail=False,guard=True):')
needle='    return fails if detail else not fails';assert NEW_ROUTE.count(needle)==1
NEW_ROUTE=NEW_ROUTE.replace(needle,"    if guard and not a.gross_allowed(gross_context,q,x,i):fails.append('market_total_gross_cap')\n"+needle)
needle='q=LR.maximum_quantity(rule,maxq,allowed);results.append((q,pool));reasons[pool]=allowed(rule.buy_minimum,True)';assert NEW_ROUTE.count(needle)==1
NEW_ROUTE=NEW_ROUTE.replace(needle,needle+";gross_routes.append(dict(pool=pool,q=q,pre_cap_q=LR.maximum_quantity(rule,maxq,lambda v:allowed(v,guard=False))))")
needle="q,pool=max(results,key=lambda z:(z[0],z[1]=='probe'))"
NEW_ROUTE=NEW_ROUTE.replace(needle,needle+"\n  snapshot(a,gross_context,'route',sid=sid,role=role,decision_at=i['clock'].decision_at,selected_q=q,routes=gross_routes)")
env=dict(J.__dict__,context=context,snapshot=snapshot);exec(compile(NEW_ROUTE,str(O/'derived_route.py'),'exec'),env);gross_route=env['route']

class Runner(A.Runner):
 def __init__(self,*args,info,**kw):
  self._gross_ready=False;super().__init__(*args,**kw);base=self.accounts['B'];self.accounts={}
  for label in('B','D_GROSS10'):
   a=copy.copy(base);a.__dict__=copy.deepcopy({k:v for k,v in base.__dict__.items()if k not in('market','facts')});a.market,a.facts,a.label=base.market,base.facts,label
   if label!='B':a.__class__=GrossAccount;a.gross_info=info;a.gross_events=[]
   self.accounts[label]=a
  self._gross_ready=True;self.integration_policy=POLICY+':'+self.rank_mode;self.assert_native_wiring()
 def assert_native_wiring(self):
  assert self.opening.__func__ is J.Runner.opening and self.planning.__func__ is N.Runner.planning and self.route.__func__ is Runner.route
  for label,a in self.accounts.items():
   expected=GrossAccount if getattr(self,'_gross_ready',False)and label!='B'else J.Account;assert type(a)is expected
   for m in('sync','cancel_buy','fill_exit','split','expire_day_buys','assert_budget_view'):assert getattr(a,m).__func__ is getattr(J.Account,m)
 def route(self,a,intent,x,at):return P.ROUTES[True](self,a,intent,x,at)if type(a)is J.Account else gross_route(self,a,intent,x,at)
 def dump_joint(self,path):
  N.Runner.dump_joint(self,path)
  IO.write_gzip_jsonl(Path(path)/'gross-admission-events.jsonl.gz',self.accounts['D_GROSS10'].gross_events,encoder=J.C.encoded)
