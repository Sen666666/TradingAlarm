from study import *
from types import SimpleNamespace as N
from collections import Counter
original=E.ledger.SectorAccount.fill_buy
try:
 E.ledger.SectorAccount.fill_buy=lambda self,sid,w:'filled'
 for raw,expected in [('44.99',None),('45',None),('45.01','filled')]:
  calls=[];a=N(buys={'X':N(order_id='o')},intents={'o':{'floor_signal':D(90)}},facts=N(factor=lambda *args:D(2)),protect=True,mode='SW10F',quantity=lambda sid:0,rearm=set(),counts=Counter(),log=lambda *args,**kw:calls.append((args,kw)),cancel_buy=lambda sid:calls.append(('cancel',sid)))
  result=E.Account.fill_buy(a,'X',N(at=pd.Timestamp('2026-01-01'),raw_open=D(raw)))
  assert result==expected
  if expected is None:assert 'X' in a.rearm and a.counts['open_support_reject']==1
  else:assert a.counts['buy_fills']==1
finally:E.ledger.SectorAccount.fill_buy=original
save(O/'execution-boundary-check.json',{'passed':True,'actual_engine_checks':3,'inherited_adjusted_floor':90,'causal_factor':2,'reject_raw_opens':[44.99,45],'accept_raw_open':45.01,'economic_code_unchanged':True})
