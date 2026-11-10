"""Frozen finite run: 507 accounts, with prefixes and locked actual entry checks."""
from pathlib import Path
import hashlib,json,math
import numpy as np,pandas as pd
from model import context,state,WINDOWS,POLICIES
from engine import backtest,SCENARIOS
R=Path(__file__).resolve().parent;OUT=R/'results/v0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 frozen=json.loads((R/'freeze.json').read_text())
 for rel,h in frozen['sha256'].items():assert sha(R/rel)==h,rel
 OUT.mkdir(parents=True,exist_ok=False);(OUT/'accounts').mkdir();(OUT/'states').mkdir()
 metadata=json.loads((R/'inputs.json').read_text())['series'];summ=[];ledgers={};prefix=[];matched=[]
 for meta in metadata:
  symbol=meta['symbol'];d=pd.read_parquet(R/'inputs'/f'{symbol}.parquet');e,b,f=context(d)
  pd.concat({'event':e,'original':b,'feature':f},axis=1).to_parquet(OUT/'states'/f'{symbol}-context.parquet')
  for window,(start,end) in WINDOWS.items():
   z=d.loc[start:end];states={}
   for p in POLICIES:
    s,ini=state(d,e,b,f,start,end,p);states[p]=(s,ini);s.to_parquet(OUT/'states'/f'{symbol}-{window}-{p}.parquet')
   # Same parameters on truncated history, exact causal prefix (two cuts in primary, one in2024).
   cuts=[len(z)//3,2*len(z)//3] if window=='primary' else [len(z)//2]
   for cut in cuts:
    stop=z.index[cut];dd=d.loc[:stop];ee,bb,ff=context(dd)
    for p in POLICIES:
     ss,_=state(dd,ee,bb,ff,start,str(stop.date()),p)
     pd.testing.assert_frame_equal(ss,states[p][0].loc[:stop],check_exact=True)
     prefix.append(dict(symbol=symbol,window=window,policy=p,cut=str(stop.date()),passed=True))
   for scenario,sc in SCENARIOS.items():
    base_trades=None
    for p in POLICIES:
     s,ini=states[p];summary,ledger,trades,fills,orders=backtest(z,s,ini,symbol,sc)
     save(symbol,meta['name'],window,scenario,'P',p,summary,ledger,trades,fills,orders,summ,ledgers)
     if p=='E0':base_trades=trades
    if window=='primary':
     for p in POLICIES[1:]:
      s,ini=states['E0'];summary,ledger,trades,fills,orders=backtest(z,s,ini,symbol,sc,matched_to=base_trades,policy=p,features=f.loc[z.index])
      assert list(trades.entry_date)==list(base_trades.entry_date),(symbol,scenario,p)
      np.testing.assert_allclose(trades.entry_price,base_trades.entry_price,rtol=0,atol=0)
      assert (pd.to_datetime(trades.exit_date)<=pd.to_datetime(base_trades.exit_date)).all()
      for j,(a,c) in enumerate(zip(base_trades.to_dict('records'),trades.to_dict('records'))):
       matched.append(dict(symbol=symbol,scenario=scenario,policy=p,leg=j,entry_date=a['entry_date'],base_exit=a['exit_date'],sensitive_exit=c['exit_date'],base_return=a['net_return'],sensitive_return=c['net_return'],delta=c['net_return']-a['net_return'],base_terminal=a['terminal'],sensitive_terminal=c['terminal']))
      save(symbol,meta['name'],window,scenario,'M',p,summary,ledger,trades,fills,orders,summ,ledgers)
    s,ini=states['E0'];summary,ledger,trades,fills,orders=backtest(z,s,ini,symbol,sc,benchmark=True)
    save(symbol,meta['name'],window,scenario,'H','HOLD',summary,ledger,trades,fills,orders,summ,ledgers)
  print('completed',symbol,flush=True)
 summary=pd.DataFrame(summ);assert len(summary)==507
 summary.to_csv(OUT/'summary.csv',index=False);pd.DataFrame(prefix).to_csv(OUT/'prefix-checks.csv',index=False);pd.DataFrame(matched).to_csv(OUT/'matched-legs.csv',index=False)
 aggregates=[]
 for window in WINDOWS:
  for scenario in SCENARIOS:
   for group in ['all13','exAU0_12']:
    syms=[x['symbol'] for x in metadata if group=='all13' or x['symbol']!='AU0']
    for mode in ['P','M','H']:
     if mode=='M' and window!='primary':continue
     ps=POLICIES if mode in ['P','M'] else ['HOLD']
     for p in ps:
      smode='P' if mode=='M' and p=='E0' else mode
      xs=summary.loc[(summary.window==window)&(summary.scenario==scenario)&(summary['mode']==smode)&(summary.policy==p)&summary.symbol.isin(syms)]
      navs=pd.concat([ledgers[(x,window,scenario,smode,p)].nav.rename(x) for x in syms],axis=1).sort_index().ffill().fillna(1.)
      nav=navs.mean(axis=1);dd=nav/np.maximum.accumulate(np.r_[1,nav])[1:]-1
      pd.DataFrame({'nav':nav,'drawdown':dd}).to_csv(OUT/f'aggregate-{window}-{scenario}-{group}-{mode}-{p}.csv')
      nt=int(xs.natural_trades.sum());nw=float((xs.natural_trades*xs.natural_win_rate.fillna(0)).sum())
      aggregates.append(dict(window=window,scenario=scenario,group=group,mode=mode,policy=p,net_return=nav.iloc[-1]-1,max_drawdown=-dd.min(),trades=xs.trades.sum(),wins=xs.wins.sum(),win_rate=xs.wins.sum()/xs.trades.sum() if xs.trades.sum() else np.nan,natural_trades=nt,natural_win_rate=nw/nt if nt else np.nan,asset_balanced_win_rate=xs.win_rate.mean(),median_asset_return=xs.net_return.median(),tail_trades=xs.tail_trades.sum(),tail_pnl=xs.tail_pnl.sum()/len(syms),ordinary_pnl=xs.ordinary_pnl.sum()/len(syms),fees=xs.fees.sum()/len(syms),slippage=xs.slippage.sum()/len(syms),exposure_fraction=xs.exposure_fraction.mean()))
 pd.DataFrame(aggregates).to_csv(OUT/'aggregates.csv',index=False)
 (OUT/'run.json').write_text(json.dumps({'accounts':len(summary),'prefix_checks':len(prefix),'matched_legs':len(matched),'freeze_sha256':sha(R/'freeze.json'),'policies':POLICIES,'parameter_search':False},indent=2))
 print('DONE507',flush=True)
def save(symbol,name,window,scenario,mode,p,summary,ledger,trades,fills,orders,summ,ledgers):
 key='__'.join([symbol,window,scenario,mode,p]);folder=OUT/'accounts'/key;folder.mkdir()
 ledger.to_parquet(folder/'ledger.parquet');trades.to_csv(folder/'trades.csv',index=False);fills.to_csv(folder/'fills.csv',index=False);orders.to_csv(folder/'orders.csv',index=False)
 summ.append(dict(key=key,symbol=symbol,name=name,window=window,scenario=scenario,mode=mode,policy=p,**summary));ledgers[(symbol,window,scenario,mode,p)]=ledger
if __name__=='__main__':main()
