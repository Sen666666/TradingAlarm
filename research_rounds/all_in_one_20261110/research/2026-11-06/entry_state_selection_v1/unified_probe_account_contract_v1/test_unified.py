from decimal import Decimal as D
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace as NS
import copy,json,inspect,hashlib
from pathlib import Path
import unified_probe as U
J,LR=U.J,U.LR
AT=datetime(2022,1,6,9,30,tzinfo=timezone(timedelta(hours=8)));DEC=AT.replace(day=5,hour=15,minute=10);BAR=J.ordinal(DEC.date())
FEES=LR.L.FeeSchedule('test',(LR.L.FeeComponent('commission',D('.0003'),D(5)),LR.L.FeeComponent('tax',D('.001'),side='sell')))
RULE=LR.L.QuantityRule('100',100,100,100,True,100)
passed=[]
def check(name,test):
 test();passed.append(name)
def budget():
 b=U.UnifiedBudget(True);b.cash=1200000.;b.promotion_seen=set();b._admission=None
 b.start('S','e',BAR-20);s=b.sectors['S'];s.active=True;s.level=2;s.attempt='a';s.started=BAR-10
 return b
def token(sid='X',rid='CPX',bar=BAR,attempt='a'):
 return J.V.Evidence(rid,'S','stock_cp1','21',bar-5,bar,bar,'e',sid,attempt)
def lot(b,sid='X',q=100,cost=10,floor=9,pool='probe',attempt='a',batch=None):
 batch=batch or str(len(b.lots)+1);b.lots.append(J.V.Lot(batch,sid,'S','e',pool,q,cost,floor,'mobile',attempt));b.prices[sid]=11.;return b.lots[-1]
class FakeAccount:
 def __init__(self,b):
  self.budget=b;self.label='PVR';self.current_nav=D('1200000');self.available=D(str(b.cash));self.core_epoch={};self.journal=[];self.positions={x.stock:object() for x in b.lots};self.buys={};self.exits={};self.jmeta={int(x.batch):dict(pool=x.pool,attempt=x.attempt,episode=x.episode) for x in b.lots};self.layers=[dict(id=int(x.batch),sid=x.stock,qty=x.qty,opened=DEC-timedelta(days=2)) for x in b.lots]
 def quantity(self,sid):return sum(x.qty for x in self.budget.lots if x.stock==sid)
 def live(self,sid):return [x for x in self.layers if x['sid']==sid and x['qty']]
 def pools_from_model(self):
  for x in self.budget.lots:self.jmeta[int(x.batch)]['pool']=x.pool
 def assert_budget_view(self,at):return None

def intent(sid='X',role='mobile',rid=None):
 rid=rid or 'CP'+sid
 return dict(sid=sid,role=role,epoch='epoch',floor=D(9),clock=NS(decision_at=DEC,earliest_execution_at=AT),quote=NS(par_value=None),CP1_id=rid if role=='mobile' else None,CP1_trace=dict(receipt_id=rid,confirmed_day=str(DEC.date()),formation_start_exclusive=str((DEC-timedelta(days=5)).date())) if role=='mobile' else None,_decision_nav=D('1200000'),_sector='S')
def preview(floor='9',price='10.005',rule=RULE):
 return dict(price=D(price),known_open=D(price)/D('1.0005'),floor=D(floor),schedule=FEES,rule=rule,maxq=100000)
def runner(b,a):
 r=object.__new__(U.UnifiedRunner);r.sector_by_sid={x:'S' for x in ['X','A','B','Y','Z']};r.profit_gate_events=[];r.admission_events=[];r.promotion_events=[];r.cost_books={'PVR':U.P.RemainingCostBook()}
 for x in b.lots:r.cost_books['PVR'].apply(dict(kind='real_buy_fill',sid=x.stock,shares=x.qty,price=D(str(x.cost)),fees=D(5)))
 r.cost_books['PVR'].journal_cursor=0
 r.market=NS(phase='OPEN',phase_at=AT,fees=lambda sid,at:FEES)
 r.facts=NS(factor=lambda sid,at:D(1))
 return r

