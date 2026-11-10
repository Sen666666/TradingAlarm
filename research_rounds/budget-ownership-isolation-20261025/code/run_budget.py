from budget_common import *
import gzip,time,collections
from dataclasses import replace
from types import SimpleNamespace as NS
from owned_account import OwnedAccount
sys.path.append(str(OLD/'code'));sys.path.append(str(IX/'code'));sys.path.append(str(ABCD/'code'));sys.path.append(str(PREV/'code'))
from current_pool_bridge import load_bundle,checked_ref
import multi_runner as runner
import finance_ladder as fl
from run_first10 import first10_specs as original_specs

class Sink:
 def __init__(self,out):
  self.out=out;out.mkdir(parents=True,exist_ok=False);self.streams={k:gzip.open(out/f'{k}.jsonl.gz','wt',compresslevel=1) for k in ['daily','decisions']};self.runner=None;self.reference={};self.signal_checks=0
 def emit(self,name,r):
  if name=='decisions':
   ack=r['ack'];first=ack.decisions[0];sig=runner.encoded(first.eligibility);day=r['at'];mode=r['account'].split('__')[0]
   if mode=='CONTROL':self.reference[day]=sig
   else:assert sig==self.reference[day];self.signal_checks+=1
   r=dict(account=r['account'],at=day,eligibility=first.eligibility,accepted=ack.accepted,rejected=ack.rejected,first_selected=first.selected,first_rejected=first.rejected,exits=ack.decisions[-1].exit_requests,occupancy=ack.occupancy)
  else:
   account=self.runner.accounts[r['account']]
   if isinstance(account,OwnedAccount):r=dict(r,owner_cash=account.owner_cash)
  self.streams[name].write(json.dumps(runner.encoded(r),ensure_ascii=False)+'\n')
 def close(self):
  for s in self.streams.values():s.close()

def context():
 scope=read(HERE/'scope.json');ids={x['symbol'] for x in scope['chosen']};b=load_bundle(OLD/'inputs-v2/input-manifest.json');b.lines=tuple(l for l in b.lines if l.security_id in ids);b.series={s:r for s,r in b.series.items() if s in ids or s in SECTORS};b.sector_series={s:v for s,v in b.sector_series.items() if s in SECTORS}
 records={r['series_id']:r for r in read(OLD/'prepared-v2/manifest.json')['series']};buy=collections.defaultdict(set)
 for sid,item in b.series.items():
  r=records[sid];item.blocked_reason=r['blocked_reason'];assert item.blocked_reason is None
  item.states=pd.read_parquet(checked_ref(r['files']['states'],OLD/'prepared-v2'),columns=['ready','target','rs','segment_id'])
  if sid in ids:
   f=pd.read_parquet(IX/'signals'/f'{sid}.parquet',columns=['ix_target','IX']);assert item.states.index.equals(f.index);item.states=item.states.copy();item.states['target']=f.ix_target
   for dt in f.index[f.IX.astype(bool)]:buy[str(dt.date())].add(sid)
 assert b.signal_ready;fl.base.configure(buy,fl.DummyBoard());m=runner.FrozenMarket(b,read(OLD/'inputs-v2/market-rules.json'),[],read(OLD/'inputs-v2/economic-protocol.json'));return b,m

def main():
 assert read(HERE/'technical/tests-v4.json')['passed'];paths=[HERE/'PROTOCOL.md',HERE/'scope.json',HERE/'technical/tests-v4.json',HERE/'pre-account-review.json',HERE/'pre-account-price-review.png']+list((HERE/'code').glob('*.py'));write(HERE/'freeze.json',dict(recorded_at=now(),status='before_economic_results',policy_accounts=2,identity_control=1,initial_capital=1000000,stock_entry_cap='0.15 * own whole-account NAV in both arms',changes_only='sector settled cash funding limit',sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},old_finance_sha256=sha(OLD/'code/sector_account.py')))
 t=time.time();b,m=context();base_spec=next(s for s in original_specs() if s.account_id=='S0_base');specs=tuple(replace(base_spec,account_id=x+'__S0_base') for x in ['CONTROL','SHARED','ISOLATED']);runner.first10_specs=lambda:specs;runner.decide_current_pool=fl.decide;runner.FrozenMarket.quotes=fl.quotes;sink=Sink(HERE/'accounts');r=runner.HistoryRunner(b,m,start=runner.iso(START+'T15:10:00+08:00'),end=runner.iso(END+'T15:10:00+08:00'),sink=sink,synthetic=False)
 owners={l.security_id:l.sector_id for l in b.lines}
 for mode in ['SHARED','ISOLATED']:r.accounts[mode+'__S0_base']=OwnedAccount(initial_cash=1000000,owners=SECTORS,owner_of_sid=owners,isolate=mode=='ISOLATED',fractional_split_policy=m.protocol.get('fractional_split_policy','reject'))
 sink.runner=r
 try:
  summary=r.run();summary['historical_account_runs']=2;summary['technical_identity_accounts']=1;r.write(HERE/'accounts',summary,dict(recorded_at=now(),same_opportunity_inputs=True,same_position_formula=True,seconds=time.time()-t))
 except BaseException as e:
  r.write(HERE/'accounts',dict(status='failed_partial',error=repr(e)),dict(recorded_at=now()));raise
 finally:sink.close()
 assert read(HERE/'accounts/CONTROL__S0_base.json')==read(HERE/'accounts/SHARED__S0_base.json')
 daily=collections.defaultdict(list)
 with gzip.open(HERE/'accounts/daily.jsonl.gz','rt') as f:
  for l in f:
   x=json.loads(l);x.pop('owner_cash',None);key=x.pop('account');daily[key].append(x)
 assert daily['CONTROL__S0_base']==daily['SHARED__S0_base']
 for mode in ['SHARED','ISOLATED']:
  a=r.accounts[mode+'__S0_base'];write(HERE/f'accounts/{mode}-ownership.json',dict(owners=a.owner_cash,journal=a.owner_journal,settlement_owner=a.settlement_owner,budget_constraints=a.budget_constraints,isolation_enabled=a.isolate))
 write(HERE/'technical/identity-and-inputs.json',dict(passed=True,full_financial_json_exact=True,control_daily_rows=len(daily['CONTROL__S0_base']),same_signal_eligibility_checks=sink.signal_checks,recorded_at=now()))
 print(dict(done=True,seconds=time.time()-t,final_nav=summary['final_nav']),flush=True)
if __name__=='__main__':main()
