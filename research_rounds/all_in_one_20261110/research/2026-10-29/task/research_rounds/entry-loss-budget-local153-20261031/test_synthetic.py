from core import *
T=S.load('lossbudget_original_ledger_fixture',S.RR/'rs-h1-execution-20261025/code/test_sector_account.py');base=T.T;R=[]
def test(name,fn):fn();R.append(dict(name=name,passed=True));print(name,'PASS',flush=True)
def btest(values,expected):
 b=Budget(D(100),D('.2'));z=[b.close(V=D(str(v)),known=True,at=str(i)) for i,v in enumerate(values)];assert z==expected

test('prior_profit_never_removes_budget',lambda:btest([120,95,79,100],[False,False,True,False]))
test('deep_profit_peak_drawdown_above_cost_budget_not_trigger',lambda:btest([300,140,100,81],[False,False,False,False]))
def actions():
 a=L.SectorAccount(initial_cash=10000);a.available=Z;a.positions['A']=L.Position('A','A','G','CNY',[L.InventoryLot(100,base)]);m=lambda price:T.marks(base,price=price)
 # Real corporate-action ledger: asset NAV is raw inventory plus accrued right, never adjusted inventory plus right.
 p=a.balance(base,m(100))['nav'];a.accrue_dividend(event_id='div',sid='A',currency='CNY',net_local=D(1000),ex_at=base,paid_at=None,source_id='declared',entitlement_basis='actual_previous_close');assert a.balance(base,m(90))['nav']==p;a.split(event_id='split',sid='A',ratio=D(2),at=base,new_shares_sellable_at=base);assert a.balance(base,m(45))['nav']==p and a.quantity('A')==200
 b=Budget(D(10000),D('.1'));assert b.close(V=p-D(10),known=True,at=str(base)) is False
 testdata=dict(before_nav=p,post_dividend_split_nav=a.balance(base,m(45))['nav'],unpaid_claim=a.balance(base,m(45))['dividend_receivable']);return testdata
def original():
 b=Budget(D(100),D('.2'));assert b.close(V=D(79),known=True,at='t',original=True) is True and b.reason=='original';assert not b.close(V=D(70),known=True,at='t',original=True)
test('earlier_original_and_same_day_conflict_one_intent',original)
def gap():
 a=L.SectorAccount(initial_cash=1000);a.available=Z;a.positions['A']=L.Position('A','A','G','CNY',[L.InventoryLot(100,base+__import__('datetime').timedelta(days=1))]);a.request_exit(T.quote(price=8),A.Clock(base,base+__import__('datetime').timedelta(days=1),base.date()));assert a.fill_exit('A',T.window(at=base,price=7,eid='before-T1')) is None;op=base+__import__('datetime').timedelta(days=1);f=a.fill_exit('A',T.window(at=op,price=7,fees=T.MINIMUM,eid='after-T1'));assert f and f.gross_cny==700 and f.gross_cny-f.fees_cny<800 and a.quantity('A')==0
 testdata=dict(actual_gross=f.gross_cny,budget_boundary=800,actual_fee=f.fees_cny);return testdata
def missing():
 b=Budget(D(100),D('.2'));assert b.close(V=None,known=False,at='unknown') is None and not b.locked;assert b.close(V=D(79),known=True,at='later') is True

test('unknown_not_false_no_trigger',missing)
# Fixture signatures are original, inspected before execution; no custom fake fill engine.
DETAILS={}
DETAILS['corporate_actions']=actions();R.append(dict(name='dividend_split_equity_continuity',passed=True))
DETAILS['gap_fill']=gap();R.append(dict(name='T1_wait_then_real_gap_fill_not_budget_price',passed=True))
save(O/'SYNTHETIC_TESTS.json',dict(passed=True,tests=R,details=DETAILS,real_original_ledger=True,history_profit_used=False));print('ALL_PASS',len(R))
