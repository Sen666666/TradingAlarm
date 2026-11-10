"""One physical input cutoff, two policy paths and the same identity control."""
from run_budget import *

def main():
 cutoff='2023-12-29';b,m=context()
 for x in b.series.values():x.states=x.states.loc[x.states.index<=pd.Timestamp(cutoff+'T23:59:59+08:00')].copy() if x.states.index.tz else x.states.loc[:cutoff].copy()
 for sid,f in m.raw.items():m.raw[sid]=f.loc[:cutoff].copy()
 m.actions={sid:[x for x in xs if x['effective_date']<=cutoff] for sid,xs in m.actions.items()}
 z=np.load(OLD/'h1/matrix.npz');ds=pd.DatetimeIndex(z['dates']);mask=ds<=pd.Timestamp(cutoff);b._h1_cache=(ds[mask],{s:j for j,s in enumerate(z['symbols'])},z['score'][mask].copy())
 buy=collections.defaultdict(set)
 for sid in m.lines:
  f=pd.read_parquet(IX/'signals'/f'{sid}.parquet',columns=['IX']).loc[:cutoff]
  for d in f.index[f.IX.astype(bool)]:buy[str(d.date())].add(sid)
 fl.base.configure(buy,fl.DummyBoard());base_spec=next(x for x in original_specs() if x.account_id=='S0_base');runner.first10_specs=lambda:tuple(replace(base_spec,account_id=x+'__S0_base') for x in ['CONTROL','SHARED','ISOLATED']);runner.decide_current_pool=fl.decide;runner.FrozenMarket.quotes=fl.quotes;sink=Sink(HERE/'technical/prefix-2023');r=runner.HistoryRunner(b,m,start=runner.iso(START+'T15:10:00+08:00'),end=runner.iso(cutoff+'T15:10:00+08:00'),sink=sink,synthetic=False)
 for mode in ['SHARED','ISOLATED']:r.accounts[mode+'__S0_base']=OwnedAccount(initial_cash=1000000,owners=SECTORS,owner_of_sid={l.security_id:l.sector_id for l in b.lines},isolate=mode=='ISOLATED',fractional_split_policy=m.protocol.get('fractional_split_policy','reject'))
 sink.runner=r
 try:r.run()
 finally:sink.close()
 counts={}
 for name in ['daily','decisions']:
  def rows(path):
   with gzip.open(path,'rt') as f:return [json.loads(x) for x in f]
  original=[x for x in rows(HERE/f'accounts/{name}.jsonl.gz') if x['at'][:10]<=cutoff];prefix=rows(HERE/f'technical/prefix-2023/{name}.jsonl.gz');assert original==prefix,name;counts[name]=len(prefix)
 write(HERE/'technical/prefix.json',dict(passed=True,cutoff=cutoff,physically_truncated=['price','prepared_states','corporate_actions','H1_matrix','IX_buy_events'],identical_rows=counts,new_economic_policy=0,recorded_at=now()))
 print(dict(passed=True,counts=counts))
if __name__=='__main__':main()
