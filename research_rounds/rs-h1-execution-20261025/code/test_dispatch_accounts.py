"""Partition scheduling must preserve every account value and decision."""
import unittest
from test_history_runner import fixture
from dispatch_accounts import restrict,GROUPS
from history_runner import encoded

class PartitionTests(unittest.TestCase):
 def test_same_universe_all_thirteen_accounts_exact_under_two_schedules(self):
  for targets in [[True]*6,[True,True,False,True,True,False]]:
   full,_,_=fixture(count=8,targets=targets);full.run();rows=[];decisions=[];accounts={}
   for group in GROUPS:
    part,_,_=fixture(count=8,targets=targets);restrict(part,group);part.run();rows+=part.daily;decisions+=part.decisions;accounts.update(part.accounts)
   key=lambda x:(x['at'],x['account'])
   self.assertEqual(encoded(sorted(rows,key=key)),encoded(sorted(full.daily,key=key)))
   self.assertEqual(encoded(sorted(decisions,key=key)),encoded(sorted(full.decisions,key=key)))
   self.assertEqual(set(accounts),set(full.accounts))
   for aid,a in accounts.items():
    self.assertEqual(encoded(a.fills),encoded(full.accounts[aid].fills))
    self.assertEqual(encoded(a.audit_log),encoded(full.accounts[aid].audit_log))
    self.assertEqual(a.available,full.accounts[aid].available)

if __name__=='__main__':unittest.main()
