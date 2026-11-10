"""Candidate-only full preparation; same small-verified economic functions."""
from pathlib import Path
import gross_adapter as C
A,N,J,L,IO,P=C.A,C.N,C.J,C.L,C.IO,C.P
POLICY=C.POLICY+':CANDIDATE_ONLY_PROVIDER_V2'

class Runner(C.Runner):
 def __init__(self,*args,info,fixed_end,**kw):
  self._full_ready=False
  super().__init__(*args,info=info,**kw)
  # Both derive from the identical original initialized mother; remove B
  # before any event. The archived B is never a native executed account here.
  self.accounts.pop('B');self.fixed_end=fixed_end
  self.opportunity_denominators=[];self.integration_policy=POLICY+':'+self.rank_mode
  self._full_ready=True;self.assert_native_wiring()
 def assert_native_wiring(self):
  assert self.opening.__func__ is J.Runner.opening
  assert self.route.__func__ is C.Runner.route
  assert self.planning.__func__ is Runner.planning
  assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
  if getattr(self,'_full_ready',False):
   assert set(self.accounts)=={'D_GROSS10'}
   assert self.integration_policy==POLICY+':'+self.rank_mode
  for label,a in self.accounts.items():
   expected=C.GrossAccount if getattr(self,'_gross_ready',False)and label!='B'else J.Account
   assert type(a)is expected and not hasattr(a,'capacity_basis')
   budget=N.BASE.NoAccountBudget if getattr(self,'_cap_bootstrap',False)else A.NoConfirmed60Budget
   assert type(a.budget)is budget
   if not getattr(self,'_cap_bootstrap',False):assert a.budget.request.__func__ is P.MOD.Contract.request
   for m in('sync','cancel_buy','fill_exit','split','expire_day_buys','assert_budget_view'):
    assert getattr(a,m).__func__ is getattr(J.Account,m)
   if label=='D_GROSS10'and getattr(self,'_gross_ready',False):
    for m in('reserve_quantity','fill_buy'):assert getattr(a,m).__func__ is getattr(C.GrossAccount,m)
 def planning(self,at):
  # Existing audited diagnostic-only compact fragment after complete N plan.
  first=len(self.opportunities);N.Runner.planning(self,at)
  rows=self.opportunities[first:]
  self.opportunity_denominators.append(dict(at=at,full_rows=len(rows),retained_role_candidates=sum(bool(x['roles'])for x in rows),accounts=len(self.accounts)))
  self.opportunities[first:]=[x for x in rows if x['roles']]
 def restore(self,path):
  expected_episode_starts=dict(self.episode_starts);expected_end=self.fixed_end
  provider=self.accounts['D_GROSS10'].gross_info
  result=A.Runner.restore(self,path)
  assert set(self.accounts)=={'D_GROSS10'}and self.fixed_end==expected_end
  assert all(k in expected_episode_starts and expected_episode_starts[k]==v for k,v in self.episode_starts.items()),'industry input episode index changed'
  self.episode_starts=expected_episode_starts
  old=self.accounts['D_GROSS10'].gross_info
  assert old.path==provider.path and old.sha256==provider.sha256
  assert old.expected_closes==provider.expected_closes
  assert old.clocks==provider.clocks[:len(old.clocks)]and len(old.clocks)<=len(provider.clocks)
  # Only the same frozen source/domain is constructor-bound; all actual
  # holdings, orders, fees, risk/H, cash and receipts remain restored state.
  self.accounts['D_GROSS10'].gross_info=provider
  self.assert_native_wiring();return result
 def dump_joint(self,path):
  C.Runner.dump_joint(self,path)
  IO.write_gzip_jsonl(Path(path)/'opportunity-denominators.jsonl.gz',self.opportunity_denominators,encoder=J.C.encoded)
