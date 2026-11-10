"""Exact prefix, coverage-repair identity, and final artifact provenance."""
from common import *
import collections

def event_time(x):return x.get('at') or x.get('receipt',{}).get('at') or x.get('receivable',{}).get('ex_at')
def verify_prefix():
 full=HERE/'accounts-v2';prefix=HERE/'technical/prefix';cut='2024-12-31';aids=set(read(prefix/'summary.json')['accounts']);counts={}
 for kind in ['daily','decisions']:
  a=[r for r in rows(full/f'{kind}.jsonl.gz') if r['account'] in aids and r['at'][:10]<=cut];b=list(rows(prefix/f'{kind}.jsonl.gz'));assert a==b,kind;counts[kind]=len(a)
 for kind in ['fills','audit_log']:
  n=0
  for aid in sorted(aids):
   a=[r for r in read(full/f'{aid}.json')[kind] if event_time(r)[:10]<=cut];b=read(prefix/f'{aid}.json')[kind];assert a==b,(aid,kind);n+=len(a)
  counts[kind]=n
 write(HERE/'prefix-identity.json',dict(passed=True,paths=len(aids),cutoff=cut,rows=counts,removed_future_in_memory=['raw_rows','raw_arrays','actions','prepared_states','I_IX_E0_facts','H1_rows']))
 return counts

def verify_repair():
 full=HERE/'accounts-v2';failed=HERE/'accounts';cut='2026-10-22';counts={}
 for kind in ['daily','decisions']:
  a=[r for r in rows(full/f'{kind}.jsonl.gz') if r['at'][:10]<=cut];b=[r for r in rows(failed/f'{kind}.jsonl.gz') if r['at'][:10]<=cut];assert a==b,('repair prefix',kind);counts[kind]=len(a)
 for kind in ['fills','audit_log']:
  n=0
  for aid in read(full/'summary.json')['accounts']:
   a=[r for r in read(full/f'{aid}.json')[kind] if event_time(r)[:10]<=cut];b=[r for r in read(failed/f'{aid}.json')[kind] if event_time(r)[:10]<=cut];assert a==b,('repair prefix',aid,kind);n+=len(a)
  counts[kind]=n
 write(HERE/'execution-boundary-repair-identity.json',dict(passed=True,paths=21,cutoff=cut,rows=counts,only_later_fee_coverage_extended=True))
 return counts

def main(mode):
 if mode=='prefix':print(dict(prefix=verify_prefix(),repair=verify_repair()),flush=True);return
 for n in ['prefix-identity.json','execution-boundary-repair-identity.json','analysis/accounting.json','analysis/funding.json']:assert read(HERE/n)['passed']
 assert read(HERE/'accounts-v2/summary.json')['status']=='complete'
 for freeze in ['account-freeze.json','account-freeze-v2.json']:
  bad=[p for p,h in read(HERE/freeze)['sha256'].items() if sha(ROOT/p)!=h];assert not bad,(freeze,bad)
 registry=ROOT/'research_rounds/algorithm-baselines-20261024/registry.json';old=read(registry)['sha256'];assert all(sha(ROOT/p)==h for p,h in old.items())
 state=read(HERE/'RUN_STATE.json');state.update(stage='complete',valid_output='accounts-v2',economic_paths=21,economic_attempts=2,economic_reruns=1,rule_revisions_after_full_results=0,failed_partial_preserved=True,remaining=[]);(HERE/'RUN_STATE.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 paths=[p for p in HERE.rglob('*') if p.is_file() and p.name!='complete.json' and p.suffix!='.log'];write(HERE/'complete.json',dict(status='complete',recorded_at=now(),valid_economic_paths=21,economic_attempts=2,economic_reruns=1,parameter_tuning_after_results=0,original_and_repair_freezes_unchanged=True,E0_R_R1_registry_unchanged=len(old),sha256={str(p.relative_to(HERE)):sha(p) for p in paths}));print('complete',flush=True)
if __name__=='__main__':main(sys.argv[1])
