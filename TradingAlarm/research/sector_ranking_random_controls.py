"""Frozen random-priority controls, no best-seed selection."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from sector_admission_audit import load_context
from trend_slot_selection import TrendSlots
from monthly_ah_engine import run
OUT=Path('results/sector-ranking-random-controls')
def main(seeds):
 assets,signals,strength,events,calendar,groups,gates,manifest=load_context();protocol=json.loads((OUT/'protocol.json').read_text())
 for seed in seeds:
  assert seed=='rank' or int(seed) in protocol['seeds']
  case='rank' if seed=='rank' else 'random_'+seed;name=case+'-base'
  rng=np.random.default_rng(int(seed)) if seed!='rank' else None
  scores=strength if seed=='rank' else {s:pd.Series(rng.random(),index=strength[s].index) for s in sorted(strength)}
  selector=TrendSlots(scores,groups=groups,gates=gates,slots=9,group_slots=3,entry_events=events)
  m,path,orders,_=run(assets,'2024-01-02','2026-10-16',policy='score_change',signals=signals,cadence='daily',selection=selector,entry_fraction=.1,fx_override=pd.Series(1.,index=calendar),cost=15,delay=0)
  if seed=='rank':
   ref=Path('results/broad-shared-first-cross');pd.testing.assert_frame_equal(path,pd.read_parquet(ref/'group_gate_cap-base-path.parquet'),check_exact=True);assert orders==json.loads((ref/'group_gate_cap-base-orders.json').read_text())
  units=pd.DataFrame(0.,index=path.index,columns=sorted(assets));change=pd.Series(0.,index=path.index)
  for o in orders:
   d=pd.Timestamp(o['date']);units.loc[d,o['symbol']]+=o['units'];change.loc[d]-=o['units']*o['raw_open']+o['fee']
  units=units.cumsum();cash=1e6+change.cumsum();marks=pd.DataFrame({s:a['raw'].close.reindex(calendar).ffill().reindex(path.index) for s,a in assets.items()});nav=cash+(units*marks).fillna(0).sum(axis=1)
  error=float((nav/1e6-path.nav).abs().max());assert error<1e-9;assert cash.min()>=-1e-6;assert units.ge(-1e-8).all().all();assert units.gt(1e-8).sum(axis=1).max()<=9
  m.update(case=case,scenario='base',seed=seed,year2026=float(path.nav.iloc[-1]/path.nav.loc['2025-12-31']-1),ledger_error=error)
  path.to_parquet(OUT/(name+'-path.parquet'));(OUT/(name+'-orders.json')).write_text(json.dumps(orders));(OUT/(name+'-metrics.json')).write_text(json.dumps(m,indent=2));print(case,m['total_return'],m['max_drawdown'],flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('seeds',nargs='+');a=p.parse_args();main(a.seeds)
