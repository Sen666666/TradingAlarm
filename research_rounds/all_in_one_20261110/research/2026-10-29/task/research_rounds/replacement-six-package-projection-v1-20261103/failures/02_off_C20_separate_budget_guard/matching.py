"""Exact rational per-guard resource witnesses; no order or account API."""
from fractions import Fraction as F
from decimal import Decimal as D
from collections import defaultdict,deque

def rat(x):return x if isinstance(x,F) else F(str(x))
def txt(x):
 x=rat(x)
 return str(x.numerator) if x.denominator==1 else str(x.numerator)+'/'+str(x.denominator)

def flow(base,supply,demand,edges,detail=False):
 """Independent resource capacity, never recycles surplus donor into FREE."""
 base=rat(base);supply={k:rat(v) for k,v in supply.items()};demand={k:rat(v) for k,v in demand.items() if rat(v)>0}
 # Actual sale costs that REDUCE this resource are prior, unavoidable burdens.
 base+=sum((v for v in supply.values() if v<0),F(0))
 positive={k:v for k,v in supply.items() if v>0}
 if base<0:demand['BASE_DEFICIT']=-base
 sources={'FREE':max(F(0),base),**positive}
 need=sum(demand.values(),F(0))
 if sum(sources.values(),F(0))<need and not detail:return False,{'why':'TOTAL_RESOURCE_SHORTFALL'}
 cap={};adj=defaultdict(list)
 def add(u,v,c):
  cap[u,v]=c;cap[v,u]=F(0);adj[u].append(v);adj[v].append(u)
 for s,v in sources.items():
  add('SRC','s|'+s,v)
  for q,n in demand.items():
   if s=='FREE' or q=='BASE_DEFICIT' or (s,q) in edges:add('s|'+s,'q|'+q,min(v,n))
 for q,n in demand.items():add('q|'+q,'SINK',n)
 residual=dict(cap);total=F(0)
 while total<need:
  prev={'SRC':None};todo=deque(['SRC'])
  while todo and 'SINK' not in prev:
   u=todo.popleft()
   for v in adj[u]:
    if v not in prev and residual[u,v]>0:prev[v]=u;todo.append(v)
  if 'SINK' not in prev:break
  v='SINK';b=None
  while prev[v] is not None:
   u=prev[v];b=residual[u,v] if b is None else min(b,residual[u,v]);v=u
  v='SINK'
  while prev[v] is not None:
   u=prev[v];residual[u,v]-=b;residual[v,u]+=b;v=u
  total+=b
 ok=total==need
 if not detail:return ok,{'why':'MATCHED' if ok else 'ELIGIBLE_RESOURCE_SHORTFALL',
   'missing':{q:txt(residual['q|'+q,'SINK']) for q in demand if residual['q|'+q,'SINK']}}
 routes=[]
 for s in sources:
  for q in demand:
   k=('s|'+s,'q|'+q)
   if k in cap and cap[k]-residual[k]>0:routes.append(dict(source=s,receiver=q,amount=txt(cap[k]-residual[k])))
 out=dict(ok=ok,initial_free_after_negative_sale_costs=txt(base),demand={q:txt(n) for q,n in demand.items()},
  positive_donor_capacity={s:txt(v) for s,v in positive.items()},flows=routes,
  donor_surplus_sealed={s:txt(residual['SRC','s|'+s]) for s in positive},
  free_unused=txt(residual['SRC','s|FREE']),missing={q:txt(residual['q|'+q,'SINK']) for q in demand if residual['q|'+q,'SINK']})
 for s in sources:assert sum((rat(r['amount']) for r in routes if r['source']==s),F(0))<=sources[s]
 for q in demand:assert sum((rat(r['amount']) for r in routes if r['receiver']==q),F(0))<=demand[q]
 assert all(r['source']=='FREE' or r['receiver']=='BASE_DEFICIT' or (r['source'],r['receiver']) in edges for r in routes)
 return ok,out

