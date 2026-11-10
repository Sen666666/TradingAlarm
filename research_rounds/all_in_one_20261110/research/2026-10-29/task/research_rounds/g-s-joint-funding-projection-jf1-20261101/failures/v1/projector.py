"""JF1 pure known-state resource projection. No account events or fake fills."""
from pathlib import Path
import sys,json,hashlib,copy
from decimal import Decimal as D
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'g-s-historical-native-prefix-20261101'))
import imports_native as N
Z=D(0);ONE=D(1);SLIP=N.LR.SLIP
CONTRACT_SHA='b0395b6ebbc0d768e4aa59ed332aaddc51a6cc52353f2a861b3d4ff6f9db260d'
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
def rule(spec):return N.T.QuantityRule(**spec)
def schedule(spec):return N.T.FeeSchedule(spec['schedule_id'],tuple(N.T.FeeComponent(**x) for x in spec['components']))
def fee(q,p,spec,side,paid=None,accrued=None):
 if not q:return Z
 return sum(schedule(spec).incremental(side,D(q)*D(p),{k:D(v) for k,v in (paid or {}).items()},
   {k:D(v) for k,v in (accrued or {}).items()},1,shares=q).values(),Z)
def num(r,k):return D(r[k])
def qty_options(d):
 r=rule(d['quantity']);q=r.buy_floor(d['max_q'])
 while q>=r.buy_minimum:
  yield q;q-=r.buy_step
 yield 0
def buy_cost(d,q):
 p=num(d,'mark')*(ONE+SLIP);return D(q)*p+fee(q,p,d['fees'],'buy')

def coverage(s):
 """Outstanding actual assets only. Received cash is already in available."""
 seen=set();assets=[]
 for a in s.get('assets',[]):
  if a['id'] in seen:raise ValueError('duplicate coverage asset')
  seen.add(a['id'])
  if a.get('cancel_pending'):raise ValueError('WAIT_CANCEL_ACK: no replacement funding')
  if a['due_at']>s['deadline']:continue
  if num(a,'amount')<0:raise ValueError('negative outstanding asset')
  assets.append(a)
 return assets

def donors(s,demands,quantities):
 """Original deterministic G/S-excess selection, without trim/commit calls."""
 positive=[d for d in demands if quantities.get(d['sid'],0)]
 if not positive:return dict(rows=[],raw_need=Z,covered=Z,uncovered=Z,still_unfunded=Z,assets=[])
 assets=coverage(s);cash=sum((buy_cost(d,quantities[d['sid']]) for d in positive),Z)
 need=max(Z,cash-max(Z,num(s,'available')-num(s,'decision_nav')*D('.1')))
 cover=min(need,sum((num(a,'amount') for a in assets),Z));left=need-cover
 if not left:return dict(rows=[],raw_need=need,covered=cover,uncovered=Z,still_unfunded=Z,assets=assets)
 blocked={d['sector'] for d in positive};excess={}
 for sec,target in s['targets'].items():
  held=sum((num(z,'capital') for z in s['lots'] if z['sector']==sec),Z)
  promised=sum((num(z,'locked_capital') for z in s['lots'] if z['sector']==sec),Z)
  excess[sec]=max(Z,held-D(target)-promised)
 available=[];classes={}
 for z in s['lots']:
  if not z['qty'] or not z['donor_eligible'] or z['sector'] in blocked:continue
  if z['purpose']=='G':available.append(z);classes[z['id']]=0
  elif z['purpose']=='S' and excess.get(z['sector'],Z)>0 and z['holding_S']:
   available.append(z);classes[z['id']]=1
 if len({z['sid'] for z in available})!=len(available):raise ValueError('UNSUPPORTED multi-layer donor fee aggregation')
 selected=[]
 for cls in (0,1):
  for role in ('mobile','core'):
   if not left:break
   group=sorted([z for z in available if classes[z['id']]==cls and z['role']==role],key=lambda z:(z['sid'],z['id']))
   if not group:continue
   caps={}
   for sec in sorted({z['sector'] for z in group}):
    part=[z for z in group if z['sector']==sec];value=sum((num(z,'capital') for z in part),Z)
    allowed=value if cls==0 else min(value,excess[sec]);fraction=allowed/value
    for z in part:caps[z['id']]=rule(z['quantity']).sell_floor(int(D(z['qty'])*fraction),z['qty'])
    residual=allowed-sum((D(caps[z['id']])*num(z,'mark') for z in part),Z)
    for z in part:
     step=min(rule(z['quantity']).sell_step,z['qty']-caps[z['id']]);cost=D(step)*num(z,'mark')
     if step and cost<=residual:caps[z['id']]+=step;residual-=cost
   def make(frac):
    rows=[]
    for z in group:
     q=rule(z['quantity']).sell_floor(int(D(caps[z['id']])*frac),z['qty']);p=num(z,'mark')*(ONE-SLIP)
     net=D(q)*p-fee(q,p,z['fees'],'sell') if q else Z
     rows.append(dict(layer=z['id'],sid=z['sid'],q=q,net=net,capital=D(q)*num(z,'mark'),
       risk_release=num(z,'risk')*D(q)/z['qty'],allocation_class='G' if cls==0 else 'S_excess'))
    return rows
   rows=make(ONE);full=sum((x['net'] for x in rows),Z)
   if full>=left:
    lo=Z;hi=ONE
    # This is the original donor cash-ratio routine, NOT a search over joint feasibility.
    for _ in range(80):
     mid=(lo+hi)/2
     if sum((x['net'] for x in make(mid)),Z)>=left:hi=mid
     else:lo=mid
    rows=make(hi)
   for r in rows:
    if r['q']:
     selected.append(r)
     if cls==1:excess[next(z['sector'] for z in group if z['id']==r['layer'])]-=r['capital']
   left=max(Z,left-sum((x['net'] for x in rows),Z))
 return dict(rows=selected,raw_need=need,covered=cover,uncovered=need-cover,still_unfunded=left,assets=assets)

