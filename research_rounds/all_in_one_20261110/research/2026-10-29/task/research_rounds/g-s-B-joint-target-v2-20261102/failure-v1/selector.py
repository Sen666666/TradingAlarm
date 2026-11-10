"""B-M2 conditional target selector. No account/event API or production writes."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,hashlib,copy,ast,math,collections
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'g-s-joint-funding-projection-jf2-20261102'))
import projector as J
Z=J.Z;ONE=J.ONE;SLIP=J.SLIP
CONTRACT_SHA='d228e5f7e447c799b8ba5c5ca11a945ce98cffb8d64592700fdd64b67d6bec5d'
RANK=W/'pvr-slot1-native-readiness-20261101/native_rank.py'
tree=ast.parse(RANK.read_text());ns={'math':math}
exec(compile(ast.fix_missing_locations(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='priority_plan'],type_ignores=[])),str(RANK)+'::frozen_pure_priority','exec'),ns)
priority_plan=ns['priority_plan']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):J.N.IO.write_json(p,json.loads(json.dumps(x,default=str)))
def num(x,k):return D(x[k])
def make_plan(s,ds,Q,quantities):
 if D(s['other_saved_goal_need'])>0:raise ValueError('RECONCILE_OTHER_COMMITTED_GOALS')
 assets=J.coverage(s);rows=[];orders=[]
 for sid,q in sorted(quantities.items()):
  if not q:continue
  lots=sorted([z for z in s['lots'] if z['sid']==sid and z.get('B_donor_eligible') and z['role']=='mobile'],key=lambda z:z['fifo'])
  if not lots:raise ValueError('no legal mobile inventory')
  if any(z['mark']!=lots[0]['mark'] or z['fees']!=lots[0]['fees'] for z in lots):raise ValueError('UNKNOWN inconsistent stock fee/mark')
  mark=num(lots[0],'mark');p=mark*(ONE-SLIP);f=J.fee(q,p,lots[0]['fees'],'sell');left=q;parts=[];allocated=Z
  for z in lots:
   if z.get('sellable_qty') is None:raise ValueError('UNKNOWN mobile sellability')
   n=min(left,z['qty'],z['sellable_qty']);left-=n
   if n:parts.append(dict(layer=z['id'],sid=sid,q=n,risk_release=num(z,'risk')*D(n)/z['qty'],capital=D(n)*mark,allocation_class='B_weaker_mobile'))
   if not left:break
  if left:raise ValueError('cannot borrow core/unavailable mobile')
  for ix,part in enumerate(parts):
   ff=f-allocated if ix==len(parts)-1 else f*D(part['q'])/q;allocated+=ff;part['net']=D(part['q'])*p-ff
  rows+=parts;orders.append(dict(sid=sid,q=q,fees=f,net=D(q)*p-f,parts=parts))
 cash=sum((J.buy_cost(d,Q.get(d['sid'],0)) for d in ds),Z)
 need=max(Z,cash-max(Z,num(s,'available')-num(s,'decision_nav')*D('.1')))
 covered=min(need,sum((num(a,'amount') for a in assets),Z));donated=sum((r['net'] for r in rows),Z)
 return dict(rows=rows,orders=orders,raw_need=need,covered=covered,uncovered=need-covered,still_unfunded=max(Z,need-covered-donated),assets=assets)

def evaluate(s,ds,Q,donor_qty):
 plan=make_plan(s,ds,Q,donor_qty)
 return dict(Q=dict(Q),D=dict(donor_qty),donors=plan,validation=J.validate(s,ds,Q,plan))

def necessary_upper(s,ds,Q,d,plan):
 """Necessary bound at current candidate's pre-fill stage with D fixed.
 It omits current-order fees, hence cannot prune a legal quantity. D is still
 exhaustively enumerated; no monotonic assumption is made over joint (Q,D).
 """
 rows=copy.deepcopy(s['rows']);by={r['id']:r for r in rows};cash=num(s,'available');nav=num(s,'nav')
 def sale(p):
  r=by[p['layer']];cap=D(p['q'])*num(r,'mark');r['capital']=num(r,'capital')-cap;r['risk']=num(r,'risk')-D(p['risk_release']);return cap
 for a in plan['assets']:
  cap=sum((sale(p) for p in a.get('parts',[])),Z);cash+=num(a,'amount')
  if a['kind']=='pending_exit':nav+=num(a,'amount')-cap
 for p in plan['rows']:
  cap=sale(p);cash+=p['net'];nav+=p['net']-cap
 for prev in ds:
  q=Q.get(prev['sid'],0)
  if not q:continue
  cost=J.buy_cost(prev,q);cap=D(q)*num(prev,'mark');cash-=cost;nav+=cap-cost
  rows.append(dict(sid=prev['sid'],sector=prev['sector'],pool=prev['pool'],capital=cap,risk=D(q)*max(Z,num(prev,'mark')-num(prev,'floor'))))
 nd=num(s,'decision_nav');bn=nav-num(s,'pending_fees');p=num(d,'mark')*(ONE+SLIP);rp=p-num(d,'floor')
 if num(d,'mark')<=num(d,'floor'):return 0,['gap_at_or_below_actual_floor']
 cap=sum((num(r,'capital') for r in rows),Z);risk=sum((num(r,'risk') for r in rows),Z)
 sec=[r for r in rows if r['sector']==d['sector']];stock=[r for r in rows if r['sid']==d['sid']]
 bounds=dict(raw_target=D(d['max_q']),cash_reserve10=(cash-nd*D('.1'))/p,
   account_capital90=(bn*D('.9')-cap)/p,account_risk6=(bn*D('.06')-risk)/rp,
   industry_target=(num(d,'industry_target')-sum((num(r,'capital') for r in sec),Z))/p,
   sector_risk5=(bn*D('.05')-sum((num(r,'risk') for r in sec),Z))/rp,
   stock10=(nd*D('.1')-sum((num(r,'capital') for r in stock),Z))/p)
 raw=min(bounds.values());q=J.rule(d['quantity']).buy_floor(max(0,int(raw)))
 return q,[k for k,v in bounds.items() if v==raw]

def sell_totals(lots,already,whole_stock):
 maxq=sum(min(z['qty'],z['sellable_qty']) for z in lots);r=J.rule(lots[0]['quantity'])
 values=[q for q in range(r.sell_step,maxq+1,r.sell_step) if q>already]
 if r.allow_full_exit_odd and maxq==whole_stock and maxq>already and maxq not in values:values.append(maxq)
 return sorted(values)

def solve_B(s,ds,*,max_native_checks=100000,progress=None,oracle=False):
 J.schema(s,ds);assert all(d['role']=='mobile' and d['pool']=='confirmed' for d in ds)
 before=J.digest(s);ds=sorted(ds,key=lambda d:(d['priority'],d['sid']));Q={d['sid']:0 for d in ds};donated={};trace=[];checks=0;donor_views=0
 for d in ds:
  sid=d['sid'];bestq=0;bestD=dict(donated);reasons=collections.Counter();local_checks=0
  if donated.get(sid,0):
   trace.append(dict(sid=sid,priority=d['priority'],raw_max=d['max_q'],q=0,reason='ALREADY_NET_DONOR_FOR_STRONGER'));continue
  def attempt(Dmap):
   nonlocal bestq,bestD,checks,local_checks,donor_views
   donor_views+=1;plan=make_plan(s,ds,Q,Dmap)
   if oracle:upper=d['max_q'];lim=[]
   else:upper,lim=necessary_upper(s,ds,Q,d,plan)
   reasons.update('necessary_bound:'+x for x in lim)
   r=J.rule(d['quantity']);q=r.buy_floor(upper)
   while q>bestq:
    test=dict(Q);test[sid]=q;checks+=1;local_checks+=1
    if checks>max_native_checks:raise RuntimeError('TECHNICAL native-check budget exceeded; no approximate result')
    x=evaluate(s,ds,test,Dmap)
    if x['validation']['ok']:bestq=q;bestD=dict(Dmap);return
    reasons.update(x['validation']['violations']);q-=r.buy_step
  attempt(donated)
  if bestq<d['max_q']:
   groups=collections.defaultdict(list)
   for z in s['lots']:
    if z['role']!='mobile' or not z.get('B_donor_eligible'):continue
    if z.get('sellable_qty') is None:raise ValueError('UNKNOWN mobile sellability')
    if z['sid']==sid or Q.get(z['sid'],0) or tuple(z['rank_key'])<=tuple(d['priority']):continue
    groups[z['sid']].append(z)
   weak=sorted(groups,key=lambda sid:tuple(groups[sid][0]['rank_key']),reverse=True);prefix=dict(donated)
   for oldsid in weak:
    lots=groups[oldsid];stock_total=sum(z['qty'] for z in s['lots'] if z['sid']==oldsid)
    values=sell_totals(lots,prefix.get(oldsid,0),stock_total)
    for total in values:
     trial=dict(prefix);trial[oldsid]=total;attempt(trial)
     if bestq==d['max_q']:break
    if bestq==d['max_q']:break
    if values:prefix[oldsid]=values[-1]
  Q[sid]=bestq;donated=bestD
  trace.append(dict(sid=sid,priority=d['priority'],raw_max=d['max_q'],q=bestq,D=dict(donated),native_checks=local_checks,
    blockers_or_necessary_bounds=dict(reasons),note='bounds are necessary-state diagnostics, not independent opportunity counts'))
  if progress:progress(trace[-1])
 result=evaluate(s,ds,Q,donated);assert result['validation']['ok'] and J.digest(s)==before
 h=collections.Counter()
 for z in s['lots']:
  if z['role']=='mobile':h[z['sid']]+=z['qty']
 T={sid:h[sid]+Q.get(sid,0)-donated.get(sid,0) for sid in set(h)|set(Q)}
 assert all(not (Q.get(sid,0) and donated.get(sid,0)) for sid in T)
 result.update(policy='B_M2_mobile_increment_competition',mobile_targets=T,trace=trace,native_checks=checks,donor_views=donor_views,
   snapshot_sha256=before,demands_sha256=J.digest(ds),selector_sha256=sha(__file__),joint_guard_sha256=sha(J.__file__),contract_sha256=sha(O/'CONTRACT_V2.txt'),
   analysis_only=True,submit_allowed=False,financial_events=0)
 result['result_id']=J.digest(result);return result
