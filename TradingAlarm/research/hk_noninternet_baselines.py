"""Frozen baseline transfer with explicit provisional cash/lot assumptions."""
import json
import pandas as pd
from hk_stock_account_pilot import ROOT,load,run
from hk_stock_rule_transfer import targets_for
OUT=ROOT/'results/hk-noninternet-transfer'
def main():
 freeze=json.loads((OUT/'freeze.json').read_text())
 protocol={'symbols':freeze['symbols'],'start':freeze['earliest_evaluation'],'rules':['buy_hold','sma200','donchian55_20','sma200_vol15'],'cost_bps':[20,40],'cash_policy':'All declared components accrue on exdate; vendorpaydate cash release; USD converted usinglaggedECBFX with10bps haircut; currency alternatives not doublecounted','order_increment':100,'limitations':['100share research increment NOT verified dated boardlot, some orders may require oddlot execution','Dates/amounts only selectively issuer-checked, not complete tax/cashcertification','Four retrospectively chosen surviving stocks, historicalindexmembership unverified','No parameter fitting; no crossmarketvalidatedstrategy claim']}
 (OUT/'baseline-protocol.json').write_text(json.dumps(protocol,indent=2))
 f=json.loads((ROOT/'data/hk-stock-pilot/usd-hkd.json').read_text());assert f['base']=='USD'
 src=pd.Series({pd.Timestamp(d)+pd.Timedelta(days=1):v['HKD'] for d,v in f['rates'].items()}).sort_index();results=[]
 for code in freeze['symbols']:
  raw,events=load(code);idx=raw.index;fx=src.reindex(src.index.union(idx)).ffill().reindex(idx);targets=targets_for(raw,events,fx)
  for rule in protocol['rules']:
   for cost in protocol['cost_bps']:
    m,p,o=run({code:raw},{code:events},fx,targets[rule],cost_bps=cost,primary=code,start=protocol['start']);m.update(symbol=code,strategy=rule,cost_bps=cost);results.append(m);p.to_csv(OUT/f'{code}-{rule}-{cost}-path.csv')
 (OUT/'baseline-results.json').write_text(json.dumps(results,indent=2));print(pd.DataFrame(results).query('cost_bps==20')[['symbol','strategy','cagr','max_drawdown','best252']].to_string(index=False))
if __name__=='__main__':main()
