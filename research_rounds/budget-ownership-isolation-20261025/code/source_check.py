from budget_common import *
from run_budget import context,checked_ref

def main():
 own=read(HERE/'freeze.json');old=read(PREV/'complete.json');registry=read(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json');groups={}
 for label,refs in [('experiment_frozen',own['sha256']),('previous_round_artifacts',old['artifacts']),('registered_E0_R_R1',registry['sha256'])]:
  for path,digest in refs.items():assert sha(ROOT/path)==digest,(label,path)
  groups[label]=len(refs)
 assert sha(OLD/'code/sector_account.py')==own['old_finance_sha256']
 b,m=context();sources={};records={r['series_id']:r for r in read(OLD/'prepared-v2/manifest.json')['series']}
 for sid,item in b.series.items():
  p=checked_ref(records[sid]['files']['states'],OLD/'prepared-v2');sources[str(p.relative_to(ROOT))]=sha(p)
  if sid in m.lines:
   for p in [checked_ref(item.record['raw'],b.manifest_path.parent),IX/'signals'/f'{sid}.parquet']:sources[str(p.relative_to(ROOT))]=sha(p)
 for p in [OLD/'h1/matrix.npz',OLD/'inputs-v2/input-manifest.json',OLD/'inputs-v2/metadata.json',OLD/'inputs-v2/market-rules.json',OLD/'inputs-v2/economic-protocol.json']:sources[str(p.relative_to(ROOT))]=sha(p)
 write(HERE/'source-identity.json',dict(passed=True,verified_groups=groups,old_finance_unchanged=True,original_references_checked=True,input_hash_recorded_after_analysis=True,inputs=sources,recorded_at=now()))
 print(dict(passed=True,groups=groups,input_files=len(sources)))
if __name__=='__main__':main()
