"""Post-freeze independent implementation/identity audit. No accounts/network.

Run only after the root confirms formal checks and real outputs are complete.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from reference import reference_frame

HERE=Path(__file__).resolve().parent
ROUND=HERE.parents[1]
WORK=ROUND.parents[1]
OLD=WORK/'research_rounds/pv-strength-20261025'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())

def compare(a,b,tolerance=2e-9):
    av,bv=a.to_numpy(float),b.to_numpy(float)
    masks=np.array_equal(np.isnan(av),np.isnan(bv))
    errors=np.abs(av-bv)
    worst=float(np.nanmax(errors)) if np.isfinite(errors).any() else 0.
    failures={}
    for c in a:
        x,y=a[c].to_numpy(float),b[c].to_numpy(float)
        if not np.allclose(x,y,rtol=tolerance,atol=tolerance,equal_nan=True):
            q=np.abs(x-y)
            failures[c]=dict(max_abs=float(np.nanmax(q)) if np.isfinite(q).any() else None,
                             unknown_mask_equal=bool(np.array_equal(np.isnan(x),np.isnan(y))))
    return dict(passed=masks and not failures,unknown_masks_identical=bool(masks),
                max_abs_error=worst,failed_columns=failures,rows=len(a),columns=len(a.columns))

def main():
    freeze=read(ROUND/'freeze-v1.json')
    formal=read(ROUND/'validation-v1/checks.json')
    summary=read(ROUND/'results/summary.json')
    assert formal['technical_passed'] and formal['real_B2_outputs_have_not_been_generated']
    frozen=[dict(path=p,expected=old,actual=sha(WORK/p),passed=sha(WORK/p)==old)
            for p,old in freeze['sha256'].items()]
    v0=read(ROUND/'freeze.json')
    preserved_v0=[dict(path=p,expected=old,actual=sha(WORK/p),passed=sha(WORK/p)==old)
                  for p,old in v0['sha256'].items()]
    old_all=[dict(path=p,expected=old,actual=sha(OLD/p),passed=sha(OLD/p)==old)
             for p,old in freeze['old_b1_files'].items()]
    spec=importlib.util.spec_from_file_location('frozen_core_audit',ROUND/'code-v1/model.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    fields=m.FIELDS+[c+'_price' for c in ['origin','extreme','support','checkpoint','old_support']]
    assets=[];prefixes=[]
    for record in summary['assets']:
        sid=record['asset']
        f=pd.read_parquet(OLD/'inputs'/(sid+'.parquet'))
        actual=pd.read_parquet(ROUND/'results'/(sid+'.parquet'))
        expected=reference_frame(f).reindex(columns=fields)
        report=compare(actual[fields],expected)
        report.update(asset=sid,input_sha256=sha(OLD/'inputs'/(sid+'.parquet')),
                      result_sha256=sha(ROUND/'results'/(sid+'.parquet')),
                      index_identical=bool(actual.index.equals(f.index)))
        # Old B1 and E0 columns remain copied from the preserved files.
        old=pd.read_parquet(OLD/'results'/(sid+'.parquet'))
        mapcols={'strength':'b1_strength','price_only_strength':'b1_price_only',
                 **{q:q for q in ['e0_ready','e0_target','e0_entered','e0_exited','e0_floor']}}
        report['old_B1_E0_columns_exact']=all(old[c].equals(actual[d]) for c,d in mapcols.items())
        report['source_input_columns_exact']=all(f[c].equals(actual[c]) for c in f)
        report['passed'] &= report['index_identical'] and report['old_B1_E0_columns_exact'] and report['source_input_columns_exact']
        assets.append(report)
        full_j=read(ROUND/'results'/(sid+'-events.json'))
        for cutdate in ('2025-08-29','2026-06-30'):
            fshort=f.loc[:cutdate]
            if not len(fshort):continue
            path=HERE/(sid+'-physical-prefix-'+cutdate+'.parquet')
            fshort.to_parquet(path)
            physical=pd.read_parquet(path)
            short,j=m.three_axis_frame(physical)
            matched=short.equals(actual.loc[physical.index,fields])
            jmatch=j==[q for q in full_j if q['date']<=str(physical.index[-1].date())]
            prefixes.append(dict(asset=sid,cut=cutdate,last_observation=str(physical.index[-1].date()),
                                 rows=len(physical),input_sha256=sha(path),
                                 all_49_fields_exact=matched,journal_exact=jmatch,
                                 passed=matched and jmatch))
    before=read(HERE/'old_identity_before.json')
    old=[dict(path=p,expected=old,actual=sha(WORK/p),passed=old==sha(WORK/p))
         for p,old in before['files'].items()]
    reg=read(WORK/'research_rounds/algorithm-baselines-20261024/registry.json')
    registered=[dict(path=p,expected=old,actual=sha(WORK/p),passed=old==sha(WORK/p))
                for p,old in reg['sha256'].items()]
    # Source contracts are about lifecycle correctness, without changing model thresholds.
    seed=f.iloc[:100].copy()
    rejections=[]
    for kind in ['duplicate_date','descending_date','missing_segment','recurring_segment',
                 'valid_zero_close','valid_nan_close','valid_zero_volume','valid_nan_volume']:
        bad=seed.copy()
        if kind=='duplicate_date':
            ii=list(bad.index);ii[1]=ii[0];bad.index=pd.DatetimeIndex(ii)
        elif kind=='descending_date':bad=bad.iloc[::-1]
        elif kind=='missing_segment':bad.iloc[0,bad.columns.get_loc('segment_id')]=np.nan
        elif kind=='recurring_segment':bad['segment_id']=['a']*30+['b']*30+['a']*40
        else:
            col='close' if 'close' in kind else 'volume'
            bad.iloc[0,bad.columns.get_loc(col)]=np.nan if 'nan' in kind else 0.
            bad.iloc[0,bad.columns.get_loc('valid_strength_observation')]=True
        try:m.three_axis_frame(bad);rejected=False
        except ValueError:rejected=True
        rejections.append(dict(contract=kind,passed=rejected))
    result=dict(recorded_at=datetime.now(timezone.utc).isoformat(),
                scope='Independent implementation and identity only; not semantic or economic admission.',
                accounts_run=0,network_requests=0,
                frozen_identity=frozen,preserved_v0_frozen_identity=preserved_v0,
                old_B1_all_frozen_files=old_all,assets=assets,real_physical_prefixes=prefixes,
                source_contract_rejections=rejections,
                old_B1_registered_identity=old,registered_baselines=registered,
                reference_sha256=sha(HERE/'reference.py'),core_sha256=sha(ROUND/'code-v1/model.py'),
                passed=all(q['passed'] for group in [frozen,preserved_v0,old_all,assets,prefixes,old,registered,rejections] for q in group))
    (HERE/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in
                      ['frozen_identity','preserved_v0_frozen_identity','old_B1_all_frozen_files',
                       'old_B1_registered_identity','registered_baselines']},ensure_ascii=False,indent=2))
    assert result['passed']

if __name__=='__main__':main()
