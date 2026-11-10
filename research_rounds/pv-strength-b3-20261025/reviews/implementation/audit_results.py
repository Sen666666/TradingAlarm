"""Run only after parent confirms frozen formal and real outputs are available."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import hashlib
import importlib.util
import json
import math
import numpy as np
import pandas as pd
from reference import reference,NUMERIC

HERE=Path(__file__).resolve().parent
ROUND=HERE.parents[1]
REPO=ROUND.parents[1]
OLD=REPO/'research_rounds/pv-strength-20261025'
B2=REPO/'research_rounds/pv-strength-three-axis-20261025'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
DISCRETE=['local','background','normal_grade','grade','freeze_active','freeze_created',
          'freeze_released','freeze_count','freeze_id','freeze_age','rapid_up']

def same_json(a,b):
    if isinstance(a,dict):return isinstance(b,dict) and a.keys()==b.keys() and all(same_json(a[k],b[k]) for k in a)
    if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(same_json(x,y) for x,y in zip(a,b))
    if isinstance(a,(float,int)) and not isinstance(a,bool):return isinstance(b,(float,int)) and math.isclose(a,b,rel_tol=0,abs_tol=1e-9)
    return a==b

def comparison(actual,expected):
    na=actual[NUMERIC].isna().equals(expected[NUMERIC].isna())
    errors=(actual[NUMERIC]-expected[NUMERIC]).abs()
    failed=[c for c in NUMERIC if not np.allclose(actual[c],expected[c],rtol=0,atol=1e-9,equal_nan=True)]
    exact=all(actual[c].equals(expected[c]) for c in DISCRETE)
    phase=actual.phase.equals(expected.phase)
    return dict(rows=len(actual),numeric_fields=len(NUMERIC),unknown_masks_exact=na,
                discrete_fields_exact=exact,phase_exact=phase,failed_columns=failed,
                maximum_absolute_error=float(errors.max().max()),passed=na and exact and phase and not failed)

def identity(mapping,base):
    return [dict(path=k,expected=v,actual=sha(base/k),passed=sha(base/k)==v) for k,v in mapping.items()]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real-output-notified',action='store_true');args=parser.parse_args()
    if not args.real_output_notified:raise SystemExit('Parent notification required before real output computation')
    if (HERE/'audit.json').exists():raise SystemExit('Refuse to overwrite audit.json')
    frozen=read(ROUND/'freeze.json');formal=read(ROUND/'validation/checks.json');summary=read(ROUND/'results/summary.json')
    assert formal.get('technical_passed',formal.get('passed',False))
    frozen_check=identity(frozen['sha256'],REPO);old_check=identity(frozen['old_files'],REPO)
    independent_before=identity(read(HERE/'old_identity_before.json')['files'],REPO)
    registered=identity(read(REPO/'research_rounds/algorithm-baselines-20261024/registry.json')['sha256'],REPO)
    assert all(x['passed'] for group in [frozen_check,old_check,independent_before,registered] for x in group)
    spec=importlib.util.spec_from_file_location('frozen_b3_audit',ROUND/'code/model.py')
    core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    assets=[];prefixes=[]
    for item in summary['assets']:
        sid=item['asset'];src=OLD/'inputs'/(sid+'.parquet');dst=ROUND/'results'/(sid+'.parquet')
        f=pd.read_parquet(src);actual=pd.read_parquet(dst);expected,journal=reference(f)
        record=comparison(actual,expected);record.update(asset=sid,input_sha256=sha(src),result_sha256=sha(dst),
             index_exact=actual.index.equals(f.index),source_columns_exact=all(actual[c].equals(f[c]) for c in f.columns))
        full_journal=read(ROUND/'results'/(sid+'-events.json'))
        record['independent_journal_matches']=same_json(full_journal,journal)
        price,_=reference(f,joint=False)
        record['price_ablation_exact']=actual.price_grade.equals(price.grade) and actual.price_freeze_created.equals(price.freeze_created)
        old=pd.read_parquet(OLD/'results'/(sid+'.parquet'));b2=pd.read_parquet(B2/'results'/(sid+'.parquet'))
        old_columns={'strength':'b1_strength',**{c:c for c in ['e0_ready','e0_target','e0_entered','e0_exited','e0_floor']}}
        record['old_B1_E0_exact']=all(old[k].equals(actual[v]) for k,v in old_columns.items())
        record['old_B2_exact']=all(b2[c].equals(actual['b2_'+c]) for c in ['pace_5','pace_21','signed_retention'])
        record['passed'] &= all(record[k] for k in ['index_exact','source_columns_exact','independent_journal_matches','price_ablation_exact','old_B1_E0_exact','old_B2_exact'])
        assets.append(record)
        for cut in ['2025-08-29','2026-06-30']:
            path=HERE/(sid+'-physical-prefix-'+cut+'.parquet')
            if path.exists():raise RuntimeError('Refuse to overwrite '+str(path))
            f.loc[:cut].to_parquet(path);physical=pd.read_parquet(path);short,events=core.strength_frame(physical)
            exact=short.equals(actual.loc[physical.index,short.columns])
            journal_exact=events==[e for e in full_journal if e['date']<=str(physical.index[-1].date())]
            prefixes.append(dict(asset=sid,cut=cut,rows=len(physical),last_date=str(physical.index[-1].date()),
                file_sha256=sha(path),all_28_columns_exact=exact,journal_exact=journal_exact,passed=exact and journal_exact))
    result=dict(recorded_at=datetime.now(timezone.utc).isoformat(),scope='independent implementation and causality; no semantic or economic promotion',
         accounts=0,network_requests=0,model_sha256=sha(ROUND/'code/model.py'),reference_sha256=sha(HERE/'reference.py'),
         runner_sha256=sha(Path(__file__)),frozen_identity=frozen_check,old_files_identity=old_check,
         independent_before_identity=independent_before,registered_baselines=registered,assets=assets,physical_prefixes=prefixes,
         passed=all(x['passed'] for group in [assets,prefixes,frozen_check,old_check,independent_before,registered] for x in group))
    with (HERE/'audit.json').open('x') as stream:json.dump(result,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n')
    print(json.dumps({'passed':result['passed'],'assets':assets,'prefixes':len(prefixes)},ensure_ascii=False,indent=2))
    assert result['passed']

if __name__=='__main__':main()
