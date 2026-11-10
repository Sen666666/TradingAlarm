from ler_common import *
import gzip,time,collections
from dataclasses import replace
import execution as ex
from run_first10 import first10_specs as originals
from current_pool_bridge import checked_ref
runner=ex.old_context.runner

class Sink:
 def __init__(self,path):
  path.mkdir(parents=True,exist_ok=False);self.streams={k:gzip.open(path/f'{k}.jsonl.gz','wt',compresslevel=1) for k in ['daily','decisions']}
 def emit(self,name,r):
  if name=='decisions':
   a=r['ack'];d=a.decisions[0];mode=r['account'].split('__')[0];states=ex.STATE.get((r['at'],r['account']),[])
   r=dict(account=r['account'],at=r['at'],accepted=a.accepted,rejected=a.rejected,first_selected=d.selected,exits=a.decisions[-1].exit_requests,occupancy=a.occupancy,eligible=[e.security_id for e in d.eligibility if e.q is True],local_policy_states=states)
  self.streams[name].write(json.dumps(runner.encoded(r),ensure_ascii=False,allow_nan=False)+'\n')
 def close(self):
  for f in self.streams.values():f.close()

def specs(prefix=False):
 result=[]
 for group in GROUPS:
  for policy in ['I','LH','LER']:
   for stress in (['base'] if policy=='LH' else ['base','cost2','delay1']):
    if prefix and not(stress=='base' or(group=='COMM' and policy=='LER')):continue
    template=next(x for x in originals() if x.account_id=='S1_'+stress)
    result.append(replace(template,account_id=f'{group}_{policy}_{stress}__S1_{stress}'))
 return tuple(result)

def context(cutoff=None):
 b,m=ex.old_context.context(cutoff);scope=read(SEC/'scope.json');facts={};data={};factors={};manifest={s['series_id']:s for s in read(OLD/'prepared-v2/manifest.json')['series']}
 for sid in scope['meta']:
  f=pd.read_parquet(IX/'signals'/f'{sid}.parquet');q=pd.read_parquet(HERE/'signals-v1'/f'{sid}.parquet');a=pd.read_parquet(OLD/'prepared-v2'/manifest[sid]['files']['signal']['path'],columns=['adjustment_factor']).adjustment_factor
  if cutoff:f=f.loc[:cutoff].copy();q=q.loc[:cutoff].copy();a=a.loc[:cutoff].copy()
  assert f.index.equals(q.index);data[sid]=f;facts[sid]=q;factors[sid]=a
 return b,m,scope,data,facts,factors

def run(path,end=END,cutoff=None,technical=False,prefix=False):
 b,m,scope,data,facts,factors=context(cutoff);ss=specs(prefix);runner.first10_specs=lambda:ss;runner.decide_current_pool=ex.decide;runner.FrozenMarket.quotes=ex.fs.quotes
 sink=Sink(path);r=runner.HistoryRunner(b,m,start=runner.iso(START+'T15:10:00+08:00'),end=runner.iso(end+'T15:10:00+08:00'),sink=sink,synthetic=technical)
 for s in ss:
  if s.account_id.split('_')[1]!='I':
   a=ex.LocalAccount(initial_cash=s.initial_capital_cny,cost_multiplier=s.stress.variable_components_multiplier,delay_events=s.stress.extra_executable_events,max_sectors=1,max_issuers_per_sector=6,fractional_split_policy=m.protocol.get('fractional_split_policy','reject'));a.install(s.account_id.split('_')[1]);r.accounts[s.account_id]=a
 ex.configure(scope,data,facts,factors,r.accounts);t=time.time()
 try:
  summary=r.run();r.write(path,summary,dict(recorded_at=now(),seconds=time.time()-t,rules_sha256=sha(HERE/'RULES.md'),execution_contract_sha256=sha(HERE/'EXECUTION_CONTRACT.md'),economic=not technical))
 except BaseException as e:
  r.write(path,dict(status='failed_partial',error=repr(e)),dict(recorded_at=now(),rules_sha256=sha(HERE/'RULES.md')));raise
 finally:sink.close()
 return r

def identity(path,end):
 def rows(p):
  with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
 old=rows(SEC/'accounts-v2/daily.jsonl.gz');new=rows(path/'daily.jsonl.gz');counts={}
 for group in GROUPS:
  aid=f'{group}_I_base__S1_base';oldid=f'{group}_I__S1_base'
  a=[{k:v for k,v in x.items() if k!='account'} for x in old if x['account']==oldid and x['at'][:10]<=end];z=[{k:v for k,v in x.items() if k!='account'} for x in new if x['account']==aid];assert a==z,(group,'I daily identity')
  a=read(SEC/'accounts-v2'/f'{oldid}.json');z=read(path/f'{aid}.json')
  if end==END:assert a==z,(group,'I full financial identity')
  else:
   assert z['fills']==[x for x in a['fills'] if x['at'][:10]<=end],group
  counts[group]=len(z['fills'])
 return counts

def main():
 mode=sys.argv[1]
 if mode=='technical':
  p=HERE/'technical/short-v1';r=run(p,end='2021-02-26',technical=True);controls=identity(p,'2021-02-26');counts={a:sum(x['kind']=='local_bound' for x in obj.audit_log) for a,obj in r.accounts.items() if isinstance(obj,ex.LocalAccount)};write(HERE/'technical/short-receipt-v1.json',dict(passed=True,old_I_controls=controls,bound_fills=counts,technical_paths=28,economic_paths=0));print(dict(controls=controls,bound_fills=counts),flush=True)
 elif mode=='economic':
  assert read(HERE/'technical/model-receipt.json')['passed'];assert read(HERE/'technical/short-receipt-v1.json')['passed'];assert read(HERE/'economic-admission.json')['passed']
  files=list((HERE/'code').glob('*.py'))+[HERE/'RULES.md',HERE/'EXECUTION_CONTRACT.md',HERE/'PROTOCOL.md',HERE/'economic-admission.json',HERE/'model-freeze-v1.json']
  write(HERE/'account-freeze.json',dict(recorded_at=now(),before_economic_results=True,policy_paths=28,new_economic_paths=24,old_base_controls=4,parameter_revisions_after_results=0,sha256={str(p.relative_to(ROOT)):sha(p) for p in files}))
  r=run(HERE/'accounts');controls=identity(HERE/'accounts',END);write(HERE/'old-I-identity.json',dict(passed=True,controls=controls));print(dict(completed=28,controls=controls,final_nav={k:str(v['nav']) for k,v in r.last_daily.items()}),flush=True)
 elif mode=='prefix':
  cutoff='2023-12-29';p=HERE/'technical/prefix-v1';run(p,end=cutoff,cutoff=cutoff,technical=True,prefix=True);counts={}
  for name in ['daily','decisions']:
   def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
   prefix_rows=rows(p/f'{name}.jsonl.gz');ids={x['account'] for x in prefix_rows};full=[x for x in rows(HERE/f'accounts/{name}.jsonl.gz') if x['account'] in ids and x['at'][:10]<=cutoff];assert full==prefix_rows,name;counts[name]=len(prefix_rows)
  write(HERE/'technical/prefix-receipt-v1.json',dict(passed=True,cutoff=cutoff,paths=14,rows=counts,physically_truncated=['raw_execution','actions','old_states','I_fields','local_receipts','OHLCV_evidence','causal_factors','H1_matrix','old_buy_reference']));print(counts,flush=True)
 else:raise ValueError(mode)
if __name__=='__main__':main()
