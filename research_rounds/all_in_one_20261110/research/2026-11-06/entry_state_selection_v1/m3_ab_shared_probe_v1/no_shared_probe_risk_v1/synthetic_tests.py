"""Pure fabricated data, no economic source load or historical replay."""
from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace as NS
import ast,dataclasses,json,random
import pandas as pd
import numpy as np
import no_risk_bridge as N
V=N.V;HERE=Path(__file__).resolve().parent
checks=[]
def record(name):checks.append(name)
def exposure(i,sector,pool='probe',q=100,mark='100',floor='1',status='held',fee='0'):
    return V.Exposure(str(i),str(i),sector,pool,q,D(mark),D(floor),D(fee),status)
h=(exposure(1,'A',q=100),)
s=V.Snapshot(D('990000'),D(0),D('1000000'),D('1000000'),h,(),(),'SYNTHETIC')
p=exposure(2,'B',q=100,status='live')
assert V.ReserveBook(s).reasons(p)==['probe_risk']
b=N.NoRiskBook(s);assert b.reasons(p)==[] and b.reserve(p)==[]
assert b.reserved_cash==D('10000') and b.capital(pool='probe')==D('20000')
assert set(b.__dict__)=={'snapshot','orders','audit'} and 'probe_resources' not in b.audit[0]
assert b.reserve(p)==['stock_order_pending']
record('shared risk removed; cash/capital reservation and duplicate guard preserved')
p2=exposure(3,'A',q=2,mark='100',floor='1',status='live')
assert 'sector_risk' in V.ReserveBook(s).reasons(p2)
assert N.NoRiskBook(s).reasons(p2)==[]
record('industry risk removed')
rng=random.Random(17)
for i in range(500):
    hs=tuple(exposure(j,str(j%4),pool=rng.choice(['probe','confirmed']),q=rng.randint(1,250),floor=str(rng.randint(1,130))) for j in range(8))
    nav=D('1000000');cash=nav-sum((x.capital for x in hs),D(0))
    ss=V.Snapshot(cash,D(0),nav,nav,hs,(),(),'SYNTHETIC')
    p=exposure(90,str(i%4),pool=rng.choice(['probe','confirmed']),q=rng.randint(1,1500),floor=str(rng.randint(1,130)),status='live',fee='5')
    old=V.ReserveBook(ss).reasons(p);new=N.NoRiskBook(ss).reasons(p)
    assert new==[x for x in old if x not in ('probe_risk','sector_risk')]
record('500 differential reason checks: only two risk reasons removed')
unknown=V.Snapshot(D('1000000'),D(0),None,D('1000000'),(),(),({'reason':'UNKNOWN'},),'SYNTHETIC')
assert N.NoRiskBook(unknown).reasons(p)==['NAV_OR_ASSET_UNKNOWN']
record('UNKNOWN still blocks new orders')
source=N.E.bridge.EVENT_ROOT/'relative_priority_v1/simulate.py'
qr=NS(buy_floor=lambda q:int(q)//100*100,buy_minimum=100)
syn=NS(SOURCE=source,ev=pd.DataFrame({'day':[]}),reset=lambda *a:None,D=D,SLIP=D('.0005'),getmeta=lambda *a:(qr,None,D(1)),fee=lambda *a:D(5),pd=pd,np=np,finite=np.isfinite)
br=N.NoRiskBridge(syn)
for riskmax in (None,D(0),D('0.00000001')):
    q,fee,risk,*_=syn.size('S',None,D(100),D(1),D(24000),riskmax,10000)
    assert q==200 and risk>D(19000)
assert syn.size('S',None,D(100),D(1),D(24000),None,100)[0]==100
assert syn.size('S',None,D(100),D(1),D(9000),None,10000)[0]==0
record('INIT CLOSE/OPEN common size ignores all risk ceilings and preserves fee budget/capacity/lot')
syn.INIT=D(24000);syn.SLOT=D(48000);syn.RISK=None;syn.facts={'S':{0:{'i_floor':1}}};syn.capacity={'S':{0:10000}};syn.mark=lambda *a:D(1000)
syn.freeze_unknown=lambda *a:(_ for _ in ()).throw(AssertionError('unexpected unknown'))
st={'addpending':D(1),'add_attempts':0,'add_profit_floor_rejects':0,'core':100,'add':0,'fac':D(1),'initial_fee':D(5),'add_size_rejects':0}
p=br._callback('source_prepare_add')({},'S',st,1,0,{'raw_open':100})
assert p['q']==200 and p['remaining_risk'] is None and p['risk']>D(19000)
record('ADD has no remaining risk cap and retains capital sizing/profit floor')
for profit,price in [(D(-1),100),(D(1000),1)]:
    syn.mark=lambda *a,v=profit:v
    st.update(addpending=D(1));assert br._callback('source_prepare_add')({},'S',st,1,0,{'raw_open':price}) is None
record('ADD negative profit and floor failures still reject')
# No derived execution path compares or branches on a monetary risk budget.
for name,d in N.DERIVATION.items():
    tree=ast.parse(d['derived_source'])
    for x in ast.walk(tree):
        if isinstance(x,ast.Compare):
            assert not any(isinstance(y,ast.Name) and y.id in ('riskmax','RISK','remaining','pr','sr') for y in ast.walk(x)),(name,ast.unparse(x))
assert N.E.ReserveBook is V.ReserveBook
assert br.open_phase.__func__.__globals__['ReserveBook'] is N.NoRiskBook
record('isolated bridge; no old-module mutation or residual risk-budget condition')
out={'status':'PASS','economic_replay':False,'checks':checks,'derivation':N.DERIVATION}
with (HERE/'SYNTHETIC_QA.json').open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2,default=str)
print('PASS',len(checks),'groups; no historical replay')
