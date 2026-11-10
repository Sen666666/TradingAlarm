"""Generated prices only. Never loads historical input or advances a history account."""
from native_c import *
import unittest,subprocess,time,traceback
from dataclasses import replace

ROOT=HERE/'runs';ROOT.mkdir(exist_ok=True)
DATES=[iso(s) for s in N.RULES['calendars']['A'] if '2025-07-01'<=s<'2025-08-01']
def op(n):return DATES[n]
def cl(n):return op(n).replace(hour=15,minute=10)
SOURCE=F1.Source('C-native-synthetic','causal-generated-prices','explicit-breadth','frozen-original-kernel')
def seed(r,s):r.f1[s]=F1.State(s,source=SOURCE,previous_close=100,prior_closes=(100,)*63,prior_abs_returns=(.01,)*63)
def ob(s,n,p=101,breadth=.8):
 if s not in CURRENT.f1:seed(CURRENT,s)
 return F1.Observation(cl(n).isoformat(),SOURCE,p,breadth)
def fixtures(r,n=9,prefix='A',sector=None,price=99,floor=94,star=False):
 a=r.account;ids=[]
 for j in range(n):
  sid=prefix+str(j);sec=sector(j) if callable(sector) else sector or 'S'+str(j//2)
  a.mark(sid,price,cl(0)-timedelta(minutes=1),sec,star,floor);ids.append(sid)
 return ids
def packet(r,sids,n,*,priorities=None,receipt=True,core=True):
 out={};a=r.account
 for j,sid in enumerate(sids):
  c=None
  if receipt:
   payload=json.dumps(dict(sid=sid,confirmed=cl(n).isoformat(),fixture=True),sort_keys=True)
   c=N.HistoricalReceipt('synthetic|'+sid+'|'+str(n),sid,cl(n)-timedelta(days=1),cl(n),cl(n),(0,1),source='synthetic_causal_CP1_interface',payload_json=payload,payload_sha256=hashlib.sha256(payload.encode()).hexdigest(),source_binding='synthetic-explicit-input-v1')
   a.receipt_registry[c.event_id]=digest(asdict(c))
  out[sid]=dict(known_at=cl(n),close=a.market.prices[sid],i_valid=True,q=True,core_event=core,receipt=c,cp_floor=a.facts.floors[sid],i_floor=a.facts.floors[sid],priority=tuple((priorities or {}).get(sid,(j,))),structure=(0,1))
 return out
def close(r,n,rows,observations=None,h1=None):
 observations=observations or {};secs=set(r.account.market.sectors.values())
 e=dict(day=cl(n).date().isoformat(),known_at=cl(n).isoformat(),industry_H1=h1 or {s:100-j for j,s in enumerate(sorted(secs))})
 return r.event(cl(n),observations=observations,stocks=rows,next_open=op(n+1),industry_evidence=e)
def obs(r,scope,n,p=101,b=.8):
 if scope not in r.f1:seed(r,scope)
 return F1.Observation(cl(n).isoformat(),SOURCE,p,b)
def win(r,sid,at,side='sell',capacity=10**8,eid=None,due=None):
 a=r.account;p=a.market.prices[sid]
 return T.window(sid,p*(ONE+LR.SLIP if side=='buy' else ONE-LR.SLIP),at,capacity,fees=a.market.fees(sid,at),rule=a.market.quantity(sid,at),eid=eid or side+'|'+sid+'|'+at.isoformat(),raw_open=p,sellable_at=at+timedelta(days=1),cash_due_at=due or at)
def funded(mode='C10',n=9,star=False):
 r=Runner(mode);ss=fixtures(r,n=n,star=star);close(r,0,packet(r,ss,0),{'G':obs(r,'G',0)});r.event(op(1),is_open=True);return r,ss
def switch(r,old,n=2,newn=4):
 new=fixtures(r,newn,'B','NEW')
 if 'NEW' not in r.f1:close(r,n-1,packet(r,old,n-1,receipt=False,core=False),{'NEW':obs(r,'NEW',n-1)})
 prior={s:(100+i,) for i,s in enumerate(old)};prior.update({s:(i,) for i,s in enumerate(new)})
 rows=packet(r,old+new,n,priorities=prior)
 # New industry uses global G with industry20, enough to require funding;
 # old/new sectors get explicit as-of H1, no future outcomes choose ranking.
 h={s:(200 if s=='NEW' else 50) for s in set(r.account.market.sectors.values())}
 close(r,n,rows,{'NEW':obs(r,'NEW',n,105)},h);return new

class Cases(unittest.TestCase):
 evidence={}
 def keep(self,name,r,at,extra=None):
  x=dict(state=r.observable(at),extra=extra or {});self.evidence[name]=x
  IO.write_json(ROOT/(name+'.json'),x,encoder=encode)
 def test01_empty_account_budget_does_not_limit_fast_G(self):
  states=[]
  for mode in ('C10','C_BATCH20'):
   r,ss=funded(mode,star=True);b=r.account.bridge(op(1));ex=b['inventory']/b['nav']
   self.assertGreater(ex,D('.895'));self.assertLess(ex,D('.901'));self.assertEqual(len(r.account.positions),9)
   self.assertEqual(D(r.budget.batch['new']),0);self.assertFalse(r.active['D'])
   # Strip intentional mode/authority proof metadata, compare native economy.
   states.append(digest(dict(balance=b,fills=[asdict(f) for f in r.account.fills],layers=r.account.layers)))
   self.keep('01_empty_'+mode,r,op(1),dict(exposure=ex))
  self.assertEqual(*states)
 def test02_healthy_full_account_joint_budget_binding(self):
  rows=[]
  for mode in ('C10','C_BATCH20'):
   r,ss=funded(mode);new=switch(r,ss);p=r.results[-1]['projection'];gross=sum(D(z['q'])*r.account.market.prices[z['sid']] for z in p['donors']['rows'])
   self.assertGreater(gross,0);self.assertEqual(r.account.available,r.account.bridge(cl(2))['available'])
   if mode=='C_BATCH20':self.assertLessEqual(gross,D('.2')*r.account.policy.nd)
   rows.append(gross);self.keep('02_full_'+mode,r,cl(2),dict(gross=gross,actual_new_stocks_before_sale=0))
  self.assertGreater(rows[0],rows[1])
 def test03_partial_sell_settlement_and_close_carry(self):
  r,ss=funded('C_BATCH20');switch(r,ss);a=r.account;d=next(z for z in a.layers if str(z['id']) in r.budget.lines and r.budget.lines[str(z['id'])]['opp'])
  sid=d['sid'];q=sum(v.remaining for v in a.policy.locks.values() if v.lot==d['id']);first=min(100,q);cash=a.available;new=D(r.budget.batch['new'])
  r.apply_window('sell',sid,win(r,sid,op(3),capacity=first,eid='partial-sell',due=op(4)))
  self.assertEqual(a.available,cash);self.assertGreater(a.balance(op(3),a.market.marks(op(3),a.positions))['sale_receivable'],0)
  self.assertEqual(D(r.budget.batch['new']),new)
  # At next CLOSE old unfilled duties survive. No refreshed certificate can
  # assume these expected proceeds are already spendable.
  allids=list(a.market.prices);pr={s:(j,) for j,s in enumerate(allids)}
  close(r,3,packet(r,allids,3,priorities=pr),{})
  expected=sum(D(max(0,z['opp']-z['mandatory']))*a.market.prices[z['sid']] for z in r.budget.batch['frozen_lines'].values())
  self.assertEqual(D(r.budget.batch['carry']),expected);self.assertGreater(expected,0)
  before=a.available;a.settle_due(op(4));self.assertGreater(a.available,before);r.assert_observers()
  self.keep('03_partial_carry',r,op(4),dict(previous_new=new,next_carry=expected,cash_before_settle=before,cash_after_settle=a.available))
 def test04_partial_STAR_buy_cancel_ACK_and_receipt_once(self):
  r=Runner('C_BATCH20');ss=fixtures(r,1,star=True,price=100,floor=95);close(r,0,packet(r,ss,0),{'G':obs(r,'G',0)})
  sid=ss[0];r.event(op(1),is_open=True,capacities={sid:0});a=r.account;o=a.buys[sid];q=o.remaining_shares
  f=r.apply_window('buy',sid,win(r,sid,op(1)+timedelta(minutes=1),'buy',q-50,'partial-buy'))
  self.assertEqual(f.shares,q-50);self.assertEqual(a.buys[sid].remaining_shares,50)
  g=r.apply_window('buy',sid,win(r,sid,op(1)+timedelta(minutes=2),'buy',50,'remainder50'))
  self.assertEqual(g.shares,50);self.assertEqual(f.fees_cny+g.fees_cny,LR.fees(q,a.market.prices[sid]*(ONE+LR.SLIP),a.market.fees(sid,op(1)),'buy'))
  self.assertIsNone(r.apply_window('buy',sid,win(r,sid,op(1)+timedelta(minutes=2),'buy',50,'remainder50')))
  other=fixtures(r,1,'P','X',star=True);close(r,1,packet(r,ss+other,1),{});r.event(op(2),is_open=True,capacities={s:0 for s in ss+other})
  o=a.buys[other[0]];before=a.available;reserve=o.remaining_budget_cny+o.fee_reserved_cny
  a.request_buy_cancel(other[0]);self.assertEqual(a.available,before);r.assert_observers();a.ack_buy_cancel(other[0]);self.assertEqual(a.available,before+reserve);r.assert_observers()
  cid=r.active['certificate_id']
  with self.assertRaises(ValueError):r.authority.bind(cid,other[0],'alias',200,r.active['receipt_bindings'][other[0]]['event_id'])
  self.keep('04_partial_STAR_cancel',r,op(2),dict(fee_once=f.fees_cny+g.fees_cny,partial_remainder=50))
 def test05_independent_stop_exempt_and_rank_not_exempt(self):
  r,ss=funded('C_BATCH20');switch(r,ss);a=r.account;before_new=r.budget.batch['new'];z=next(z for z in a.layers if z['qty']);key=str(z['id'])
  with self.assertRaises(ValueError):a.trim(z['id'],z['qty'],T.admission.Clock(cl(2),op(3),cl(2).date()),'rank_decline')
  with self.assertRaises(ValueError):a.trim(z['id'],z['qty'],T.admission.Clock(cl(2),op(3),cl(2).date()),'I_structure_exit')
  charged=sum(D(p['charge']) for p in r.budget.plans.values())
  rows=packet(r,list(a.market.prices),3,receipt=False,core=False);rows[z['sid']]['i_valid']=False
  close(r,3,rows,{})
  self.assertEqual(sum(D(p['charge']) for p in r.budget.plans.values()),charged)
  self.assertEqual(r.budget.lines[key]['mandatory'],z['qty']);r.assert_observers()
  a.mark(z['sid'],90,op(4),a.market.sectors[z['sid']],False);self.assertGreater(a.totals()['risk'],0)
  self.keep('05_stop_exempt',r,op(4),dict(original_authorization_not_refunded=before_new,current_mandatory=z['qty']))
 def test06_cancel_funding_ACK_no_same_batch_refund(self):
  r,ss=funded('C_BATCH20');switch(r,ss);a=r.account;sid=next(iter(a.exits));new=r.budget.batch['new'];cash=a.available
  a.request_funding_cancel(sid,cl(2)+timedelta(minutes=1));self.assertEqual(a.available,cash)
  self.assertTrue(any(z['opp'] for z in r.budget.lines.values() if z['sid']==sid))
  r.event(cl(2)+timedelta(minutes=2),funding_cancel_acks=[(sid,True)])
  self.assertEqual(a.available,cash);self.assertEqual(r.budget.batch['new'],new);self.assertTrue(all(not z['opp'] for z in r.budget.lines.values() if z['sid']==sid))
  self.keep('06_cancel_funding',r,cl(2)+timedelta(minutes=2))
 def test07_split_native_lock_pending_and_atomic_fraction(self):
  r,ss=funded('C_BATCH20');switch(r,ss);a=r.account;sid=next(iter(a.exits));before=a.quantity(sid);cash=a.available
  at=op(3)-timedelta(minutes=10);r.event(at,actions=[dict(event_id='split2',sid=sid,ratio=D(2),at=at,new_shares_sellable_at=op(4))])
  self.assertEqual(a.quantity(sid),before*2);self.assertEqual(a.available,cash);r.assert_observers()
  before_digest=digest(r.observable(at));badat=at+timedelta(minutes=1)
  with self.assertRaises(ValueError):r.event(badat,actions=[dict(event_id='fraction',sid=sid,ratio=D('.3333'),at=badat,new_shares_sellable_at=op(4))])
  self.assertEqual(digest(r.observable(at)),before_digest)
  self.keep('07_native_split_atomic',r,at)
 def test08_source_snapshot_certificate_tamper_rejected(self):
  r,ss=funded('C_BATCH20');bad=copy.deepcopy(r.active);sid=next(iter(bad['Q']));bad['Q'][sid]+=100
  with self.assertRaises(ValueError):r.verify_native(bad)
  bad['certificate_id']=digest({k:v for k,v in bad.items() if k!='certificate_id'})
  with self.assertRaises(ValueError):r.verify_native(bad)
  s,ds,_=r.provider(cl(1),[],dict(known_at=cl(1).isoformat()))
  with self.assertRaises(ValueError):r.advance_snapshot('wrong',s)
  require(r.results[0]['projection']['analysis_only'],'projection flag retained')
  with self.assertRaises(ValueError):J.verify_certificate(r.active,r.trusted[r.active['trusted_id']]['snapshot'],r.trusted[r.active['trusted_id']]['demands'])
  self.keep('08_tamper',r,cl(1))
 def test09_restart_and_idempotent_callbacks(self):
  r,ss=funded('C_BATCH20');switch(r,ss);cp=ROOT/'checkpoints'/'carry.pkl';r.checkpoint(cp);before=digest(r.observable(cl(2)))
  out=ROOT/'checkpoints'/'restored.json'
  subprocess.run([sys.executable,'-B',str(HERE/'restore_check.py'),str(cp),str(out),cl(2).isoformat()],check=True,capture_output=True,text=True)
  self.assertEqual(json.loads(out.read_text())['digest'],before)
  restored=Runner.restore(cp);self.assertEqual(digest(restored.observable(cl(2))),before)
  side=cp.with_suffix('.provenance.json');old=side.read_bytes();x=json.loads(old);x['binding']['mode']='C10';IO.write_json(side,x)
  with self.assertRaises(ValueError):Runner.restore(cp)
  IO.write_bytes(side,old);self.keep('09_restart',r,cl(2),dict(checkpoint_sha=N.sha(cp),child_digest=before))
 def test10_core_priority_zero_fill_and_T1_selected_layer(self):
  r=Runner('C_BATCH20');ss=fixtures(r,1,sector='S',price=20,floor=19);close(r,0,packet(r,ss,0),{'S':obs(r,'S',0)})
  r.event(op(1),is_open=True,capacities={ss[0]:0});a=r.account;o=a.buys[ss[0]];self.assertEqual(a.supports[o.order_id]['role'],'core');self.assertFalse(a.policy.consumed)
  self.assertEqual(len(a.buys),1);self.assertFalse(a.layers)
  f=r.apply_window('buy',ss[0],win(r,ss[0],op(1)+timedelta(minutes=1),'buy',100,'core100'));z=a.layers[0];a.ack_buy_cancel(ss[0])
  rows=packet(r,ss,1,receipt=False,core=False);rows[ss[0]]['i_valid']=False;close(r,1,rows,{})
  self.assertIsNone(r.apply_window('sell',ss[0],win(r,ss[0],cl(1)+timedelta(minutes=1),capacity=100,eid='T1blocked')))
  self.assertEqual(a.quantity(ss[0]),100);self.keep('10_core_T1',r,cl(1)+timedelta(minutes=1))
 def test11_real_sale_then_settlement_then_fresh_buy(self):
  r,ss=funded('C_BATCH20');new=switch(r,ss);a=r.account;cash=a.available;first_receipts=set(r.active['receipt_bindings'])
  r.event(op(3),is_open=True,sell_windows=lambda s,t:win(r,s,t,due=op(4)))
  self.assertEqual(a.available,cash);self.assertTrue(all(not a.quantity(s) for s in new))
  self.assertGreater(a.balance(op(3),a.market.marks(op(3),a.positions))['sale_receivable'],0)
  allids=list(a.market.prices);close(r,3,packet(r,allids,3,receipt=False,core=False),{})
  self.assertEqual(r.results[-1]['state'],'WAIT_NATIVE_OLD_GOAL_RECONCILIATION')
  r.event(op(4));self.assertGreater(a.available,cash)
  rows=packet(r,allids,4,receipt=False,core=False);rows.update(packet(r,new[:1],4,core=False));close(r,4,rows,{})
  self.assertFalse(r.active['D']);r.event(op(5),is_open=True)
  self.assertGreater(a.quantity(new[0]),0);self.assertTrue(all(c not in a.policy.consumed for c in [r.results[2]['certificate']['receipt_bindings'][s]['event_id'] for s in first_receipts]))
  self.keep('11_real_sell_settle_fresh',r,op(5),dict(cash_unsettled=cash,new_bought=a.quantity(new[0])))
 def test12_recompute_new_receipt_cannot_refresh_budget(self):
  r,ss=funded('C_BATCH20');switch(r,ss);before=r.budget.dumps();new=r.budget.batch['new']
  with self.assertRaises(ValueError):r.event(cl(2),observations={},stocks={},industry_evidence=r.industry_evidence,event_id='different-same-close')
  self.assertEqual(r.budget.dumps(),before)
  result=r.plan(r.account.pending,T.admission.Clock(cl(2),op(3),cl(2).date()))
  self.assertEqual(result['state'],'WAIT_NATIVE_OLD_GOAL_RECONCILIATION');self.assertEqual(r.budget.batch['new'],new)
  self.keep('12_no_refresh',r,cl(2))
 def test13_unbought_STAR_after_native_sector_advance_S80(self):
  r=Runner('C_BATCH20');ss=fixtures(r,8,sector='S',price=160,floor=152,star=True)
  close(r,0,packet(r,ss,0),{'S':obs(r,'S',0)});r.event(op(1),is_open=True);self.assertFalse(r.account.positions)
  close(r,1,packet(r,ss,1),{'S':obs(r,'S',1,105)});r.event(op(2),is_open=True)
  b=r.account.bridge(op(2));ex=b['inventory']/b['nav'];self.assertGreater(ex,D('.795'));self.assertEqual(len(r.account.positions),8)
  self.assertFalse(r.account.policy.k);self.assertEqual(D(r.budget.batch['new']),0)
  self.keep('13_S80_unbought',r,op(2),dict(exposure=ex))
 def test14_C_industry_order_is_actual_reservation_order(self):
  r=Runner('C_BATCH20');a=fixtures(r,1,'A','LOW');z=fixtures(r,1,'Z','HIGH');ss=a+z
  close(r,0,packet(r,ss,0),{'G':obs(r,'G',0)},dict(LOW=1,HIGH=99));r.event(op(1),is_open=True,capacities={s:0 for s in ss})
  row=next(x for x in r.account.native_callbacks if x['kind']=='entire_C_batch_reserved_before_windows')
  self.assertEqual([s for s,oid in row['orders']],z+a)
  for oid,m in r.account.supports.items():self.assertIn('original_priority',m['original_intent'])
  self.assertFalse(r.account.layers);self.assertEqual(len(r.account.buys),2)
  self.keep('14_actual_C_order',r,op(1))
 def test15_future_fields_and_unknown_risk_atomic_reject(self):
  r,ss=funded('C_BATCH20');before=digest(r.observable(op(1)));rows=packet(r,ss,1);rows[ss[0]]['known_at']=cl(2)
  with self.assertRaises(ValueError):close(r,1,rows,{})
  self.assertEqual(digest(r.observable(op(1))),before)
  # UNKNOWN risk is not zero: erase one required lock snapshot only in this
  # adversarial branch and prove planning stops without touching native cash.
  rows=packet(r,ss,1,receipt=False,core=False);rows[ss[0]]['i_valid']=False;close(r,1,rows,{})
  a=r.account;lock=next(iter(a.policy.locks.values()));lock.e0=None;cash=a.available;fills=len(a.fills)
  with self.assertRaises(UnknownRisk):close(r,2,packet(r,ss,2),{})
  self.assertEqual(r.account.available,cash);self.assertEqual(len(r.account.fills),fills)
  IO.write_json(ROOT/'15_unknown_rejection.json',dict(unknown_rejected=True,cash_unchanged=cash,fill_count=fills,no_missing_stock_deleted=True))
 def test16_partial_buy_split_receipt_quantity_domain(self):
  r=Runner('C_BATCH20');ss=fixtures(r,1,star=True,price=100,floor=95);sid=ss[0];close(r,0,packet(r,ss,0),{'G':obs(r,'G',0)})
  r.event(op(1),is_open=True,capacities={sid:0});o=r.account.buys[sid];q=o.remaining_shares
  r.apply_window('buy',sid,win(r,sid,op(1)+timedelta(minutes=1),'buy',q-50,'pre-split-partial'))
  at=op(1)+timedelta(minutes=2);kw=dict(event_id='pending-buy-split2',sid=sid,ratio=D(2),at=at,new_shares_sellable_at=op(2));r.event(at,actions=[kw])
  self.assertEqual(r.account.buys[sid].remaining_shares,100);r.assert_observers()
  again=digest(r.observable(at));r.account.split(**kw);self.assertEqual(digest(r.observable(at)),again)
  f=r.apply_window('buy',sid,win(r,sid,at+timedelta(minutes=1),'buy',100,'post-split-remainder'))
  self.assertEqual(f.shares,100);r.assert_observers();self.assertEqual(r.account.quantity(sid),2*q)
  self.keep('16_partial_split',r,at+timedelta(minutes=1))

if __name__=='__main__':
 t=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromTestCase(Cases);result=unittest.TextTestRunner(verbosity=2).run(suite)
 payload=dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),seconds=time.monotonic()-t,scope='native generated-price synthetic only',historical_account_events=0,cases=list(Cases.evidence))
 IO.write_json(ROOT/'RESULTS.json',payload);print(json.dumps(payload));raise SystemExit(not result.wasSuccessful())
