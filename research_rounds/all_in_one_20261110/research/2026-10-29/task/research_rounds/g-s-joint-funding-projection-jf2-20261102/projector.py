"""JF1 pure known-state resource projection. No account events or fake fills."""
from pathlib import Path
import sys,json,hashlib,copy,inspect
from datetime import datetime
from decimal import Decimal as D
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'g-s-historical-native-prefix-20261101'))
import imports_native as N
Z=D(0);ONE=D(1);SLIP=N.LR.SLIP
CONTRACT_SHA='b0395b6ebbc0d768e4aa59ed332aaddc51a6cc52353f2a861b3d4ff6f9db260d'
AMENDMENT_SHA='5661cfdb2e0627b63d05a880c5fd161434996ab1b231d700fd90cda86506ee32'
def aware(x):
 t=datetime.fromisoformat(x)
 if t.tzinfo is None or t.utcoffset() is None:raise ValueError('aware original clock required')
 return t
def schema(s,ds):
 for k in ('account_id','target_id','receipt_registry','other_saved_goal_need','analysis_only','at','deadline'):
  if k not in s:raise ValueError('missing trusted snapshot field '+k)
 aware(s['at']);aware(s['deadline'])
 for d in ds:
  for k in ('price_known_at','known_at','receipt_id','receipt_binding','deadline'):
   if k not in d:raise ValueError('missing demand field '+k)
  for k in ('price_known_at','known_at','deadline'):aware(d[k])
  b=d['receipt_binding']
  for k in ('event_id','sid','source','source_binding','payload_sha256','start','end','confirmed','deadline','structure','scale','market_context'):
   if k not in b:raise ValueError('missing receipt field '+k)
  for k in ('start','end','confirmed','deadline'):aware(b[k])
  if b['event_id']!=d['receipt_id'] or b['sid']!=d['sid'] or b['deadline']!=d['deadline']:raise ValueError('receipt identity/expiry mismatch')
  if s['receipt_registry'].get(d['receipt_id'])!=digest(b):raise ValueError('receipt not in trusted snapshot registry')
def source_binding():
 contract=Path(__file__).resolve().parent.parent/'g-s-joint-funding-projection-contract-20261101/CONTRACT.txt'
 if hashlib.sha256(contract.read_bytes()).hexdigest()!=CONTRACT_SHA:raise ValueError('joint projection contract changed')
 cost=getattr(N.LR,'CURRENT',{}).get('cost',1)
 if cost!=1:raise ValueError('JF1 only frozen normal cost semantics')
 paths={Path(__file__).resolve(),Path(N.__file__).resolve(),Path(N.LR.__file__).resolve(),contract}
 amendment=Path(__file__).with_name('AMENDMENT.txt')
 if hashlib.sha256(amendment.read_bytes()).hexdigest()!=AMENDMENT_SHA:raise ValueError('JF2 amendment changed')
 paths.add(amendment)
 paths.update(Path(inspect.getsourcefile(x)).resolve() for x in (N.T.QuantityRule,N.T.FeeSchedule,N.LR.fees,N.LR.protection_risk))
 return dict(sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},cost_multiplier=cost,slippage=str(SLIP))
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
 if D(s['other_saved_goal_need'])>0:raise ValueError('RECONCILE_OTHER_COMMITTED_GOALS: exclusive cash/assets and complete old resource commitments unproven')
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
  lot=next(z for z in s['lots'] if z['id']==part['layer'])
  if lot.get('sellable_qty') is None:raise ValueError('UNKNOWN designated sale availability')
  if q>lot['sellable_qty']:violations.append('designated_sale_not_yet_sellable:'+row['sid'])
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
   if d['role']=='core' or d['use']=='T':
    check('original_trial_or_core_target2',D(Q[d['sid']])*num(d,'mark')*(ONE+SLIP),nd*D('.02'),stage)
   if d['pool']=='probe':
    trial=[r for r in rows if r['pool']=='probe'];check('probe_capital10',sum((num(r,'capital') for r in trial),Z),bn*D('.1'),stage);check('probe_risk.5',sum((num(r,'risk') for r in trial),Z),bn*D('.005'),stage)
   if d['role']=='core':
    q=Q[d['sid']];p=num(d,'mark')*(ONE+SLIP)
    check('core_risk.25',N.LR.protection_risk(q,p,num(d,'floor'),schedule(d['fees'])),nd*D('.0025'),stage)
 for d in active:
  q=Q[d['sid']];qr=rule(d['quantity']);p=num(d,'mark')*(ONE+SLIP);f=fee(q,p,d['fees'],'buy');gross=D(q)*p
  b=d['receipt_binding']
  temporal=aware(b['start'])<=aware(b['end'])<=aware(b['confirmed'])==aware(d['known_at'])==aware(s['at'])
  if not d['eligible'] or not d['receipt_valid'] or not temporal or aware(d['deadline'])<aware(s['deadline']):violations.append('asof_or_permission_or_receipt:'+d['sid'])
  if aware(d['price_known_at'])>aware(s['at']):violations.append('future_price_known_at:'+d['sid'])
  if d['role']=='core' and d['use']!='T':violations.append('core_only_original_trial_role:'+d['sid'])
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
 schema(s,ds)
 before=digest(s)
 try:
  plan=donors(s,ds,Q);v=validate(s,ds,Q,plan)
  return dict(Q=Q,donors=plan,validation=v)
 finally:assert digest(s)==before,'pure preview changed frozen state'

