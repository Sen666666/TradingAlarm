from common_abcd import *
import gzip

def main():
 expected={}
 with gzip.open(SRC/'accounts/decisions.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line)
   if x['account'].startswith('IX__S0_'):
    x['account']='A__'+x['account'].split('__')[1];expected[x['account'],x['at']]=x
 n=0
 with gzip.open(HERE/'technical/A-controls/decisions.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line);assert x.pop('rotation') is None;assert x==expected.pop((x['account'],x['at'])),(x['account'],x['at']);n+=1
 assert not expected
 write(HERE/'technical/A-controls/decision-comparison.json',dict(passed=True,all_compact_decisions_exact=n,recorded_at=now()))
 print(dict(old_decisions_exact=n),flush=True)
if __name__=='__main__':main()
