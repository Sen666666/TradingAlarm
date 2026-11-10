"""One frozen continuous two-arm mechanism replay after engineering gates."""
import joint as J
from pathlib import Path
import time,json,pickle,copy,hashlib
O=J.O;W=J.W
class Pair(J.Runner):
 def planning(self,at):
  super().planning(at)
  if str(at.date()) in ['2025-09-30','2025-12-31','2026-03-31']:
   state=dict(at=at,runner={k:copy.deepcopy(getattr(self,k)) for k in ['last_epoch','epoch','global_watch','applied_actions']},accounts={k:copy.deepcopy({f:v for f,v in a.__dict__.items() if f not in ['market','facts']}) for k,a in self.accounts.items()});raw=pickle.dumps(state,protocol=5);loaded=pickle.loads(raw)
   for k,a in self.accounts.items():
    assert loaded['accounts'][k]['available']==a.available and loaded['accounts'][k]['budget'].consumed==a.budget.consumed and loaded['accounts'][k]['positions']==a.positions and loaded['accounts'][k]['budget'].orders==a.budget.orders
   path=O/('checkpoint-'+str(at.date())+'.pkl');path.write_bytes(raw);J.save('checkpoint-'+str(at.date()),dict(sha256=hashlib.sha256(raw).hexdigest(),no_quarter_reset=True,accounts=list(self.accounts),restart_state_roundtrip=True))
def main():
 assert W.M.read(O/'JOINT_GATE.json')['passed'];assert W.M.read(O/'budget_v2/results.json')['passed'];start=time.monotonic();shared=W.context();rows=J.T.read(O/'STOCK_CANONICAL_RECEIPTS.json');receipts={sid:{} for sid in shared[1].lines}
 for row in rows:receipts[row['canonical_series']][row['confirmed_day']]=row
 sources=[O/'run_pair.py',O/'joint.py',O/'wire.py',O/'INTEGRATION_CONTRACT.txt',O/'budget_v2/model.py',W.CACHE/'MANIFEST.json',O/'STOCK_CANONICAL_RECEIPTS.json',O/'JOINT_GATE.json',J.M.O/'recovery.csv'];J.save('PAIR_FREEZE',dict(before_run=True,arms=['A_probe_only','B_finite_expansion'],scope=[J.START,J.END],cash_each=1000000,stocks=77,industries=5,no_account_before_start=True,no_grants_before_start=True,budget_seconds=120,sha256={str(p):W.M.sha(p) for p in sources}));r=Pair(shared,receipts);prepared=time.monotonic()
 try:r.run(end=J.END,begin=J.START,max_seconds=110)
 except BaseException:
  r.dump_joint(O/'failed-pair');raise
 r.dump_joint(O/'pair');J.save('PAIR_DONE',dict(completed=True,arms=2,closes=len(r.daily),run_seconds=r.run_seconds,preparation_seconds=prepared-start,total_seconds=time.monotonic()-start,ending_NAV={k:str(a.current_nav) for k,a in r.accounts.items()},trades={k:len(a.trades) for k,a in r.accounts.items()},no_other_policy_paths=True));print('PAIR_DONE',r.run_seconds,{k:str(a.current_nav) for k,a in r.accounts.items()},flush=True)
if __name__=='__main__':main()
