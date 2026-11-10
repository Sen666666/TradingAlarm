from decimal import Decimal as D
import hashlib,json
from pathlib import Path

O=Path(__file__).resolve().parent
def eq(a,b):
    assert a==b,(a,b)

# Native protocol-style raw/exec distinction; deliberately exact numbers.
N=D('100000');alpha=D('.10');raw=D('10');p=D('10.005')
q=D('1000');fee=D('5');gross=q*p;cost=gross+fee
drag=fee+q*(p-raw)
eq(cost,D('10010'));eq(drag,D('10'))

# Actual pending-to-filled cost conservation; minimum fee entirely on first part.
q1=D('400');g1=q1*p;f1=D('5');B1=g1+f1
remaining_gross=gross-g1;remaining_fee=fee-f1
eq(B1+remaining_gross+remaining_fee,cost)
s=D('.0005');full_pending_drag=fee+gross*s/(1+s)
eq(full_pending_drag,drag)
N1=N-f1-q1*(p-raw)
after_pending_drag=remaining_fee+remaining_gross*s/(1+s)
eq(N1-after_pending_drag,N-drag)

# A pre-cost equity cap can pass exactly and then violate after fee/slip.
edge_cost=D('10000');edge_gross=D('9995');edge_fee=D('5')
edge_raw=edge_gross/D('1.0005')/D('1000')
edge_drag=edge_fee+(edge_gross-D('1000')*edge_raw)
assert edge_cost<=alpha*N
assert edge_cost>alpha*(N-edge_drag)

# Cost basis is released by actual parts, not sale cash/profit.
before=D('1200');qbefore=D('300');sold=D('100')
consumed=before*sold/qbefore;remaining=before-consumed
eq(consumed,D('400'));eq(remaining,D('800'))
# A split does not refund money: surviving-layer cost unchanged, qty changes.
split_qty=D('200')*D('1.5');eq(split_qty,D('300'))
eq(remaining,D('800'))

# The floor-anchor fact alone cannot release capacity when breached or locked.
E=D('10.005');F=D('10.1')
def release(mark,locked=False,known=True):
    return known and F>=E and mark>F and not locked
assert release(D('10.2'))
assert not release(D('10.1'))
assert not release(D('10'))
assert not release(D('10.2'),locked=True)
assert not release(D('10.2'),known=False)

out=dict(status='PASS_EXACT_INDEPENDENT_ALGEBRA_ONLY_NOT_NATIVE_IMPLEMENTATION',
    checks=['native_fee_slip_equity_drag','pending_partial_cost_conservation',
            'minimum_fee_first_part','post_cost_cap_edge','actual_part_cost_release',
            'surviving_split_no_money_refund','mark_breach_exit_unknown_no_release'],
    values={k:str(v) for k,v in dict(cost=cost,full_drag=drag,first_basis=B1,
        remaining_gross=remaining_gross,Nguard_before=N-drag,
        Nguard_after=N1-after_pending_drag,partial_remaining_basis=remaining).items()},
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    native_accounts=0,producer_implementation_checked=False)
(O/'ATOMIC_ALGEBRA_CHECK.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
