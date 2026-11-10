"""Isolated synthetic fractional sleeves; shared allocation function and endpoints."""
import argparse,json,hashlib
import pandas as pd
from build_stock_features import ROOT
from monthly_ah_engine import allocation_weights
from monthly252_sleeve_comparison import endpoints


def main(output):
    out=ROOT/'results'/output;protocol=json.loads((out/'protocol.json').read_text());manifest=json.loads((ROOT/protocol['manifest']).read_text());data=ROOT/'data/ths-refresh-20261018'
    names=[r['symbol'] for r in manifest['records']];weights={}
    for r in manifest['records']:
        p=data/f"{r['ths_symbol']}-signal.parquet";assert hashlib.sha256(p.read_bytes()).hexdigest()==r['signal_sha256'];f=pd.read_parquet(p)
        signal=f[['signal_open','signal_high','signal_low','signal_close']].rename(columns=lambda x:x.removeprefix('signal_'))
        weights[r['symbol']]=allocation_weights({r['symbol']:{'signal':signal}},'atr_risk_cap')[r['symbol']]
    table=pd.read_parquet(out/'episodes.parquet');table['scenario']=table.delay.map({0:'base',1:'delay1'})
    table['equal_capital']=.9
    table['atr_risk_cap']=[float(weights[e.symbol].loc[:pd.Timestamp(e.signal_date)].iloc[-1]) for e in table.itertuples()]
    rows=[]
    for strategy,g in table.groupby('strategy'):
        for allocation in ('equal_capital','atr_risk_cap'):
            for r in endpoints(g,names,fraction_column=allocation):
                rows.append(dict(strategy=strategy,allocation=allocation,**r,attempted_cash_sensitivity=r['equal_initial_sleeve_return']*len(names)/manifest['attempted']))
    for r in rows:
        if r['cutoff']=='2026-10-16':
            previous=next(v for v in rows if v['cutoff']=='2025-12-31' and all(v[k]==r[k] for k in ('strategy','allocation','scenario','cost','terminal')))
            r['year2026_carry_return']=(1+r['equal_initial_sleeve_return'])/(1+previous['equal_initial_sleeve_return'])-1
    (out/'sleeve-report.json').write_text(json.dumps(dict(rows=rows,meaning='Equal initial isolated fractional synthetic sleeves; reinvest net capital within symbol only,90percententrycap andfixed4percentnominal2ATRrisk per sleeve. Endpoints only,no MDD. Not wholeportfolio dynamicallocation,actualshareaccount,taxes,lots orcertifiedexecution. Attemptedcash sensitivity leaves excludednamesincash;doesnotvalidateexclusions.2026carryreturn uses2025endNAV,notaveragedepisodereturns.'),indent=2)+'\n')
    for r in rows:
        if r['cutoff']=='2026-10-16' and r['scenario']=='base' and r['cost']==15 and r['terminal']=='last_mark':print(r)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);main(p.parse_args().output)
