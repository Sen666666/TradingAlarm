"""Two independent process groups, the identical frozen ledger/admission loop.

Partitioning is execution scheduling only. All13 account IDs occur once; no
account shares money or inventory with another. Outputs merge chronologically.
"""
from pathlib import Path
import sys,json,subprocess,gzip,heapq,re,os,time
from dataclasses import asdict
from current_pool_bridge import checked_ref,load_bundle,load_prepared_states,sha256
from history_runner import FrozenMarket,HistoryRunner,StreamingSink,iso,prepared_directory
from run_first10 import validate,first10_specs
from build_inputs import read,write,now

GROUPS=(('T0','T1','B0'),('S0','S1'))
def restrict(runner,group):
 runner.specs=tuple(s for s in runner.specs if s.variant in group)
 runner.accounts={s.account_id:runner.accounts[s.account_id] for s in runner.specs}
 runner.memory={k:v for k,v in runner.memory.items() if k in runner.accounts}
 return runner

def worker(package_path,output,group):
 p=Path(package_path).resolve();package=read(p);base=p.parent
 assert package['mode']=='frozen_A13_historical'
 refs={k:checked_ref(package[k],base) for k in ['scope','data_closeout','economic_protocol_frozen','economic_protocol','bridge_manifest','prepared_manifest','market_rules','fx_quotes']}
 validate(data_closeout=refs['data_closeout'],economic_protocol_frozen=refs['economic_protocol_frozen'],scope=refs['scope'])
 receipt=read(refs['economic_protocol_frozen']);bound={str((refs['economic_protocol_frozen'].parent/k).resolve()):v for k,v in receipt['artifacts'].items()}
 for k in ['economic_protocol','bridge_manifest','prepared_manifest','market_rules','fx_quotes']:
  assert bound[str(refs[k])]==sha256(refs[k])
 protocol=read(refs['economic_protocol']);assert protocol['status']=='frozen' and protocol['algorithm_changes']==0
 assert package['start']==protocol['account_start'] and package['end']==protocol['account_end']
 for name in ['history_runner.py','sector_account.py','current_fixed_pool.py','run_first10.py','b0_rebalance.py','market_rules.py','dispatch_accounts.py']:
  assert protocol['code_sha256'][name]==sha256(Path(__file__).with_name(name))
 b=load_bundle(refs['bridge_manifest']);load_prepared_states(b,prepared_directory(refs['prepared_manifest']));assert b.signal_ready
 assert checked_ref(b.manifest['data_pool_closeout'],b.manifest_path.parent)==refs['data_closeout']
 m=FrozenMarket(b,read(refs['market_rules']),read(refs['fx_quotes'])['quotes'],protocol)
 sink=StreamingSink(output);r=restrict(HistoryRunner(b,m,start=iso(package['start']),end=iso(package['end']),sink=sink),GROUPS[int(group)])
 provenance=dict(package=str(p),package_sha256=sha256(p),dispatcher_sha256=sha256(__file__),runner_sha256=sha256(Path(__file__).with_name('history_runner.py')),
  account_specs=[asdict(x) for x in r.specs],group=int(group),selection_and_state_shared_by_hash=True)
 try:summary=r.run();r.write(output,summary,provenance)
 except BaseException as exc:
  r.write(output,dict(status='failed_partial_run',error=type(exc).__name__+':'+str(exc),historical_account_runs_started=len(r.specs),completed_accounts=0),provenance);raise
 finally:sink.close()

def merge_stream(paths,target):
 rank={s.account_id.encode():i for i,s in enumerate(first10_specs())};pattern=re.compile(rb'^\{"account": "([^"]+)", "at": "([^"]+)"')
 sources=[gzip.open(p,'rb') for p in paths];heap=[]
 def push(i):
  line=sources[i].readline()
  if line:
   match=pattern.match(line);assert match,'Unexpected encoded stream format'
   heapq.heappush(heap,(match[2],rank[match[1]],i,line))
 for i in range(len(sources)):push(i)
 with gzip.open(target,'wb',compresslevel=1) as out:
  while heap:
   stamp,order,i,line=heapq.heappop(heap);out.write(line);push(i)
 for f in sources:f.close()

def main(package,output):
 output=Path(output).resolve();output.mkdir(exist_ok=False);(output/'groups').mkdir();procs=[];logs=[]
 for i,group in enumerate(GROUPS):
  log=(output/'groups'/f'G{i}.log').open('x');logs.append(log)
  procs.append(subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker',str(Path(package).resolve()),str(output/'groups'/f'G{i}'),str(i)],stdout=log,stderr=log))
 while True:
  codes=[p.poll() for p in procs]
  if any(c not in (None,0) for c in codes):
   for other in procs:
    if other.poll() is None:other.terminate()
   write(output/'summary.json',dict(status='failed_partial_run',historical_account_runs_started=13,completed_accounts=0));raise RuntimeError('Partition worker failed; preserve partial evidence')
  if all(c==0 for c in codes):break
  time.sleep(1)
 for f in logs:f.close()
 summaries=[read(output/'groups'/f'G{i}'/'summary.json') for i in range(len(GROUPS))]
 for name in ['daily','decisions']:merge_stream([output/'groups'/f'G{i}'/(name+'.jsonl.gz') for i in range(len(GROUPS))],output/(name+'.jsonl.gz'))
 final={}
 for i,s in enumerate(summaries):
  for aid in s['accounts']:os.link(output/'groups'/f'G{i}'/(aid+'.json'),output/(aid+'.json'));final[aid]=s['final_nav'][aid]
 os.link(output/'groups/G0/B0_annual_targets.json',output/'B0_annual_targets.json')
 assert set(final)=={s.account_id for s in first10_specs()}
 summary=dict(research_basis='current_pool_historical_development',synthetic=False,historical_account_runs=13,completed_accounts=13,
  initial_capital_cny=1000000,accounts=[s.account_id for s in first10_specs()],daily_rows=sum(s['daily_rows'] for s in summaries),final_nav=final,
  limitations=[dict(group=i,provider_notices=s['limitations']) for i,s in enumerate(summaries)],final_positions_closed=False,
  dispatch='two independent groups; no cross-account liquidity/capital sharing; chronological lossless source-line merge')
 write(output/'summary.json',summary);write(output/'provenance.json',dict(recorded_at=now(),package=str(Path(package).resolve()),package_sha256=sha256(package),dispatcher_sha256=sha256(__file__),
  group_provenance=[read(output/'groups'/f'G{i}'/'provenance.json') for i in range(len(GROUPS))],all_main_accounts_unique=True))
 print(summary['final_nav'],flush=True)

if __name__=='__main__':
 if sys.argv[1]=='worker':worker(sys.argv[2],sys.argv[3],sys.argv[4])
 else:main(sys.argv[1],sys.argv[2])