def test_flat():
 for role in ('core','mobile'):
  b=budget();a=FakeAccount(b);r=runner(b,a);i=intent(role=role);out,why=r.route(a,i,preview(),AT);assert out and why is None
  q,pool=out;assert pool=='probe';assert D(q)*D('10.005')<=D(24000);assert r.admission_events[-1]['fee_inclusive_risk']<=D(3000)
  assert b.orders[i['budget_order']].role==role
  if role=='mobile':assert i['CP1_id'] in b.consumed
  else:assert i['CP1_id'] not in b.consumed
check('flat_CORE_and_MOBILE_probe_2pct_fee_risk_identity',test_flat)
def test_deep_risk():
 b=budget();a=FakeAccount(b);r=runner(b,a);out,_=r.route(a,intent(),preview(floor='1'),AT);assert out and out[0]<=300;assert r.admission_events[-1]['fee_inclusive_risk']<=D(3000)
check('flat_deep_floor_fee_inclusive_risk_reduces_qty',test_deep_risk)
def test_units():
 b=budget();a=FakeAccount(b);r=runner(b,a);rule=LR.L.QuantityRule('star',200,1,1,True,1);out,_=r.route(a,intent(),preview(rule=rule),AT);assert out and out[0]>=200 and out[0]%100!=0
check('native_dated_rule_not_hardcoded_100',test_units)
def test_shared():
 b=budget();a=FakeAccount(b);r=runner(b,a)
 for n in range(20):
  sid='S'+str(n);sec='I'+str(n);r.sector_by_sid[sid]=sec;b.sectors[sec]=copy.deepcopy(b.sectors['S']);i=intent(sid);i['_sector']=sec
  out,why=r.route(a,i,preview(floor='9.9'),AT)
  if out:a.available-=D(out[0])*D('10.005')+LR.fees(out[0],D('10.005'),FEES,'buy')
 assert b.resources('probe')[0]<=.1*(b.nav-sum(o.qty*o.fee_per_share for o in b.orders.values()))+1e-6
 assert len(b.orders)<20 and len(b.orders)>1
check('global_probe_pool_shared_no_stock_count_cap',test_shared)
def test_promote_isolated():
 b=budget();lot(b,'A',cost=8);lot(b,'B',cost=12);a=FakeAccount(b);r=runner(b,a)
 r.promote_candidate(a,intent('A'),D(11),AT);r.promote_candidate(a,intent('B'),D(11),AT)
 assert [x.pool for x in b.lots]==['confirmed','probe'];assert a.jmeta[1]['pool']=='confirmed' and a.jmeta[2]['pool']=='probe';assert not b.consumed
 b.migrate('S');assert b.lots[1].pool=='probe'
check('profitable_A_cannot_carry_losing_B_jmeta_bridge',test_promote_isolated)
def test_industry_cancel():
 b=budget();lot(b,'A');lot(b,'B');b.sectors['S'].level=0
 out=b.request('o','X','S',100,10.,9.,token(),BAR,.05,probe_request=True,role='mobile');assert out=='reserved'
 it=J.V.Evidence('industry','S','industry_cp1','21',BAR-3,BAR,BAR,'e');b.industry(it,BAR)
 assert b.orders['o'].status=='cancel_pending';assert all(x.pool=='probe' for x in b.lots);assert b.resources()[2]>0
 b.cancel_ack('o');assert b.resources()[2]==0 and all(x.pool=='probe' for x in b.lots)
check('industry_and_cancel_ACK_never_promote_release_only_ack',test_industry_cancel)
def test_commute():
 outputs=[]
 for order in [('A','B'),('B','A')]:
  b=budget();lot(b,'A',cost=8);lot(b,'B',cost=8);a=FakeAccount(b);r=runner(b,a)
  for sid in order:r.promote_candidate(a,intent(sid),D(11),AT)
  outputs.append(([(x.stock,x.pool,x.qty,x.floor,x.role) for x in b.lots],b.cash,b.nav,b.resources(),b.resources(sector='S'),b.consumed,b.promotion_seen,a.jmeta))
 assert outputs[0]==outputs[1]
