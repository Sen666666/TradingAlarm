"""Finish evidence export after strict-JSON serialization failure. No refitting."""
from pathlib import Path
import json,datetime,hashlib
import numpy as np,pandas as pd
from calibrate import make_features,FEATURES
HERE=Path(__file__).resolve().parent;PRIOR=HERE.parent/'gold-chart-fit-20261024';OUT=HERE/'results/v0'
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    return x
def dump(p,x):p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
def main():
    d=pd.read_csv(PRIOR/'data/sina-AU0.csv',index_col='date',parse_dates=True);points=json.loads((HERE/'refined-targets.json').read_text())['points'];f=make_features(d,points)
    saved=pd.read_parquet(OUT/'all-features.parquet');pd.testing.assert_frame_equal(f,saved[f.columns],check_freq=False)
    checks=[]
    for date in ['2025-04-16','2025-09-01','2025-10-22','2026-01-21','2026-08-10','2026-10-23']:
        ff=make_features(d.loc[:date],points);pd.testing.assert_frame_equal(ff,f.loc[:date],check_freq=False);checks.append(dict(cutoff=date,rows=len(ff),passed=True))
    scores=pd.read_csv(OUT/'conditional-scores.csv');omitted=pd.read_csv(OUT/'omitted-episode-summary.csv');context=pd.read_csv(OUT/'start-context.csv')
    labels=pd.read_csv(HERE/'measured-daily.csv',index_col='date',parse_dates=True);training=labels.join(f).loc[lambda x:x.known.eq(1)&x.level.gt(0)&x.pair.notna()]
    # Quantities visible at the estimated ends. These are descriptive hypotheses,
    # not additional fitted exits. All nearby dates remain inspectable.
    r=np.log(d.close/d.close.shift());clv=(d.close-d.low)/(d.high-d.low);tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
    ends=[];nearby=[]
    for p in points:
        if p['kind']!='end':continue
        n=d.index.get_loc(p['date'])
        for i in range(max(0,n-3),min(len(d),n+4)):
            date=d.index[i];z=f.loc[date]
            row=dict(source_end=p['date'],source_id=p['id'],date=str(date.date()),offset_observations=i-n,close=d.close.iloc[i],return_pct=np.expm1(r.iloc[i])*100,daily_change_z=r.iloc[i]/z.sigma,relative_volume=z.q,true_range_pct=tr.iloc[i]/d.close.iloc[i-1]*100,clv=clv.iloc[i],z20=z.z20,z63=z.z63,above_ma20=d.close.iloc[i]>z.ma20,above_ma63=d.close.iloc[i]>z.ma63,unreclaimed_adverse=z.unreclaimed_adverse)
            nearby.append(row)
            if not i-n:ends.append(row)
    pd.DataFrame(nearby).to_csv(OUT/'exit-neighborhoods.csv',index=False);pd.DataFrame(ends).to_csv(OUT/'exit-context.csv',index=False)
    volume_conflicts=pd.read_csv(OUT/'volume-veto-contradictions.csv')
    done=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),conditional_color_observations=len(training),confident_grade_counts=training.level.value_counts().sort_index().to_dict(),features=FEATURES,all_calibration=scores.loc[scores.split.eq('all_visible_colors')].to_dict('records'),omitted_episode=omitted.to_dict('records'),start_context=context.to_dict('records'),exit_context=ends,volume_veto_conflicts=len(volume_conflicts),prefix_checks=checks,accounts=0,original_code_changes=0,post_run_hypothesis_changes=0,
      repairs=['First conditional prefix harness skipped future start incorrectly and dropped current bar before future end; archived and corrected, full-sample features exactly unchanged.','Second run completed calculations and prefix checks but strict JSON export rejected NaN held-out-pair placeholder. Finalize exports nulls from saved scores, no refit.'],
      caveat='Colors are explained only after screenshot source starts supplied. No independent start/exit prediction, no avoided-August claim, no proprietary formula recovery. All folds within viewed image are development sensitivity.')
    dump(OUT/'complete.json',done);dump(OUT/'finalization.json',dict(at=done['at'],calibration_runs=2,distinct_explanatory_hypotheses=8,first_run_results_unchanged=True,second_run_export_failure='NaN in unused held_out_pair field on full-fit rows',finalizer_refits=0,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    print('completed',len(training),'conditional hot-color observations;',len(checks),'prefix checks; no refit')
    print(pd.DataFrame(ends)[['source_end','return_pct','daily_change_z','relative_volume','z20','z63','above_ma20']].to_string(index=False))
if __name__=='__main__':main()
