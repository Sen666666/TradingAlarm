from util_ix import *
def main():
 assert read(HERE/'validation/tests.json')['passed']
 assert read(HERE/'validation/multi-decision-identity.json')['passed']
 assert read(HERE/'review/verification.json')['passed']
 assert read(HERE/'technical/E0-controls/comparison.json')['passed']
 verify(read(HERE/'old-identity-before.json')['sha256'])
 paths=[HERE/'PROTOCOL.md',HERE/'PRE_ACCOUNT_REVIEW.md',HERE/'runner-derivation.json',HERE/'multi-runner-derivation.json']+list((HERE/'code').glob('*.py'))
 for directory in ['signals','review','validation']:
  paths += [p for p in (HERE/directory).rglob('*') if p.is_file()]
 paths += [HERE/'technical/E0-controls/comparison.json']
 write(HERE/'freeze.json',dict(recorded_at=now(),status='before_new_economic_accounts',entry_schemes=ENTRY_TYPES,allocations=['T0','T1','S0','S1'],scenarios=['base','cost2','delay1'],planned_new_accounts=48,initial_cash_per_account=1000000,score_formula_changes=0,rotation_added=False,position_formula_changes=0,industry_gating='old E0 unchanged',ranking='old RS-H1 unchanged',history='seen_development_current_survivor_cap_industry_bias',known_strict_delay_degeneracy=True,sha256={str(p.relative_to(ROOT)):sha(p) for p in paths}))
 print(dict(frozen=len(paths),planned_accounts=48),flush=True)
if __name__=='__main__':main()
