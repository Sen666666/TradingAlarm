from gate_common import *
from dataclasses import replace
import gzip,time,collections
import adapter as ad
from run_first10 import first10_specs as original_specs
runner=ad.native.runner

class Sink:
 def __init__(self,path):
  path.mkdir(parents=True,exist_ok=False);self.streams={k:gzip.open(path/f'{k}.jsonl.gz','wt',compresslevel=1) for k in ['daily','decisions']}
 def emit(self,name,r):
  if name=='decisions':
   ack=r['ack'];d=ack.decisions[0];group,policy,stress=r['account'].split('__')[0].split('_');blocked=ad.EXCLUSIONS.get((r['at'],policy),[]);ids=set(ad.SCOPE['groups'][group])
   r=dict(account=r['account'],at=r['at'],accepted=ack.accepted,rejected=ack.rejected,first_selected=d.selected,exits=ack.decisions[-1].exit_requests,occupancy=ack.occupancy,eligible=[e.security_id for e in d.eligibility if e.q is True],ema_entry_exclusions=[s for s in blocked if s in ids])
  self.streams[name].write(json.dumps(runner.encoded(r),ensure_ascii=False,allow_nan=False)+'\n')
 def close(self):
  for s in self.streams.values():s.close()

def specs(prefix=False):
 result=[]
 for group in GROUPS:
  for policy in ['E0','E0G','I','IG']:
   for stress in (['base','cost2'] if policy.endswith('G') and not prefix else ['base']):
    src=next(s for s in original_specs() if s.account_id=='S1_'+stress)
    assert src.allocation.max_issuers_per_sector==6 and src.allocation.max_sectors==1
    result.append(replace(src,account_id=f'{group}_{policy}_{stress}__S1_{stress}'))
 return tuple(result)

def context(cutoff=None):
 b,m=ad.native.context(cutoff);scope=read(SEC/'scope.json');data={};gs={};manifest={x['series_id']:x for x in read(OLD/'prepared-v2/manifest.json')['series']};same=0
 for sid in scope['meta']:
  f=pd.read_parquet(IX/'signals'/f'{sid}.parquet');i=pd.read_parquet(SEC/'signals'/f'{sid}.parquet');f=f.join(i)
  old=pd.read_parquet(OLD/'prepared-v2'/manifest[sid]['files']['states']['path'],columns=['target']);np.testing.assert_array_equal(f.e0_target.to_numpy(bool),old.target.to_numpy(bool));same+=len(f)
  q=pd.read_parquet(HERE/'facts'/f'{sid}.parquet')
  if cutoff:
   f=f.loc[:cutoff].copy();q=q.loc[:cutoff].copy();rebuilt=gate(f);pd.testing.assert_frame_equal(rebuilt,q,check_exact=True);q=rebuilt
  data[sid]=f;gs[sid]=q
 ad.configure(scope,data,gs)
 return b,m,same

def run(path,end=END,cutoff=None,technical=False,prefix=False):
 b,m,same=context(cutoff);ss=specs(prefix);runner.first10_specs=lambda:ss;runner.decide_current_pool=ad.decide;runner.FrozenMarket.quotes=ad.fs.quotes
 sink=Sink(path);r=runner.HistoryRunner(b,m,start=runner.iso(START+'T15:10:00+08:00'),end=runner.iso(end+'T15:10:00+08:00'),sink=sink,synthetic=technical);start=time.time()
 try:r.write(path,r.run(),dict(recorded_at=now(),seconds=time.time()-start,original_E0_state_rows_exact=same,protocol_sha256=sha(HERE/'PROTOCOL.md'),economic=not technical))
 except BaseException as e:r.write(path,dict(status='failed_partial',error=repr(e)),dict(recorded_at=now()));raise
 finally:sink.close()
 return r

def identity(path,end):
 def rows(p):
  with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
 old=rows(LER/'accounts/daily.jsonl.gz');new=rows(path/'daily.jsonl.gz');result={}
 for group in GROUPS:
  aid=f'{group}_I_base__S1_base';a=[x for x in old if x['account']==aid and x['at'][:10]<=end];z=[x for x in new if x['account']==aid];assert a==z,(group,'daily baseline mismatch')
  original=read(LER/'accounts'/f'{aid}.json');latest=read(path/f'{aid}.json')
  if end==END:assert latest==original,(group,'financial baseline mismatch')
  else:assert latest['fills']==[x for x in original['fills'] if x['at'][:10]<=end],group
  result[group]=len(latest['fills'])
 return result

def main():
 mode=sys.argv[1]
 if mode=='short':
  p=HERE/'technical/short';run(p,end='2021-02-26',technical=True);write(HERE/'technical/short-identity.json',dict(passed=True,controls=identity(p,'2021-02-26'),technical_paths=24,economic_paths=0));print('short I controls pass',flush=True)
 elif mode=='economic':
  assert read(HERE/'economic-admission.json')['passed']
  files=list((HERE/'code').glob('*.py'))+[HERE/'PROTOCOL.md',HERE/'preparation.json',HERE/'GRAPH_REVIEW.md',HERE/'economic-admission.json']
  write(HERE/'account-freeze.json',dict(recorded_at=now(),before_results=True,paths=24,new_economic=20,controls=4,sha256={str(p.relative_to(ROOT)):sha(p) for p in files}))
  run(HERE/'accounts');write(HERE/'I-controls.json',dict(passed=True,controls=identity(HERE/'accounts',END)));print('economic 24 paths complete',flush=True)
 elif mode=='prefix':
  p=HERE/'technical/prefix';cutoff='2023-12-29';run(p,end=cutoff,cutoff=cutoff,technical=True,prefix=True)
  def load(p):
   with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
  counts={}
  for kind in ['daily','decisions']:
   pref=load(p/f'{kind}.jsonl.gz');ids={x['account'] for x in pref};full=[x for x in load(HERE/'accounts'/f'{kind}.jsonl.gz') if x['account'] in ids and x['at'][:10]<=cutoff];assert full==pref,kind;counts[kind]=len(pref)
  write(HERE/'technical/prefix-identity.json',dict(passed=True,cutoff=cutoff,paths=16,rows=counts,EMA_recomputed_from_truncated_source=True));print(counts,flush=True)
 else:raise ValueError(mode)

if __name__=='__main__':main()
