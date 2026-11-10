"""Frozen random-priority falsification of entry-strength ranking; development audit."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from sector_episode_allocation import allocate
BASE=Path('results/sector-episode-allocation');OUT=Path('results/sector-ranking-control')
def random_priority(episodes,seed):
    out=episodes.sort_values(['entry_date','symbol']).copy()
    out['strength']=np.random.default_rng(seed).random(len(out))
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=dict(seeds=list(range(9200,9220)),variants=['stock_only','gate','gate_group_cap'],mapping='relative_proxy',cost=15,method='Replace entry-priority strength with seeded independent random scores; existing entries/exits, gate, slot limits, sizing unchanged. Strong ranking is control.',interpretation='Random-order distribution not independent market realizations or formal p value. Exposure and path-dependent admissions may differ. Development data; no best seed selection.',scope='Synthetic fractional episode admission, not raw-share cash account; no live strategy recommendation')
    p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==protocol
    p.write_text(json.dumps(protocol,indent=2))
    paths=[BASE/'candidate-input.parquet',BASE/'marks-input.parquet',BASE/'gates-input.parquet',Path('results/sector-stock-daily-mapping/assignments.parquet')]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    e=pd.read_parquet(paths[0]);marks=pd.read_parquet(paths[1]);g=pd.read_parquet(paths[2]);m=pd.read_parquet(paths[3]);gates={(r.date,r.proxy):r.gate for r in g.itertuples()};mapping={(r.date,r.symbol):r.relative_proxy for r in m.itertuples()}
    records=[];controls=0
    for variant in protocol['variants']:
        for seed in [None]+protocol['seeds']:
            path,t=allocate(e if seed is None else random_priority(e,seed),marks,mapping,gates,variant,15)
            if seed is None:
                pd.testing.assert_frame_equal(path,pd.read_parquet(BASE/f'relative_proxy-{variant}-15-path.parquet'),check_exact=True)
                pd.testing.assert_frame_equal(t,pd.read_parquet(BASE/f'relative_proxy-{variant}-15-trades.parquet'),check_exact=True);controls+=1
            records.append(dict(variant=variant,seed=seed,return_fraction=float(path.nav.iloc[-1]-1),return2026=float(path.nav.iloc[-1]/path.loc[:'2025-12-31'].nav.iloc[-1]-1),drawdown=float((path.nav/path.nav.cummax()-1).min()),exposure=float(path.exposure.mean()),ordinary_pnl=float(t.loc[t.return_fraction.lt(.3),'pnl'].sum()),tail_pnl=float(t.loc[t.return_fraction.ge(.3),'pnl'].sum()),episodes=len(t)))
        print(variant,'done',flush=True)
    f=pd.DataFrame(records);f.to_csv(OUT/'runs.csv',index=False);summary=[]
    for variant,g in f.groupby('variant'):
        actual=g.loc[g.seed.isna()].iloc[0];random=g.loc[g.seed.notna()]
        summary.append(dict(variant=variant,ranked_return=float(actual.return_fraction),random_median=float(random.return_fraction.median()),random_min=float(random.return_fraction.min()),random_max=float(random.return_fraction.max()),fraction_random_beats_rank=float(random.return_fraction.gt(actual.return_fraction).mean()),ranked_2026=float(actual.return2026),random_median2026=float(random.return2026.median()),random_median_ordinary=float(random.ordinary_pnl.median()),random_median_tail=float(random.tail_pnl.median()),ranked_exposure=float(actual.exposure),random_median_exposure=float(random.exposure.median())))
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    (OUT/'validation.json').write_text(json.dumps(dict(exact_controls=controls,cash_reconciliations=len(f),hashes=hashes),indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
