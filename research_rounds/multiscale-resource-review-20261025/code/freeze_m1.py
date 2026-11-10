from common_m1 import *
def main():
 paths=[HERE/'PROTOCOL.md']+list((HERE/'code').glob('*.py'))
 paths += [GAP/'complete.json',GAP/'cohort-v1/all-event-labels.parquet',SRC/'complete.json',SRC/'accounts/IX__S0_base.json',SRC/'accounts/decisions.jsonl.gz',SRC/'accounts/daily.jsonl.gz',OLD/'h1/matrix.npz',OLD/'inputs-v2/metadata.json',OLD/'inputs-v2/market-rules.json',OLD/'inputs-v2/input-manifest.json']
 paths+=list((SRC/'signals').glob('*.parquet'))
 paths+=list((ROOT/'research_rounds/pv-strength-b5-20261025/inputs').glob('*.parquet'))
 for sid in list(NAMES)[:7]:paths+=list((ROOT/'research_rounds/pv-strength-b5-20261025/results-v2'/sid).glob('*.parquet'))
 paths+=[HERE/'technical-v4/synthetic-checks.json']
 for p in [ROOT/'research_rounds/pv-strength-b4-20261025/complete.json',ROOT/'research_rounds/pv-strength-b5-20261025/complete.json',ROOT/'research_rounds/b5-g1-20261025/complete.json',ROOT/'research_rounds/algorithm-baselines-20261024/registry.json']:paths.append(p)
 write(HERE/'freeze-v2.json',dict(recorded_at=now(),candidate='B5-M1 descriptor only',new_accounts=0,history='seen historical development',repair='Explicit nullable Boolean acute flag makes prefix dtype identical when later invalid rows exist; numerical values/formulas unchanged from v1',sha256={str(p.relative_to(ROOT)):sha(p) for p in paths}))
 print(dict(frozen=len(paths)),flush=True)
if __name__=='__main__':main()
