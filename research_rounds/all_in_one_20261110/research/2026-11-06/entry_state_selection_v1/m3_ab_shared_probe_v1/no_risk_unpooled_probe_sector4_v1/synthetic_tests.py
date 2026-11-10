from pathlib import Path
from decimal import Decimal as D
import json,random,ast
import capital_bridge as C
V=C.N.V;HERE=Path(__file__).resolve().parent
checks=[]
def ex(i,sector,q=100,pool='probe',status='held',fee='0',floor='1'):
 return V.Exposure(str(i),str(i),sector,pool,q,D(100),D(floor),D(fee),status)
def snap(held):
 capital=sum((x.capital for x in held),D(0));return V.Snapshot(D(1000000)-capital,D(0),D(1000000),D(1000000),tuple(held),(),(),'PURE_SYNTHETIC')
s=snap([ex(i,str(i),q=200) for i in range(6)]);p=ex(100,'NEW',q=200,status='live')
assert 'pool_capital' in C.N.NoRiskBook(s).reasons(p)
b=C.CapitalPolicyBook(s);assert b.reasons(p)==[];assert b.reserve(p)==[] and b.reserved_cash==D(20000)
checks.append('probe pool >10% admits otherwise legal capital proposal')
s=snap([ex(1,'A',q=200,pool='confirmed')]);p=ex(2,'A',q=200,status='live')
assert 'sector_capital' in C.N.NoRiskBook(s).reasons(p)
assert C.CapitalPolicyBook(s).reasons(p)==[]
assert 'sector_capital' in C.CapitalPolicyBook(s).reasons(ex(3,'A',q=201,status='live'))
assert 'sector_capital' in C.CapitalPolicyBook(s).reasons(ex(3,'A',q=200,status='live',fee='5'))
assert C.CapitalPolicyBook(s).reasons(ex(3,'A',q=799,pool='confirmed',status='live'))==[]
assert 'sector_capital' in C.CapitalPolicyBook(s).reasons(ex(3,'A',q=801,pool='confirmed',status='live'))
checks.append('4% combined-pool industry boundary including fee-adjusted NAV; confirmed10% unchanged')
rng=random.Random(20260924)
for i in range(500):
 hs=[ex(j,str(j%4),q=rng.randint(1,300),pool=rng.choice(['probe','confirmed'])) for j in range(8)];s=snap(hs);p=ex(99,str(i%4),q=rng.randint(1,2000),pool=rng.choice(['probe','confirmed']),status='live',fee='5')
 before=C.N.NoRiskBook(s).reasons(p);after=C.CapitalPolicyBook(s).reasons(p)
 expected=[x for x in before if x not in ('pool_capital','sector_capital')]
 effective=s.nav-p.fee;sc=C.CapitalPolicyBook(s).capital(sector=p.sector)
 if sc+p.capital>effective*(D('.04') if p.pool=='probe' else D('.10')):expected.append('sector_capital')
 assert set(after)==set(expected),(before,after,expected)
 assert not set(after)&{'probe_risk','sector_risk','round_fee_inclusive_risk','pool_capital'}
checks.append('500 differential cases only authorized combined capital policy changes')
for method in ('_entry_proposal','_add_proposal','_checkclose','reserve_proposal','commit','close_phase','prepare_promotions','commit_promotions'):
 assert getattr(C.CapitalPolicyBridge,method) is getattr(C.N.NoRiskBridge,method)
assert C.CapitalPolicyBridge.open_phase.__globals__['ReserveBook'] is C.CapitalPolicyBook
assert C.N.NoRiskBridge.open_phase.__globals__['ReserveBook'] is C.N.NoRiskBook
checks.append('sizing/risk removal/CP/exit/UNKNOWN identical inheritance; isolated book binding')
with (HERE/'SYNTHETIC_QA.json').open('x') as f:json.dump(dict(status='PASS',historical_replay=False,checks=checks,derivation=C.DERIVATION),f,indent=2)
print('PASS',len(checks),'groups +500 cases')