def validate(s,ds,Q,plan):
 """Resource arithmetic at native reservation/amend boundaries, not execution."""
 active=[d for d in ds if Q.get(d['sid'],0)];checks=[];violations=[]
 if not active:return dict(ok=True,checks=[],violations=[],terminal=dict(nav=s['nav'],available=s['available']),conditional=False)
 if plan['still_unfunded']:violations.append('insufficient_original_donors')
 rows=copy.deepcopy(s['rows']);cash=num(s,'available');nav=num(s,'nav');pendingfees=num(s,'pending_fees');nd=num(s,'decision_nav')
 by={r['id']:r for r in rows}
 def subtract(part):
  if part['layer'] not in by:raise ValueError('coverage refers to absent lot')
  row=by[part['layer']];q=part['q'];cap=D(q)*num(row,'mark');risk=D(part['risk_release'])
  if q>row['qty'] or risk>num(row,'risk'):raise ValueError('overlapping sale coverage')
  row['qty']-=q;row['capital']=num(row,'capital')-cap;row['risk']=num(row,'risk')-risk
  return cap
 for a in plan['assets']:
  sold=sum((subtract(p) for p in a.get('parts',[])),Z)
  cash+=num(a,'amount')
  if a['kind']=='pending_exit':nav+=num(a,'amount')-sold
  elif a['kind']!='sale_receivable':raise ValueError('unsupported coverage kind')
 for sale in plan['rows']:
  lot=next(z for z in s['lots'] if z['id']==sale['layer'])
  if lot.get('sellable_qty') is None:raise ValueError('UNKNOWN donor sellability')
  if sale['q']>lot['sellable_qty']:violations.append('donor_not_sellable_before_deadline:'+sale['sid'])
  sold=subtract(sale);cash+=sale['net'];nav+=sale['net']-sold
 def check(label,lhs,rhs,stage):
  gap=rhs-lhs;checks.append(dict(stage=stage,constraint=label,value=lhs,limit=rhs,residual=gap))
  if gap<0:violations.append(stage+':'+label)
 def check_all(stage,d=None):
  bn=nav-pendingfees;capital=sum((num(r,'capital') for r in rows),Z);risk=sum((num(r,'risk') for r in rows),Z)
  check('cash_reserve10',nd*D('.1'),cash,stage);check('account_capital90',capital,bn*D('.9'),stage);check('account_risk6',risk,bn*D('.06'),stage)
  if d:
   sec=[r for r in rows if r['sector']==d['sector']];stock=[r for r in rows if r['sid']==d['sid']]
   check('industry_target',sum((num(r,'capital') for r in sec),Z),num(d,'industry_target'),stage)
   check('sector_risk5',sum((num(r,'risk') for r in sec),Z),bn*D('.05'),stage)
   check('stock10',sum((num(r,'capital') for r in stock),Z),nd*D('.1'),stage)
   if d['pool']=='probe':
    trial=[r for r in rows if r['pool']=='probe'];check('probe_capital10',sum((num(r,'capital') for r in trial),Z),bn*D('.1'),stage);check('probe_risk.5',sum((num(r,'risk') for r in trial),Z),bn*D('.005'),stage)
   if d['role']=='core':
    q=Q[d['sid']];p=num(d,'mark')*(ONE+SLIP)
    check('core_risk.25',N.LR.protection_risk(q,p,num(d,'floor'),schedule(d['fees'])),nd*D('.0025'),stage)
 for d in active:
  q=Q[d['sid']];qr=rule(d['quantity']);p=num(d,'mark')*(ONE+SLIP);f=fee(q,p,d['fees'],'buy');gross=D(q)*p
  if not d['eligible'] or not d['receipt_valid'] or d['known_at']>s['at'] or d['deadline']<s['deadline']:violations.append('asof_or_permission_or_receipt:'+d['sid'])
  if num(d,'mark')<=num(d,'floor'):violations.append('gap_at_or_below_actual_floor:'+d['sid'])
  if q!=qr.buy_floor(q) or q>d['max_q']:violations.append('target_or_new_order_minimum:'+d['sid'])
  cash-=gross+f;pendingfees+=f
  row=dict(id='NEW|'+d['sid'],sid=d['sid'],sector=d['sector'],pool=d['pool'],role=d['role'],qty=q,mark=d['mark'],capital=gross,risk=D(q)*max(Z,p-num(d,'floor')),fee=f)
  rows.append(row);by[row['id']]=row;check_all('reserve:'+d['sid'],d)
 for d in active:
  check_all('amend-before-conditional-fill:'+d['sid'],d)
  row=by['NEW|'+d['sid']];p=num(d,'mark')*(ONE+SLIP);f=row['fee'];markcap=D(row['qty'])*num(d,'mark')
  nav+=markcap-num(row,'capital')-f;pendingfees-=f;row['capital']=markcap;row['risk']=D(row['qty'])*max(Z,num(d,'mark')-num(d,'floor'))
  check_all('after-conditional-fill:'+d['sid'],d)
 # Preserve every touched sector/stock/probe constraint in final combined state.
 for d in active:check_all('terminal:'+d['sid'],d)
 return dict(ok=not violations,checks=checks,violations=sorted(set(violations)),terminal=dict(nav=nav,available=cash,capital=sum((num(r,'capital') for r in rows),Z),risk=sum((num(r,'risk') for r in rows),Z)),
   conditional=bool(plan['rows'] or plan['assets']),projected_risk_released=sum((r['risk_release'] for r in plan['rows']),Z)+sum((D(p['risk_release']) for a in plan['assets'] for p in a.get('parts',[])),Z),actual_risk_released=Z,actual_cash_released=Z)

