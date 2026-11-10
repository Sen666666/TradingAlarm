"""Finite A-only supplemental queue; unchanged collector, no automatic retries."""
from pathlib import Path
from contextlib import ExitStack
import json,sys,subprocess,fcntl,hashlib,datetime,argparse
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
OLD=ROOT/'research_rounds/current-pool-20261022/code'
sys.path.insert(0,str(OLD));import history_batch as hb

def main():
 p=argparse.ArgumentParser();p.add_argument('--index',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 manifest=json.loads(a.index.read_text());a.output.mkdir(parents=True,exist_ok=False)
 hb.immutable(a.output/'queue-protocol.json',a.index.read_bytes())
 state={'status':'running','batches':{},'algorithm_changes':0,'account_runs':0};hb.atomic(a.output/'queue-state.json',state)
 with ExitStack() as stack:
  lock=stack.enter_context((OLD/'.node-9602.run.lock').open('a'));fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  for item in manifest['batches']:
   plan=Path(item['path']);assert hashlib.sha256(plan.read_bytes()).hexdigest()==item['sha256'];d=hb.validate_plan(json.loads(plan.read_text()));assert all(str(x['node'])=='9602' and x['symbol'].startswith(('USHA','USZA','USHT','USTM')) for x in d['items'])
   name=plan.stem;out=a.output/'batches'/name;logs=a.output/'logs';logs.mkdir(exist_ok=True)
   with (logs/(name+'.stdout')).open('x') as log,(logs/(name+'.stderr')).open('x') as err:
    proc=subprocess.run([sys.executable,str(HERE/'code/collect.py'),'history','--plan',str(plan),'--output',str(out)],stdout=log,stderr=err)
   summary=hb.read_json(out/'run-summary.json',{})
   detail={'returncode':proc.returncode,'summary':summary}
   state['batches'][name]=detail
   print(json.dumps({'batch':name,'count':len(d['items']),'summary':summary,'returncode':proc.returncode},ensure_ascii=False),flush=True)
   if proc.returncode or summary.get('stopped_nodes_this_run'):
    state['status']='halted';state['stop_batch']=name;hb.atomic(a.output/'queue-state.json',state);return 2
   cp=[hb.read_json(out/'checkpoints'/(x['symbol']+'.json'),{}) for x in d['items']]
   if any(x.get('history_status') not in ('complete','page_budget_exhausted','quarantined') for x in cp):
    state['status']='halted';state['stop_batch']=name;state['reason']='incomplete_history';hb.atomic(a.output/'queue-state.json',state);return 2
   detail['history_counts']={v:sum(x.get('history_status')==v for x in cp) for v in ['complete','page_budget_exhausted','quarantined']}
   hb.atomic(a.output/'queue-state.json',state)
  state['status']='finished';state['finished_at']=hb.now();hb.atomic(a.output/'queue-state.json',state)
 return 0
if __name__=='__main__':raise SystemExit(main())
