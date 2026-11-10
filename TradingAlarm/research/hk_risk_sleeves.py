"""Three independent funded sleeves; conditional account experiment, no leverage."""
import json
import numpy as np
import pandas as pd
from hk_holding_horizon import ROOT,load,run,adjusted_signal
OUT=ROOT/'results/hk-risk-sleeves'

def targets(signal,risk=False,stop=False):
 high=signal.high.shift().rolling(55).max();low=signal.low.shift().rolling(20).min()
 tr=pd.concat([signal.high-signal.low,(signal.high-signal.close.shift()).abs(),(signal.low-signal.close.shift()).abs()],axis=1).max(axis=1)
 atr=tr.rolling(20).mean();held=False;weight=0.;floor=0.;values=[]
 for dt,c,h,l,a in zip(signal.index,signal.close,high,low,atr):
  if dt<pd.Timestamp('2021-12-31'):values.append(0.);continue
  if held and (c<l or (stop and c<=floor)):held=False;weight=0.
  elif not held and c>h and np.isfinite(a) and a>0:
   held=True;weight=min(1.,.015/(2*a/c)) if risk else 1.;floor=c-2*a
  values.append(weight)
 return pd.Series(values,index=signal.index)

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'capital':'HKD3million split equally into three HKD1million sleeves, no transfers or portfolio rebalancing','symbols':['00700','09618','03690'],'rules':['full_breakout','risk_breakout','risk_breakout_stop'],'entry':'Prior55high breakout; state reset at2021-12-31, trade next raw open','exit':'Prior20low close break, plus optional entry signal-close minus2ATR fixed stop','risk':'Target fraction min(1,1.5%/(2*ATR20/signalclose)) within each sleeve, frozen per entry; initial equivalent0.5% whole-account planned signal risk, NOT a loss bound','cost_bps':[20,40],'limitations':['Three retrospectively chosen correlated surviving stocks, not broad A/HK validation','Equal funded sleeves cannot reallocate idle cash; weights drift with sleeve returns','Daily fraction rebalancing, entry-open gap and close-confirmed stops change actual risk','Inherited vendor cash dates, in-kind claims/fraction assumptions, unverified dated lots/taxes/fill model','No 20% drawdown guarantee; best252 is a rolling window, not a predefined bull-market campaign']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 loaded={c:load(c) for c in protocol['symbols']};raw={c:v[0] for c,v in loaded.items()};events={c:v[1] for c,v in loaded.items()}
 f=json.loads((ROOT/'data/hk-stock-pilot/usd-hkd.json').read_text());assert f['base']=='USD'
 src=pd.Series({pd.Timestamp(d)+pd.Timedelta(days=1):v['HKD'] for d,v in f['rates'].items()}).sort_index()
 paths={};sleeves=[]
 for code in raw:
  idx=raw[code].index;fx=src.reindex(src.index.union(idx)).ffill().reindex(idx);signal=adjusted_signal(code,raw,events,fx)
  for name,risk,stop in [('full_breakout',False,False),('risk_breakout',True,False),('risk_breakout_stop',True,True)]:
   target=targets(signal,risk,stop)
   for cost in protocol['cost_bps']:
    m,p,o=run(raw,events,fx,target,cost_bps=cost,primary=code)
    m.update(symbol=code,strategy=name,cost_bps=cost);sleeves.append(m);paths[(name,cost,code)]=p
    p.to_csv(OUT/f'{code}-{name}-{cost}.csv')
 results=[]
 for name in protocol['rules']:
  for cost in protocol['cost_bps']:
   parts=[paths[(name,cost,c)] for c in protocol['symbols']]
   if not all(p.index.equals(parts[0].index) for p in parts):raise ValueError('calendar mismatch; do not silently intersect')
   nav=sum(p.nav for p in parts)/3;dd=nav/nav.cummax().clip(lower=1)-1;years=(nav.index[-1]-nav.index[0]).days/365.25
   m=dict(strategy=name,cost_bps=cost,cagr=float(nav.iloc[-1]**(1/years)-1),max_drawdown=float(dd.min()),best252=float(nav.pct_change(252).max()),total_return=float(nav.iloc[-1]-1),fees_hkd=float(sum(p.fee.sum() for p in parts)))
   results.append(m);pd.DataFrame({'nav':nav,'drawdown':dd}).to_csv(OUT/f'portfolio-{name}-{cost}.csv')
 (OUT/'results.json').write_text(json.dumps(results,indent=2));(OUT/'sleeves.json').write_text(json.dumps(sleeves,indent=2))
 print(pd.DataFrame(results).to_string(index=False))
if __name__=='__main__':main()
