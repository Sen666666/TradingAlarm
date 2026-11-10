"""Signal opportunity diagnostics only: fractional total-return-price positions.
Not an executable portfolio: distributions implicitly reinvested; no FX/lot/minfee model.
"""
import json
import numpy as np
import pandas as pd
from sector_factors import expanded_assets
from portfolio_engine import trend_gate
from portfolio_data import ROOT

def channel(frame,exit_window):
 enter=frame.close>frame.high.shift().rolling(55).max()
 leave=frame.close<frame.low.shift().rolling(exit_window).min()
 held=False;state=[]
 for buy,sell in zip(enter,leave):
  if sell:held=False
  elif buy:held=True
  state.append(held)
 return pd.Series(state,index=frame.index)

def episodes(frame,gate,start='2022-01-01'):
 # Prior close decides current open; no entry with zero reported volume.
 active=gate.shift().fillna(False).astype(bool);opened=None;trades=[]
 for date,row in frame.loc[start:].iterrows():
  if row.get('volume',1)<=0:continue
  if opened and not active.loc[date]:
   trades.append(dict(entry_date=str(opened[0].date()),exit_date=str(date.date()),
       net_return=float(row.open*.9985/(opened[1]*1.0015)-1),closed=True))
   opened=None
  elif opened is None and active.loc[date]:opened=(date,row.open)
 if opened:
  trades.append(dict(entry_date=str(opened[0].date()),exit_date=None,
    net_return=float(frame.close.iloc[-1]/(opened[1]*1.0015)-1),closed=False))
 return trades

def main():
 records=[]
 for n,a in expanded_assets().items():
  if a['kind']!='equity':continue
  f=a['signal']
  for name,g in [('sma200',trend_gate(f)),('channel55_20',channel(f,20)),('channel55_55',channel(f,55))]:
   trades=episodes(f,g);closed=[t['net_return'] for t in trades if t['closed']]
   records.append({'symbol':n,'signal':name,'episodes':trades,'closed_count':len(closed),
      'closed_win_rate':float(np.mean(np.array(closed)>0)) if closed else None,
      'best_closed_return':max(closed) if closed else None,
      'closed_above80':sum(x>=.8 for x in closed),
      'open_above80':sum(t['net_return']>=.8 for t in trades if not t['closed'])})
 out={'status':'Signal diagnostic, not account returns or deployable backtest',
 'purpose':'Distinguish lack of large asset opportunities from failure to hold the large winners.',
 'caveats':['Local currency total-return OHLC, fractional positions','15bps entry/exit only; no lot,minfee,liquidity participation,FX or actual dividend payment delay','Closed and open episodes separated; a mark-to-market gain can reverse','Exit55 is a mechanism comparison, not an optimized threshold'], 'records':records}
 (ROOT/'results/tail-signal-audit.json').write_text(json.dumps(out,indent=2))
 for signal in ['sma200','channel55_20','channel55_55']:
  rows=[r for r in records if r['signal']==signal]
  print(signal,'closed>80%',sum(r['closed_above80'] for r in rows),'open>80%',sum(r['open_above80'] for r in rows),'closed trades',sum(r['closed_count'] for r in rows))
if __name__=='__main__':main()
