"""Post-trajectory diagnostic; never used for parameter selection."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from trend_pv_segment import segment_frame,exposure


def main(out):
    ix=pd.bdate_range('2020-01-01',periods=400);rows=[]
    for name,r in [('flat',np.zeros(400)),('one_level_jump',np.r_[np.zeros(200),.10,np.zeros(199)]),('drift_reversal',np.r_[np.full(200,.002),np.full(200,-.002)])]:
        c=pd.Series(np.exp(np.cumsum(r)),index=ix);v=pd.Series(100.,index=ix);v.iloc[200:208]=800
        d=segment_frame(c,v);h=exposure(d.strength);d['close']=c;d['volume']=v;d['target']=h;d.to_csv(out/f'synthetic-{name}.csv')
        rows.append(dict(case=name,entries=int(h.diff().fillna(h).gt(0).sum()),resets=int(d.reset.fillna(0).sum()),post_change_first_nonpositive=str(d.loc[ix[200]:].query('strength <= 0').index.min())))
    for seed in range(20):
        rng=np.random.default_rng(seed);c=pd.Series(np.exp(np.cumsum(rng.normal(0,.01,400))),index=ix);v=pd.Series(np.exp(rng.normal(6,.5,400)),index=ix)
        d=segment_frame(c,v);h=exposure(d.strength)
        rows.append(dict(case=f'zero_drift_random_walk_{seed}',entries=int(h.diff().fillna(h).gt(0).sum()),resets=int(d.reset.fillna(0).sum()),exposure=float(h.iloc[63:].mean())))
    (out/'synthetic-diagnostics.json').write_text(json.dumps({'status':'post-trajectory diagnostic only; not false-positive guarantee and not strategy PnL','rows':rows},indent=2))
    print(rows[:3]);print('null mean entries',np.mean([r['entries'] for r in rows[3:]]),'resets',np.mean([r['resets'] for r in rows[3:]]))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
