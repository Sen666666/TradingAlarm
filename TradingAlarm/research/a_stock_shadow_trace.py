"""Trace diagnosed admission differences while reproducing frozen outcomes."""
import json
import pandas as pd
from a_stock_campaign_shadow import build_bundle,simulate,ROOT


def main():
    b=build_bundle();out=ROOT/'results/a-stock-shadow-path-attribution'
    watches={'601077.SH','601825.SH','601229.SH','600919.SH'}
    dates=set(pd.bdate_range('2023-04-17','2023-04-21').strftime('%Y-%m-%d'))
    dates|=set(pd.bdate_range('2024-01-10','2024-01-31').strftime('%Y-%m-%d'))
    for gate,label in [(False,'lowvol_all'),(True,'lowvol_best_quintile')]:
        for full in (False,True):
            trace=[]
            m,p,o,c,s=simulate(b,gate=gate,full_entry_risk=full,decision_trace=trace,
                             trace_symbols=watches,trace_dates=dates)
            folder=ROOT/('results/a-stock-campaign-shadow-fullrisk' if full else 'results/a-stock-campaign-shadow')
            case=label+'-15'
            assert o==json.loads((folder/f'{case}-orders.json').read_text())
            assert dict(closed=c,open=s)==json.loads((folder/f'{case}-campaigns.json').read_text())
            pd.testing.assert_frame_equal(p,pd.read_csv(folder/f'{case}-path.csv',index_col=0),
                                          check_exact=False,rtol=1e-12,atol=1e-9)
            name=label+'-'+('full' if full else 'partial')+'-trace.json'
            (out/name).write_text(json.dumps(trace,indent=2))
            print(name,'records',len(trace),'original orders, campaigns and NAV reproduced',flush=True)


if __name__=='__main__':main()
