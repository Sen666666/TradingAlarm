from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import sys
import numpy as np

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
B5 = ROOT / 'research_rounds/pv-strength-b5-20261025'
OLD = ROOT / 'research_rounds/strategy-switching-20261024'
SCENARIOS = {'base':dict(cost=1,delay=1),'cost2':dict(cost=2,delay=1),'delay1':dict(cost=1,delay=2)}
POLICIES = ['E0','G1_I','G1_X','G1_IX']

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

def clean(x):
    if isinstance(x, dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [clean(v) for v in x]
    if isinstance(x,(bool,np.bool_)): return bool(x)
    if isinstance(x,(int,np.integer)): return int(x)
    if isinstance(x,(float,np.floating)): return float(x) if math.isfinite(float(x)) else None
    if isinstance(x,(Path,datetime)): return str(x)
    return x

def read(p): return json.loads(Path(p).read_text())

def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f: json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')

def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def b5():
    sys.path.insert(0,str(B5/'code'))
    return module('_g1_frozen_b5_api',B5/'code/api.py')

def engine():
    return module('_g1_frozen_temperature_engine',ROOT/'research_rounds/temperature-regime-comparison-20261025/code/engine.py')

def verify_hashes(mapping):
    failures=[str(p) for p,h in mapping.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    if failures: raise AssertionError(f'Hash mismatch: {failures}')
    return len(mapping)

def old_hashes():
    result={}
    for file,key in [
        ('research_rounds/algorithm-baselines-20261024/registry.json','sha256'),
        ('research_rounds/pv-strength-b4-20261025/complete.json','sha256'),
        ('research_rounds/pv-strength-b5-20261025/complete.json','sha256'),
        ('research_rounds/strategy-switching-20261024/freeze.json','sha256')]:
        mapping=read(ROOT/file)[key]
        if 'strategy-switching' in file:
            mapping={str((OLD/p).resolve().relative_to(ROOT)):h for p,h in mapping.items()}
        result.update(mapping)
    # Entire saved previous economic results, not only production sources.
    for p in (OLD/'results/v0').rglob('*'):
        if p.is_file(): result[str(p.relative_to(ROOT))]=sha(p)
    return result
