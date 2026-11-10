"""Descriptive tail fragility of frozen signals; never portfolio return or inference."""
import json
import pandas as pd
from build_stock_features import ROOT


def describe(frame, cost):
    key=f'R_cost{cost}'
    all_r=frame[key].sort_values(ascending=False)
    closed=frame.loc[frame.status.eq('closed'),key].sort_values(ascending=False)
    def stats(r):
        return dict(count=len(r),sum_R=float(r.sum()),mean_R=float(r.mean()) if len(r) else None,
                    ordinary_below3R_sum=float(r[r<3].sum()),tail_count=int(r.ge(3).sum()),
                    tail_sum=float(r[r>=3].sum()),
                    remove_largest_1_sum=float(r.iloc[1:].sum()),
                    remove_largest_3_sum=float(r.iloc[3:].sum()))
    return dict(marked=stats(all_r),closed=stats(closed),
                open_mark_R=float(frame.loc[frame.status.ne('closed'),key].sum()))


def main():
    folder=ROOT/'results/global-signal-transfer'
    d=pd.read_parquet(folder/'campaigns.parquet')
    d=d[(d.period_start=='2007-01-01')&(d.period_end=='2025-12-31')].copy()
    assert not d.duplicated(['symbol','entry_date']).any()
    results=[]
    for symbol,g in d.groupby('symbol'):
        for cost in (15,30):
            row=dict(symbol=symbol,cost_bps=cost,**describe(g,cost))
            tails=g[g[f'R_cost{cost}']>=3].sort_values(f'R_cost{cost}',ascending=False)
            row['tails']=[{k:(None if pd.isna(v) else v) for k,v in r.items()}
                          for r in tails[['entry_date','exit_date','mark_date','status',f'R_cost{cost}']].to_dict('records')]
            results.append(row)
    out=dict(method='Whole-history trades only; excludes overlapping restarted blocks. Fixed 3R threshold inherited from prior report. Remove-largest results are descriptive counterfactuals, not a trade-selection rule or probability estimate. R is initial-ATR normalized per-trade profit, not account return. Correlated assets and dates are not independent samples. Closed positions may retain unpaid distribution rights.',
             records=results)
    (folder/'tail-concentration.json').write_text(json.dumps(out,indent=2))
    progress_path=ROOT/'progress.json';progress=json.loads(progress_path.read_text())
    progress['global_price_volume_transfer']['tail_concentration']=dict(path=str(folder/'tail-concentration.json'),
        conclusion='Report closed/open separately and leave-largest sensitivities. This does not establish portfolio profitability or likelihood of future 80 percent account gains.')
    progress_path.write_text(json.dumps(progress,indent=2,ensure_ascii=False))
    for r in results:
        if r['cost_bps']==15:print(r['symbol'],json.dumps({k:r[k] for k in ('marked','closed','open_mark_R')}))


if __name__=='__main__':main()
