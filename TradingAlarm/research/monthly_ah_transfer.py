import json
from build_stock_features import ROOT
from hk_extension import load_extended
from monthly_ah_engine import run
from campaign_completion_ledger_audit import reconcile


def main():
    out=ROOT/'results/monthly-ah-etf-transfer';protocol=json.loads((out/'protocol.json').read_text());assets,_=load_extended();results=[]
    for i,(start,end) in enumerate(protocol['periods']):
        for scenario,cost,fx,delay in [('base',15,10,0),('cost2',30,20,0),('delay1',15,10,1)]:
            for policy in ('monthly','score_change'):
                m,p,o,d=run(assets,start,end,policy,cost,fx,delay);check=reconcile(assets,p,o,cost,fx)
                case=f'{i}-{scenario}-{policy}'
                if policy=='score_change':
                    for order in o:
                        ds=[x for x in d if order['signal_date']<x['date']<=order['date']];assert len(ds)==1
                        j=d.index(ds[0]);s=order['symbol'];assert j==0 or d[j]['scores'][s]!=d[j-1]['scores'][s]
                p.to_parquet(out/f'{case}-path.parquet')
                (out/f'{case}-orders.json').write_text(json.dumps(o,indent=2));(out/f'{case}-decisions.json').write_text(json.dumps(d,indent=2))
                r=dict(case=case,period=i,scenario=scenario,policy=policy,**m,ledger=check);results.append(r)
                (out/'results.json').write_text(json.dumps(results,indent=2));print(r,flush=True)

if __name__=='__main__':main()
