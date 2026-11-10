"""Reconciled synthetic sleeve PNL tail attribution, hindsight only."""
import json,math
import pandas as pd
from build_stock_features import ROOT
from monthly_ah_engine import allocation_weights


def main(output='broad-ths-channel-all500'):
    out=ROOT/'results'/output;protocol=json.loads((out/'protocol.json').read_text())
    manifest=json.loads((ROOT/protocol['manifest']).read_text());weights={}
    for r in manifest['records']:
        f=pd.read_parquet(ROOT/'data/ths-refresh-20261018'/f"{r['ths_symbol']}-signal.parquet");signal=f[['signal_open','signal_high','signal_low','signal_close']].rename(columns=lambda x:x.removeprefix('signal_'));weights[r['symbol']]=allocation_weights({r['symbol']:{'signal':signal}},'atr_risk_cap')[r['symbol']]
    t=pd.read_parquet(out/'episodes.parquet');t=t[t.cutoff.eq('2026-10-16')&t.delay.eq(0)].sort_values(['symbol','entry_date']);reports=[];ledger=[]
    for strategy,g in t.groupby('strategy'):
        for allocation in ('equal_capital','atr_risk_cap'):
            rows=[]
            for symbol,h in g.groupby('symbol'):
                nav=1.
                for e in h.itertuples():
                    f=.9 if allocation=='equal_capital' else float(weights[symbol].loc[:pd.Timestamp(e.signal_date)].iloc[-1]);pnl=nav*f*e.return15;nav+=pnl
                    rows.append(dict(symbol=symbol,entry_date=e.entry_date,status=e.status,return_fraction=e.return15,pnl_initial_sleeve=pnl))
            pnl=sum(x['pnl_initial_sleeve'] for x in rows)/len(manifest['records'])
            saved=next(x for x in json.loads((out/'sleeve-report.json').read_text())['rows'] if x['strategy']==strategy and x['allocation']==allocation and x['cutoff']=='2026-10-16' and x['scenario']=='base' and x['cost']==15 and x['terminal']=='last_mark')
            assert abs(pnl-saved['equal_initial_sleeve_return'])<1e-12
            thresholds=[]
            for threshold in (.3,.8,2.):
                tail=[x for x in rows if x['return_fraction']>=threshold];ordinary=[x for x in rows if x['return_fraction']<threshold]
                a=sum(x['pnl_initial_sleeve'] for x in ordinary)/len(manifest['records']);b=sum(x['pnl_initial_sleeve'] for x in tail)/len(manifest['records']);assert abs(a+b-pnl)<1e-12
                thresholds.append(dict(trade_return_threshold=threshold,tail_trades=len(tail),ordinary_trades=len(ordinary),ordinary_pnl_fraction=a,tail_pnl_fraction=b))
            sortedp=sorted(x['pnl_initial_sleeve'] for x in rows);n=math.ceil(len(rows)*.1)
            reports.append(dict(strategy=strategy,allocation=allocation,total_synthetic_pnl_fraction=pnl,episodes=len(rows),thresholds=thresholds,ordinary_bottom90_pnl_fraction=sum(sortedp[:-n])/len(manifest['records'])))
            ledger.extend(dict(strategy=strategy,allocation=allocation,**x) for x in rows)
    pd.DataFrame(ledger).to_parquet(out/'tail-economics-ledger.parquet',index=False)
    (out/'tail-economics.json').write_text(json.dumps(dict(reports=reports,meaning='SyntheticisolatedsleevePNL withwithin-symbolreinvestment,fees15bps,samebaseline,noeventredistribution. Contributions add exactlytoendpointreturns. Thresholds30/80/200percentrefer individualtradeadjustedreturn,notaccountcyclegain. Allclassificationhindsight,notentryfilter orcounterfactualdeletion;open/stalemarksincludedandnotrealized.'),indent=2)+'\n')
    for r in reports:print(r)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='broad-ths-channel-all500')
    main(parser.parse_args().output)
