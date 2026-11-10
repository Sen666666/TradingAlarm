"""Complete fixed-grid comparisons; matched entry diagnostics are not portfolio PNL."""
import json
import pandas as pd
from build_stock_features import ROOT


def main():
    old=ROOT/'results/a-stock-monthly252';out=ROOT/'results/a-stock-monthly252-daily-exit'
    a=pd.read_parquet(old/'episodes.parquet');b=pd.read_parquet(out/'episodes.parquet')
    keys=['symbol','source','cutoff','scenario','entry_date']
    assert not a.duplicated(keys).any() and not b.duplicated(keys).any()
    merged=a.merge(b,on=keys,how='outer',suffixes=('_old','_new'),indicator=True,validate='one_to_one')
    matched=merged[merged._merge.eq('both')].copy()
    assert (matched.entry_price_old==matched.entry_price_new).all()
    matched['delta_return15']=matched.return15_new-matched.return15_old
    matched.to_parquet(out/'matched-entry-episodes.parquet',index=False)
    controls={(r['cutoff'],r['scenario'],r['cost']):r for r in json.loads((old/'summary.json').read_text())}
    results=json.loads((out/'summary.json').read_text());comparisons=[]
    for r in results:
        c=controls[r['cutoff'],r['scenario'],r['cost']]
        comparisons.append(dict(cutoff=r['cutoff'],scenario=r['scenario'],cost=r['cost'],closed_mean_delta=r['closed_mean']-c['closed_mean'],marked_known_mean_delta=r['known_marked_mean']-c['known_marked_mean'],ordinary_closed_mean_delta=r['closed_ordinary_bottom90_mean']-c['closed_ordinary_bottom90_mean'],old_counts=c['counts'],new_counts=r['counts']))
    attribution=[]
    for keys,g in matched.groupby(['cutoff','scenario','status_old','status_new']):
        attribution.append(dict(cutoff=keys[0],scenario=keys[1],old_status=keys[2],new_status=keys[3],pairs=len(g),mean_delta=float(g.delta_return15.mean()),improved=int(g.delta_return15.gt(0).sum())))
    unmatched=[]
    for keys,g in merged[~merged._merge.eq('both')].groupby(['cutoff','scenario','_merge'],observed=True):
        unmatched.append(dict(cutoff=keys[0],scenario=keys[1],side=str(keys[2]),count=len(g)))
    decision=dict(adopted=False,comparisons=comparisons,matched_entry_groups=attribution,unmatched=unmatched,
        validation={'exact_symbol_controls':5426,'tests':6,'summary_cases':len(results)},
        improved_closed_mean=sum(r['closed_mean_delta']>0 for r in comparisons),improved_marked_known_mean=sum(r['marked_known_mean_delta']>0 for r in comparisons),
        limits=['Same-entry pairs isolate alternative exits until divergence;unmatched subsequent entries remain part of fullstrategy difference.',
                'Different episode counts and durations make pooledmean differences descriptive,not accountreturn uplift. Closed-onlymean can improve byrealizing winners previouslyopen.',
                'Synthetic prices,imperfectPIT/limits/actions;reused sample andcorrelatedepisodes. No optimizedperiodselection orcausal futureperformance claim.'])
    (out/'decision.json').write_text(json.dumps(decision,indent=2))
    p=ROOT/'progress.json';v=json.loads(p.read_text());v['multihorizon_trend_comparator']['a_stock_monthly252']['daily_exit']={'path':'results/a-stock-monthly252-daily-exit/decision.json','status':'Frozen comparison complete;notadopted'};p.write_text(json.dumps(v,indent=2))
    print(json.dumps({'closed_improved':decision['improved_closed_mean'],'marked_improved':decision['improved_marked_known_mean'],'latest':[r for r in results if r['cutoff']=='2026-05-15'],'latest_matched':[r for r in attribution if r['cutoff']=='2026-05-15' and r['scenario']=='base']},indent=2))

if __name__=='__main__':main()
