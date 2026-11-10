"""Frozen synthetic probes of neutral-state evidence; no parameter selection."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from neutral_trend_strength import neutral_frame,neutral_regimes
from geometric_strength import strength_exposure
ROOT=Path(__file__).resolve().parent

def main(score='strength',filename='probe-report.json'):
    rows=[]
    for drift in (0.,.003,.01):
        for seed in range(20):
            noise=np.random.default_rng(seed).normal(0,.02,300);price=pd.Series(np.exp(np.cumsum(drift+noise)));volume=price*0+1
            for joint in (False,True):
                f=neutral_frame(price,price,volume,joint);s=f[score].iloc[50:];exposure=strength_exposure(f[score]).iloc[50:]
                rows.append({'drift':drift,'seed':seed,'model':'price_volume' if joint else 'price_only','occupied_fraction':float(exposure.mean()),'above_entry_fraction':float(s.ge(5+5*np.tanh(1)).mean()),'score_mean':float(s.mean()),'neutral_mean':float(f.neutral_probability.iloc[50:].mean()),'entries':int(exposure.diff().eq(1).sum())})
    t=pd.DataFrame(rows);out=ROOT/'results/trend-strength-neutral';t.to_parquet(out/(filename.removesuffix('.json')+'.parquet'),index=False)
    summary=t.groupby(['model','drift'])[['occupied_fraction','above_entry_fraction','score_mean','neutral_mean','entries']].mean().reset_index().to_dict('records')
    responses=[]
    for label,values in [('reversal',np.r_[np.ones(50),-np.ones(30)]),('shock',np.r_[np.ones(50),-8,-np.ones(29)]),('trend_to_zero',np.r_[np.ones(50),np.zeros(30)])]:
        f=neutral_regimes(values);indices=np.flatnonzero(f[score].iloc[50:].to_numpy()<=5)
        responses.append({'case':label,'score_before':float(f[score].iloc[49]),'score_after':float(f[score].iloc[50]),'score_after20':float(f[score].iloc[69]),'bars_until_exit':int(indices[0]+1) if len(indices) else None,'neutral_after20':float(f.neutral_probability.iloc[69])})
    (out/filename).write_text(json.dumps({'score':score,'summary':summary,'responses':responses,'design':'Same20fixedseeds and noiseSD0.02 as priorprobe;last250 of300observations. Constant volume means jointactivityproxy stillincludesprice andisnotindependent volume evidence. Directnormalized sequences separatechangepointmodel fromnormalization. Synthetictruth only,notmarketpredictability.'},indent=2)+'\n');print(summary);print(responses)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--score',default='strength');p.add_argument('--filename',default='probe-report.json');a=p.parse_args();main(a.score,a.filename)
