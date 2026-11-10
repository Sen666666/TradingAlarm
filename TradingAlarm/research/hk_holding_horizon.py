"""Predeclared 10/20-session time caps versus unchanged trend exit."""
import json
import pandas as pd
from hk_stock_account_pilot import ROOT,load,run,IN_KIND,baselines
OUT=ROOT/'results/hk-holding-horizon'

def capped_breakout(signal,cap=None):
 high=signal.high.shift().rolling(55).max();low=signal.low.shift().rolling(20).min()
 held=False;age=0;values=[]
 for c,h,l in zip(signal.close,high,low):
  if held:
   age+=1
   if c<l or (cap is not None and age>=cap):held=False;age=0
  elif c>h:held=True;age=0
  values.append(float(held))
 return pd.Series(values,index=signal.index)

def adjusted_signal(code,raw,events,fx):
 parent=raw[code].loc['2020-01-01':].copy();cash=pd.Series(0.,index=parent.index)
 for e in events[code]:
  if e['ex'] in cash.index:cash.loc[e['ex']]+=e['amount']*(float(fx.loc[e['ex']]) if e['currency']=='USD' else 1.)
 if code=='00700':
  for d,(child,den) in IN_KIND.items():cash.loc[d]+=raw[child].loc[d,'close']/den
 level=parent.close.iloc[0]*((parent.close+cash)/parent.close.shift()).fillna(1).cumprod()
 signal=parent.copy()
 for col in ['open','high','low','close']:signal[col]*=level/parent.close
 return signal

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'entry':'close above previous 55-session high; next open execution','exit':'previous 20-session low, with optional 10/20 held-session cap','caps':[None,10,20],'cost_bps':[20,40],'start':'2022-01-01','reentry':'earliest following close after exit signal if entry remains true; no same-close reentry','scope':'Three previously selected surviving HK internet stocks, conditional accounting only','limitations':['Same entry rule, not paired identical trades: early exits permit earlier reentry','Time cap is maximum, not mean holding time; not a reconstruction of Trend Animal','Inherited vendor actions, fee, lot and recipient claim assumptions from HK account pilot','No untouched holdout or broad A/HK evidence; best252 is not an identified market campaign']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 loaded={c:load(c) for c in ['00700','09618','03690']};raw={c:v[0] for c,v in loaded.items()};events={c:v[1] for c,v in loaded.items()}
 f=json.loads((ROOT/'data/hk-stock-pilot/usd-hkd.json').read_text());assert f['base']=='USD'
 src=pd.Series({pd.Timestamp(d)+pd.Timedelta(days=1):v['HKD'] for d,v in f['rates'].items()}).sort_index()
 results=[]
 for code in raw:
  idx=raw[code].index;fx=src.reindex(src.index.union(idx)).ffill().reindex(idx)
  signal=adjusted_signal(code,raw,events,fx)
  pd.testing.assert_series_equal(capped_breakout(signal),baselines(signal).donchian55_20,check_names=False)
  for cap in protocol['caps']:
   target=capped_breakout(signal,cap)
   for cost in protocol['cost_bps']:
    m,p,o=run(raw,events,fx,target,cost_bps=cost,primary=code)
    m.update(symbol=code,cap=cap,cost_bps=cost);results.append(m)
    p.to_csv(OUT/f'{code}-cap{cap}-cost{cost}.csv')
 (OUT/'results.json').write_text(json.dumps(results,indent=2))
 print(pd.DataFrame(results)[['symbol','cap','cost_bps','cagr','max_drawdown','best252','orders']].to_string(index=False))
if __name__=='__main__':main()
