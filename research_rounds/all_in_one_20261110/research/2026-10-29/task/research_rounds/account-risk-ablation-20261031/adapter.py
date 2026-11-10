"""Single-factor research diagnosis. Never enables the separate v4 lot draft."""
from pathlib import Path
import sys
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'case-stage-ledger-20261031/v3'))
import launch_v3 as L
J=L.J
N=J.W.load('single_factor_budget_no_account',O/'model_without_account_check.py')
class NoAccountBudget(J.Budget):
 request=N.Contract.request
def enable(account):
 # Same initialized market attempt/consumption/resources; no reseeding or cash.
 account.budget.__class__=NoAccountBudget
env=dict(J.__dict__);exec((O/'route_without_account_check.py').read_text(),env)
class Runner(L.PreparedRunner):
 route=env['route']
 def __init__(self,*args,**kwargs):
  super().__init__(*args,policies=('B',),**kwargs)
  for a in self.accounts.values():enable(a)
