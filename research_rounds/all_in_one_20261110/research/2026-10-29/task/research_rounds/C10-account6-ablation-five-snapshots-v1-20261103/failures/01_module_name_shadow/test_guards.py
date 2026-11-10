"""Affected guard components only; no ledger/event/strategy replay."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime
from types import SimpleNamespace
import sys,copy
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import engine as E
X=E.X

class QuoteFixture:
 """Pure inputs to the actual native preview function, not a fake ledger."""
 def __init__(self,*,risk=70000,capital=200000,sector='OLD',available=1000000,stock_cap=0,star=False,unknown=False):
  self.nd=D(1000000);self.available=D(available);self.market=SimpleNamespace(prices={'X':D(100)},quantity=lambda sid,at:X.A.E.N.quantity(at,star=star),fees=lambda sid,at:X.A.E.N.fees(at,star=star))
  self.facts=SimpleNamespace(factor=lambda sid,at:D(1));self.policy=SimpleNamespace(nd=self.nd,consumed=set(),locks={},allowed=lambda *a,**kw:True,targets=lambda sec:D(800000));self.exits={};self.buys={};self.core_epoch={}
  self.rows=[dict(sid='OLD',sector=sector,pool='confirmed',capital=D(capital),risk=D(risk),reserve=D(0))]
  if stock_cap:self.rows.append(dict(sid='X',sector='NEW',pool='confirmed',capital=D(stock_cap),risk=D(0),reserve=D(0)))
  self.unknown=unknown
 def nav(self,at):return self.nd
 def quantity(self,sid):return 0
 def resources(self,**kwargs):
  if self.unknown:raise X.A.E.UnknownRisk('fixture missing mark')
  return copy.deepcopy(self.rows)
 def totals(self,rows):return {k:sum((r[k] for r in rows),D(0)) for k in ['capital','risk','reserve']}
 def receipt_verified(self,c):return True  # Isolated risk/quantity guard fixture.

def main():
 original=X.A.E.Account._preview;off,op=E.native_preview_factory(False);on,np=E.native_preview_factory(True)
 at=datetime.fromisoformat('2025-07-02T09:30:00+08:00');decision=datetime.fromisoformat('2025-07-01T15:10:00+08:00');epoch=('X',0)
 cls=original.__globals__['HistoricalReceipt'];receipt=cls('fixture-receipt','X',decision,decision,decision,epoch)
 intent=dict(sid='X',sector='NEW',i_valid=True,stock_q=True,receipt=receipt,clock=SimpleNamespace(decision_at=decision),epoch=epoch,I_floor=D(90),cp_floor=D(90),core=True)
 rows=[]
 def case(name,fixture,*,i=None,role='mobile',use='S',cap=None,expect_on=None,why=None):
  i=i or intent;before=copy.deepcopy(fixture.rows)
  a=original(fixture,i,use,role,at,cap=cap);b=off(fixture,i,use,role,at,cap=cap);c=on(fixture,i,use,role,at,cap=cap)
  assert a==b,(name,'OFF native preview differs')
  if expect_on is not None:assert c['q']==expect_on,(name,c)
  if why:assert why in str(c['why']),(name,c)
  assert fixture.rows==before
  rows.append(dict(name=name,original_q=a['q'],ablation_q=c['q'],original_reasons=a['why'],ablation_reasons=c['why'],risk_inputs_unchanged=True,component_only=True))
 case('account6_only_veto_removed',QuoteFixture(),expect_on=1000)
 case('nonbinding_account6_identity',QuoteFixture(risk=1000),expect_on=1000)
 case('sector5_still_blocks',QuoteFixture(sector='NEW',risk=60000),expect_on=0,why='sector_risk5')
 case('capital90_still_blocks',QuoteFixture(capital=900000),expect_on=0,why='account_capital90')
 case('cash10_still_blocks',QuoteFixture(available=100000),expect_on=0,why='cash_reserve10')
 case('stock10_still_blocks',QuoteFixture(stock_cap=100000),expect_on=0,why='stock10')
 case('STAR_new_order_min200',QuoteFixture(star=True),cap=199,expect_on=0,why='target_minimum')
 core=dict(intent,I_floor=D(50),cp_floor=D(50));case('core_quarter_percent_still_blocks',QuoteFixture(risk=0),i=core,role='core',use='T',expect_on=0,why='core_risk.25')
 unknown=QuoteFixture(unknown=True);case('UNKNOWN_not_zero',unknown,expect_on=0,why='UNKNOWN')
 gap=dict(intent,I_floor=D(101),cp_floor=D(101));case('price_below_floor_not_zero_risk_permission',QuoteFixture(),i=gap,expect_on=0,why='gap_at_or_below_actual_floor')
 X.save(O/'NATIVE_PREVIEW_COMPONENT_GATE.json',dict(passed=True,cases=rows,original_mode_all_exact=True,
   original_canonical_identity_not_tested_by_this_fixture=True,full_native_OPEN_not_run=True,financial_events=0,original_patch=op,ablation_patch=np))
 _,a=E.factory(False);_,b=E.factory(True);X.save(O/'PATCH_AST.json',dict(original=a,ablation=b,native_preview=np,only_three_account6_guard_changes=True))
 print('GUARD_COMPONENTS_PASS',len(rows),flush=True)
if __name__=='__main__':main()
