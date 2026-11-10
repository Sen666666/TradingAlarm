from types import SimpleNamespace
from decimal import Decimal as D
from pathlib import Path
import json
from test_report_arithmetic_v2 import check
from report_layers_v2 import reports
def mixed(settled):
    rid='SYNTHETIC_MIXED';sid='SYNTHETIC'
    acts=[dict(round_id=rid,sid=sid,day=d,q=q,side=side,price=px,fee=5.,execution_action_id=str(i)) for i,(d,q,side,px) in enumerate([('1',200,'buy_core',100.05),('2',100,'buy_add',100.05),('3',100,'sell_add',99.95)])]
    st=dict(sid=sid,sector='SYNTHETIC',core=200,add=0,cash=D(-20035)+(D(3) if settled else D(0)),receivable=D(0) if settled else D(3),dividend_paid=D(3) if settled else D(0),spent=D(30025),fees=D(15),entry_day='1',origin='SYNTHETIC',factor=1.)
    z=dict(raw_open=100,raw_close=100,adjustment_factor=1.)
    s=SimpleNamespace(actions=acts,archives={rid:st},claims={'c':dict(owner_round_id=rid,core_amount=D(2),amount=D(3),recognized=True,settled=settled)},pd=SimpleNamespace(Timestamp=lambda x:x),raw={sid:{d:z for d in ('1','2','3')}},SLIP=D('.0005'),getmeta=lambda sid,d:(None,None,None),fee=lambda *args:D(5),finite=lambda x:True,lineage=lambda z:'SYNTHETIC',np=SimpleNamespace(isclose=lambda *a,**k:True))
    b=SimpleNamespace(s=s,states={sid:dict(state='HELD',round_id=rid)},caps={rid:D(1200000)},pools={rid:'confirmed'})
    r=reports(b,'3');rows={x['layer']:x for x in r['layers']}
    assert rows['core']['round_status']=='OPEN_CENSORED' and rows['core']['layer_status']=='OPEN_CENSORED'
    assert rows['add']['layer_status']==('EXECUTION_AND_SETTLEMENT_CLOSED' if settled else 'EXECUTION_CLOSED_SETTLEMENT_OPEN')
    assert rows['add']['execution_closed'] and not rows['core']['execution_closed']
    return dict(settled=settled,status='PASS',core=rows['core']['layer_status'],ADD=rows['add']['layer_status'])
if __name__=='__main__':
    results=dict(domain='SYNTHETIC_REPORT_ONLY_STUB_FEE',closed=[check(False),check(True)],mixed=[mixed(False),mixed(True)])
    with (Path(__file__).parent/'REPORT_ARITHMETIC_AND_LAYER_STATUS_QA.json').open('x') as f:json.dump(results,f,indent=2,default=str)
    print('PASS four report-only allocation/status cases')
