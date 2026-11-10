from common_abcd import *
def main():
 assert read(HERE/'technical/A-controls/decision-comparison-v2.json')['passed'];assert read(HERE/'technical/unit-tests-v2.json')['passed'];assert read(HERE/'review/board-prefix.json')['passed'];assert read(HERE/'technical/A-controls/comparison.json')['passed']
 old={}
 for name in ['ix-a-share-entry-20261025','winner-gap-attribution-20261025','multiscale-resource-review-20261025','gradual-recovery-rc1-20261025']:
  d=read(ROOT/'research_rounds'/name/'complete.json');old.update(d.get('artifacts',{}))
 registry=read(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json');old.update(registry['sha256'])
 verified=verify(old);write(HERE/'old-identity-before.json',dict(recorded_at=now(),files=verified,sha256=old))
 source=read(HERE/'prepared/manifest.json');verify(source['source_sha256']);verify(source['outputs'])
 paths=[HERE/'PROTOCOL.md',HERE/'PRE_ACCOUNT_REVIEW.md']+list((HERE/'code').glob('*.py'))+list((HERE/'review').glob('*'))+[HERE/'technical/unit-tests-v2.json',HERE/'technical/A-controls/comparison.json',HERE/'technical/A-controls/decision-comparison-v2.json',HERE/'prepared/manifest.json',HERE/'old-identity-before.json']
 ids={str(p.relative_to(ROOT)):sha(p) for p in paths};ids.update(source['outputs']);ids.update(source['source_sha256'])
 write(HERE/'freeze.json',dict(recorded_at=now(),status='before_BCD_economics',new_economic_accounts=9,technical_A_controls=3,initial_cash=1000000,groups=['A','B','C','D'],stresses=['base','cost2','delay1'],old_IX_unchanged=True,original_position_sizing=True,post_result_parameters_search=False,sha256=ids))
 print(dict(frozen=True,old_files_verified=verified,freeze_files=len(ids)),flush=True)
if __name__=='__main__':main()
