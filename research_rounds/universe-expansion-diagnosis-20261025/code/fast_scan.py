from common import *
from fast_single import run,frames
import importlib.util

def old_engine():
 p=ROOT/'research_rounds/temperature-regime-comparison-20261025/code/engine.py';spec=importlib.util.spec_from_file_location('old_single_ref',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 out=HERE/'fast-diagnostics';out.mkdir(exist_ok=False);engine=old_engine();tests=[];rows=[];alltrades=[]
 # Known original continuous case, same states and carry, no newly calculated
 # trend evidence. Compare the whole NAV and every actual leg return.
 cid='continuous_USHJ512480';d=pd.read_parquet(G1/'inputs/USHJ512480.parquet').loc[START:END];s=pd.read_parquet(G1/'prepared'/cid/'G1_IX.parquet');ini=read(G1/'prepared'/cid/'initial.json')['G1_IX'];st,n,tr=run(d,s,ini);old,l,t,_,_=engine.backtest(d,s,ini,'USHJ512480',dict(cost=1,delay=1),policy='G1_IX',entry_event_column='buy_event');np.testing.assert_allclose(n,l.nav,rtol=1e-12,atol=1e-12);np.testing.assert_allclose([a['net_return'] for a in tr],t.net_return,rtol=1e-12,atol=1e-12);tests.append(dict(symbol='USHJ512480',nav_rows=len(n),trade_returns=len(tr),exact_within_1e12=True));write(out/'original-etf-continuous.json',st)
 meta=read(OLD/'inputs-v2/metadata.json');symbols=[str(s) for s in np.load(OLD/'h1/matrix.npz')['symbols'] if not str(s).startswith('URFI')]
 cols=['open','close','e0_target','e0_floor','e0_entered','e0_exited','ix_target','ix_floor','ix_entered','ix_exited','IX','grade','strength_ready','segment_id']
 for k,sid in enumerate(symbols):
  f=pd.read_parquet(IX/'signals'/f'{sid}.parquet',columns=cols)
  if f.loc[START:END].empty:rows.append(dict(symbol=sid,policy='IX',status='no_observations_in_window',industry=meta[sid]['industry']));continue
  for policy in ['E0','IX']:
   x,s,ini=frames(f,policy);st,n,tr=run(x,s,ini);rows.append(dict(symbol=sid,industry=meta[sid]['industry'],policy=policy,status='ready',first=str(x.index[0].date()),last=str(x.index[-1].date()),observations=len(x),end_observed=str(x.index[-1].date())==END,segments=int(x.segment_id.nunique()),**st))
   if k<8:
    ss=s.copy();pref='ix' if policy=='IX' else 'e0';ss['entered']=x[pref+'_entered'];ss['exited']=x[pref+'_exited'];ss['exit_line']=ss.floor;ss['entry_kind']='';ss['exit_reason']=''
    oi=dict(**ini,previous_close=float(f.iloc[f.index.searchsorted(START)-1].close) if f.index.searchsorted(START)>0 else float(x.close.iloc[0]));old,l,t,_,_=engine.backtest(x,ss,oi,sid,dict(cost=1,delay=1),policy=policy,entry_event_column='buy_event' if policy=='IX' else None);np.testing.assert_allclose(n,l.nav,rtol=1e-12,atol=1e-12);np.testing.assert_allclose([a['net_return'] for a in tr],t.net_return,rtol=1e-12,atol=1e-12);tests.append(dict(symbol=sid,policy=policy,nav_rows=len(n),trade_returns=len(tr),exact_within_1e12=True))
   for a in tr:alltrades.append(dict(symbol=sid,industry=meta[sid]['industry'],policy=policy,entry_date=str(x.index[a['entry_i']].date()),exit_date=str(x.index[a['exit_i']].date()),net_return=a['net_return'],terminal=a['terminal']))
  if (k+1)%300==0:print(dict(scanned=k+1),flush=True)
 a=pd.DataFrame(rows);a.to_csv(out/'standalone-stock-summary.csv',index=False);pd.DataFrame(alltrades).to_parquet(out/'standalone-stock-trades.parquet');summary=[]
 for policy,g in a[a.status.eq('ready')].groupby('policy'):
  summary.append(dict(scope='all_1709_standalone',policy=policy,count=len(g),mean=g.net_return.mean(),median=g.net_return.median(),positive_fraction=g.net_return.gt(0).mean(),mean_drawdown=g.max_drawdown.mean(),median_drawdown=g.max_drawdown.median(),median_trades=g.trades.median(),end_observed=g.end_observed.sum()))
  for industry in ['半导体','通信设备','银行']:
   q=g[g.industry.eq(industry)];summary.append(dict(scope=industry,policy=policy,count=len(q),mean=q.net_return.mean(),median=q.net_return.median(),positive_fraction=q.net_return.gt(0).mean(),mean_drawdown=q.max_drawdown.mean(),median_drawdown=q.max_drawdown.median(),median_trades=q.trades.median(),end_observed=q.end_observed.sum()))
 pd.DataFrame(summary).to_csv(out/'summary.csv',index=False);write(out/'operator-validation.json',dict(passed=True,tests=tests,account_runs=0,not_a_real_lot_portfolio=True));print(pd.DataFrame(summary).to_string(index=False),flush=True)
if __name__=='__main__':main()
