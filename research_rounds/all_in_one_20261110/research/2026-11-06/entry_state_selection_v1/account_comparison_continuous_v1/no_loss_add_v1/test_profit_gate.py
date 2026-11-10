from decimal import Decimal as D
from profit_gate import RemainingCostBook,judge,SOURCE,DERIVED

def row(kind,**kw):return dict(kind=kind,sid='X',**kw)
b=RemainingCostBook()
b.apply(row('real_buy_fill',shares=100,price=D(10),fees=D(5)))
b.apply(row('real_buy_fill',shares=100,price=D(20),fees=D(5)))
assert b.states['X']['cost']==D(3010)
# Selling any layer must retire stock-wide average cost, not that layer's cost.
b.apply(row('real_sell_fill',shares=100,price=D(30),fees=D(5)))
assert b.states['X']['cost']==D(1505) and b.states['X']['qty']==100
assert not judge(100,1505,14,5)['allowed'] # past realized gain cannot subsidize losing remainder
before=dict(b.states['X']);b.apply(row('industry_confirmation'));assert b.states['X']==before
b.apply(row('actual_split',ratio=D('1.5')))
assert b.states['X']['qty']==150 and b.states['X']['cost']==D(1505)
assert not judge(150,1505,D('10.04'),5)['allowed']
assert judge(150,1505,11,5)['allowed']
# Buy-positive slippage does not manufacture a profit at the gate.
assert not judge(100,D('1000'),10,0)['allowed']
b.apply(row('real_sell_fill',shares=150,price=5,fees=5));assert b.states['X']['cost']==0
assert judge(0,0,1,0)['allowed']
b.apply(row('real_buy_fill',shares=100,price=2,fees=5));assert b.states['X']['round']==2
assert b.states['X']['cost']==205
# Boundary is strict and unknown/no-positive open must never silently pass held positions.
assert not judge(100,D('994.5'),10,5)['allowed']
try:judge(100,1000,0,5)
except AssertionError:pass
else:raise AssertionError('nonpositive open accepted')
assert len(DERIVED.splitlines())==len(SOURCE.splitlines())+2
print('PASS: average cost, sale-layer independence, locked-profit exclusion, split, flat re-entry, strict boundary, invalid open, exact two-line route delta')
