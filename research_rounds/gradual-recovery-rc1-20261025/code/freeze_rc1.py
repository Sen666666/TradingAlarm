from common_rc1 import *
def main():
 assert read(HERE/'technical/checks.json')['passed'];paths=[HERE/'PROTOCOL.md',HERE/'technical/checks.json',HERE/'inputs/manifest.json',M1/'complete.json',SRC/'complete.json',B5/'complete.json',G1/'complete.json',ROOT/'research_rounds/algorithm-baselines-20261024/registry.json']+list((HERE/'code').glob('*.py'))+list((HERE/'inputs').rglob('*.parquet'))
 for p in [G1/'code/grade.py',G1/'code/policies_g1.py',M1/'code/model_m1.py',B5/'code/api.py',B5/'code/evidence.py',B5/'code/policy.py']:paths.append(p)
 write(HERE/'freeze.json',dict(recorded_at=now(),formal_candidates=1,parameter_sets=1,old_algorithms_changed=0,accounts=0,history='seen_development',sha256={str(p.relative_to(ROOT)):sha(p) for p in paths}));print(dict(frozen=len(paths)),flush=True)
if __name__=='__main__':main()
