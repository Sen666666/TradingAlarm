from common_abcd import *
import gzip

def rows(path):
 with gzip.open(path,'rt') as f:
  for line in f:yield json.loads(line)

def main():
 for cutoff in ['2018-12-28','2023-12-29']:
  out=HERE/f'technical/prefix-{cutoff}';expected={};n=0
  for folder in [HERE/'technical/A-controls',HERE/'accounts']:
   for x in rows(folder/'decisions.jsonl.gz'):
    if x['account'].endswith('_base') and x['at'][:10]<=cutoff:expected[x['account'],x['at']]=x
  for x in rows(out/'decisions.jsonl.gz'):
   assert x==expected.pop((x['account'],x['at'])),(cutoff,x['account'],x['at']);n+=1
  assert not expected
  write(out/'decision-comparison.json',dict(passed=True,cutoff=cutoff,entire_compact_decisions_exact=n,including_rotation_streaks_bans_and_actual_admission=True,recorded_at=now()))
 print(dict(prefix_decisions_passed=True),flush=True)
if __name__=='__main__':main()
