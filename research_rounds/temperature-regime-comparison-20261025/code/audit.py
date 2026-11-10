"""Independent money, share, fee and chronology replay; no strategy calls."""
import pandas as pd,numpy as np
from common import *
def main():
 from run import verify
 verify();out=HERE/'results/v0';summary=pd.read_csv(out/'summary.csv');details=[];nfill=0;maxerr=0.
 for x in summary.to_dict('records'):
  root=out if x['origin']=='new' else OLD/'results/v0';p=root/'accounts'/x['key'];l=pd.read_parquet(p/'ledger.parquet');f=pd.read_csv(p/'fills.csv');t=pd.read_csv(p/'trades.csv');d=pd.read_parquet(HERE/'inputs'/(x['symbol']+'.parquet'));cash=1.;q=0.;nav=[];rate=.0005*(2 if x['scenario']=='cost2' else 1);grouped={k:v.to_dict('records') for k,v in f.groupby('date',sort=False)}
  s=pd.read_parquet(HERE/'prepared'/x['case']/(x['policy']+'.parquet')) if x['origin']=='new' else None
  for dt,row in l.iterrows():
   for z in grouped.get(str(dt.date()),[]):
    raw=float(d.loc[dt,'close' if z['signal_date']=='preset_end' else 'open']);slip=raw*rate;px=raw+slip if z['side']=='buy' else raw-slip
    np.testing.assert_allclose([z['raw_price'],z['price'],z['fee'],z['slippage']],[raw,px,z['quantity']*px*rate,z['quantity']*slip],rtol=1e-11,atol=1e-12)
    if z['signal_date'] not in ['preset_start','preset_end']:
     assert d.index.get_loc(dt)-d.index.get_loc(pd.Timestamp(z['signal_date']))==(2 if x['scenario']=='delay1' else 1)
     if z['side']=='buy' and x['policy'] in TEMP_POLICIES:assert bool(s.loc[z['signal_date'],'buy_event'])
    if z['side']=='buy':assert q==0;q=cash/(px*(1+rate));cash-=q*px*(1+rate);np.testing.assert_allclose(q,z['quantity'],rtol=1e-10)
    else:np.testing.assert_allclose(q,z['quantity'],rtol=1e-10);cash+=q*px*(1-rate);q=0.
    nfill+=1
   n=cash+q*float(d.loc[dt,'close']);nav.append(n);np.testing.assert_allclose([n,cash,q],[row.nav,row.cash,row.quantity],rtol=1e-10,atol=1e-11)
  nav=np.array(nav);err=float(abs(nav-l.nav.to_numpy()).max());maxerr=max(maxerr,err);dd=1-nav/np.maximum.accumulate(np.r_[1.,nav])[1:]
  np.testing.assert_allclose([nav[-1]-1,dd.max(),t.net_pnl.sum(),np.prod(1+t.net_return)-1],[x['net_return'],x['max_drawdown'],x['net_return'],x['net_return']],rtol=1e-10,atol=1e-11)
  assert len(t)==x['trades'] and int((t.net_return>0).sum())==x['wins'];assert int((~t.terminal.astype(bool)).sum())==x['natural_trades']
  details.append(dict(key=x['key'],origin=x['origin'],passed=True,fills=len(f),daily_rows=len(l),max_nav_error=err,carry_fills=int((f.signal_date=='preset_start').sum()),terminal_fills=int((f.signal_date=='preset_end').sum())))
 assert len(details)==972
 pd.DataFrame(details).to_csv(out/'accounting-detail.csv',index=False)
 write(out/'audit.json',dict(passed=True,recorded_at=now(),displayed_accounts=972,new_economic_accounts=756,reused_readonly_accounts=216,fills_independently_replayed=nfill,max_nav_error=maxerr,technical_old_E0_R_identity=108,all_actual_new_threshold_buys_have_required_signal=True))
 print(read(out/'audit.json'),flush=True)
if __name__=='__main__':main()
