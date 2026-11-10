"""Equal initial capital isolated synthetic sleeves, no cross-sleeve reallocation.
Fractional adjusted-price units, no taxes/lots/participation; endpoint diagnostics only.
"""
import json
import pandas as pd
from build_stock_features import ROOT


def endpoints(table,names,fraction_column=None):
    rows=[]
    for (cutoff,scenario),g in table.groupby(['cutoff','scenario']):
        for cost in (15,30):
            for terminal in ('last_mark','zero_stress'):
                x=g.copy();fraction=x[fraction_column] if fraction_column else 1.
                if fraction_column and not fraction.between(0,1).all():raise ValueError('invalid entry capital fraction')
                x['growth']=1+fraction*x[f'return{cost}']
                if terminal=='zero_stress':
                    x.loc[x.status.eq('terminal_unknown'),'growth']=1-fraction[x.status.eq('terminal_unknown')] if fraction_column else 0.
                # Chronological non-overlapping reinvestment within each symbol.
                v=x.groupby('symbol').growth.prod().reindex(names,fill_value=1.)-1
                rows.append(dict(cutoff=cutoff,scenario=scenario,cost=cost,terminal=terminal,equal_initial_sleeve_return=float(v.mean()),median_sleeve_return=float(v.median()),profitable_sleeves=int(v.gt(0).sum()),symbols=len(names)))
    return rows


def main():
    old=ROOT/'results/a-stock-monthly252';out=ROOT/'results/a-stock-monthly252-daily-exit'
    names=json.loads((old/'coverage.json').read_text())['records'];assert len(names)==5426
    a=endpoints(pd.read_parquet(old/'episodes.parquet'),names);b=endpoints(pd.read_parquet(out/'episodes.parquet'),names)
    assert len(a)==len(b)==60
    comparisons=[]
    for x,y in zip(a,b):
        for key in ('cutoff','scenario','cost','terminal'):assert x[key]==y[key]
        comparisons.append(dict(**{k:x[k] for k in ('cutoff','scenario','cost','terminal')},monthly=x['equal_initial_sleeve_return'],daily_exit=y['equal_initial_sleeve_return'],difference=y['equal_initial_sleeve_return']-x['equal_initial_sleeve_return'],monthly_median=x['median_sleeve_return'],daily_median=y['median_sleeve_return']))
    r=dict(assumptions='5426equalinitialsyntheticfractional sleeves,includingnevertradedcash. Reinvest realizednetreturns onlywithin eachsymbol;no redistribution/cashyield. Entryfee denominator andexitfee numerator match episode model. Endpointonly,no verifiedaccountMDD;no lots,stocktax,liquidityconstraints or PITuniverse repair.',comparisons=comparisons,improved=sum(c['difference']>0 for c in comparisons))
    (out/'sleeve-comparison.json').write_text(json.dumps(r,indent=2))
    print(json.dumps({'improved':r['improved'],'comparisons':len(comparisons),'latest_base':[c for c in comparisons if c['cutoff']=='2026-05-15' and c['scenario']=='base' and c['cost']==15]},indent=2))

if __name__=='__main__':main()
