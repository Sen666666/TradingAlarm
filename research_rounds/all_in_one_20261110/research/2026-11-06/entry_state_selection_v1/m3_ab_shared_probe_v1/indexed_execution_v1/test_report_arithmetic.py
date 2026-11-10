"""Only report allocation arithmetic; stub fees, no market/strategy simulation."""
from types import SimpleNamespace
from decimal import Decimal as D
from pathlib import Path
import json
from report_layers_v1 import reports
def check(settled):
    rid='SYNTHETIC_REPORT';sid='SYNTHETIC'
    actions=[dict(round_id=rid,sid=sid,day=d,q=q,side=side,price=px,fee=5.,execution_action_id=str(i))
        for i,(d,q,side,px) in enumerate([('1',200,'buy_core',100.05),('2',100,'buy_add',100.05),('3',300,'sell_all',99.95)])]
    st=dict(sid=sid,sector='SYNTHETIC',core=0,add=0,cash=D(-45)+(D(3) if settled else D(0)),receivable=D(0) if settled else D(3),dividend_paid=D(3) if settled else D(0),spent=D(30025),fees=D(15),entry_day='1')
    s=SimpleNamespace(actions=actions,archives={rid:st},claims={'c':dict(owner_round_id=rid,core_amount=D(2),amount=D(3),recognized=True,settled=settled)},
        pd=SimpleNamespace(Timestamp=lambda x:x),raw={sid:{d:dict(raw_open=100) for d in ('1','2','3')}},
        SLIP=D('.0005'),getmeta=lambda sid,d:(None,None,None),fee=lambda *args:D(5))
    b=SimpleNamespace(s=s,states={},caps={rid:D(1200000)},pools={rid:'confirmed'})
    r=reports(b,'3');j=r['exact_trade_journal'][-1]['report_only_allocations']
    assert j['core']['fee']==D(5)*D(200)/D(300) and j['add']['fee']==D(5)-j['core']['fee']
    assert sum(x['fee'] for x in j.values())==D(5)
    assert r['rounds'][0]['whole_round_NET80']==D(-42)
    assert sum(x['NET80'] for x in r['layers'])==D(-42)
    assert r['rounds'][0]['status']==('EXECUTION_AND_SETTLEMENT_CLOSED' if settled else 'EXECUTION_CLOSED_SETTLEMENT_OPEN')
    return dict(settled=settled,status='PASS',allocations=j,net=D(-42))
if __name__=='__main__':
    result=[check(False),check(True)]
    with (Path(__file__).parent/'REPORT_ARITHMETIC_QA.json').open('x') as f:json.dump(dict(domain='SYNTHETIC_REPORT_ONLY_STUB_FEE',checks=result),f,indent=2,default=str)
    print('PASS report allocation and settlement split',len(result))