def preview(s,ds,Q):
 before=digest(s)
 try:
  plan=donors(s,ds,Q);v=validate(s,ds,Q,plan)
  return dict(Q=Q,donors=plan,validation=v)
 finally:assert digest(s)==before,'pure preview changed frozen state'

def solve(s,ds):
 before=digest(s);Q={d['sid']:0 for d in ds};trace=[]
 for d in sorted(ds,key=lambda d:(d['priority'],d['sid'])):
  for q in qty_options(d):
   test=dict(Q);test[d['sid']]=q
   x=preview(s,ds,test);trace.append(dict(sid=d['sid'],q=q,ok=x['validation']['ok'],violations=x['validation']['violations']))
   if x['validation']['ok']:Q=test;break
  else:raise AssertionError('zero option must retain previous valid prefix')
 result=preview(s,ds,Q);assert result['validation']['ok'];assert digest(s)==before
 result.update(trace=trace,contract_sha256=CONTRACT_SHA,snapshot_sha256=before,known_at=s['at'],deadline=s['deadline'],raw_targets={d['sid']:d['max_q'] for d in ds},
   state='CONDITIONAL_WAIT_ACTUAL_SALES_AND_SETTLEMENT' if result['validation'].get('conditional') else ('NO_LEGAL_NEW_QUANTITY' if not any(Q.values()) else 'REAL_RESOURCE_RECHECK_REQUIRED'),
   native_financial_events=0,projection_is_not_cash=True)
 result['certificate_id']=digest(result);return result

class CertificateBook:
 """Capped planning commitments only; not a cash ledger or receipt credit."""
 def __init__(self):self.certificates={};self.active={};self.orders={};self.filled={}
 def accept(self,certificate,context):
  if not certificate['validation']['ok']:raise ValueError('cannot commit failed certificate')
  cid=certificate['certificate_id'];self.certificates[cid]=copy.deepcopy(certificate);self.active[context]=cid
 def cap(self,context,sid,raw_q,at):
  c=self.certificates[self.active[context]]
  if at>c['deadline']:return 0
  cid=self.active[context];used=self.filled.get(cid,{}).get(sid,0)
  used+=sum(x['remaining'] for x in self.orders.values() if x['certificate']==cid and x['sid']==sid)
  return min(raw_q,max(0,c['Q'].get(sid,0)-used))
 def bind_reservation(self,context,sid,order_id,q,at):
  if order_id in self.orders or q<=0 or q>self.cap(context,sid,q,at):raise ValueError('certificate quantity already committed')
  self.orders[order_id]=dict(certificate=self.active[context],sid=sid,remaining=q,cancel_pending=False)
 def actual_fill(self,order_id,q):
  o=self.orders[order_id]
  if q<=0 or q>o['remaining']:raise ValueError('invalid actual callback quantity')
  o['remaining']-=q;f=self.filled.setdefault(o['certificate'],{});f[o['sid']]=f.get(o['sid'],0)+q
 def cancel_request(self,order_id):self.orders[order_id]['cancel_pending']=True
 def cancel_ack(self,order_id):self.orders[order_id]['remaining']=0
 def dumps(self):return json.dumps(dict(contract=CONTRACT_SHA,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),certificates=self.certificates,active=self.active,orders=self.orders,filled=self.filled),sort_keys=True,default=str)
 @classmethod
 def loads(cls,text):
  r=json.loads(text)
  if r['contract']!=CONTRACT_SHA or r['source_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():raise ValueError('certificate source/contract identity changed')
  x=cls();x.certificates=r['certificates'];x.active=r['active'];x.orders=r['orders'];x.filled=r['filled'];return x
