"""Transfer frozen rules to existing HK samples without parameter search."""
import json
import numpy as np
import pandas as pd
from hk_stock_account_pilot import ROOT, load, run, baselines
OUT=ROOT/'results/hk-stock-rule-transfer'

def targets_for(parent,events,fx):
 parent=parent.loc['2020-01-01':].copy()
 cash=pd.Series(0.,index=parent.index)
 for e in events:
  if e['ex'] in cash.index:
   rate=float(fx.loc[e['ex']]) if e['currency']=='USD' else 1.
   if not np.isfinite(rate) or rate<=0:raise ValueError('missing ex-date FX')
   cash.loc[e['ex']]+=e['amount']*rate
 gross=(parent.close+cash)/parent.close.shift()
 level=parent.close.iloc[0]*gross.fillna(1).cumprod()
 signal=parent.copy()
 for col in ['open','high','low','close']:signal[col]*=level/parent.close
 targets=baselines(signal)
 vol=np.log(signal.close).diff().rolling(60).std()*np.sqrt(252)
 targets['sma200_vol15']=targets.sma200*(.15/vol).clip(upper=1).fillna(0)
 return targets

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'symbols':['09618','03690'],'start':'2022-01-01','rules':['buy_hold','sma200','donchian55_20','sma200_vol15'],'cost_bps_per_side':[20,40],'minimum_fee_hkd':18,'order_increment_shares':100,'status':'Conditional transfer experiment; no parameter optimization','limitations':['Retrospectively selected surviving internet stocks, not representative HK or A-share universe','Vendor raw prices and corporate action completeness not independently certified','100-share research order increment, not verified dated exchange board lots','Daily open fill, no dated taxes, spread, capacity or suspension-history verification','USD dividends converted with lagged ECB FX; payment dates from vendor','Previously viewed sample, not untouched out-of-sample validation']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 f=json.loads((ROOT/'data/hk-stock-pilot/usd-hkd.json').read_text())
 if f['base']!='USD':raise ValueError('wrong FX base')
 source=pd.Series({pd.Timestamp(d)+pd.Timedelta(days=1):v['HKD'] for d,v in f['rates'].items()}).sort_index()
 result=[]
 for code in protocol['symbols']:
  parent,events=load(code);idx=parent.index
  fx=source.reindex(source.index.union(idx)).ffill().reindex(idx)
  targets=targets_for(parent,events,fx)
  for name in protocol['rules']:
   for cost in protocol['cost_bps_per_side']:
    m,p,o=run({code:parent},{code:events},fx,targets[name],cost_bps=cost,primary=code)
    m.update(symbol=code,strategy=name,cost_bps=cost);result.append(m)
    p.to_csv(OUT/f'{code}-{name}-cost{cost}-path.csv')
    (OUT/f'{code}-{name}-cost{cost}-orders.json').write_text(json.dumps(o))
 (OUT/'results.json').write_text(json.dumps(result,indent=2))
 print(pd.DataFrame(result)[['symbol','strategy','cost_bps','cagr','max_drawdown','best252']].to_string(index=False))
if __name__=='__main__':main()
