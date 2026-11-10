from sec_common import *
import collections,gzip,time
from dataclasses import replace
sys.path.append(str(OLD/'code'));sys.path.append(str(IX/'code'));sys.path.append(str(PREV/'code'))
from current_pool_bridge import load_bundle,checked_ref
import multi_runner as runner
from run_first10 import first10_specs
import fixed_scope as fs

class Sink:
 def __init__(self,p):
  p.mkdir(parents=True,exist_ok=False);self.streams={k:gzip.open(p/f'{k}.jsonl.gz','wt',compresslevel=1) for k in ['daily','decisions']}
 def emit(self,name,r):
  if name=='decisions':
   a=r['ack'];d=a.decisions[0];r=dict(account=r['account'],at=r['at'],accepted=a.accepted,rejected=a.rejected,first_selected=d.selected,exits=a.decisions[-1].exit_requests,occupancy=a.occupancy,eligible=[e.security_id for e in d.eligibility if e.q is True],fallbacks=d.fallbacks if hasattr(d,'fallbacks') else ())
  self.streams[name].write(json.dumps(runner.encoded(r),ensure_ascii=False)+'\n')
 def close(self):
  for f in self.streams.values():f.close()

def context(cutoff=None):
 scope=read(HERE/'scope.json');ids=set(scope['meta']);b=load_bundle(OLD/'inputs-v2/input-manifest.json');b.lines=tuple(x for x in b.lines if x.security_id in ids);sectors={x.sector_id for x in b.lines};b.series={s:r for s,r in b.series.items() if s in ids or s in sectors};b.sector_series={s:r for s,r in b.sector_series.items() if s in sectors};records={r['series_id']:r for r in read(OLD/'prepared-v2/manifest.json')['series']};signals={}
 for sid,x in b.series.items():
  r=records[sid];assert r['blocked_reason'] is None;x.states=pd.read_parquet(checked_ref(r['files']['states'],OLD/'prepared-v2'),columns=['ready','target','rs','segment_id'])
  if sid in ids:
   f=pd.read_parquet(IX/'signals'/f'{sid}.parquet');i=pd.read_parquet(HERE/'signals'/f'{sid}.parquet');assert f.index.equals(x.states.index) and i.index.equals(f.index);signals[sid]=f.join(i);x.states=x.states.copy();x.states['target']=f.ix_target
  if cutoff:x.states=x.states.loc[:cutoff].copy()
 m=runner.FrozenMarket(b,read(OLD/'inputs-v2/market-rules.json'),[],read(OLD/'inputs-v2/economic-protocol.json'))
 if cutoff:
  for sid,f in m.raw.items():m.raw[sid]=f.loc[:cutoff].copy()
  m.actions={s:[e for e in es if e['effective_date']<=cutoff] for s,es in m.actions.items()};signals={s:f.loc[:cutoff].copy() for s,f in signals.items()};z=np.load(OLD/'h1/matrix.npz');dates=pd.DatetimeIndex(z['dates']);mask=dates<=pd.Timestamp(cutoff);b._h1_cache=(dates[mask],{s:j for j,s in enumerate(z['symbols'])},z['score'][mask].copy())
 ref={s:{d for d in ds if cutoff is None or d<=cutoff} for s,ds in read(HERE/'pure-q-events.json')['events'].items()};fs.configure(scope,signals,ref)
 return b,m

def specs(groups=tuple(GROUPS)):
 template=next(x for x in first10_specs() if x.account_id=='S1_base')
 return tuple(replace(template,account_id=k+'_'+p+'__S1_base') for k in groups for p in ['IX','I'])

def run(out,end=END,cutoff=None,groups=tuple(GROUPS),synthetic=False):
 b,m=context(cutoff);runner.first10_specs=lambda:specs(groups);runner.decide_current_pool=fs.decide;runner.FrozenMarket.quotes=fs.quotes;sink=Sink(out);r=runner.HistoryRunner(b,m,start=runner.iso(START+'T15:10:00+08:00'),end=runner.iso(end+'T15:10:00+08:00'),sink=sink,synthetic=synthetic);t=time.time()
 try:r.write(out,r.run(),dict(recorded_at=now(),same_frozen_algorithms=True,RS_H1_unchanged=True,position_formula_unchanged=True,seconds=time.time()-t,pure_q_checks=fs.Q_CHECKS))
 except BaseException as e:r.write(out,dict(status='failed_partial',error=repr(e)),dict(recorded_at=now()));raise
 finally:sink.close()
 return r

def main():
 if '--technical' in sys.argv:
  r=run(HERE/'technical/short',end='2021-01-15',groups=('SEMI','COMM'),synthetic=True);write(HERE/'technical/short-complete.json',dict(passed=True,days=10,policy_paths=4,economic_paths=0));print('short technical pass');return
 if '--prefix' in sys.argv:
  cutoff='2023-12-29';run(HERE/'technical/prefix',end=cutoff,cutoff=cutoff,synthetic=True)
  counts={}
  for name in ['daily','decisions']:
   def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
   full=[x for x in rows(HERE/f'accounts/{name}.jsonl.gz') if x['at'][:10]<=cutoff];prefix=rows(HERE/f'technical/prefix/{name}.jsonl.gz');assert full==prefix,name;counts[name]=len(prefix)
  write(HERE/'technical/prefix-identity.json',dict(passed=True,cutoff=cutoff,physical_truncation=['raw_prices','prepared_states','I_IX_saved_market_evidence','corporate_actions','H1_matrix','buy_eligibility_dates'],rows=counts));print(counts);return
 assert read(HERE/'pairs/receipt.json')['retained']>0 and read(HERE/'technical/short-complete.json')['passed'];assert read(HERE/'technical/preflight.json')['passed']
 refs={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'PROTOCOL.md',HERE/'scope.json',HERE/'pair-freeze.json',HERE/'pairs/receipt.json',HERE/'pairs/summary.csv',HERE/'technical/preflight.json']+list((HERE/'code').glob('*.py'))};write(HERE/'account-freeze.json',dict(recorded_at=now(),before_account_results=True,after_paired_diagnostic=True,unchanged_predeclared_rules=True,policy_paths=8,initial_each=1000000,sha256=refs));r=run(HERE/'accounts');print(dict(done=True,nav={k:str(v['nav']) for k,v in r.last_daily.items()}),flush=True)
if __name__=='__main__':main()
