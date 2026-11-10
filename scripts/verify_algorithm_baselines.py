"""Read-only validation of canonical E0/R/R1 aliases and pinned source identity.

No signal calculation, account, quote request, registry update or auto-repair.
"""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'research_rounds/algorithm-baselines-20261024/registry.json'

def main():
    d=json.loads(REGISTRY.read_text())
    assert set(d['algorithms'])=={'E0','R','R1'}
    failures=[]
    for name,expected in d['sha256'].items():
        p=ROOT/name
        if not p.is_file():failures.append({'path':name,'reason':'missing'})
        elif hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            failures.append({'path':name,'reason':'hash_mismatch'})
    engine=ROOT/'research_rounds/r1-structural-reentry-20261024/engine.py'
    original=ROOT/'research_rounds/strategy-switching-20261024/engine.py'
    if engine.read_bytes()!=original.read_bytes():
        failures.append({'reason':'reference_execution_engines_differ'})
    result={'passed':not failures,'registry':str(REGISTRY),'aliases':list(d['algorithms']),
            'pinned_files_checked':len(d['sha256']),'failures':failures,
            'signals_run':0,'accounts_run':0,'network_requests':0}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
