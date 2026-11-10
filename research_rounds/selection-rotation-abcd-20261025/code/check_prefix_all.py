from common_abcd import *
import gzip
from check_prefix_decisions import main as decisions

def rows(p):
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def main():
 for cutoff in ['2018-12-28','2023-12-29']:
  expected={};out=HERE/f'technical/prefix-{cutoff}';n=0
  for folder in [HERE/'technical/A-controls',HERE/'accounts']:
   for x in rows(folder/'daily.jsonl.gz'):
    if x['account'].endswith('_base') and x['at'][:10]<=cutoff:expected[x['account'],x['at']]=x
  for x in rows(out/'daily.jsonl.gz'):
   assert x==expected.pop((x['account'],x['at'])),(cutoff,x['account'],x['at']);n+=1
  assert not expected
  write(out/'comparison.json',dict(recorded_at=now(),passed=True,accounts=4,daily_rows_exact=n,future_states_prices_actions_removed=True))
 decisions()
if __name__=='__main__':main()
