"""V3 thin adapter over the real ledger: hand-written fixtures, no history/PnL run."""
from pathlib import Path
from types import SimpleNamespace
from datetime import timedelta
from dataclasses import replace
import hashlib,json,time,unittest
import joint_v3 as J

W=J.W
T=W.load('v3_authoritative_ledger_fixtures',W.RR/'rs-h1-execution-20261025/code/test_sector_account.py')
D=W.D;BASE=T.T;ORIG=BASE-timedelta(days=1)
DETAIL=[]

def account(expand=True):
 state={'price':D(10),'factor':D(1)}
 market=SimpleNamespace(protocol={'fractional_split_policy':'floor_position_fraction_writeoff'},
  marks=lambda at,ids:{s:T.marks(at,state['price'],sid=s)[s] for s in ids})
 facts=SimpleNamespace(factor=lambda *_:state['factor'],floor=lambda *_:D('9.9'),structure_lookup={})
 a=J.Account('B' if expand else 'A',market,facts,expand,{'A':'S'});a.fixture_state=state
 start(a,'S');progress(a,'S',ORIG,'S-first')
 return a

def start(a,sector):a.budget.start(sector,'E',J.ordinal(ORIG))
def progress(a,sector,at,eid):
 d=J.ordinal(at)
 return a.budget.industry(J.V.Evidence(eid,sector,'industry_cp1','21',d-1,d,d,'E'),d)
def intent(at=BASE,rid='stock1',sid='A',floor='9.9'):
 quote=T.quote(sid=sid,price=10,fees=T.MINIMUM)
 return dict(sid=sid,clock=T.admission.Clock(at,at+timedelta(days=1),at.date()),quote=quote,
  budget=D(20000),cap=2000,weight=1.,group=0,score=90,kind='add',role='mobile',
  floor=D(floor),epoch=(0,1),reason='fresh_CP1_mobile',rank=0,CP1_id=rid,
  CP1_trace=dict(receipt_id=rid,formation_start_exclusive=str((at-timedelta(days=1)).date())))
def routed(a,i,sector='S',raw=10):
 x,why=J.LR.preview(i,D(raw),a.fixture_state['factor'],T.RULE,T.MINIMUM)
 assert not why
 at=i['clock'].earliest_execution_at;a.sync(at)
 a.current_nav=a.balance(at,a.market.marks(at,a.positions))['nav']
 r,why=J.Runner.route(SimpleNamespace(sector_by_sid={i['sid']:sector}),a,i,x,at)
 return x,r,why
def reserve(a,i,x,r):
 q,pool=r;a.reserve_quantity(i,q,x['price'],x['schedule'],i['clock'].earliest_execution_at)
 a.sync(i['clock'].earliest_execution_at);return q
def win(i,x,capacity=10**8,at=None,price=None,raw=None,eid=None,cash_due=None):
 at=at or i['clock'].earliest_execution_at
 return T.window(sid=i['sid'],price=price or x['price'],raw_open=D(raw or 10),at=at,
  capacity=capacity,fees=T.MINIMUM,eid=eid or i['CP1_id'],cash_due_at=cash_due or at)
def buy(a,i,sector='S'):
 x,r,why=routed(a,i,sector);assert not why,(i,why)
 q=reserve(a,i,x,r);f=a.fill_buy(i['sid'],win(i,x));assert f and f.shares==q
 return x,r,f
def legacy(a,sid,sector,qty,pool='probe',floor='9.999'):
 """Explicit preexisting fixture position; not claimed as a new v3 admission."""
 if sector not in a.budget.sectors:start(a,sector)
 i=intent(at=BASE,rid='legacy-'+sid,sid=sid,floor=floor)
 i.update(kind='core',role='core',budget=D(qty)*10,cap=qty,budget_order='legacy-'+sid,pool=pool)
 s=a.budget.sectors[sector]
 a.budget.orders[i['budget_order']]=J.V.Order(i['budget_order'],sid,sector,'E',pool,qty,10,float(floor),
  float(J.LR.fees(qty,D(10),T.MINIMUM,'buy')/D(qty)),role='core',attempt=s.attempt)
 at=i['clock'].earliest_execution_at
 a.reserve_quantity(i,qty,D(10),T.MINIMUM,at)
 x={'price':D(10)};f=a.fill_buy(sid,win(i,x));assert f and f.shares==qty
 return f
