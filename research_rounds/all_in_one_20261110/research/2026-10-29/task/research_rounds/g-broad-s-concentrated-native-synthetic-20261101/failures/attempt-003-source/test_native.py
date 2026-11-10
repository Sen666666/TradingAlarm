"""Generated-price synthetic cases only; no historical account runner invoked."""
import unittest,json,sys,subprocess,pickle,copy,traceback
from pathlib import Path
from datetime import datetime,timedelta
from dataclasses import replace,asdict
from decimal import Decimal as D
import native_capital as N
from native_capital import SyntheticRunner,CapitalAccount,encode,digest
from policy import Policy,UnknownRisk
from imports_native import T,F1,IO,O,RULES,quantity,fees,sha,COMPOSITE

DATES=[datetime.fromisoformat(s) for s in RULES['calendars']['A'] if '2025-07-01'<=s<'2025-09-01']
def op(n):return DATES[n]
def cl(n):return op(n).replace(hour=15,minute=10)
def clock(n):return T.admission.Clock(cl(n),op(n+1),cl(n).date())
SOURCE=F1.Source('synthetic-fixed-domain','synthetic-causal-prices','synthetic-breadth','V2')
def seed(r,scope):r.f1[scope]=F1.State(scope,source=SOURCE,previous_close=100,prior_closes=(100,)*63,prior_abs_returns=(.01,)*63)
def observation(scope,at,close,breadth=.8):return F1.Observation(at.isoformat(),SOURCE,close,breadth)
def proof(r,scope,n,price=101,breadth=.8):
 if scope not in r.f1:seed(r,scope)
 return r.planning(cl(n),{scope:observation(scope,cl(n),price,breadth)})
