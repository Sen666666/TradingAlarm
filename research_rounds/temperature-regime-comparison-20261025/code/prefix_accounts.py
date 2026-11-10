"""Physical bar/state truncation of the twelve event entry rules, base only."""
import pandas as pd,numpy as np
from common import *
from engine import backtest

def main():
 from run import verify
 verify();rows=[];total=0
 for c in read(HERE/'cases.json'):
  d=pd.read_parquet(HERE/'inputs'/(c['symbol']+'.parquet')).loc[c['start']:c['end']];ini=read(HERE/'prepared'/c['id']/'initial.json')
  for p in TEMP_POLICIES:
   s=pd.read_parquet(HERE/'prepared'/c['id']/(p+'.parquet'));folder=HERE/'results/v0/accounts'/('__'.join([c['id'],p,'base']));full=pd.read_parquet(folder/'ledger.parquet');fullfills=pd.read_csv(folder/'fills.csv')
   for n in [len(d)//2,len(d)-1]:
    sub=d.iloc[:n].copy();ss=s.iloc[:n].copy();_,l,_,f,_=backtest(sub,ss,ini[p],c['symbol'],SCENARIOS['base'],policy=p,entry_event_column='buy_event')
    pd.testing.assert_frame_equal(l.iloc[:-1],full.iloc[:n-1],check_exact=True,check_freq=False)
    actual=f.loc[f.signal_date.ne('preset_end')].reset_index(drop=True);expected=fullfills.loc[(fullfills.date<=str(sub.index[-1].date()))&fullfills.signal_date.ne('preset_end')].reset_index(drop=True)
    pd.testing.assert_frame_equal(actual,expected,check_exact=False,check_dtype=False,rtol=1e-11,atol=1e-12)
    last=l.iloc[-1];terminal=f.loc[f.signal_date.eq('preset_end')];nav=float(last.nav)
    if len(terminal):
     x=terminal.iloc[0];nav+=float(x.quantity)*(float(sub.close.iloc[-1])-float(x.price))+float(x.fee)
    np.testing.assert_allclose(nav,float(full.nav.iloc[n-1]),rtol=1e-11,atol=1e-12)
    rows.append(dict(case=c['id'],policy=p,cut=str(sub.index[-1].date()),prefix_rows=n,preterminal_daily_rows_exact=n-1,last_mark_nav_difference=abs(nav-float(full.nav.iloc[n-1])),actual_fills_matched=len(actual),passed=True));total+=n-1
  print({'prefix_case':c['id']},flush=True)
 assert len(rows)==432;pd.DataFrame(rows).to_csv(HERE/'audit/account-prefixes.csv',index=False)
 write(HERE/'audit/account-prefixes.json',dict(passed=True,recorded_at=now(),technical_account_prefix_replays=432,exact_nonterminal_daily_rows=total,terminal_fee_slippage_reversed_for_last_mark_only=True,models='twelve frozen temperature entry/exit projections, base',economic_candidates_added=0))
 print(read(HERE/'audit/account-prefixes.json'),flush=True)
if __name__=='__main__':main()
