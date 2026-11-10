"""Reconcile shared-account episodes and fixed calendar phases; development only."""
import json
from pathlib import Path
import pandas as pd
OUT=Path('results/broad-shared-slots')
def main(output='broad-shared-slots'):
 OUT=Path('results')/output
 root=Path('data/ths-refresh-20261018');manifest=json.loads((root/'validated-input-balanced-second500.json').read_text());marks={}
 for r in manifest['records']:
  f=pd.read_parquet(root/f"{r['ths_symbol']}-signal.parquet");marks[r['symbol']]=float(f.signal_close.loc[:'2026-10-16'].dropna().iloc[-1])
 cache=pd.read_parquet('results/broad-exit-disagreement/all-observed-signals.parquet');ages={}
 for symbol,z in cache.groupby('symbol'):
  z=z.sort_values('date');age=-1;values=[]
  for r in z.itertuples():
   age=age+1 if r.zero else -1;values.append(age)
  ages[symbol]=pd.Series(values,index=z.date)
 alternate_ages=None;age_basis='pairwise_volume'
 for filename,column,label in [('linear-signals.parquet','exposure','linear_volume'),('graded-signals.parquet','graded','graded_pairwise')]:
  if (OUT/filename).exists():
   alternate_ages={};age_basis=label
   for symbol,z in pd.read_parquet(OUT/filename).groupby('symbol'):
    z=z.sort_values('date');age=-1;values=[]
    for value in z[column]:
     age=age+1 if value>0 else -1;values.append(age)
    alternate_ages[symbol]=pd.Series(values,index=z.date)
 summary=json.loads((OUT/'summary.json').read_text());rows=[];phases=[];details=[]
 for result in summary:
  case=result['case']+'-'+result['scenario'];path=pd.read_parquet(OUT/(case+'-path.parquet'));orders=json.loads((OUT/(case+'-orders.json')).read_text());active={};episodes=[]
  model_ages=alternate_ages if alternate_ages is not None and not result['case'].startswith('control_') else ages
  for o in orders:
   s=o['symbol'];u=o['units'];value=u*o['raw_open']
   if s not in active:
    assert u>0
    active[s]=dict(symbol=s,entry_date=o['date'],signal_date=o['signal_date'],entry_signal_age=int(model_ages[s].loc[:o['signal_date']].iloc[-1]),entry_signal_age_basis=age_basis if model_ages is alternate_ages else 'pairwise_volume',units=0.,buy_cash=0.,pnl=0.)
   ep=active[s];ep['units']+=u;ep['pnl']-=value+o['fee']
   if u>0:ep['buy_cash']+=value+o['fee']
   if abs(ep['units'])<1e-8:
    ep.update(status='closed',exit_date=o['date']);episodes.append(ep);del active[s]
  for s,ep in active.items():
   ep['pnl']+=ep['units']*marks[s];ep.update(status='open_marked',exit_date=None);episodes.append(ep)
  total=sum(e['pnl'] for e in episodes);error=abs(total/1e6-result['total_return']);assert error<1e-9
  for e in episodes:e.update(case=case,return_on_purchase_cash=e['pnl']/e['buy_cash'])
  frame=pd.DataFrame(episodes);details.extend(episodes);tail=frame.return_on_purchase_cash.ge(.3);ordinary=frame[~tail];wins=ordinary[ordinary.pnl.gt(0)];losses=ordinary[ordinary.pnl.lt(0)]
  rows.append(dict(case=case,episodes=len(frame),closed=int(frame.status.eq('closed').sum()),tail30_count=int(tail.sum()),tail30_account_contribution=float(frame.loc[tail,'pnl'].sum()/1e6),ordinary_account_contribution=float(ordinary.pnl.sum()/1e6),ordinary_wins=float(wins.pnl.sum()/1e6),ordinary_losses=float(losses.pnl.sum()/1e6),episode_reconciliation_error=error,late_state_entry_fraction=float(frame.entry_signal_age.gt(0).mean()),fresh_signal_pnl=float(frame.loc[frame.entry_signal_age.eq(0),'pnl'].sum()/1e6),late_signal_pnl=float(frame.loc[frame.entry_signal_age.gt(0),'pnl'].sum()/1e6)))
  for label,start,end in [('2026JanMay','2026-01-01','2026-05-31'),('2026June','2026-06-01','2026-06-30'),('2026JulOct','2026-07-01','2026-10-16')]:
   sub=path.loc[start:end];prior=path.loc[path.index<pd.Timestamp(start)].nav.iloc[-1]
   phases.append(dict(case=case,phase=label,return_nav=float(sub.nav.iloc[-1]/prior-1),mean_cash_weight=float((sub.cash/(sub.nav*1e6)).mean())))
 pd.DataFrame(details).to_parquet(OUT/'episodes.parquet',index=False)
 (OUT/'tail-economics.json').write_text(json.dumps(rows,indent=2));(OUT/'2026-phases.json').write_text(json.dumps(phases,indent=2));print(pd.DataFrame(rows).to_string(index=False))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--output',default='broad-shared-slots');main(p.parse_args().output)