def fixtures(a,n=9,sector=lambda i:'S'+str(i//2),price=100,floor=95,at=None,prefix='A'):
 at=at or cl(0);sids=[]
 for i in range(n):
  s=prefix+str(i);a.mark(s,price,at,sector(i),True,floor);sids.append(s)
 return sids
def intents(a,sids,n=0,receipt='cp',core=True):
 return [a.intent(s,clock(n),receipt=receipt+'|'+s+'|'+str(n),core=core,cp_floor=a.facts.floors[s],priority=(i,)) for i,s in enumerate(sids)]
def allow(p,scope,n=1,mature=False,permit=True):
 p.evidence(scope,'synthetic-direct-interface',['break_started'],permit,True,n,1)
 if mature:p.evidence(scope,'synthetic-direct-interface',['price_advance'],permit,True,n+1,2)
def activate(a,sids):
 w=[dict(sid=s,sector=a.market.sectors[s],priority=(i,)) for i,s in enumerate(sids)]
 def minimum_ok(w,quota):
  s=w['sid'];p=a.market.prices[s]*(1+N.LR.SLIP);q=quantity(cl(0),True).buy_minimum
  return D(q)*p<=min(quota,a.policy.nd*D('.1')) and D(q)*max(D(0),p-a.facts.floors[s]/a.market.factors[s])<=a.policy.nd*D('.05')
 a.policy.choose_k({},[],w,minimum_ok)
def win(a,sid,at,capacity=10**8,eid='sell',side='sell',due=None,price=None):
 p=a.market.prices[sid];return T.window(sid,price or p*(1-N.LR.SLIP if side=='sell' else 1+N.LR.SLIP),at,capacity,fees=fees(at,a.market.stars[sid]),rule=quantity(at,a.market.stars[sid]),eid=eid,raw_open=p,sellable_at=at+timedelta(days=1),cash_due_at=due or at)

class Cases(unittest.TestCase):
 evidence={};root=None
 def keep(self,key,value):
  self.evidence[key]=value
  IO.write_json(self.root/(key+'.json'),value,encoder=encode)
 def test_01_G_real_near90_and_common_prefix_false_start(self):
  r=SyntheticRunner();a=r.account;sids=fixtures(a);proof(r,'G',0)
  requests=intents(a,sids);plans=r.opening(requests,op(1));b=a.bridge(op(1));exposure=b['inventory']/b['nav']
  self.assertTrue(all(x['q'] for x in plans));self.assertGreater(exposure,D('.895'));self.assertLess(exposure,D('.901'))
  self.assertEqual(len({a.market.sectors[s] for s in sids}),5);self.assertTrue(all(z['kind']=='add' for z in a.layers))
  prefix=digest(a.exported(op(1)));winner=pickle.loads(pickle.dumps(r));loser=pickle.loads(pickle.dumps(r))
  self.assertEqual(digest(winner.account.exported(op(1))),prefix);self.assertEqual(digest(loser.account.exported(op(1))),prefix)
  wa=winner.account;la=loser.account
  for s in sids:wa.mark(s,115,cl(1),wa.market.sectors[s],True);la.mark(s,94,cl(1),la.market.sectors[s],True)
  # F1 price failure uses real frozen kernel, no future label at initial order.
  proof(loser,'G',1,90,.2)
  for z in la.layers:la.trim(z['id'],z['qty'],clock(1),'G_price_failure')
  pre=la.available;lock_before=la.totals()['risk'];self.assertGreater(lock_before,0)
  for s in sids:la.fill_exit(s,win(la,s,op(2),eid='false-start|'+s,due=op(3)))
  self.assertEqual(la.available,pre);self.assertGreater(la.balance(op(2),{})['sale_receivable'],0)
  la.settle_due(op(3));self.assertEqual(la.quantity(sids[0]),0);self.assertGreater(sum(la.policy.losses.values()),D(50000))
  self.keep('01_G90_common_prefix',dict(initial=a.exported(op(1)),initial_exposure=exposure,prefix=prefix,common_prefix_equal=True,winning_nav=wa.nav(cl(1)),false_start=la.exported(op(3)),actual_false_start_loss=D(1000000)-la.nav(op(3)),lock_before_sell=lock_before))
 def test_02_S80_unbought_high_price_and_real_reallocation(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,8,lambda i:'B',160,152,prefix='B');proof(r,'B',0)
  refused=r.opening(intents(a,ss),op(1));self.assertTrue(all(not x['q'] for x in refused));self.assertFalse(a.policy.consumed)
  proof(r,'B',1,105);activate(a,ss);plans=r.opening(intents(a,ss,1),op(2));b=a.bridge(op(2))
  self.assertTrue(all(x['q'] for x in plans));self.assertGreater(b['inventory']/b['nav'],D('.795'))
  # A separate actual native old-G account: cash is occupied, no virtual release.
  old=SyntheticRunner();o=old.account;asids=fixtures(o,8,lambda i:'A'+str(i//2));proof(old,'G',0);old.opening(intents(o,asids),op(1));o.settle_due(op(1));o.snapshot(cl(1))
  bsids=fixtures(o,8,lambda i:'B',160,152,cl(1),'B');allow(o.policy,'B',10,True);activate(o,bsids)
  need=intents(o,bsids,1);available_before=o.available
  # Defer new receipt to a new legitimate day after old sells actually settle.
  for z in o.layers[:7]:o.trim(z['id'],z['qty'],clock(1),'valid_G_allocation_trim')
  can_before=sum(o.route(i,op(2))['q'] for i in need)
  for s in asids[:7]:o.fill_exit(s,win(o,s,op(2),eid='allocation|'+s,due=op(3)))
  self.assertEqual(o.available,available_before);can_unsettled=sum(o.route(i,op(2))['q'] for i in need);self.assertEqual(can_before,can_unsettled)
  frozen_next_nav=o.nav(cl(2));o.settle_due(op(3));after_settle=o.available
  for s in bsids:o.market.known[s]=cl(2)
  o.policy.nd=frozen_next_nav;o.current_nav=o.policy.nd
  # Fresh CP1, not an extended old receipt.
  plans2=old.opening(intents(o,bsids,2,receipt='post-settlement'),op(3));b2=o.bridge(op(3));bcap=sum(z['qty']*o.market.prices[z['sid']] for z in o.layers if z['qty'] and o.market.sectors[z['sid']]=='B')
  self.assertGreater(bcap/b2['nav'],D('.79'));self.assertGreater(after_settle,available_before)
  # Double cost: realized loss on new B + opportunity cost of sold valid A.
  o.snapshot(cl(3));sold_qty=sum(f.shares for f in o.fills if f.side=='sell')
  for s in asids:o.mark(s,130,cl(3),o.market.sectors[s])
  for s in bsids:o.mark(s,151,cl(3),'B')
  for z in list(o.layers):
   if z['qty'] and z['sid'] in bsids:o.trim(z['id'],z['qty'],clock(3),'new_theme_failed')
  before_loss=sum((z['cash'] for z in o.layers if z['sid'] in bsids),D(0))
  for s in bsids:o.fill_exit(s,win(o,s,op(4),eid='B-failure|'+s))
  o.settle_due(op(4));realB=sum((z['cash'] for z in o.layers if z['sid'] in bsids),D(0));self.assertLess(realB,0)
  self.keep('02_S80_reallocation',dict(first_trial_refused=refused,first_funded_after_native_advance=a.exported(op(2)),S_exposure=b['inventory']/b['nav'],cash_before_sell=available_before,cash_before_settlement=available_before,cash_after_settlement=after_settle,local_preview_only_before=can_before,local_preview_only_unsettled=can_unsettled,post_settle_B_capital=bcap,post_settle_NAV=b2['nav'],actual_new_B_closed_net=realB,sold_valid_A_quantity=sold_qty,foregone_A_price_gain_only=D(sold_qty)*30,foregone_is_not_trade_loss=True,terminal=o.exported(op(4))))
 def test_03_K_nine_min10_and_holder_without_fresh(self):
  r=SyntheticRunner();a=r.account;sids=fixtures(a,9,lambda i:'S'+str(i),499,474)
  # At actual 5bps known-open price, exactly 200 shares is below stock10.
  for s in sids:allow(a.policy,a.market.sectors[s],1,True)
  w=[dict(sid=s,sector=a.market.sectors[s],priority=(i,)) for i,s in enumerate(sids)]
  # The contract's exact 10% minimum example is a target-structure pure policy case.
  a.policy.choose_k({},[],w,lambda x,t:t>=D(100000));self.assertEqual(list(a.policy.k),['S'+str(i) for i in range(8)])
  actual=r.opening(intents(a,sids),op(1));self.assertEqual(sum(bool(x['q']) for x in actual),8);self.assertEqual(actual[-1]['q'],0)
  self.assertEqual(len(a.positions),8)
  # No fresh witness: actual holdings can support K; no new order/credit created.
  for s in sids[:8]:a.policy.scopes[a.market.sectors[s]].permit=False
  a.policy.choose_k({a.market.sectors[s]:s for s in sids[:8]},[],[],lambda x,t:False)
  self.assertEqual(len(a.policy.k),8);self.assertFalse(a.route(a.intent(sids[0],clock(1),core=False),op(2))['q'])
  self.keep('03_K_minimum_and_holder',dict(plans=actual,state=a.exported(op(1)),K_holding_without_fresh=list(a.policy.k),exact_10percent_example='target-structure policy subcase; real native orders use 499 and 5bps and fees'))
 def test_04_partial_STAR_fees_cancel_pending_receipt_deadline(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,1,lambda i:'S',100,95);proof(r,'G',0);i=intents(a,ss)[0]
  # Limit original 250 shares for a genuine partial remainder 50.
  x=a.submit(i,op(1));o=a.buys[ss[0]];o.remaining_shares=250;o.target_shares=250;o.remaining_budget_cny=D(250)*x['p'];o.budget_cny=o.remaining_budget_cny
  # Refund only the principal removed by this explicit pre-fill native amendment.
  original_gross=D(x['q'])*x['p'];a.available+=original_gross-o.remaining_budget_cny
  f1=a.fill_buy(ss[0],win(a,ss[0],op(1),200,'partial-200','buy'));self.assertEqual(f1.shares,200)
  f2=a.fill_buy(ss[0],win(a,ss[0],op(1)+timedelta(minutes=1),50,'partial-50','buy'));self.assertEqual(f2.shares,50)
  self.assertEqual(a.quantity(ss[0]),250);self.assertEqual(len(a.policy.consumed),1)
  totalfee=f1.fees_cny+f2.fees_cny;expected=N.LR.fees(250,x['p'],fees(op(1),True),'buy');self.assertEqual(totalfee,expected)
  # New STAR order remains min200 despite existing stock; not step1-minimum.
  j=a.intent(ss[0],clock(1),receipt='fresh-second',core=False,cp_floor=D(95));a.policy.nd=D(1000000)
  z=a._preview(j,'G','mobile',op(2),cap=50);self.assertEqual(z['q'],0)
  # A separate open original order, request != ack.
  bs=fixtures(a,1,lambda i:'T',50,48,cl(1),'P');j=a.intent(bs[0],clock(1),receipt='pending',core=False,cp_floor=D(48));x2=a.submit(j,op(2));pre=a.available;reserve=a.balance(op(2),a.market.marks(op(2),a.positions))['order_reserved']
  a.request_buy_cancel(bs[0]);self.assertEqual(a.available,pre);self.assertEqual(a.balance(op(2),a.market.marks(op(2),a.positions))['order_reserved'],reserve)
  a.ack_buy_cancel(bs[0]);self.assertGreater(a.available,pre)
  reused=dict(j,clock=clock(2),deadline=op(3).replace(hour=15,minute=10));self.assertFalse(a.submit(reused,op(3))['q'])
  # A new receipt cannot extend the old order's saved deadline.
  late=dict(j,receipt='new-signal',clock=clock(1));self.assertEqual(a.submit(late,op(3))['why'],['original_deadline'])
  self.keep('04_STAR_partial_and_cancel',dict(first=asdict(f1),second=asdict(f2),total_fee=totalfee,original_order_fee_once=expected,cancel_before_cash=pre,cancel_pending_cash=pre,cancel_after_ack=a.available,state=a.exported(op(3))))
 def test_05_overlap_original_G_cap_not_OR(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,1);proof(r,'G',0);allow(a.policy,'S0',10,True);a.market.sectors[ss[0]]='S0';activate(a,ss)
  i=intents(a,ss)[0];x=a.submit(i,op(1));o=a.buys[ss[0]];m=a.supports[o.order_id];self.assertEqual(x['use'],'S')
  # Freeze a constructible stricter original G cap (100 of 999), then current
  # G can fit more. This unit isolates original-support cap from live allowance.
  m['g_backup']=100;m['g_original_gross']=D(100)*m['limit'];a.policy.scopes['S0'].permit=False
  before=a.available;result=a.revalidate(ss[0],op(1)+timedelta(minutes=1));self.assertEqual(result['status'],'cancel_requested')
  # 100 is not a legal new STAR order. No relabel-as-G 999 and no cash release.
  self.assertEqual(a.buys[ss[0]].remaining_shares,x['q']);self.assertEqual(a.available,before)
  a.ack_buy_cancel(ss[0]);self.assertNotIn(ss[0],a.buys)
  # Separate genuine partial: original G total500, alreadyfilled300 =>200.
  b=SyntheticRunner();c=b.account;ts=fixtures(c,1);proof(b,'G',0);allow(c.policy,'S0',10,True);activate(c,ts);j=intents(c,ts)[0];xx=c.submit(j,op(1));oo=c.buys[ts[0]];mm=c.supports[oo.order_id]
  mm['g_backup']=500;mm['g_original_gross']=D(500)*mm['limit'];c.fill_buy(ts[0],win(c,ts[0],op(1),300,'first300','buy'));c.policy.scopes['S0'].permit=False
  amended=c.revalidate(ts[0],op(1)+timedelta(minutes=1));self.assertEqual(amended['q'],200);self.assertEqual(amended['use'],'G')
  ff=c.fill_buy(ts[0],win(c,ts[0],op(1)+timedelta(minutes=2),200,'next200','buy'));self.assertEqual(ff.shares,200);self.assertEqual(len(c.policy.consumed),1)
  self.keep('05_original_backup_cap',dict(no_legal_100=result,original_order=x['q'],partial300_then200=amended,state=c.exported(op(1)+timedelta(minutes=2)),coverage='originalG cap overwrite is an explicit contract boundary fixture, not a claimed naturally generated market case'))
 def test_06_ACT_strict_clock_once_phase_real_exit_obligations(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,8);proof(r,'G',0);r.opening(intents(a,ss),op(1));a.snapshot(cl(1))
  for s in ss:a.mark(s,70,cl(1),a.market.sectors[s])
  # Same-close price advance cannot restore incident it just triggered.
  proof(r,'G',1,105,.8);inc=a.policy.incident;self.assertFalse(a.policy.act['on']);self.assertEqual(len(a.exits),8);self.assertFalse(inc['phase_started_once'])
  self.assertFalse(a.policy.allowed('G','G'))
  # Interface proof after cutoff but delayed old original cursor must reject.
  a.policy.evidence('L','synthetic-delayed',['break_started'],True,True,3,1,confirmed_cursor=inc['cutoff']);a.policy.unlock(3,a.nav(cl(1)));self.assertFalse(a.policy.allowed('L','T'))
  a.policy.evidence('L','synthetic-delayed',['repair_restored'],True,True,4,2);a.policy.unlock(4,D(900000));self.assertTrue(a.policy.allowed('L','T'));phase=a.policy.act['episode'];self.assertEqual(a.policy.act['peak'],D(900000))
  a.policy.evidence('G',a.policy.scopes['G'].source,['price_advance'],True,True,5,3);a.policy.unlock(5,D(850000));self.assertEqual(a.policy.act['episode'],phase);self.assertEqual(a.policy.act['peak'],D(900000));self.assertEqual(len(a.exits),8)
  # An advance while P=false is pending, then unlocks without a new advance.
  a.policy.evidence('M','other',['break_started'],False,True,5,1);a.policy.evidence('M','other',['price_advance'],False,True,6,2);a.policy.unlock(6,D(850000));self.assertFalse(a.policy.allowed('M','S'))
  a.policy.evidence('M','other',[],True,True,7,3);a.policy.unlock(7,D(850000));self.assertTrue(a.policy.allowed('M','S'));self.assertEqual(a.policy.act['peak'],D(900000))
  self.keep('06_ACT_once',dict(state=a.exported(cl(1)),later_unlock_phase_peak=a.policy.act['peak'],later_NAV=D(850000),later_phase_DD=1-D(850000)/a.policy.act['peak'],native_pending_exit_count=len(a.exits),strict_same_close_rejected=True))
 def test_07_native_exit_lock_T1_partial_split_missing_and_restart(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,1,lambda i:'S',50,48);proof(r,'G',0);i=intents(a,ss)[0];x=a.submit(i,op(1))
  # Native original order may partial-fill400; cancel rest via real ack.
  a.fill_buy(ss[0],win(a,ss[0],op(1),400,'400','buy'));a.request_buy_cancel(ss[0]);a.ack_buy_cancel(ss[0]);z=a.layers[0];a.snapshot(op(1));a.trim(z['id'],400,T.admission.Clock(op(1),op(1)+timedelta(minutes=1),op(1).date()),'protective_exit')
  self.assertIsNone(a.fill_exit(ss[0],win(a,ss[0],op(1)+timedelta(minutes=1),100,'T1-block')))
  a.mark(ss[0],47,cl(1),'S');lock=next(iter(a.policy.locks.values()));self.assertEqual(lock.charge(D(47),D(48)),D(800));self.assertEqual(a.totals()['risk'],D(800))
  before=a.available;a.fill_exit(ss[0],win(a,ss[0],op(2),100,'sell100',due=op(3)));self.assertEqual(a.available,before);self.assertEqual(lock.charge(D(47),D(48)),D(600))
  a.split(event_id='split2',sid=ss[0],ratio=D(2),at=op(2)+timedelta(minutes=1),new_shares_sellable_at=op(3));self.assertEqual(lock.remaining,600);self.assertEqual(lock.charge(D('23.5'),D(24)),D(600))
  a.fill_exit(ss[0],win(a,ss[0],op(3),200,'sell200',due=op(4)));self.assertEqual(lock.remaining,400);self.assertEqual(lock.charge(D('23.5'),D(24)),D(400));self.assertEqual(a.exits[ss[0]].remaining_target,400)
  a.settle_due(op(3));b=a.bridge(op(3));cp=self.root/'checkpoints'/'lock.pkl';r.checkpoint(cp)
  out=self.root/'checkpoints'/'child.json';subprocess.run([sys.executable,'-B',str(O/'restore_check.py'),str(cp),str(out),op(3).isoformat()],check=True,capture_output=True,text=True)
  child=json.loads(out.read_text());self.assertEqual(child['digest'],digest(a.exported(op(3))))
  # Tampered contract/source binding and checkpoint bytes fail, not self-heal.
  side=cp.with_suffix('.provenance.json');saved=side.read_bytes();data=json.loads(saved);data['binding']['contract']='wrong';IO.write_json(side,data)
  with self.assertRaises(ValueError):SyntheticRunner.restore(cp)
  IO.write_bytes(side,saved)
  # UNKNOWN exit snapshot blocks new admission while old exit remains intact.
  bad=pickle.loads(pickle.dumps(r));next(iter(bad.account.policy.locks.values())).e0=None
  ts=fixtures(bad.account,1,lambda i:'T',30,29,cl(3),'U');j=bad.account.intent(ts[0],clock(3),receipt='unknown-receipt',core=False,cp_floor=D(29));blocked=bad.account.submit(j,op(4));self.assertFalse(blocked['q']);self.assertIn('UNKNOWN',str(blocked['why']))
  self.keep('07_exit_lock_split_restore',dict(state=a.exported(op(3)),cross_process_digest=child,checkpoint_sha=sha(cp),unknown_rejected=blocked,T1_actual_zero_fill=True,cash_not_released_until_settle=True))
 def test_08_partial_allocation_split_target_regression(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,1,lambda i:'S',50,48);proof(r,'G',0);a.submit(intents(a,ss)[0],op(1));a.fill_buy(ss[0],win(a,ss[0],op(1),400,'buy400','buy'));a.ack_buy_cancel(ss[0]);a.snapshot(cl(1));a.trim(a.layers[0]['id'],200,clock(1))
  a.fill_exit(ss[0],win(a,ss[0],op(2),100,'reduce100'));self.assertEqual(a.exits[ss[0]].remaining_target,100)
  a.split(event_id='partial-allocation-split',sid=ss[0],ratio=D(2),at=op(2)+timedelta(minutes=1),new_shares_sellable_at=op(3));self.assertEqual(a.quantity(ss[0]),600);self.assertEqual(a.exits[ss[0]].remaining_target,200)
  self.assertEqual(next(iter(a.policy.locks.values())).remaining,200)
  self.keep('08_partial_allocation_split',dict(native_held=600,native_pending_reduction=200,original_failure_preserved=str(O/'failures/ORIGINAL_PARTIAL_EXIT_SPLIT_REPRO.json'),state=a.exported(op(2)+timedelta(minutes=1))))
 def test_09_core_mobile_priority_actual_zero_fill_and_fallback(self):
  # G allows independent mobile; even zero fill reservation suppresses core.
  r=SyntheticRunner();a=r.account;ss=fixtures(a,1);proof(r,'G',0);i=intents(a,ss)[0];x=r.opening([i],op(1),{ss[0]:0})[0];self.assertEqual(x['role'],'mobile');self.assertEqual(len(a.buys),1);self.assertEqual(len(a.layers),0)
  self.assertEqual(a.order_meta[x['order_id']]['kind'],'add');self.assertEqual(len(a.policy.consumed),1)
  # Trial context core-first, unsuccessful core can fall back to closer mobile.
  b=SyntheticRunner();c=b.account;ts=fixtures(c,1,lambda i:'S',50,30);proof(b,'S',0);j=intents(c,ts)[0];j['cp_floor']=D('49.5');xx=c.submit(j,op(1));self.assertEqual(xx['role'],'mobile');self.assertEqual(xx['use'],'T')
  ff=c.fill_buy(ts[0],win(c,ts[0],op(1),10**8,'fallback','buy'));self.assertGreater(ff.shares,0)
  # Core is independently possible with moderate floor, and never a big G core.
  d=SyntheticRunner();e=d.account;us=fixtures(e,1,lambda i:'S',20,19);proof(d,'S',0);jj=e.intent(us[0],clock(0),receipt=None,core=True);xxx=e.submit(jj,op(1));self.assertEqual(xxx['role'],'core');self.assertEqual(xxx['use'],'T');e.fill_buy(us[0],win(e,us[0],op(1),10**8,'core','buy'))
  self.keep('09_actual_role_priority',dict(G_zero_fill=a.exported(op(1)),trial_core_failed_mobile_reserved=c.exported(op(1)),trial_core_actual=e.exported(op(1))))
 def test_10_original_budget_caps_gap_and_no_resource_laundering(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,2,lambda i:'S',100,95);proof(r,'G',0);a.submit(intents(a,ss)[0],op(1));before=a.available
  a.request_buy_cancel(ss[0]);row=a.resources()[0];self.assertEqual(row['kind'],'cancel_pending');self.assertGreater(row['capital'],0)
  # Large gap shrinks within the original selected quantity/gross and price floor.
  a.ack_buy_cancel(ss[0]);i=a.intent(ss[1],clock(1),receipt='gap',cp_floor=D(95));a.market.known[ss[1]]=cl(1);x=a.submit(i,op(2));o=a.buys[ss[1]];q0=o.remaining_shares;g0=o.remaining_budget_cny;a.mark(ss[1],110,op(2)+timedelta(minutes=1),'S')
  z=a.revalidate(ss[1],op(2)+timedelta(minutes=1));self.assertLessEqual(z.get('q',q0),q0)
  if z['status']=='amended':self.assertLessEqual(o.remaining_budget_cny,g0)
  # A gap below an actual old floor cannot become a zero-risk admission.
  a.mark(ss[1],94,op(2)+timedelta(minutes=2),'S');z2=a.revalidate(ss[1],op(2)+timedelta(minutes=2));self.assertEqual(z2['status'],'cancel_requested')
  self.keep('10_gap_and_resources',dict(gap110=z,gap94=z2,state=a.exported(op(2)+timedelta(minutes=2))))

def main():
 root=O/'runs'/sys.argv[1] if len(sys.argv)>1 else O/'runs'/'attempt-001';root.mkdir(parents=True,exist_ok=False);Cases.root=root
 IO.prepare_targets(dict(final=root/'RESULTS.json',checkpoint=root/'checkpoints'/'probe.pkl',failure=root/'failure'/'ERROR.json'))
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
 payload=dict(contract=COMPOSITE,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful(),historical_paths=0,cases=list(Cases.evidence),failure_details=[dict(test=str(t),traceback=v) for t,v in result.failures+result.errors])
 IO.write_json(root/'RESULTS.json',payload);print(json.dumps(payload,ensure_ascii=False,indent=2))
 return not result.wasSuccessful()
if __name__=='__main__':raise SystemExit(main())
