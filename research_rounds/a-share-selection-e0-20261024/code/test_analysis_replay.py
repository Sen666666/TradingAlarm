"""Independent evaluator exercised on partial fill, split, unpaid dividend, exit."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
import unittest
import pandas as pd
from test_b0_rebalance import quote,window,mark,T,CLOCK
from sector_account import SectorAccount
from history_runner import encoded
from analyze_accounts import audit_account

class EvaluatorTests(unittest.TestCase):
 def test_partial_fill_distribution_and_exit_reconcile_from_economic_cash(self):
  a=SectorAccount(initial_cash=1000000,fractional_split_policy='floor_position_fraction_writeoff')
  self.assertTrue(a.reserve_budget(quote=quote(),clock=CLOCK,gross_budget_cny=10000)[0])
  buy=T+timedelta(days=1);a.fill_buy('A',replace(window(at=buy,due=buy),execution_price=D('10.005')));a.settle_due(buy)
  n=a.quantity('A');self.assertEqual(n,900)
  rows=[]
  def save(at,price):
   balance=a.balance(at,{'A':mark(price,at)} if a.positions else {})
   rows.append(encoded(dict(account='T0_base',at=at,**balance,positions={sid:p.shares for sid,p in a.positions.items()})))
  save(buy,10)
  ex=T+timedelta(days=2)
  a.accrue_dividend(event_id='div',sid='A',currency='CNY',net_local=D(n)*D('.08'),ex_at=ex,paid_at=None,source_id='synthetic',entitlement_basis='synthetic')
  sale=T+timedelta(days=3);a.split(event_id='split',sid='A',ratio='2',at=ex,new_shares_sellable_at=sale);save(ex,D('5.5'))
  clock=replace(CLOCK,decision_at=ex,earliest_execution_at=sale,session_date=ex.date());a.request_exit(quote(price=5.5,at=ex),clock)
  a.fill_exit('A',replace(window(price=6,at=sale,due=sale,eid='sale'),execution_price=D('5.997')));a.settle_due(sale);save(sale,6)
  prices_by_day={str(buy.date()):D(10),str(ex.date()):D('5.5'),str(sale.date()):D(6)}
  class P:
   def mark(self,sid,day):return prices_by_day[day]
  contribution=[]
  camps,audit=audit_account('T0_base',encoded(dict(audit_log=a.audit_log)),rows,P(),{'A':{'name':'test','industry':'G','sector_id':'G'}},[pd.Timestamp(T+timedelta(days=i)) for i in range(6)],contribution)
  self.assertTrue(audit['passed']);self.assertEqual(len(camps),1);self.assertTrue(camps[0]['closed'])
  expected=D(2*n)*D('5.997')+D(n)*D('.08')-D(n)*D('10.005')
  self.assertEqual(camps[0]['net_pnl'],expected)
  self.assertEqual(sum(x['net_contribution'] for x in contribution),expected)

if __name__=='__main__':unittest.main()
