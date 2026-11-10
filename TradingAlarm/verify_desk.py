"""Operational parity verification; reads frozen history, does not run a backtest."""
from pathlib import Path
import json,hashlib,sys
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
import numpy as np
from desk.data import MarketData,ROOT
from desk.refresh import prepare_facts,compute_recovery


def verify_one(args):
    sid,signal_path,fact_path=args
    f=prepare_facts(pd.read_parquet(signal_path));old=pd.read_parquet(fact_path)
    for c in ['e0_ready','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_ready','factor','raw_close']:
        np.testing.assert_allclose(f.loc[old.index,c].astype(float),old[c].astype(float),rtol=0,atol=0,equal_nan=True,err_msg=sid+'/'+c)
    return dict(symbol=sid,rows=len(f))


def main():
    m=MarketData('/tmp/tradingalarm-contract-readonly');tasks=[(s,str(m.signals_dir/f'{s}.parquet'),str(m.facts_dir/f'{s}.parquet')) for s in m.facts];receipts=[]
    with ProcessPoolExecutor(max_workers=6) as pool:
        for x in pool.map(verify_one,tasks):
            receipts.append(x)
            if len(receipts)%40==0:print('facts',len(receipts),'/',len(tasks),flush=True)
    signals={s:pd.read_parquet(m.signals_dir/f'{s}.parquet') for s in m.meta};z=compute_recovery(signals,pd.DataFrame(m.roster))
    for c in ['market','prior_high63','breadth']:np.testing.assert_allclose(z.loc[m.recovery.index,c],m.recovery[c],rtol=1e-12,atol=1e-12,equal_nan=True)
    np.testing.assert_array_equal(z.loc[m.recovery.index,'breakout'],m.recovery.breakout)
    result=dict(passed=True,facts=receipts,market_rows=len(z),market_decisions_exact=True,network_requests=0,new_backtests=0,source_identity=m.integrity)
    target=ROOT/'TradingAlarm/desk-verification.json';target.write_text(json.dumps(result,indent=2));print('operational parity passed',flush=True)

if __name__=='__main__':main()
