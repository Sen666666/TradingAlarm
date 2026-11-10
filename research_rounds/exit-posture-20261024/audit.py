"""Independent fill replay, account identities and actual matched-entry audit."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
R=Path(__file__).resolve().parent;O=R/'results/v0'
def main():
 summary=pd.read_csv(O/'summary.csv');fail=[];maxerr=0.;checks=0
 for x in summary.to_dict('records'):
  folder=O/'accounts'/x['key'];l=pd.read_parquet(folder/'ledger.parquet');f=pd.read_csv(folder/'fills.csv');t=pd.read_csv(folder/'trades.csv');d=pd.read_parquet(R/'inputs'/f"{x['symbol']}.parquet")
  cash=1.;qty=0.;nav=[];cost=2 if x['scenario']=='cost2' else 1;fee=(.0002 if x['symbol']=='AU0' else .0005)*cost
  for dt,row in l.iterrows():
   fs=f.loc[f.date==str(dt.date())]
   for fill in fs.to_dict('records'):
    raw=float(d.loc[dt,'close' if fill['signal_date']=='preset_end' else 'open']);slip=.04*cost if x['symbol']=='AU0' else raw*.0005*cost
    px=raw+slip if fill['side']=='buy' else raw-slip
    np.testing.assert_allclose([fill['raw_price'],fill['price'],fill['fee']],[raw,px,fill['quantity']*px*fee],rtol=2e-11,atol=2e-12)
    if fill['side']=='buy':
     assert qty==0;qty=cash/(px*(1+fee));cash-=qty*px*(1+fee)
     np.testing.assert_allclose(qty,fill['quantity'],rtol=1e-10)
    else:
     np.testing.assert_allclose(qty,fill['quantity'],rtol=1e-10);cash+=qty*px*(1-fee);qty=0.
    sig=fill['signal_date']
    if sig not in ['preset_start','preset_end']:
     si=d.index.get_loc(pd.Timestamp(sig));ti=d.index.get_loc(dt);assert ti>si
     # All non-forced orders obey one/two following observed opens; matched force exit may be earlier than an extra delayed order.
     assert ti-si==(2 if x['scenario']=='delay1' else 1),(x['key'],fill)
    checks+=1
   nv=cash+qty*d.loc[dt,'close'];nav.append(nv)
   np.testing.assert_allclose([nv,cash,qty],[row.nav,row.cash,row.quantity],rtol=2e-10,atol=2e-11)
  nav=np.array(nav);err=float(np.max(np.abs(nav-l.nav.to_numpy())));maxerr=max(maxerr,err)
  dd=1-nav/np.maximum.accumulate(np.r_[1.,nav])[1:]
  np.testing.assert_allclose([nav[-1]-1,dd.max(),t.net_pnl.sum(),np.prod(1+t.net_return)-1],[x['net_return'],x['max_drawdown'],x['net_return'],x['net_return']],rtol=1e-10,atol=1e-11)
  assert int(t.net_return.gt(0).sum())==x['wins'] and len(t)==x['trades']
  if x['mode']=='M':
   bt=pd.read_csv(O/'accounts'/x['key'].replace('__M__'+x['policy'],'__P__E0')/'trades.csv')
   assert t.entry_date.tolist()==bt.entry_date.tolist();np.testing.assert_allclose(t.entry_price,bt.entry_price,rtol=0,atol=0)
   assert (pd.to_datetime(t.exit_date)<=pd.to_datetime(bt.exit_date)).all()
 assert len(summary)==507
 prefix=pd.read_csv(O/'prefix-checks.csv');assert prefix.passed.all()
 report={'accounts':len(summary),'independently_replayed_fills':checks,'max_nav_error':maxerr,'exact_prefix_checks':len(prefix),'locked_entry_accounts':int(summary['mode'].eq('M').sum()),'failed':fail,'raw_review_reference_erratum':'raw-review.json page names review-1..4 should read raw-1..4; all four actual PNGs frozen and viewed before run','passed':True}
 (O/'audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
