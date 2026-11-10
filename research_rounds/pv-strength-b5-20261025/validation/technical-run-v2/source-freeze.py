"""Freeze one implementation before formal compatibility runs; never overwrite."""
from common import HERE, REPO, read, write, sha, now, old_identity
import platform
import numpy as np
import pandas as pd

def main():
    identity = old_identity()
    assert identity['passed'], identity
    inputs = read(HERE / 'inputs/manifest.json')
    for row in inputs['series']:
        assert sha(HERE / row['file']) == row['sha256']
        for path, expected in row['source_files'].items():
            assert sha(REPO / path) == expected
    paths = [HERE / 'SCOPE.md', HERE / 'PROTOCOL.md']
    paths += sorted((HERE / 'code').glob('*.py'))
    paths += sorted((HERE / 'inputs').glob('*'))
    paths += [p for p in sorted((HERE / 'validation').rglob('*'))
              if p.is_file() and ('fixture' in str(p) or 'protocol-addendum' in p.name)]
    required = ['arithmetic.py', 'evidence.py', 'policy.py', 'api.py', 'test_contract.py', 'verify_real.py']
    assert all((HERE / 'code' / p).exists() for p in required)
    write(HERE / 'freeze.json', dict(
        recorded_at=now(), status='frozen_before_formal_compatibility_runs',
        model='PVS-B5', purpose='E0 evidence and participation separation, unchanged B4 strength',
        account_runs=0, network_requests=0, formal_designs=1,
        strength_formula_changes=0, enhancement_policy_implemented=False,
        sha256={str(p.relative_to(REPO)): sha(p) for p in paths},
        old_identity=identity, real_series=len(inputs['series']),
        real_rows=sum(x['rows'] for x in inputs['series']),
        runtime=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__)))
    print({'frozen_files': len(paths), 'real_series': len(inputs['series'])}, flush=True)

if __name__ == '__main__':
    main()
