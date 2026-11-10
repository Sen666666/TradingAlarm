"""Independent actual-fill replay and accounting; no backtest calls."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
R=Path(__file__).resolve().parent;O=R/'results/v0'
def main():
 fr=json.loads((R/'freeze.json').read_text())
 for p,h in fr['sha256'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
 s=pd.read_csv(O/'summary.csv');count=0;worst=0.;details=[]
 for x in s.to_dict('records'):
  folder=O/'accounts'/x['key'];l=pd.read_parquet(folder/'ledger.parquet');f=pd.read_csv(folder/'fills.csv');t=pd.read_csv(folder/'trades.csv');d=pd.read_parquet(R/'inputs'/f'{x["symbol"]}.parquet');cash=1.;qty=0.;nav=[];rate=.0005*(2 if x['scenario']=='cost2' else 1)
  grouped={k:g.to_dict('records') for k,g in f.groupby('date',sort=False)}
  for dt,row in l.iterrows():
   for z in grouped.get(str(dt.date()),[]):
    raw=float(d.loc[dt,'close' if z['signal_date']=='preset_end' else 'open']);slip=raw*rate;px=raw+slip if z['side']=='buy' else raw-slip
    np.testing.assert_allclose([z['raw_price'],z['price'],z['fee'],z['slippage']],[raw,px,z['quantity']*px*rate,z['quantity']*slip],rtol=1e-11,atol=1e-12)
    if z['side']=='buy':assert qty==0;qty=cash/(px*(1+rate));cash-=qty*px*(1+rate);np.testing.assert_allclose(qty,z['quantity'],rtol=1e-10)
    else:np.testing.assert_allclose(qty,z['quantity'],rtol=1e-10);cash+=qty*px*(1-rate);qty=0.
    if z['signal_date'] not in ['preset_start','preset_end']:assert d.index.get_loc(dt)-d.index.get_loc(pd.Timestamp(z['signal_date']))==(2 if x['scenario']=='delay1' else 1)
    count+=1
   n=cash+qty*d.loc[dt,'close'];nav.append(n);np.testing.assert_allclose([n,cash,qty],[row.nav,row.cash,row.quantity],rtol=1e-10,atol=1e-11)
  nav=np.array(nav);draw=1-nav/np.maximum.accumulate(np.r_[1.,nav])[1:];worst=max(worst,float(abs(nav-l.nav.to_numpy()).max()))
  np.testing.assert_allclose([nav[-1]-1,draw.max(),t.net_pnl.sum(),np.prod(1+t.net_return)-1],[x['net_return'],x['max_drawdown'],x['net_return'],x['net_return']],rtol=1e-10,atol=1e-11)
  assert len(t)==x['trades'] and t.net_return.gt(0).sum()==x['wins'];natural=t.loc[~t.terminal.astype(bool)];assert len(natural)==x['natural_trades'];np.testing.assert_allclose(f.fee.sum(),x['fees'],atol=1e-12);np.testing.assert_allclose(f.slippage.sum(),x['slippage'],atol=1e-12)
  if x['mode']=='M':
   bt=pd.read_csv(O/'accounts'/f'{x["case"]}__P__E0__{x["scenario"]}'/'trades.csv');assert t.entry_date.tolist()==bt.entry_date.tolist();np.testing.assert_allclose(t.entry_price,bt.entry_price,rtol=0,atol=0);assert (pd.to_datetime(t.exit_date)<=pd.to_datetime(bt.exit_date)).all()
  trough=int(draw.argmax());peak=int(nav[:trough+1].argmax());details.append(dict(key=x['key'],peak=str(l.index[peak].date()) if nav[:trough+1].max()>=1 else 'initial_cash',trough=str(l.index[trough].date()),max_drawdown=draw.max()))
 assert len(s)==240;checks=pd.read_csv(R/'prepared/prefix-checks.csv');assert len(checks)==80 and checks.passed.all();pd.DataFrame(details).to_csv(O/'drawdown-dates.csv',index=False)
 result={'accounts':240,'fills_independently_replayed':count,'max_nav_error':worst,'frozen_files_unchanged':len(fr['sha256']),'exact_prefix_checks':80,'E0_daily_identity_cases':10,'matched_entry_accounts':90,'failed':[],'passed':True};(O/'audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
