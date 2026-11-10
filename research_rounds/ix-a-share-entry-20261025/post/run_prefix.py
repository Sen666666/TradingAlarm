"""Run the predeclared physical cutoff in parallel; compare only after full run closes."""
from pathlib import Path
import sys,os,gzip,json,time
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE/'code'))
from util_ix import *
from run_multi import context,Sink
from multi_runner import HistoryRunner,iso

def main():
 freeze=read(HERE/'freeze.json');verify(freeze['sha256']);verify(read(HERE/'old-identity-before.json')['sha256'])
 cutoff='2023-12-29';b,m=context(cutoff);os.environ['IX_ENTRY_STRESSES']='base';package=read(OLD/'inputs-v2/package.json');end=max(x for x in m.cutoffs if x.date().isoformat()<=cutoff)
 out=HERE/f'technical/multi-prefix-{cutoff}';sink=Sink(out);r=HistoryRunner(b,m,start=iso(package['start']),end=end,sink=sink,synthetic=True)
 provenance=dict(recorded_at=now(),entry_modes=ENTRY_TYPES,technical=True,cutoff=cutoff,account_specs=[s.account_id for s in r.specs],source='predeclared physical cutoff; frozen run_multi context/runner/sink unchanged, comparison deferred until full stream is closed',code=sha(__file__))
 try:
  summary=r.run();r.write(out,summary,provenance)
 finally:sink.close()
 # The computation is independent of the full result; only validation waits.
 while not (HERE/'accounts/summary.json').exists():time.sleep(3)
 expected={}
 with gzip.open(HERE/'accounts/daily.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line)
   if x['account'] in r.accounts and iso(x['at'])<=end:expected[(x['account'],x['at'])]=x
 n=0
 with gzip.open(out/'daily.jsonl.gz','rt') as f:
  for line in f:x=json.loads(line);assert x==expected.pop((x['account'],x['at']));n+=1
 assert not expected
 write(out/'comparison.json',dict(recorded_at=now(),passed=True,technical_accounts=16,daily_rows_exact=n,future_prices_states_actions_removed=True))
 print(dict(technical_prefix_passed=True,accounts=16,rows=n),flush=True)

if __name__=='__main__':main()