def solve(s,ds):
 schema(s,ds)
 before=digest(s);Q={d['sid']:0 for d in ds};trace=[]
 for d in sorted(ds,key=lambda d:(d['priority'],d['sid'])):
  for q in qty_options(d):
   test=dict(Q);test[d['sid']]=q
   x=preview(s,ds,test);trace.append(dict(sid=d['sid'],q=q,ok=x['validation']['ok'],violations=x['validation']['violations']))
   if x['validation']['ok']:Q=test;break
  else:raise AssertionError('zero option must retain previous valid prefix')
 result=preview(s,ds,Q);assert result['validation']['ok'];assert digest(s)==before
 # Existing live sell obligations cannot be silently removed/replaced. If a
 # whole old funding order could be excessive, native goal/cancel reconciliation
 # is required before this numeric projection may become new authority.
 oldassets=result['donors']['assets'];remaining=sum((num(a,'amount') for a in oldassets),Z)
 need=result['donors']['raw_need']+D(s.get('other_saved_goal_need',0));reconcile=[]
 for a in sorted([a for a in oldassets if a.get('pure_funding')],key=lambda a:(-a.get('sequence',0),a['id'])):
  if remaining-num(a,'amount')>=need:
   reconcile.append(a['id']);remaining-=num(a,'amount')
 result.update(trace=trace,contract_sha256=CONTRACT_SHA,amendment_sha256=AMENDMENT_SHA,snapshot_sha256=before,demands_sha256=digest(ds),account_id=s['account_id'],target_id=s['target_id'],
   receipt_bindings={d['sid']:d['receipt_binding'] for d in ds},known_at=s['at'],deadline=s['deadline'],raw_targets={d['sid']:d['max_q'] for d in ds},
   source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
   native_source_binding=source_binding(),
   requires_native_existing_funding_reconciliation=bool(reconcile),possible_whole_order_excess=reconcile,
   state='CONDITIONAL_WAIT_ACTUAL_SALES_AND_SETTLEMENT' if result['validation'].get('conditional') else ('NO_LEGAL_NEW_QUANTITY' if not any(Q.values()) else 'REAL_RESOURCE_RECHECK_REQUIRED'),
   native_financial_events=0,projection_is_not_cash=True)
 result['certificate_id']=digest(result);return result

