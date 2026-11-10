"""Source/cache comparison only; never selects the new universe or overwrites it."""
from pathlib import Path
import json,hashlib
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'pvr_information_v1/export/features.parquet'
DUAL=ROOT.parent/'pvr_dual_memory_v1/features/DUAL_MEMORY_FEATURES.parquet'
NEW=ROOT/'features/LOCAL_FIXED_DATE_FEATURES.parquet'
KEY=['sid','day'];FIELDS=['r','scale','amount_ref','u','b','e','E','score']
TOL=1e-8

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=ROOT/'cache_comparison';out.mkdir(exist_ok=False)
    x=pd.read_parquet(NEW);dates=sorted(x.day.unique())
    old=pd.read_parquet(SOURCE,columns=KEY+FIELDS+['pvr_status'],filters=[('day','in',dates)])
    assert len(old)==1709*7 and not old.duplicated(KEY).any()
    j=x.merge(old,on=KEY,how='inner',suffixes=('_new','_old'),validate='one_to_one');assert len(j)==1681*7
    records=[]
    for day,g in j.groupby('day'):
        both=np.isfinite(g.score_new)&np.isfinite(g.score_old)
        z=dict(day=day,exact_symbol_overlap_rows=len(g),both_PVR_known=int(both.sum()),new_known_old_unknown=int((np.isfinite(g.score_new)&~np.isfinite(g.score_old)).sum()),old_known_new_unknown=int((~np.isfinite(g.score_new)&np.isfinite(g.score_old)).sum()),neither_known=int((~np.isfinite(g.score_new)&~np.isfinite(g.score_old)).sum()))
        for col in FIELDS:
            a=g.loc[both,col+'_new'].to_numpy(float);b=g.loc[both,col+'_old'].to_numpy(float)
            delta=np.abs(a-b);z[col+'_max_abs_difference']=float(delta.max())if len(delta)else None
            if col!='amount_ref':z[col+'_within_1e8']=int(np.isclose(a,b,atol=TOL,rtol=0).sum())
            else:z['amount_ref_new_old_median_ratio']=float(np.median(a/b))
        records.append(z)
    # Raw amount_ref is unit dependent. The normalized b/e comparison is the
    # correct diagnostic; never demand reference amounts have the same units.
    j['score_abs_difference']=(j.score_new-j.score_old).abs()
    j.to_csv(out/'ALL_EXACT_OLD_SYMBOL_DATE_COMPARISONS.csv',index=False)
    pd.DataFrame(records).to_csv(out/'PVR_CACHE_COMPARISON_BY_DATE.csv',index=False)
    od=pd.read_parquet(DUAL,columns=KEY+['E_fast','E_slow'])
    d=x[KEY+['E_fast','E_slow']].merge(od,on=KEY,how='inner',validate='one_to_one',suffixes=('_new','_old'))
    ds=[]
    for day,g in d.groupby('day'):
        row=dict(day=day,old_pending_derived_overlap_only=len(g))
        for col in ['E_fast','E_slow']:
            valid=np.isfinite(g[col+'_new'])&np.isfinite(g[col+'_old'])
            v=(g.loc[valid,col+'_new']-g.loc[valid,col+'_old']).abs()
            row[col+'_both_known']=int(valid.sum());row[col+'_max_abs_difference']=float(v.max())if len(v)else None;row[col+'_within_1e8']=int(v.le(TOL).sum())
        ds.append(row)
    d.to_csv(out/'OLD_PENDING_DUAL_CACHE_COMPARISONS_DIAGNOSTIC_ONLY.csv',index=False)
    pd.DataFrame(ds).to_csv(out/'DUAL_CACHE_COMPARISON_BY_DATE.csv',index=False)
    receipt=dict(status='COMPLETE_SOURCE_AWARE_CACHE_DIAGNOSIS_NOT_UNIVERSE_GATE',tolerance=1e-8,tolerance_purpose='Report numerical closeness, not a tradability/return/ranking threshold',old_score_source='All1709 pure existing feature-grid, not old account candidates',old_dual_source='Only existing old pending-derived raw-dual feature rows; diagnostic overlaps only, never new eligibility',new_values_not_replaced=True,forward_labels_loaded=False,new_accounts=0,sources={str(p.resolve()):sha(p)for p in[Path(__file__),SOURCE,DUAL,NEW]},outputs={p.name:sha(p)for p in out.iterdir()if p.is_file()})
    with(out/'COMPLETION.json').open('x')as f:json.dump(receipt,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(pd.DataFrame(records)[['day','both_PVR_known','score_max_abs_difference','score_within_1e8','e_max_abs_difference','e_within_1e8','amount_ref_new_old_median_ratio']].to_string(index=False))
    print(pd.DataFrame(ds).to_string(index=False))

if __name__=='__main__':main()
