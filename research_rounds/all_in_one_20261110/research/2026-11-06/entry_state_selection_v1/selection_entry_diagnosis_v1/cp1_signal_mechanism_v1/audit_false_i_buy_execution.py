
from pathlib import Path
import pandas as pd,numpy as np,json
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1')
raw={x['series_id']:x['raw']['path'] for x in json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json').read_text())['series']}
a=pd.read_csv(O/'FALSE_I_BUY_FIRST_MOBILE_FEATURES.csv')
rows=[]
for sid,g in a.groupby('sid'):
 f=pd.read_parquet(raw[sid]);f.index=pd.to_datetime(f.trade_date)
 for q in g.itertuples():
  z=dict(account=q.account,sid=sid,year=q.year,signal_day=q.signal_day,entry_day=q.entry_day,round_pnl=q.round_pnl,closed=q.closed,closed_in_entry_year=q.closed_in_entry_year,raw_path=raw[sid])
  for tag,day in [('signal',q.signal_day),('entry',q.entry_day)]:
   d=pd.Timestamp(day)
   if d not in f.index: z[tag+'_bar_missing']=True;continue
   r=f.loc[d];i=f.index.get_loc(d);prev=f.iloc[i-1]if i>0 else None
   for c in ['open','high','low','close','amount','volume']:z[tag+'_'+c]=r[c]
   z[tag+'_one_price_bar']=bool(np.isclose(float(r.high),float(r.low),rtol=0,atol=1e-8))
   z[tag+'_one_price_up']=bool(z[tag+'_one_price_bar']and prev is not None and float(r.close)>float(prev.close)*(1+1e-8))
   z[tag+'_prev_trading_observation']=str(f.index[i-1].date())if i>0 else None
   z[tag+'_calendar_gap']=int((d-f.index[i-1]).days)if i>0 else None
  rows.append(z)
r=pd.DataFrame(rows);r.to_csv(O/'FALSE_I_BUY_RAW_EXECUTION_FLAGS.csv',index=False)
print('ONE PRICE UP ENTRY (not proof no fill, not knowledge at prior close)')
cols=['sid','year','signal_day','entry_day','round_pnl','closed','entry_open','entry_amount','signal_calendar_gap']
print(r[r.entry_one_price_up][cols].to_string(index=False))
s=[]
for y,g in r.groupby('year'):
 g=g[g.closed&((g.year!=2022)|g.closed_in_entry_year)]
 s.append(dict(year=y,n=len(g),original_pnl=g.round_pnl.sum(),one_price_up_n=g.entry_one_price_up.sum(),one_price_up_pnl=g.loc[g.entry_one_price_up,'round_pnl'].sum(),other_n=(~g.entry_one_price_up).sum(),other_pnl=g.loc[~g.entry_one_price_up,'round_pnl'].sum()))
pd.DataFrame(s).to_csv(O/'FALSE_I_BUY_RAW_EXECUTION_SENSITIVITY.csv',index=False);print(pd.DataFrame(s).to_string(index=False))
