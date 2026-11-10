"""Additional exact equality/fresh-state distinction; no old run is repeated."""
from pathlib import Path
import importlib.util, json, hashlib, time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    start=time.monotonic(); freeze=json.loads((O/'BOUNDARY_EDGE_FREEZE.json').read_text())
    assert not(O/'BOUNDARY_EDGE_RESULTS.json').exists()
    for p,h in freeze.items(): assert sha(p)==h,p
    spec=importlib.util.spec_from_file_location('same_frozen_flags_edge',O/'compute_flags.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    index=pd.date_range('2000-01-01',periods=100)
    def calc(c):
        f=pd.DataFrame(dict(close=c,raw_close=c,factor=1.,segment_id=0),index=index)
        return m.compute_flags(f,price_observed=pd.Series(True,index=index),debug=True)
    c=np.arange(100,dtype=float)+100
    c[64]=134. # mean of prior59=105..163; inclusive60 remains exactly134.
    a=calc(c)
    assert a.MA60.iloc[64]==134. and c[64]==a.MA60.iloc[64]
    assert a.MA60_lag5.iloc[64]==129.5 and bool(a.A.iloc[64])
    d=np.full(100,100.);d[65:]=125.
    b=calc(d)
    assert d[64]==b.BB_upper.iloc[64] and bool(b.B.iloc[65])
    assert d[66]>b.BB_upper.iloc[66] and not bool(b.B.iloc[66])
    for p,h in freeze.items():assert sha(p)==h,p
    (O/'BOUNDARY_EDGE_RESULTS.json').write_text(json.dumps(dict(passed=True,seconds=time.monotonic()-start,
        checks=['price_equals_MA_with_positive_slope_is_A_TRUE',
                'prior_price_equals_upper_then_strict_break_is_B_TRUE',
                'sustained_above_upper_without_fresh_cross_is_B_FALSE'],
        new_accounts=0,repeated_full_source_verification=False),indent=2)+'\n')
    print('BOUNDARY_EDGE_PASS')
if __name__=='__main__':main()