def relation(old,new,mode):
 if mode=='ALL':return True
 import math
 v=[old.get('PVR'),old.get('stock_H1'),new.get('PVR'),new.get('stock_H1')]
 if any(x is None or not math.isfinite(float(x)) for x in v):return None
 op,oh,np,nh=map(float,v)
 if mode=='HARD':return np>=op and nh>=oh and (np>op or nh>oh)
 if mode=='WEAK':return not(op>=np and oh>=nh and (op>np or oh>nh))
 raise ValueError(mode)

def witness(J,s,ds,Q,plan,validation,scores,mode,detail=False):
 """Decompose precisely the original validator's checked resource stages.
 Negative fees/slippage remain burdens; native strict validator is mandatory.
 """
 if not validation['ok']:return False,{'why':'NATIVE_RESOURCE_REJECT'}
 active=[d for d in ds if Q.get(d['sid'],0)]
 if not active:return not plan['rows'],{'why':'NO_NEW_Q_NO_OPPORTUNITY_D'}
 if plan['assets']:raise ValueError('UNSUPPORTED independent coverage asset in six fixed snapshots')
 nd=rat(s['decision_nav']);nav=rat(s['nav'])-rat(s['pending_fees']);rows=s['rows']
 data={};byd={d['sid']:d for d in active};prefix={};filled=[]
 for d in active:
  sid=d['sid'];q=Q[sid];p=D(d['mark'])*(D(1)+J.SLIP);g=D(q)*p;m=D(q)*D(d['mark'])
  data[sid]=dict(g=rat(g),loss=rat(g)-rat(m),fee=rat(J.fee(q,p,d['fees'],'buy')),risk=rat(D(q)*max(D(0),p-D(d['floor']))),sector=d['sector'])
 stages={}
 for d in active:
  sid=d['sid'];prefix[sid]=data[sid];stages['reserve:'+sid]=(dict(prefix),set(),sid)
 for d in active:
  sid=d['sid'];stages['amend-before-conditional-fill:'+sid]=(data,set(filled),sid);filled.append(sid)
  stages['after-conditional-fill:'+sid]=(data,set(filled),sid)
 for d in active:stages['terminal:'+d['sid']]=(data,set(filled),d['sid'])
 sales={}
 for r in plan['rows']:
  z=next(z for z in s['lots'] if z['id']==r['layer']);sid=r['sid'];x=sales.setdefault(sid,dict(cap=F(0),risk=F(0),net=F(0),sector=z['sector']))
  x['cap']+=rat(D(r['q'])*D(z['mark']));x['risk']+=rat(r['risk_release']);x['net']+=rat(r['net'])
 for x in sales.values():x['loss']=x['cap']-x['net']
 edges={(old,new) for old in sales for new in data if relation(scores[old],scores[new],mode) is True}
 witnesses=[];seen=set();rounding_max=F(0)
 for ch in validation['checks']:
  stage=ch['stage'];kind=ch['constraint'];reserved,done,focus=stages[stage];sec=byd[focus]['sector']
  key=(kind,tuple(reserved),tuple(sorted(done)),sec if kind in ('industry_target','sector_risk5') else focus if kind=='stock10' else None)
  if key in seen:continue
  seen.add(key)
  if kind=='cash_reserve10':
   base=rat(s['available'])-nd*F('0.1');supply={sid:x['net'] for sid,x in sales.items()};dem={sid:x['g']+x['fee'] for sid,x in reserved.items()}
  elif kind=='account_capital90':
   base=nav*F('.9')-sum((rat(r['capital']) for r in rows),F(0));supply={sid:x['cap']-F('.9')*x['loss'] for sid,x in sales.items()}
   dem={sid:x['g']+F('.9')*x['fee']-(F('.1')*x['loss'] if sid in done else 0) for sid,x in reserved.items()}
  elif kind=='account_risk6':
   base=nav*F('.06')-sum((rat(r['risk']) for r in rows),F(0));supply={sid:x['risk']-F('.06')*x['loss'] for sid,x in sales.items()}
   dem={sid:x['risk']+F('.06')*x['fee']-(F('.94')*x['loss'] if sid in done else 0) for sid,x in reserved.items()}
  elif kind=='industry_target':
   base=rat(byd[focus]['industry_target'])-sum((rat(r['capital']) for r in rows if r['sector']==sec),F(0))
   supply={sid:x['cap'] if x['sector']==sec else F(0) for sid,x in sales.items()}
   dem={sid:x['g']-(x['loss'] if sid in done else 0) if x['sector']==sec else F(0) for sid,x in reserved.items()}
  elif kind=='sector_risk5':
   base=nav*F('.05')-sum((rat(r['risk']) for r in rows if r['sector']==sec),F(0))
   supply={sid:(x['risk'] if x['sector']==sec else F(0))-F('.05')*x['loss'] for sid,x in sales.items()}
   dem={sid:(x['risk']-(x['loss'] if sid in done else 0) if x['sector']==sec else F(0))+F('.05')*x['fee']+(F('.05')*x['loss'] if sid in done else 0) for sid,x in reserved.items()}
  elif kind=='stock10':
   base=nd*F('.1')-sum((rat(r['capital']) for r in rows if r['sid']==focus),F(0))
   supply={sid:x['cap'] if sid==focus else F(0) for sid,x in sales.items()}
   dem={sid:x['g']-(x['loss'] if sid in done else 0) if sid==focus else F(0) for sid,x in reserved.items()}
  else:raise ValueError('UNSUPPORTED original guard '+kind)
  assert all(v>=0 for v in dem.values()),(kind,'negative receiver resource demand')
  exact=base+sum(supply.values(),F(0))-sum(dem.values(),F(0));native=rat(ch['residual']);drift=abs(exact-native);rounding_max=max(rounding_max,drift)
  # This tolerance audits Decimal operation-order roundoff only; no admission
  # tolerance is used: native validation is strict, and network flow exact.
  if drift>F('0.0000000000000001'):raise ValueError(('guard decomposition differs',kind,stage,txt(exact),txt(native)))
  ok,w=flow(base,supply,dem,edges,detail)
  if not ok:return False,dict(why='MATCHING:'+kind,stage=stage,scope=sec if kind in ('industry_target','sector_risk5') else focus if kind=='stock10' else 'account',witness=w)
  if detail:witnesses.append(dict(constraint=kind,stage=stage,scope=sec if kind in ('industry_target','sector_risk5') else focus if kind=='stock10' else 'account',aggregate_residual=txt(exact),native_residual=ch['residual'],witness=w))
 return True,dict(why='ALL_RESOURCES_MATCHED',mode=mode,checked_resource_states=len(seen),edges=[list(e) for e in sorted(edges)],
   max_native_decimal_order_roundoff=txt(rounding_max),witnesses=witnesses if detail else None,
   actual_cash_released=0,actual_risk_released=0)

def self_test():
 cases=[]
 def check(name,b,s,d,e,expected):
  ok,w=flow(b,s,d,e,True);assert ok==expected,(name,w);cases.append(dict(name=name,passed=True,actual_ok=ok,witness=w))
 check('small_A_cannot_back_large_B',0,{'D':100},{'A':1,'B':99},{('D','A')},False)
 for resource in ('cash','capital','risk'):
  check('no_'+resource+'_leak_even_if_other_resources_pass',0,{'D':100},{'A':1,'B':99},{('D','A')},False)
 check('original_free_resource_still_supports_B',99,{'D':100},{'A':1,'B':99},{('D','A')},True)
 check('one_capacity_not_spent_twice',0,{'D':100},{'A':60,'B':60},{('D','A'),('D','B')},False)
 check('lot_surplus_sealed',0,{'D':200},{'A':1,'B':0},{('D','A')},True)
 check('background_deficit_not_free',-50,{'D':100},{'A':1,'B':49},{('D','A')},False)
 check('background_repaired_then_eligible_A',-50,{'D':100},{'A':1},{('D','A')},True)
 check('negative_sale_cost_deducted',10,{'D':-2},{'B':9},set(),False)
 return cases