check('independent_promotion_commutes_financial_identity_state',test_commute)
def test_no_cash_promote():
 b=budget();lot(b,cost=8);b.cash=1;a=FakeAccount(b);r=runner(b,a);r.promote_candidate(a,intent(),D(11),AT);assert b.lots[0].pool=='confirmed'
 out,why=r.route(a,intent(),preview(),AT);assert not out and 'cash' in why and b.lots[0].pool=='confirmed';assert not b.consumed
check('promotion_independent_of_add_funding_failure',test_no_cash_promote)
def test_price_floor():
 b=budget();lot(b,cost=8);a=FakeAccount(b);r=runner(b,a);i=intent();i['floor']=D(11);r.promote_candidate(a,i,D(11),AT);assert b.lots[0].pool=='probe'
check('positive_profit_but_open_at_CP_line_cannot_promote',test_price_floor)
def test_identity():
 for variant in ('old_attempt','consumed','same_timestamp','pending_buy','pending_exit'):
  b=budget();lot(b,cost=8,attempt='old' if variant=='old_attempt' else 'a');a=FakeAccount(b);r=runner(b,a);i=intent()
  if variant=='consumed':b.consumed.add(i['CP1_id'])
  if variant=='same_timestamp':a.layers[0]['opened']=DEC
  if variant=='pending_buy':a.buys['X']=object()
  if variant=='pending_exit':a.exits['X']=object()
  r.promote_candidate(a,i,D(11),AT);assert b.lots[0].pool=='probe',variant
check('old_attempt_consumed_CP_fill_timing_real_pending_guards',test_identity)
def test_industry_conflict():
 b=budget();lot(b,'A',q=10000,cost=10,pool='confirmed');a=FakeAccount(b);r=runner(b,a);out,why=r.route(a,intent('X'),preview(),AT);assert out is None and 'sector_capital' in why
check('preserved_industry_ALL_2pct_blocks_new_probe',test_industry_conflict)
def test_flat_after_exit():
 b=budget();a=FakeAccount(b);r=runner(b,a);i=intent();i['was_held_at_signal']=True;out,_=r.route(a,i,preview(),AT);assert out[1]=='probe' and r.admission_events[-1]['fee_inclusive_risk']<=D(3000)
check('post_sell_real_Q_overrides_signal_held_flag',test_flat_after_exit)
def test_reentry():
 b=budget();a=FakeAccount(b);r=runner(b,a);b.consumed.add('oldCP');out,why=r.route(a,intent(rid='oldCP'),preview(),AT);assert not out
 out,why=r.route(a,intent(rid='freshCP'),preview(),AT);assert out[1]=='probe' and 'freshCP' in b.consumed
check('fresh_CP_stop_reentry_allowed_old_CP_rejected',test_reentry)
def test_avg_cost():
 book=U.P.RemainingCostBook();book.apply(dict(kind='real_buy_fill',sid='X',shares=200,price='10',fees='10'));book.apply(dict(kind='dividend',sid='X',amount=999));book.apply(dict(kind='real_sell_fill',sid='X',shares=100,price=20,fees=5));assert book.states['X']['cost']==D(1005)
 book.apply(dict(kind='actual_split',sid='X',ratio='2'));assert book.states['X']['qty']==200 and book.states['X']['cost']==D(1005)
 assert not U.P.judge(200,D('1999'),D(10),D(0))['allowed']
check('remaining_average_cost_dividend_partial_split_strict_net',test_avg_cost)
def test_source():
 native=inspect.getsource(J.Runner.opening);import textwrap
 assert U.OPEN_SOURCE.replace('a.sync(at);self.promote_open_candidates(a,at);funded=[]','a.sync(at);funded=[]')==textwrap.dedent(native)
 assert 'self.migrate(sector)' not in U.REQUEST_SOURCE
check('opening_exact_one_phase_diff_and_no_request_migration',test_source)
result=dict(passed=True,count=len(passed),tests=passed,implementation_sha256=hashlib.sha256(Path(U.__file__).read_bytes()).hexdigest(),scope='synthetic only, no native account economic history')
Path(__file__).with_name('SYNTHETIC_RESULTS.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
