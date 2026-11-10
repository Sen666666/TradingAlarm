"""Independent actual-fill reconstruction and causal recovery provenance."""
from pathlib import Path
import json
import pandas as pd,numpy as np
from run import verify
R=Path(__file__).resolve().parent;P=R.parent/'strategy-switching-20261024';S=R.parent/'market-regimes-exit-20261024/inputs';O=R/'results/v0'
def main():
 fr=verify();summary=pd.read_csv(O/'R1-summary.csv');count=0;worst=0.;details=[];entries=[]
 for x in summary.to_dict('records'):
  folder=O/'accounts'/x['key'];l=pd.read_parquet(folder/'ledger.parquet');f=pd.read_csv(folder/'fills.csv');t=pd.read_csv(folder/'trades.csv');d=pd.read_parquet(S/f'{x["symbol"]}.parquet');state=pd.read_parquet(R/'prepared'/x['case']/'R1.parquet');cash=1.;qty=0.;nav=[];rate=.0005*(2 if x['scenario']=='cost2' else 1)
  grouped={k:g.to_dict('records') for k,g in f.groupby('date',sort=False)}
  for dt,row in l.iterrows():
   for fill in grouped.get(str(dt.date()),[]):
    raw=float(d.loc[dt,'close' if fill['signal_date']=='preset_end' else 'open']);slip=raw*rate;px=raw+slip if fill['side']=='buy' else raw-slip
    np.testing.assert_allclose([fill['raw_price'],fill['price'],fill['fee'],fill['slippage']],[raw,px,fill['quantity']*px*rate,fill['quantity']*slip],rtol=1e-11,atol=1e-12)
    if fill['side']=='buy':assert qty==0;qty=cash/(px*(1+rate));cash-=qty*px*(1+rate);np.testing.assert_allclose(qty,fill['quantity'],rtol=1e-10)
    else:np.testing.assert_allclose(qty,fill['quantity'],rtol=1e-10);cash+=qty*px*(1-rate);qty=0.
    if fill['signal_date'] not in ['preset_start','preset_end']:assert d.index.get_loc(dt)-d.index.get_loc(pd.Timestamp(fill['signal_date']))==(2 if x['scenario']=='delay1' else 1)
    count+=1
   n=cash+qty*d.loc[dt,'close'];nav.append(n);np.testing.assert_allclose([n,cash,qty],[row.nav,row.cash,row.quantity],rtol=1e-10,atol=1e-11)
  nav=np.array(nav);draw=1-nav/np.maximum.accumulate(np.r_[1.,nav])[1:];worst=max(worst,float(abs(nav-l.nav.to_numpy()).max()))
  np.testing.assert_allclose([nav[-1]-1,draw.max(),t.net_pnl.sum(),np.prod(1+t.net_return)-1],[x['net_return'],x['max_drawdown'],x['net_return'],x['net_return']],rtol=1e-10,atol=1e-11)
  assert len(t)==x['trades'] and t.net_return.gt(0).sum()==x['wins'];natural=t.loc[~t.terminal.astype(bool)];assert len(natural)==x['natural_trades'];np.testing.assert_allclose(f.fee.sum(),x['fees'],atol=1e-12);np.testing.assert_allclose(f.slippage.sum(),x['slippage'],atol=1e-12)
  emap={};sid=0
  for dt,row in state.iterrows():
   if row.entered:sid+=1;emap[sid]=(dt,row)
  for tr in t.to_dict('records'):
   entry_type='carry';recognized='preset_start';pivot_date='';anchor_date='';anchor_floor=np.nan;pivot=np.nan;cycle=0
   if int(tr['signal_id'])>0:
    dt,row=emap[int(tr['signal_id'])];recognized=str(dt.date());entry_type=row.entry_kind;cycle=int(row.cycle_id)
    assert dt<=pd.Timestamp(tr['entry_signal'])<pd.Timestamp(tr['entry_date'])
    if row.recovery_entry:
     anchor_date=row.recovery_exit_signal;pivot_date=row.confirmed_pivot_date;anchor_floor=row.recovery_anchor_floor;pivot=row.confirmed_pivot_price
     assert pd.Timestamp(anchor_date)<pd.Timestamp(pivot_date)<dt and pivot>anchor_floor and row.shadow_target==1
    np.testing.assert_allclose(tr['initial_floor'],state.loc[pd.Timestamp(tr['entry_signal']),'floor'],atol=1e-12)
   assert tr['entry_price']/(1+rate)>tr['initial_floor']
   entries.append(dict(case=x['case'],scenario=x['scenario'],type=x['type'],role=x['role'],**tr,qualification=entry_type,recognized=recognized,recovery_exit_signal=anchor_date,pivot_date=pivot_date,pivot_price=pivot,anchor_floor=anchor_floor,cycle_id=cycle))
  trough=int(draw.argmax());peak=int(nav[:trough+1].argmax());details.append(dict(key=x['key'],peak=str(l.index[peak].date()) if nav[:trough+1].max()>=1 else 'initial_cash',trough=str(l.index[trough].date()),max_drawdown=draw.max()))
 old=pd.read_csv(P/'results/v0/summary.csv');comp=pd.read_csv(O/'comparison.csv');controls=comp[comp.reused_control.astype(bool)]
 for row in controls.to_dict('records'):
  source=old.loc[old.key.eq(row['key'])].iloc[0]
  for col in ['net_return','max_drawdown','trades','wins','natural_trades','terminal_trades','tail_pnl','ordinary_pnl','fees','slippage']:np.testing.assert_allclose(row[col],source[col],rtol=0,atol=1e-15)
 refs=pd.read_csv(O/'cash-reference.csv')
 for row in refs.to_dict('records'):
  l=pd.read_parquet(O/'cash-reference'/f"{row['case']}__{row['scenario']}.parquet");e=pd.read_parquet(P/'results/v0/accounts'/f"{row['case']}__E0__{row['scenario']}/ledger.parquet")
  np.testing.assert_allclose(l.nav,.5*e.nav+.5,atol=1e-12);np.testing.assert_allclose(l.nav,l.cash+l.quantity*l.close,atol=1e-12);np.testing.assert_allclose([l.nav.iloc[-1]-1,-l.drawdown.min()],[row['net_return'],row['max_drawdown']],atol=1e-12)
 assert len(summary)==54 and len(controls)==216 and len(refs)==54
 pd.DataFrame(entries).to_csv(O/'R1-trades-with-provenance.csv',index=False);pd.DataFrame(details).to_csv(O/'drawdown-dates.csv',index=False)
 pre=json.loads((R/'preflight.json').read_text());assert pre['passed'] and pre['exact_prefix_checks']==54
 result=dict(passed=True,new_R1_accounts=54,reused_controls_identical=216,cash_reference_paths=54,fills_independently_replayed=count,max_nav_error=worst,causal_actual_recovery_buys=int(pd.DataFrame(entries).qualification.eq('higher_trough_reentry').sum()),exact_prefix_checks=54,old_R_daily_identity_cases=18,synthetic_economic_checks=len(pre['synthetic_economic_checks']),frozen_files_unchanged=len(fr['sha256']),failed=[])
 (O/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
