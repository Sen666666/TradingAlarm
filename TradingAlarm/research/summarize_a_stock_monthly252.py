"""Frozen broad-universe evidence, separating marked and closed outcomes."""
import json
import pandas as pd
from build_stock_features import ROOT


def main():
    out=ROOT/'results/a-stock-monthly252';data=pd.read_parquet(out/'episodes.parquet');summary=json.loads((out/'summary.json').read_text());coverage=json.loads((out/'coverage.json').read_text())
    assert coverage['symbols']==5426
    assert (pd.to_datetime(data.signal_date)<pd.to_datetime(data.entry_date)).all()
    assert (pd.to_datetime(data.entry_date)<=pd.to_datetime(data.cutoff)).all()
    assert (pd.to_datetime(data.mark_date)<=pd.to_datetime(data.cutoff)).all()
    assert data.loc[data.status.eq('closed'),'exit_date'].notna().all()
    assert data.loc[~data.status.eq('closed'),'exit_date'].isna().all()
    details=[]
    for keys,g in data.groupby(['cutoff','scenario','source','status']):
        v=g.return15
        details.append(dict(cutoff=keys[0],scenario=keys[1],source=keys[2],status=keys[3],count=len(g),mean=float(v.mean()),median=float(v.median()),over30percent=int(v.gt(.3).sum()),over80percent=int(v.gt(.8).sum()),over200percent=int(v.gt(2.).sum())))
    (out/'distribution-detail.json').write_text(json.dumps(details,indent=2))
    final=[r for r in summary if r['cutoff']=='2026-05-15']
    d=dict(adopted=False,scope='Synthetic adjusted-price episode study,not portfolio or rawshare return',coverage=coverage['symbols'],cutoffs=5,execution_scenarios=3,cost_assumptions=2,tests=3,
        final=final,closed_mean_positive_summaries=sum(r['closed_mean']>0 for r in summary),summary_count=len(summary),
        ordinary_closed_mean_positive_summaries=sum(r['closed_ordinary_bottom90_mean']>0 for r in summary),
        limitations=['Local plus accepted retired sample is not complete point-in-time stock universe. Source parity checked for all observed feature prices;source adjustment/providerrevision errors still possible.',
                    'Observed zero-range restriction is execution stress,not fully verified historic limits/ST/queues. Fixedside fees omit actual stocktax/minimums/participation.',
                    'Singleunit returns pool correlated episodes and allocate no scarce capital;cannot establish80percentaccountcycle or20percentMDD.',
                    'Terminalunknown does not mean proven delisting or zero recovery;lastmark andzeroassetvalue are separate scenarios.',
                    'Cumulative cutoffs reuse overlapping history,not independent validation. Long openwinners and retrospective tail removal must not be mistaken for realizedpredictive selection.'],
        next='Use cutoff/source/closed-open distribution to determine whether monthly252 merits capital-constrained A-stock research. Do not select sectors,thresholds orhorizons from these outcomes; retain current-data-quality limits.')
    (out/'decision.json').write_text(json.dumps(d,indent=2))
    p=ROOT/'progress.json';v=json.loads(p.read_text());v['multihorizon_trend_comparator']['a_stock_monthly252']={'decision':'results/a-stock-monthly252/decision.json','status':'Broadsyntheticsignalepisodes complete;notadopted;notaccountbacktest'};p.write_text(json.dumps(v,indent=2))
    print(json.dumps({'positive_closed_means':d['closed_mean_positive_summaries'],'positive_ordinary_means':d['ordinary_closed_mean_positive_summaries'],'summaries':len(summary),'final':final},indent=2))

if __name__=='__main__':main()