def verify_certificate(c,s,ds):
 if not isinstance(c,dict) or 'certificate_id' not in c:raise ValueError('missing certificate digest')
 body={k:v for k,v in c.items() if k!='certificate_id'}
 if digest(body)!=c['certificate_id']:raise ValueError('certificate body digest mismatch')
 if c.get('snapshot_sha256')!=digest(s) or c.get('account_id')!=s.get('account_id') or c.get('target_id')!=s.get('target_id'):raise ValueError('actual snapshot/account/target mismatch')
 expected=solve(s,ds)
 if digest(c)!=digest(expected):raise ValueError('certificate differs from trusted snapshot and receipt proof')
 return True

class CertificateBook:
 """A restricting certificate store; caller must supply original trusted views."""
 def __init__(self):self.certificates={};self.active={};self.orders={};self.filled={};self.fill_receipts={}
 def commitments(self):return copy.deepcopy(dict(orders=self.orders,filled=self.filled,fill_receipts=self.fill_receipts))
 def _check(self):
  sums={}
  for cid,c in self.certificates.items():
   if cid!=c.get('certificate_id') or digest({k:v for k,v in c.items() if k!='certificate_id'})!=cid:raise ValueError('certificate body digest mismatch in state')
  for oid,o in self.orders.items():
   if not {'certificate','sid','receipt_id','initial','remaining','filled','cancelled','cancel_pending'}<=set(o):raise ValueError('missing order state field')
   if o['certificate'] not in self.certificates:raise ValueError('unknown order certificate')
   c=self.certificates[o['certificate']];sid=o['sid']
   for k in ('initial','remaining','filled','cancelled'):
    if type(o.get(k)) is not int or o[k]<0:raise ValueError('invalid committed quantity')
   if o['initial']!=o['remaining']+o['filled']+o['cancelled']:raise ValueError('order quantity conservation')
   if sid not in c['Q'] or o['receipt_id']!=c['receipt_bindings'][sid]['event_id']:raise ValueError('order receipt not bound to certificate')
   key=(o['certificate'],sid);sums[key]=sums.get(key,0)+o['remaining']+o['filled']
  for (cid,sid),q in sums.items():
   if q>self.certificates[cid]['Q'][sid]:raise ValueError('certificate quantity overcommitted')
   if self.filled.get(cid,{}).get(sid,0)!=sum(o['filled'] for o in self.orders.values() if o['certificate']==cid and o['sid']==sid):raise ValueError('missing aggregate filled state')
  for cid,by in self.filled.items():
   if cid not in self.certificates:raise ValueError('unknown filled certificate')
   for sid,q in by.items():
    if type(q) is not int or q<0 or q!=sum(o['filled'] for o in self.orders.values() if o['certificate']==cid and o['sid']==sid):raise ValueError('filled state conservation')
  for oid,o in self.orders.items():
   actual=sum(v['q'] for v in self.fill_receipts.values() if v['order_id']==oid)
   if actual!=o['filled']:raise ValueError('fill receipt state conservation')
  for v in self.fill_receipts.values():
   if v.get('order_id') not in self.orders or type(v.get('q')) is not int or v['q']<=0:raise ValueError('unbound fill receipt')
  for ctx,cid in self.active.items():
   if cid not in self.certificates or self.certificates[cid]['target_id']!=ctx:raise ValueError('active target identity mismatch')
 def accept(self,c,context,*,snapshot,demands,actual_commitments):
  self._check()
  if digest(actual_commitments)!=digest(self.commitments()):raise ValueError('actual commitment state mismatch')
  verify_certificate(c,snapshot,demands)
  if snapshot['analysis_only']:raise ValueError('analysis view is not actual account authority')
  if context!=c['target_id']:raise ValueError('persistent target identity mismatch')
  if not c['validation']['ok']:raise ValueError('cannot commit failed certificate')
  if c.get('requires_native_existing_funding_reconciliation'):raise ValueError('WAIT existing funding goal/cancel acknowledgement reconciliation')
  previous=self.active.get(context)
  if previous and previous!=c['certificate_id']:
   old=self.certificates[previous]
   if old['snapshot_sha256']==c['snapshot_sha256'] or aware(c['known_at'])<=aware(old['known_at']):raise ValueError('fresh receipt cannot replace proof on same/stale snapshot')
   if any(o['remaining'] for o in self.orders.values() if o['certificate']==previous):raise ValueError('WAIT previous actual order responsibilities')
  self.certificates[c['certificate_id']]=copy.deepcopy(c);self.active[context]=c['certificate_id'];self._check()
 def cap(self,context,sid,raw_q,at,*,receipt_id):
  self._check();c=self.certificates[self.active[context]]
  if sid not in c['receipt_bindings'] or receipt_id!=c['receipt_bindings'][sid]['event_id']:raise ValueError('different receipt cannot use this authorization')
  if aware(at)<aware(c['known_at']) or aware(at)>aware(c['deadline']):return 0
  cid=self.active[context];used=self.filled.get(cid,{}).get(sid,0)
  used+=sum(o['remaining'] for o in self.orders.values() if o['certificate']==cid and o['sid']==sid)
  return min(raw_q,max(0,c['Q'].get(sid,0)-used))
 def bind_reservation(self,context,sid,order_id,q,at,*,receipt_id):
  if type(q) is not int or order_id in self.orders or q<=0 or q>self.cap(context,sid,q,at,receipt_id=receipt_id):raise ValueError('certificate quantity already committed')
  self.orders[order_id]=dict(certificate=self.active[context],sid=sid,receipt_id=receipt_id,initial=q,remaining=q,filled=0,cancelled=0,cancel_pending=False);self._check()
 def actual_fill(self,order_id,q,*,fill_receipt_id):
  if not fill_receipt_id:raise ValueError('actual fill receipt required')
  if fill_receipt_id in self.fill_receipts:
   if self.fill_receipts[fill_receipt_id]!=dict(order_id=order_id,q=q):raise ValueError('fill receipt alias mismatch')
   return
  o=self.orders[order_id]
  if type(q) is not int or q<=0 or q>o['remaining']:raise ValueError('invalid actual callback quantity')
  o['remaining']-=q;o['filled']+=q;f=self.filled.setdefault(o['certificate'],{});f[o['sid']]=f.get(o['sid'],0)+q
  self.fill_receipts[fill_receipt_id]=dict(order_id=order_id,q=q);self._check()
 def cancel_request(self,order_id):self.orders[order_id]['cancel_pending']=True
 def cancel_ack(self,order_id):
  o=self.orders[order_id];o['cancelled']+=o['remaining'];o['remaining']=0;self._check()
 def dumps(self):
  self._check()
  body=dict(schema='JF2',contract=CONTRACT_SHA,amendment=AMENDMENT_SHA,native_source_binding=source_binding(),certificates=self.certificates,active=self.active,**self.commitments())
  return json.dumps(dict(body,book_id=digest(body)),sort_keys=True,default=str)
 @classmethod
 def loads(cls,text,*,trusted_inputs,actual_commitments):
  r=json.loads(text)
  required={'schema','contract','amendment','native_source_binding','certificates','active','orders','filled','fill_receipts','book_id'}
  if set(r)!=required:raise ValueError('missing/unsupported persisted schema')
  if digest({k:v for k,v in r.items() if k!='book_id'})!=r['book_id']:raise ValueError('book body digest mismatch')
  if r['schema']!='JF2' or r['contract']!=CONTRACT_SHA or r['amendment']!=AMENDMENT_SHA or r['native_source_binding']!=source_binding():raise ValueError('native source/contract identity changed')
  for cid,c in r['certificates'].items():
   if cid!=c.get('certificate_id') or c.get('snapshot_sha256') not in trusted_inputs:raise ValueError('trusted original snapshot missing')
   s,ds=trusted_inputs[c['snapshot_sha256']];verify_certificate(c,s,ds)
   if s['analysis_only']:raise ValueError('analysis view cannot restore authority')
  x=cls();x.certificates=r['certificates'];x.active=r['active'];x.orders=r['orders'];x.filled=r['filled'];x.fill_receipts=r['fill_receipts'];x._check()
  if digest(actual_commitments)!=digest(x.commitments()):raise ValueError('actual commitment state mismatch')
  return x
