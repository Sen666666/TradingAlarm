"""Carry-in calendar-year diagnostics of saved account paths; no new fitting.

Years retain positions, cash and claims from the continuous simulation. They
are descriptive reused-sample blocks, not independent restart backtests.
"""
import argparse
import json
import math
import pandas as pd
from build_stock_features import ROOT
from strategy_signals import period_metrics


def describe(path):
    years=[]
    for year in sorted(path.index.year.unique()):
        m=period_metrics(path,f'{year}-01-01',f'{year}-12-31')
        m['year']=int(year)
        m['pnl_cny']=m['starting_nav']*m['return_fraction']*1e6
        years.append(m)
    compounded=math.prod(1+x['return_fraction'] for x in years)-1
    total=float(path.nav.iloc[-1]-1)
    assert abs(compounded-total)<1e-10
    assert abs(sum(x['pnl_cny'] for x in years)-total*1e6)<1e-6
    peak=path.nav.cummax().clip(lower=1.)
    dd=path.nav/peak-1
    trough=dd.idxmin()
    before=path.loc[:trough,'nav']
    peak_date=before.idxmax() if before.max()>=1 else None
    return dict(years=years,total_return=total,max_drawdown=float(dd.min()),
                trough=str(trough.date()),peak=str(peak_date.date()) if peak_date is not None else 'initial_cash')


def main(output,control,candidate):
    out=ROOT/'results'/output
    rows=json.loads((out/'results.json').read_text())
    selected=[r for r in rows if r['strategy'] in (control,candidate)]
    summaries={r['case']:describe(pd.read_parquet(out/f"{r['case']}-path.parquet")) for r in selected}
    pairs=[]
    for c in selected:
        if c['strategy']!=control:continue
        matches=[r for r in selected if r['strategy']==candidate and all(r[k]==c[k] for k in ('group','scenario','cadence'))]
        assert len(matches)==1
        a=summaries[c['case']];b=summaries[matches[0]['case']]
        assert [x['year'] for x in a['years']]==[x['year'] for x in b['years']]
        annual=[dict(year=x['year'],control_return=x['return_fraction'],candidate_return=y['return_fraction'],
                     difference=y['return_fraction']-x['return_fraction'],pnl_difference_cny=y['pnl_cny']-x['pnl_cny'])
                for x,y in zip(a['years'],b['years'])]
        assert abs(sum(x['pnl_difference_cny'] for x in annual)-(b['total_return']-a['total_return'])*1e6)<1e-6
        pairs.append(dict(group=c['group'],scenario=c['scenario'],cadence=c['cadence'],years=annual,
                          control_drawdown=a['max_drawdown'],candidate_drawdown=b['max_drawdown'],
                          candidate_peak=b['peak'],candidate_trough=b['trough']))
    assert pairs
    report=dict(meaning='Continuous account carry-in calendar years. Reused research sample, not untouched holdout or independent annual restarts. PNL differences are additive; return differences are not.',
                control=control,candidate=candidate,paths=summaries,pairs=pairs,
                validation=dict(paths=len(summaries),annual_compounding_and_pnl_reconciled=True))
    (out/'period-report.json').write_text(json.dumps(report,indent=2)+'\n')
    for p in pairs:
        print(p['group'],p['scenario'],[(x['year'],round(x['control_return']*100,2),round(x['candidate_return']*100,2)) for x in p['years']],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--control',required=True)
    parser.add_argument('--candidate',required=True)
    args=parser.parse_args();main(args.output,args.control,args.candidate)
