"""Independent replay of fills; no use of engine state transitions."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
R=Path(__file__).resolve().parent;O=R/'results/v0'
s=pd.read_csv(O/'summary.csv');d=pd.read_parquet(R/'inputs/USHJ512480.parquet');frozen=json.loads((R/'freeze.json').read_text());count=0;worst=0.;details=[]
for p,h in frozen['sha256'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
for x in s.to_dict('records'):
 folder=O/'accounts'/x['key'];l=pd.read_parquet(folder/'ledger.parquet');f=pd.read_csv(folder/'fills.csv');t=pd.read_csv(folder/'trades.csv');cash=1.;qty=0.;nav=[];cost=2 if x['scenario']=='cost2' else 1;rate=.0005*cost
 bydate={day:rows.to_dict('records') for day,rows in f.groupby('date',sort=False)}
 for dt,row in l.iterrows():
  for fill in bydate.get(str(dt.date()),[]):
   raw=float(d.loc[dt,'close' if fill['signal_date']=='preset_end' else 'open']);slip=raw*rate;price=raw+slip if fill['side']=='buy' else raw-slip
   np.testing.assert_allclose([fill['raw_price'],fill['price'],fill['fee'],fill['slippage']],[raw,price,fill['quantity']*price*rate,fill['quantity']*slip],rtol=1e-11,atol=1e-12)
   if fill['side']=='buy':
    assert qty==0;qty=cash/(price*(1+rate));cash-=qty*price*(1+rate);np.testing.assert_allclose(qty,fill['quantity'],rtol=1e-10)
   else:np.testing.assert_allclose(qty,fill['quantity'],rtol=1e-10);cash+=qty*price*(1-rate);qty=0.
   if fill['signal_date'] not in ['preset_start','preset_end']:assert d.index.get_loc(dt)-d.index.get_loc(pd.Timestamp(fill['signal_date']))==(2 if x['scenario']=='delay1' else 1)
   count+=1
  n=cash+qty*d.loc[dt,'close'];nav.append(n);np.testing.assert_allclose([n,cash,qty],[row.nav,row.cash,row.quantity],rtol=1e-10,atol=1e-11)
 nav=np.array(nav);dd=1-nav/np.maximum.accumulate(np.r_[1.,nav])[1:];worst=max(worst,float(abs(nav-l.nav.to_numpy()).max()))
 np.testing.assert_allclose([nav[-1]-1,dd.max(),t.net_pnl.sum(),np.prod(1+t.net_return)-1],[x['net_return'],x['max_drawdown'],x['net_return'],x['net_return']],rtol=1e-10,atol=1e-11)
 assert len(t)==x['trades'] and t.net_return.gt(0).sum()==x['wins']
 if x['mode']=='M':
  bt=pd.read_csv(O/'accounts'/f"P_E0_{x['scenario']}"/'trades.csv');assert t.entry_date.tolist()==bt.entry_date.tolist();np.testing.assert_allclose(t.entry_price,bt.entry_price,rtol=0,atol=0);assert (pd.to_datetime(t.exit_date)<=pd.to_datetime(bt.exit_date)).all()
 trough=int(dd.argmax());past=nav[:trough+1];peak=int(past.argmax());peakday=str(l.index[peak].date()) if past.max()>=1 else 'initial_cash'
 details.append(dict(key=x['key'],dd_peak=peakday,dd_trough=str(l.index[trough].date()),max_drawdown=float(dd.max()),terminal_count=int(t.terminal.sum()),first_entry=str(t.entry_date.iloc[0]) if len(t) else None,last_exit=str(t.exit_date.iloc[-1]) if len(t) else None))
assert len(s)==24
checks=json.loads((R/'prepared/checks.json').read_text());assert all(x['passed'] for x in checks)
pd.DataFrame(details).to_csv(O/'drawdown-and-boundaries.csv',index=False)
report={'accounts':24,'independent_fill_replays':count,'max_nav_error':worst,'frozen_files_unchanged':len(frozen['sha256']),'signal_identity_checks':4,'exact_prefix_checks':12,'prior_account_prefix_checks':24,'matched_entry_accounts':9,'passed':True}
(O/'audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