def sell(a,sid,decision_at,*,cash_due=None):
 clock=T.admission.Clock(decision_at,decision_at+timedelta(days=1),decision_at.date())
 a.sell(sid,clock,T.quote(sid=sid,price=10,fees=T.MINIMUM),[x['id'] for x in a.live(sid)],'fixture_native_exit')
 at=clock.earliest_execution_at
 f=a.fill_exit(sid,T.window(sid=sid,price=10,at=at,fees=T.MINIMUM,eid='sell-'+sid+'-'+str(at),cash_due_at=cash_due or at))
 assert f;a.sync(at);return f
def journal_bridge(a,at):
 bal=a.balance(at,a.market.marks(at,a.positions));r=SimpleNamespace(balance_audit=[],market=a.market)
 J.Runner.daily_bridge(r,a,at,bal);return r.balance_audit[-1]
def record(name,**kw):DETAIL.append(dict(name=name,**W.canon(kw)))

class BridgeTests(unittest.TestCase):
 def test_equal_probe_mobile_old_core_lock_no_grant_dependency(self):
  quantities=[]
  for expand in [False,True]:
   a=account(expand);a.core_epoch['A']=(0,1)
   if expand:progress(a,'S',BASE,'S-confirm')
   i=intent();x,r,why=routed(a,i);self.assertIsNone(why);self.assertEqual(r[1],'probe')
   q=reserve(a,i,x,r);a.fill_buy('A',win(i,x));quantities.append(q)
   self.assertEqual(a.jmeta[a.layers[-1]['id']]['role'],'mobile')
   self.assertFalse(hasattr(a.budget,'grants'))
  self.assertEqual(*quantities);record('equal_probe',quantities=quantities)

 def test_actual_sale_reinvestment_no_turnover_coupon_old_receipt_rejected(self):
  a=account();progress(a,'S',BASE,'S-confirm');legacy(a,'LEGACY','S',5000,pool='confirmed')
  turnover=D(0);industry_time=a.budget.sectors['S'].last_evidence_time
  for k in range(6):
   at=BASE+timedelta(days=1+4*k);i=intent(at=at,rid='fresh-'+str(k));x,r,f=buy(a,i)
   self.assertEqual(r[1],'confirmed');turnover+=f.gross_cny
   s=sell(a,'A',at+timedelta(days=2));a.settle_due(s.at);a.sync(s.at)
  self.assertGreater(turnover,D(100000));self.assertEqual(a.budget.sectors['S'].last_evidence_time,industry_time)
  duplicate=intent(at=BASE+timedelta(days=27),rid='fresh-0')
  _,r,why=routed(a,duplicate);self.assertIsNone(r);self.assertEqual(why,'no_fresh_stock_CP1')
  bridge=journal_bridge(a,duplicate['clock'].earliest_execution_at)
  record('real_revolving_capacity',turnover=str(turnover),fees=str(a.fees_cny),industry_receipt_not_refreshed=True,journal_NAV_gap=bridge['independent_NAV_difference'])

 def test_other_industry_actual_exit_releases_confirmed_pool_without_new_industry_receipt(self):
  a=account();progress(a,'S',BASE,'S-confirm')
  legacy(a,'S-OLD','S',4000,pool='confirmed')
  legacy(a,'X-OLD','X',28000,pool='confirmed');legacy(a,'Y-OLD','Y',28000,pool='confirmed')
  i=intent(at=BASE+timedelta(days=1),rid='before-other-exit');_,r,why=routed(a,i)
  self.assertIsNone(r);self.assertEqual(a.budget.sectors['S'].status,'confirmed_unfunded')
  evidence_time=a.budget.sectors['S'].last_evidence_time
  f=sell(a,'X-OLD',BASE+timedelta(days=2));a.settle_due(f.at);a.sync(f.at)
  i=intent(at=BASE+timedelta(days=4),rid='fresh-after-other-exit');x,r,why=routed(a,i)
  self.assertIsNone(why);self.assertEqual(r[1],'confirmed');reserve(a,i,x,r)
  self.assertEqual(a.budget.sectors['S'].last_evidence_time,evidence_time)
  record('other_sector_capacity_released',actual_sold=f.shares,new_quantity=r[0],same_industry_receipt=True)

 def test_sell_intent_unsettled_receivable_cannot_fund_only_real_settlement(self):
  a=account();progress(a,'S',BASE,'S-confirm');legacy(a,'OLD','LEGACY',90000)
  i=intent(at=BASE,rid='before-sale');_,r,why=routed(a,i);self.assertIsNone(r);self.assertIn('cash',why)
  clock=T.admission.Clock(BASE+timedelta(days=1),BASE+timedelta(days=2),(BASE+timedelta(days=1)).date())
  a.sell('OLD',clock,T.quote(sid='OLD',price=10,fees=T.MINIMUM),[x['id'] for x in a.live('OLD')],'fixture_exit')
  before=a.available;late=BASE+timedelta(days=5)
  i=intent(at=BASE+timedelta(days=1),rid='sell-not-filled');_,r,_=routed(a,i);self.assertIsNone(r);self.assertEqual(a.available,before)
  f=a.fill_exit('OLD',T.window(sid='OLD',at=clock.earliest_execution_at,price=10,fees=T.MINIMUM,eid='actual-sale',cash_due_at=late));self.assertIsNotNone(f)
  a.sync(f.at);self.assertEqual(a.available,before);self.assertGreater(a.budget.receivable_equity,0)
  i=intent(at=BASE+timedelta(days=3),rid='unsettled');_,r,why=routed(a,i);self.assertIsNone(r);self.assertIn('cash',why)
  a.settle_due(late);a.sync(late)
  i=intent(at=late,rid='after-settlement');x,r,why=routed(a,i);self.assertIsNone(why);reserve(a,i,x,r)
  record('actual_sale_settlement',before_cash=str(before),after_cash=str(a.available),new_quantity=r[0],noncash_receivable_not_spendable=True)

 def test_multisector_h1_order_serial_reserve_does_not_double_spend(self):
  a=account();legacy(a,'OLD','LEGACY',87000);accepted=[];rejected=[]
  for k in range(6):
   sector='T'+str(k);start(a,sector);progress(a,sector,ORIG,sector+'-first');progress(a,sector,BASE,sector+'-confirm')
  for k in range(6):
   i=intent(rid='fresh-sector-'+str(k),sid='STOCK'+str(k));x,r,why=routed(a,i,'T'+str(k))
   if r:reserve(a,i,x,r);accepted.append((k,r[0]))
   else:rejected.append(why)
  reserved=a.budget.resources()[2];self.assertLessEqual(reserved,float(a.budget.cash));self.assertEqual(len(accepted),2)
  self.assertTrue(all('cash' in x for x in rejected));record('serial_cash',accepted=accepted,rejected=rejected,reserved=reserved,remaining_available=str(a.available))

 def test_partial_fill_failure_cancel_and_same_observation_no_restart(self):
  a=account();progress(a,'S',BASE,'S-confirm');i=intent();x,r,_=routed(a,i);q=reserve(a,i,x,r)
  a.fill_buy('A',win(i,x,capacity=100));at=i['clock'].earliest_execution_at+timedelta(hours=1)
  a.budget.observe('S',J.ordinal(at),failure=True);reserve_before=a.budget.resources()[2]
  self.assertGreater(reserve_before,0);a.cancel_buy('A');a.sync(at)
  self.assertEqual(a.quantity('A'),100);self.assertEqual(a.budget.resources()[2],0)
  self.assertEqual(progress(a,'S',at,'same-day'),'not_new_progress');self.assertFalse(a.budget.sectors['S'].active)
  record('partial_cancel',ordered=q,actual=100,reserve_before=reserve_before,fees=str(a.fees_cny))

 def test_full_fill_wins_pending_cancel_preserves_lot_and_pool(self):
  a=account();i=intent();x,r,_=routed(a,i);q=reserve(a,i,x,r)
  progress(a,'S',i['clock'].earliest_execution_at,'S-confirm');self.assertEqual(a.budget.orders[i['budget_order']].status,'cancel_pending')
  a.fill_buy('A',win(i,x));a.sync(i['clock'].earliest_execution_at)
  self.assertEqual(a.quantity('A'),q);self.assertEqual(a.budget.resources()[2],0)
  self.assertTrue(all(z.pool=='confirmed' for z in a.budget.lots));record('cancel_race',shares=q,pool='confirmed')

 def test_known_core_line_does_not_read_current_close_at_open(self):
  a=account();i=intent();i.update(kind='core',role='core',CP1_id=None,CP1_trace=None,risk_budget=D(2500))
  x,r,why=routed(a,i);self.assertIsNone(why);reserve(a,i,x,r);a.fill_buy('A',win(dict(i,CP1_id='core-window'),x))
  known=a.budget.resources()[1];a.facts=SimpleNamespace(factor=lambda *_:D(1),floor=lambda *_:None,structure_lookup={})
  a.sync(BASE+timedelta(days=2));self.assertEqual(a.budget.resources()[1],known)
  self.assertEqual(a.jmeta[a.layers[-1]['id']]['last_core_line'],'9.9');record('decision_known_core',risk=known)

 def test_stock_ten_percent_and_mobile_two_percent_targets(self):
  a=account();progress(a,'S',BASE,'S-confirm')
  for k in range(5):
   i=intent(BASE+timedelta(days=2*k+1),rid='grow'+str(k));x,r,f=buy(a,i)
   self.assertLessEqual(f.gross_cny,D(20000))
  i=intent(BASE+timedelta(days=12),rid='gap-stock');x,why=J.LR.preview(i,D(20),D(1),T.RULE,T.MINIMUM)
  self.assertIsNone(why);x['known_open']=D(20);a.sync(i['clock'].earliest_execution_at)
  r,why=J.Runner.route(SimpleNamespace(sector_by_sid={'A':'S'}),a,i,x,i['clock'].earliest_execution_at)
  self.assertIsNone(r);self.assertIn('stock_capital',why);self.assertNotIn(i['CP1_id'],a.budget.consumed)
  record('sizing_caps',held=a.quantity('A'),gap_open=20,rejected=why)

 def test_original_core_quarter_percent_risk_fee_and_lot_sizing(self):
  a=account();i=intent(floor='8');i.update(kind='core',role='core',CP1_id=None,CP1_trace=None,budget=D(100000),cap=10000)
  J.LR.resize_core(i,D(1000000),D(1));x,r,why=routed(a,i)
  self.assertIsNone(why);risk=J.LR.protection_risk(r[0],x['price'],x['floor'],T.MINIMUM)
  self.assertLessEqual(risk,D(2500));self.assertEqual(r[0]%100,0)
  record('original_core_risk',quantity=r[0],risk=str(risk),risk_budget='2500')

 def test_dividend_and_held_split_same_units_cash_fees_no_fabrication(self):
  a=account();progress(a,'S',BASE,'S-confirm');i=intent();x,r,f=buy(a,i);q=f.shares;at=BASE+timedelta(days=2)
  a.sync(at);nav=a.budget.nav;cash=a.available;fees=a.fees_cny
  a.accrue_dividend(event_id='dividend',sid='A',currency='CNY',net_local=D(q)*D('.1'),ex_at=at,paid_at=None,source_id='explicit-fixture',entitlement_basis='real shares')
  a.fixture_state.update(price=D('9.9'),factor=D(10)/D('9.9'));a.sync(at);risk=a.budget.resources()[1]
  self.assertAlmostEqual(a.budget.nav,nav);self.assertEqual(a.available,cash)
  a.split(event_id='held-2x',sid='A',ratio=D(2),at=at,new_shares_sellable_at=at+timedelta(days=1))
  a.fixture_state.update(price=D('4.95'),factor=a.fixture_state['factor']*2);a.sync(at)
  self.assertEqual(a.quantity('A'),2*q);self.assertAlmostEqual(a.budget.nav,nav)
  self.assertAlmostEqual(a.budget.resources()[1],risk);self.assertEqual(a.fees_cny,fees);self.assertEqual(a.available,cash)
  bridge=journal_bridge(a,at);record('held_rights_units',quantity=a.quantity('A'),cash=str(cash),receivable=a.budget.receivable_equity,journal_NAV_gap=bridge['independent_NAV_difference'])

 def pending_fixture(self):
  a=account();i=intent();i.update(budget=D(4002),cap=400)
  x,r,why=routed(a,i);self.assertIsNone(why);self.assertEqual(r[0],400);reserve(a,i,x,r);return a,i,x,r

 def test_whole_pending_split_quantity_limit_floor_and_reserved_cash(self):
  a,i,x,r=self.pending_fixture();before=a.available;reserved=a.budget.resources()[2];at=i['clock'].earliest_execution_at
  a.split(event_id='pending-2x',sid='A',ratio=D(2),at=at,new_shares_sellable_at=at+timedelta(days=1))
  a.fixture_state.update(price=D(5),factor=D(2));a.sync(at);bo=a.budget.orders[i['budget_order']]
  self.assertEqual(bo.qty,2*r[0]);self.assertEqual(a.buys['A'].remaining_shares,bo.qty)
  self.assertAlmostEqual(bo.limit,float(x['price']/2));self.assertAlmostEqual(bo.floor,4.95)
  self.assertAlmostEqual(a.budget.resources()[2],reserved);self.assertEqual(a.available,before);split_pending=bo.qty
  a.fill_buy('A',win(i,x,at=at+timedelta(days=1),price=x['price']/2,raw=5,eid='post-split'))
  a.sync(at+timedelta(days=1));self.assertEqual(a.quantity('A'),2*r[0]);self.assertEqual(a.budget.resources()[2],0)
  record('whole_pending_split',before_quantity=r[0],after_split_pending=split_pending,after_fill_remaining=bo.qty,actual_inventory=a.quantity('A'),pre_fill_reservation=reserved)

 def test_partial_fill_then_pending_split_then_partial_and_cancel(self):
  a,i,x,r=self.pending_fixture();at=i['clock'].earliest_execution_at
  a.fill_buy('A',win(i,x,capacity=100));cash=a.available;fees=a.fees_cny;a.sync(at);nav=a.budget.nav;reserved=a.budget.resources()[2]
  a.split(event_id='partial-2x',sid='A',ratio=D(2),at=at,new_shares_sellable_at=at+timedelta(days=1))
  a.fixture_state.update(price=D(5),factor=D(2));a.sync(at);bo=a.budget.orders[i['budget_order']]
  self.assertEqual(a.quantity('A'),200);self.assertEqual(bo.qty,2*(r[0]-100));self.assertEqual(a.buys['A'].remaining_shares,bo.qty)
  self.assertAlmostEqual(a.budget.resources()[2],reserved);self.assertAlmostEqual(a.budget.nav,nav);self.assertEqual(a.available,cash)
  a.fill_buy('A',win(i,x,capacity=100,at=at+timedelta(days=1),price=x['price']/2,raw=5,eid='partial-after-split'))
  self.assertEqual(a.quantity('A'),300);self.assertEqual(a.fees_cny,fees)
  a.cancel_buy('A');a.sync(at+timedelta(days=1));self.assertEqual(a.budget.resources()[2],0);self.assertEqual(a.quantity('A'),300)
  bridge=journal_bridge(a,at+timedelta(days=1));record('partial_pending_split',inventory=300,fees=str(a.fees_cny),journal_NAV_gap=bridge['independent_NAV_difference'])

 def test_corrupt_mirror_reserve_inventory_and_native_NAV_are_not_swallowed(self):
  a,i,x,r=self.pending_fixture();at=i['clock'].earliest_execution_at;bo=a.budget.orders[i['budget_order']];old=bo.limit
  bo.limit+=123/bo.qty
  with self.assertRaises(AssertionError):a.assert_budget_view(at)
  with self.assertRaises(AssertionError):a.sync(at)
  bo.limit=old;a.assert_budget_view(at)
  a.fill_buy('A',win(i,x));a.budget.lots[0].qty+=1
  with self.assertRaises(AssertionError):a.assert_budget_view(at)
  with self.assertRaises(AssertionError):a.sync(at)
  a.budget.lots[0].qty-=1;a.assert_budget_view(at)
  native=a.balance
  def corrupt(*args,**kwargs):
   bal=native(*args,**kwargs);bal['nav']+=D(123);return bal
  a.balance=corrupt
  with self.assertRaises(AssertionError):a.sync(at)
  a.balance=native;a.sync(at)
  record('negative_assertion_tests',reserve_plus_123_detected_by_direct_check_and_sync=True,inventory_plus_one_detected_by_direct_check_and_sync=True,native_NAV_plus_123_detected_by_sync=True,no_residual_auto_fill=True)

if __name__=='__main__':
 t=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromTestCase(BridgeTests)
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 output=dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),seconds=time.monotonic()-t,
  scope='hand-written fixtures calling authoritative original ledger/admission and v3 route; no historical account paths',
  tests_detail=DETAIL,historical_CASE_or_universe_paths=0,budget_synthetic_fill_sell_not_used=True,
  physical_historical_prefix='old v2 evidence retained; v3 historical regression pending review/replay authorization')
 Path(__file__).with_name('BRIDGE_GATE.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
