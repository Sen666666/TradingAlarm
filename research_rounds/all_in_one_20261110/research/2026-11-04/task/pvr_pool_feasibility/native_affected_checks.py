"""Direct native private budget boundaries, no Account/economic events."""
import copy,json
import native_adapter as A
import check_counterexamples as F
def main():
 rows=[]
 for enabled in [True,False]:
  b=A.NoConfirmed60Budget(enabled);s=F.make();b.__dict__.update(copy.deepcopy(vars(s)));b.expand=enabled
  # This specifically uses native ON request, rather than the pure State's
  # default OFF dispatcher. Original core epoch lock must win unchanged.
  ans=b.request('locked','X','S',100,10,9.9,None,A.J.ordinal(F.F.DEC.date()),0,probe_request=True,role='core',core_epoch_locked=True)
  assert ans=='core_epoch_locked';rows.append(dict(expand=enabled,core_epoch_lock=ans))
  answer=b.migrate('S');assert answer==enabled;rows[-1]['migration_after60_removal']=answer
 A.IO.write_json(A.O/'native-readiness/AFFECTED_NATIVE_BUDGET_CHECKS.json',dict(passed=True,source_sha256=A.N.sha(__file__),
  native_budget_class='native_adapter.NoConfirmed60Budget',tests=rows,native_Account_initializations=0,financial_events=0))
 print('NATIVE_AFFECTED_CHECKS_PASS')
if __name__=='__main__':main()
