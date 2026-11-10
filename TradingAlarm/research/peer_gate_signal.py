"""Gate admission on original entry event; hold through gate fluctuations until base exit."""
import pandas as pd
from pathlib import Path

def gate_exposure(base,gate):
    accepted=False;previous=False;values=[]
    for value,allowed in zip(base,gate.reindex(base.index).fillna(False)):
        current=bool(value)
        if not current:accepted=False
        elif not previous:accepted=bool(allowed)
        values.append(float(accepted));previous=current
    return pd.Series(values,index=base.index,name=base.name)

def load_gates():
    p=Path(__file__).resolve().parent/'results/peer-trend-breadth-audit/features.parquet'
    f=pd.read_parquet(p);piv=f.pivot(index=['date','symbol'],columns='mapping',values=['peers','breadth'])
    common=piv[('peers','proxy')].ge(10)&piv[('peers','relative_proxy')].ge(10)
    g=pd.DataFrame({'peer_coverage_volume':common,'peer_raw_volume':common&piv[('breadth','proxy')].gt(.5),'peer_relative_volume':common&piv[('breadth','relative_proxy')].gt(.5)}).reset_index()
    return {s:a.set_index('date').drop(columns='symbol') for s,a in g.groupby('symbol')}
