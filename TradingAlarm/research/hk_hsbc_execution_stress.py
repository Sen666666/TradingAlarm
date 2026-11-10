"""Predefined execution stress; no strategy parameter search or winner selection."""
import json
import pandas as pd
from hk_stock_account_pilot import ROOT,load,run
from hk_stock_rule_transfer import targets_for
OUT=ROOT/'results/hk-hsbc-execution-stress'
def main():
 OUT.mkdir(exist_ok=True)
 protocol=dict(symbol='00005',start='2022-03-07',rule='sma200',increments=[100,400],signal_lags=[1,2],cost_bps=[20,40],lot_evidence='https://www1.hkexnews.hk/listedco/listconews/sehk/1999/0420/ltn19990420022.htm',limitations=['1999 official 400-share lot evidence; continuous dated history not certified','Same retrospective survivor and data, not independent validation','Dividend dates/currency and raw price source not fully audited','Best252 is rolling window, not predefined bull episode'])
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 raw,events=load('00005');f=json.loads((ROOT/'data/hk-stock-pilot/usd-hkd.json').read_text());assert f['base']=='USD'
 src=pd.Series({pd.Timestamp(d)+pd.Timedelta(days=1):v['HKD'] for d,v in f['rates'].items()}).sort_index();fx=src.reindex(src.index.union(raw.index)).ffill().reindex(raw.index)
 target=targets_for(raw,events,fx)['sma200'];results=[]
 for lot in protocol['increments']:
  for lag in protocol['signal_lags']:
   for cost in protocol['cost_bps']:
    m,p,o=run({'00005':raw},{'00005':events},fx,target,cost_bps=cost,primary='00005',start=protocol['start'],order_increment=lot,signal_lag=lag)
    assert all(x['delta']%lot==0 and raw.index.get_loc(pd.Timestamp(x['date']))-raw.index.get_loc(pd.Timestamp(x['signal_date']))==lag for x in o)
    m.update(order_increment=lot,signal_lag=lag,cost_bps=cost);results.append(m)
    name=f'lot{lot}-lag{lag}-cost{cost}';p.to_csv(OUT/f'{name}-path.csv');(OUT/f'{name}-orders.json').write_text(json.dumps(o,indent=2))
 baseline=json.loads((ROOT/'results/hk-noninternet-transfer/baseline-results.json').read_text())
 for r in results:
  if r['order_increment']==100 and r['signal_lag']==1:
   old=next(x for x in baseline if x['symbol']=='00005' and x['strategy']=='sma200' and x['cost_bps']==r['cost_bps'])
   for key in ['cagr','max_drawdown','best252','total_return','orders','fees']:assert r[key]==old[key],key
 (OUT/'results.json').write_text(json.dumps(results,indent=2));print(pd.DataFrame(results)[['order_increment','signal_lag','cost_bps','cagr','max_drawdown','best252','orders']].to_string(index=False))
if __name__=='__main__':main()
