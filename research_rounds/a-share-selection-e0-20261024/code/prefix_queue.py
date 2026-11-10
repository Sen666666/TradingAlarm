"""Wait for fixed main cutoffs, then independently replay the three prefixes."""
import time,subprocess,sys,gzip,json
from build_inputs import HERE,read,write,now,ref

def latest():
 last=None
 try:
  with gzip.open(HERE/'accounts-v1/daily.jsonl.gz','rt') as f:
   for line in f:
    try:last=json.loads(line)['at'][:10]
    except json.JSONDecodeError:pass
 except (EOFError,FileNotFoundError):pass
 return last

def main():
 out=HERE/'technical-prefix';out.mkdir(exist_ok=False)
 write(out/'protocol.json',dict(recorded_at=now(),cutoffs=['2017-12-31','2020-12-31','2023-12-31'],base_policies=['T0','T1','S0','S1'],
  main_economic_accounts_unchanged=13,technical_replay_accounts=12,source_ref=ref(HERE/'code/prefix_live.py'),
  reason='Same predeclared truncation check with bounded reading of the live main stream, no edit of frozen source or strategy decisions'))
 for cutoff in ['2017-12-31','2020-12-31','2023-12-31']:
  while (latest() or '')<=cutoff:
   summary=HERE/'accounts-v1/summary.json'
   if summary.exists() and read(summary).get('status')=='failed_partial_run':raise RuntimeError('Main failed; prefix queue stops')
   time.sleep(10)
  with (out/(cutoff+'.log')).open('x') as log:
   p=subprocess.run([sys.executable,str(HERE/'code/prefix_live.py'),cutoff],stdout=log,stderr=log)
  if p.returncode:raise RuntimeError('Technical prefix failed '+cutoff)
  print(read(out/cutoff/'exact-comparison.json'),flush=True)

if __name__=='__main__':main()
