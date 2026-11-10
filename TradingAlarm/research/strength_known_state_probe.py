"""Known synthetic drift probes, not financial return forecasts or fitted hyperparameters."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from adaptive_geometric_strength import adaptive_frame
from geometric_strength import strength_exposure

def main():
    rows=[]
    for drift in (0.,.003,.01):
        for seed in range(20):
            noise=np.random.default_rng(seed).normal(0,.02,300)
            price=pd.Series(np.exp(np.cumsum(drift+noise)));volume=price*0+1
            f=adaptive_frame(price,price,volume);s=f.strength.iloc[50:];exposure=strength_exposure(f.strength).iloc[50:]
            rows.append({'drift':drift,'seed':seed,'occupied_fraction':float(exposure.mean()),'above_entry_fraction':float(s.ge(5+5*np.tanh(1)).mean()),'score_mean':float(s.mean()),'entries':int(exposure.diff().eq(1).sum())})
    t=pd.DataFrame(rows);out=Path(__file__).resolve().parent/'results/strength-state-duration';t.to_parquet(out/'known-state-probes.parquet',index=False)
    summary=t.groupby('drift')[['occupied_fraction','above_entry_fraction','score_mean','entries']].mean().reset_index().to_dict('records')
    (out/'known-state-probes.json').write_text(json.dumps({'summary':summary,'design':'20fixedseeds,300bar Gaussian log-return paths percase,noiseSD0.02;flatvolume;last250bars evaluated;same noise seeds acrossdrifts. Parameters unchanged,not selected for profitability. Known persistent drift is simulated truth,notmarketlabel. Drift0 exposure is diagnostic,not necessarily a bad trade in realmarkets. No confidence/significance claim.'},indent=2)+'\n');print(summary)
if __name__=='__main__':main()
