"""Independent saved-output witness checks; does not invoke or import the candidate model."""
from pathlib import Path
import hashlib,json,math
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'results/v0'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    fr=json.loads((HERE/'input-freeze.json').read_text());freeze=json.loads((HERE/'freeze.json').read_text());checks=[]
    for name,h in freeze['files'].items():assert sha(HERE/name)==h,name
    old=ROOT/'research_rounds/pv-participation-response-20261020/code'
    for name,h in fr['baseline_code'].items():assert sha(old/name)==h,name
    tp=ROOT/'research_rounds/temperature-prototype-20261023'
    protocol=json.loads((tp/'protocol.json').read_text());assert sha(tp/'temperature.py')==protocol['code_sha256']
    for rec in fr['series']:
        sid=rec['symbol'];p=HERE/'inputs'/(sid+'.parquet');assert sha(p)==rec['input_sha256']
        bars=pd.read_parquet(p);d=pd.read_parquet(OUT/'daily'/(sid+'.parquet'))
        pd.testing.assert_frame_equal(bars,d[bars.columns],check_exact=True)
        entry=0;danger=0;eligible=0
        for seg,z in bars.groupby('segment_id',sort=False):
            saved=d.loc[z.index];cp=z.close.to_numpy(float);vp=z.volume.to_numpy(float)
            # Raw-array witnesses independently compute trailing statistics for every opening and fast danger exit.
            for k in np.flatnonzero((saved.new_entered.eq(1)|saved.exit_kind.eq('放量急跌')).to_numpy()):
                row=saved.iloc[k];q=vp[k]/float(np.median(vp[k-21:k]))
                rr=np.log(cp[k-63:k]/cp[k-64:k-1]);sigma=math.sqrt(float(np.mean(rr*rr)))
                assert math.isclose(row.q,q,rel_tol=1e-12)
                assert math.isclose(row.sigma,sigma,rel_tol=1e-11,abs_tol=1e-13)
                if row.new_entered:
                    assert row.accepted==1
                    assert row.anchor==cp[k]
                    assert row.anchor_sigma==row.sigma
                    # No special dates and no waiting for the long background to turn up if 63-close high has broken.
                    ma=float(np.mean(cp[k-62:k+1]));oldma=float(np.mean(cp[k-82:k-19]))
                    down=(cp[k]<cp[k-63] and ma<oldma)
                    assert not down or cp[k]>float(np.max(cp[k-63:k]))
                    assert not row.new_exited;entry+=1
                    eligible+=int(not down)
                if row.exit_kind=='放量急跌':
                    dz=math.log(cp[k]/cp[k-1])/sigma
                    assert dz<=-2 and q>=2
                    assert saved.new_target.iloc[k-1]==1 and row.new_target==0
                    assert row.memory==1 and row.memory_reclaim==cp[k-1] and row.memory_low==z.low.iloc[k]
                    danger+=1
            changes=saved.new_target.diff().fillna(saved.new_target.iloc[0])
            assert np.array_equal(changes.to_numpy(),(saved.new_entered-saved.new_exited).to_numpy())
            for dt in saved.index[saved.new_exited.eq(1)]:
                row=saved.loc[dt];k=z.index.get_loc(dt)
                assert row.exit_kind in ['放量急跌','结构破坏','持续转弱']
                if row.exit_kind=='结构破坏':assert cp[k]<=saved.new_floor.iloc[k-1]
                if row.exit_kind=='持续转弱':
                    for j in range(k-2,k+1):assert cp[j]<np.mean(cp[j-19:j+1]) and cp[j]<=cp[j-20]
        checks.append(dict(symbol=sid,input_rows=len(d),entries_checked=entry,entry_not_down=eligible,danger_witnesses=danger))
    s=pd.read_csv(OUT/'series-summary.csv');primary=s[s.primary]
    total={m:{k:int(primary[m+'_'+k].sum()) for k in ['starts','days','ends10','down_starts']} for m in ['original','temperature','new','price','no_background','no_danger']}
    a=json.loads((OUT/'checks.json').read_text());cf=a['single_day_volume']
    result=dict(status='passed',checks=checks,old_algorithm_files_unchanged=True,freeze_hashes_match=True,
        prefixes_verified_by_replay=len(a['prefixes']),single_day_volume_counterfactuals=len(cf),
        single_day_target_changes=sum(r['actual_target']!=r['reduced_volume_target'] for r in cf),
        single_day_exit_cause_changes=sum(r['actual_exit']!=r['reduced_volume_exit'] for r in cf),
        primary_totals=total,account_runs=0,caveat='Checks establish implementation/causality, not forecasting or economic superiority.')
    p=OUT/'independent-audit.json'
    with p.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
if __name__=='__main__':main()
