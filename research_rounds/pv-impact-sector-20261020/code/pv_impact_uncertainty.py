"""Post-result uncertainty and balance diagnostic; does not change trading/model rules."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd

def main(out):
    pairs=pd.read_csv(out/'matched-pairs.csv');rows=[];rng=np.random.default_rng(20261020)
    for (g,p),f in pairs.groupby(['group','period']):
        names=sorted(f.symbol.unique());samples=[]
        by={s:f.loc[f.symbol.eq(s),'forward_difference'].to_numpy() for s in names}
        for _ in range(2000):samples.append(np.concatenate([by[s] for s in rng.choice(names,len(names),replace=True)]).mean())
        gap=(pd.to_datetime(f.high_date)-pd.to_datetime(f.low_date)).abs().dt.days
        near=f[gap<=126]
        rows.append(dict(group=g,period=p,n=len(f),assets=len(names),mean=float(f.forward_difference.mean()),median=float(f.forward_difference.median()),positive_fraction=float(f.forward_difference.gt(0).mean()),asset_cluster_bootstrap95=[float(x) for x in np.quantile(samples,[.025,.975])],median_pair_date_gap_days=float(gap.median()),within126_days_n=len(near),within126_days_mean=float(near.forward_difference.mean()) if len(near) else None,without_largest_positive_pair=float(f.forward_difference.drop(f.forward_difference.idxmax()).mean()) if len(f)>1 else None))
    (out/'uncertainty.json').write_text(json.dumps({'status':'post-result diagnostic, no threshold adoption; bootstrap small selected asset clusters is not proof of independence','rows':rows},indent=2))
    print(json.dumps(rows,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
