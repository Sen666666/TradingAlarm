"""Known-process diagnostic, not simulated evidence of market profitability."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from markov_trend_strength import markov_frame
from markov_state_execution import map_state_exposure
from cumulative_trend_strength import cumulative_frame
from range_direction_strength import range_frame
from geometric_strength import strength_exposure

OUT=Path('results/trend-response-benchmark')
START=252;BREAK=294;DIVERGE=299;END=357


def paired_prices(noise,drift):
    mean=np.zeros(len(noise));mean[START:BREAK]=drift;mean[BREAK:DIVERGE]=-.5
    up=mean.copy();down=mean.copy();up[DIVERGE:]=drift;down[DIVERGE:]=-drift
    return [pd.Series(np.exp(np.cumsum(.02*(noise+m)))) for m in (up,down)]


def exposures(p):
    v=pd.Series(1.,index=p.index);frame=pd.DataFrame(dict(high=p,low=p,close=p))
    return dict(markov=map_state_exposure(markov_frame(p,v)),cumulative=strength_exposure(cumulative_frame(p,v).strength),slow_close=strength_exposure(range_frame(frame,v,close_only=True).strength))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'protocol.json').write_text(json.dumps(dict(status='Frozen before outcomes',seeds=list(range(100)),sigma=.02,drift_sigma=[.15,.5],schedule=dict(warmup=START,trend_until=BREAK,common_negative_segment_until=DIVERGE,end=END),noise='Gaussian iid; identical innovations across paired branches; constant volume',models=['frozen Markov MAP price','frozen capped cumulative price','frozen slow close direction'],tests='Exact identical states before branch divergence. Conditional reversal detection only among models holding immediately before common negative segment.',limits='Stylized diagnostic with intentionally known drift, not market reality, not portfolio PNL, not future-performance evidence. No parameter tuning.'),indent=2))
    rows=[]
    for seed in range(100):
        noise=np.random.default_rng(seed).normal(size=END)
        for drift in [.15,.5]:
            prices=paired_prices(noise,drift);branches=[exposures(p) for p in prices]
            for model in branches[0]:
                up=branches[0][model];down=branches[1][model]
                pd.testing.assert_series_equal(up.iloc[:DIVERGE],down.iloc[:DIVERGE])
                held=bool(up.iloc[BREAK-1]);flat=np.flatnonzero(down.iloc[BREAK:].to_numpy()==0)
                rows.append(dict(seed=seed,drift=drift,model=model,warmup_false_long=float(up.iloc[126:START].mean()),trend_long=float(up.iloc[START:BREAK].mean()),held_before_break=held,exit_during_identical_segment=bool(up.iloc[BREAK:DIVERGE].eq(0).any()) if held else None,reversal_first_exit_delay=int(flat[0]) if held and len(flat) else None,reversal_never_exit=bool(held and not len(flat)),reversal_long_fraction=float(down.iloc[DIVERGE:].mean()),recovery_long_fraction=float(up.iloc[DIVERGE:].mean())))
    f=pd.DataFrame(rows);f.to_csv(OUT/'trials.csv',index=False);summaries=[]
    for (drift,model),g in f.groupby(['drift','model']):
        held=g.loc[g.held_before_break]
        summaries.append(dict(drift=drift,model=model,trials=len(g),warmup_false_long=float(g.warmup_false_long.mean()),trend_long=float(g.trend_long.mean()),held_before_break=len(held),common_segment_exit_rate=float(held.exit_during_identical_segment.astype(float).mean()) if len(held) else None,median_reversal_exit_delay=float(held.reversal_first_exit_delay.median()) if len(held) else None,reversal_never_exit=int(held.reversal_never_exit.sum()),reversal_long_fraction=float(g.reversal_long_fraction.mean()),recovery_long_fraction=float(g.recovery_long_fraction.mean())))
    (OUT/'summary.json').write_text(json.dumps(summaries,indent=2));print(json.dumps(summaries,indent=2))


if __name__=='__main__':main()
