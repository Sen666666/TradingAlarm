"""Pure observer boundary checks, explicitly not native partial/CA proof."""
from pathlib import Path
from types import SimpleNamespace as S
from decimal import Decimal as D
import hashlib,json
import guard as G


class Mark:
    def __init__(self,p):self.p=p
    def cny_price(self,at):return self.p


def account(alpha='.20'):
    a=S(layers=[],positions={'X':100},jmeta={},exits={},buys={},audit_log=[],trades=[],journal=[])
    a.factor=D(1);a.price=D(12)
    a.facts=S(factor=lambda sid,at:a.factor)
    a.market=S(marks=lambda at,ids:{sid:Mark(a.price)for sid in ids})
    a.balance=lambda at,marks:{'nav':D(10000)}
    G.init(a,alpha,True)
    x=dict(id=1,sid='X',kind='add',qty=100,floor=D(9))
    a.layers.append(x);a.jmeta[1]={'last_core_line':'9'}
    G.after_buy(a,S(gross_cny=D(1000),fees_cny=D(5),shares=100),x)
    return a


def main():
    tests=[];a=account();c=G.context(a,'T',D('.0005'))
    assert c['used_cost']==1005 and c['protected_cost']==0;tests.append('actual_gross_plus_fee')
    assert not G.reserve_allowed(a,c,100,D(10),D(10),D(5));tests.append('fee_after_NAV_cliff')
    assert G.reserve_allowed(a,c,50,D(10),D(10),D(5));tests.append('legal_smaller_quantity')
    a.layers[0]['floor']=D('10.1');c=G.context(a,'T',D('.0005'))
    assert c['used_cost']==0 and c['protected_cost']==1005;tests.append('current_valid_line_releases_only_overlay_cost')
    a.capacity_release=False;c=G.context(a,'T',D('.0005'))
    assert c['used_cost']==1005 and c['counts']['qualification_protected']==1 and c['counts']['released']==0;tests.append('NR20_one_factor')
    a.capacity_release=True;a.price=D(10);c=G.context(a,'T',D('.0005'))
    assert c['used_cost']==1005 and c['counts']['breached']==1;tests.append('breached_reoccupies')
    a.price=D(12);a.exits['X']=object();c=G.context(a,'T',D('.0005'))
    assert c['used_cost']==1005;tests.append('pending_exit_reoccupies')
    a.exits.clear();a.factor=D('NaN');c=G.context(a,'T',D('.0005'))
    assert c['used_cost']==1005 and c['unknown_layers']==[1]
    assert G.reserve_allowed(a,c,50,D(10),D(10),D(5));tests.append('unknown_protection_full_cost_not_global_ban')
    a.factor=D(1);del a.capacity_basis[1]
    try:G.context(a,'T',D('.0005'))
    except AssertionError:tests.append('missing_new_basis_fails_closed')
    else:raise AssertionError('missing basis silently grandfathered')
    a=account();a.layers[0]['qty']=75;G.after_sell(a,{1:100},[dict(layer=1,shares=25)],'T')
    assert a.capacity_basis[1]==D('753.75');tests.append('actual_partial_sell_cost_allocation')
    a.layers[0]['qty']=90;G.after_split(a,{1:75},D('1.2'),'T')
    assert a.capacity_basis[1]==D('753.75') and a.capacity_entry[1]==D(10)/D('1.2');tests.append('surviving_split_preserves_cash_cost')
    a.layers[0]['qty']=0;G.after_split(a,{1:90},D('.001'),'T')
    assert a.capacity_basis[1]==0 and a.capacity_events[-2]['kind']=='native_fraction_zero_batch_cost_writeoff';tests.append('zero_quantity_writeoff_no_NAV_mutation')
    a.capacity_in_callback=True
    try:G.context(a,'T',D('.0005'))
    except AssertionError:tests.append('half_callback_admission_forbidden')
    else:raise AssertionError('half callback inspect allowed')
    p=Path(__file__).resolve().parent
    result=dict(passed=True,scope='PURE_COST_OBSERVER_EDGE_CHECKS_ONLY_NOT_NATIVE_CA_OR_MATCHING',checks=tests,
                source_sha256={str(x):hashlib.sha256(x.read_bytes()).hexdigest()for x in [p/'guard.py',Path(__file__)]})
    (p/'COST_OBSERVER_EDGE_CHECKS.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
