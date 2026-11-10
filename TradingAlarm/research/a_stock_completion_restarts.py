"""Fixed yearly fresh-capital sensitivity, not independent out-of-sample tests."""
import json
import numpy as np
import pandas as pd
from a_stock_campaign_shadow import build_bundle,simulate,ROOT


def main():
    out=ROOT/'results/a-stock-completion-restarts';out.mkdir(exist_ok=True)
    protocol=dict(starts=['2023-01-01','2024-01-01','2025-01-01','2026-01-01'],
        scope='Lowvol priority without gate;partial/fullrisk/completion x15/30bps. Same1m cashreset,featuresalreadywarmed,originalrisklimits. No optimized startdate.',
        limitations='Overlapping reused histories,not independent holdouts. Targeted stress of singlecompletion-event finding;doesnotcertifyallmarkets,rawsharesor80percentaccountgoal.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2))
    b=build_bundle();dates=pd.DatetimeIndex(b['dates']);rows=[]
    for start in protocol['starts']:
        first=int(np.flatnonzero(dates>=pd.Timestamp(start))[0])-1
        assert first>=0
        subset={k:(v if k=='names' else v[first:]) for k,v in b.items()}
        for label,full,completion in [('partial',False,False),('fullrisk',True,False),('completion',False,True)]:
            for cost in (15,30):
                case=f'{start}-{label}-{cost}'
                m,p,o,c,s=simulate(subset,cost_bps=cost,full_entry_risk=full,complete_initial=completion)
                m.update(case=case,start=start,variant=label,cost_bps=cost,
                    completion_events=[dict(date=x['date'],symbol=x['symbol']) for x in o if x.get('kind')=='completion'])
                rows.append(m);p.to_csv(out/f'{case}-path.csv')
                (out/f'{case}-orders.json').write_text(json.dumps(o))
                (out/f'{case}-campaigns.json').write_text(json.dumps(dict(closed=c,open=s)))
                (out/'results.json').write_text(json.dumps(rows,indent=2))
                print(case,round(m['total_shadow_return']*100,3),round(m['max_shadow_drawdown']*100,3),'completions',len(m['completion_events']),flush=True)


if __name__=='__main__':main()
