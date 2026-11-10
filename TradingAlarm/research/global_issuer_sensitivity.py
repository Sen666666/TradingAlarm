"""Re-run fixed signal paths with precise issuer amounts, separate from frozen runs."""
import json
import pandas as pd
from build_stock_features import ROOT
from global_signal_transfer import load,run_period


def main():
    folder=ROOT/'results/global-signal-transfer'
    baseline=pd.read_parquet(folder/'campaigns.parquet')
    blocks=json.loads((folder/'protocol.json').read_text())['blocks']
    rows=[];reports=[]
    for symbol in ('SPY','IEF','EFA','DBC'):
        raw,events,frame=load(symbol,ROOT/f'data/global-transfer/{symbol}-issuer-distributions.json')
        for start,end in blocks:
            new=pd.DataFrame(run_period(symbol,raw,events,frame,start,end));rows.extend(new.to_dict('records'))
            old=baseline[(baseline.symbol==symbol)&(baseline.period_start==start)&(baseline.period_end==end)]
            identity=['entry_date','exit_date','mark_date','status']
            paths_equal=old.reindex(columns=identity).fillna('').to_dict('records')==new.reindex(columns=identity).fillna('').to_dict('records')
            result=dict(symbol=symbol,start=start,end=end,original_campaigns=len(old),issuer_campaigns=len(new),same_entry_exit_status=paths_equal)
            for cost in (15,30):
                key=f'R_cost{cost}';result[f'mean_R_change_cost{cost}']=float(new[key].mean()-old[key].mean())
                result[f'issuer_mean_R_cost{cost}']=float(new[key].mean())
            reports.append(result)
    pd.DataFrame(rows).to_parquet(folder/'issuer-sensitivity-campaigns.parquet',index=False)
    result=dict(reports=reports,interpretation='Source-amount correction under frozen rules, not an alpha parameter choice. No cash settlement or reinvestment modeled here. 2006 SPY payment-date anomaly retained and flagged; before 2007 execution, does not affect accrual signal amounts. Full holdings and cash ledger remain pending.')
    (folder/'issuer-sensitivity.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
