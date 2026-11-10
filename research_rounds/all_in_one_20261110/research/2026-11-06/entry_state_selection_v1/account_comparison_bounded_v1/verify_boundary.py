"""Read saved reconstruction only. Correct nested fill-receipt timestamps."""
from pathlib import Path
import json,gzip,hashlib,argparse
O=Path(__file__).resolve().parent
OLD=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/runs/BASELINE')
def rowday(r):return str(r.get('at') or r.get('day') or r.get('receipt',{}).get('at') or r.get('receivable',{}).get('ex_at') or '')[:10]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--day',required=True);z=ap.parse_args();day=z.day
 p=O/'boundaries'/day;win='2022_2024' if day=='2024-09-24' else 'strong';base=OLD/win/'pair'
 a=json.load(gzip.open(p/'pair/B.json.gz','rt'));b=json.load(gzip.open(base/'B.json.gz','rt'))
 checks={};counts={}
 for k in ('audit','journal','decisions','trades'):
  expected=[r for r in b[k] if rowday(r)<=day]
  assert all(rowday(r) for r in b[k]),('unknown rowtime',k)
  checks[k]=a[k]==expected;counts[k]=len(a[k])
 for k in ('daily','funding','opportunities','industry','balances','rank-policy'):
  with gzip.open(p/'pair'/(k+'.jsonl.gz'),'rt') as f:actual=[json.loads(l) for l in f]
  with gzip.open(base/(k+'.jsonl.gz'),'rt') as f:expected=[r for l in f if rowday(r:=json.loads(l))<=day]
  checks[k]=actual==expected;counts[k]=len(actual)
 result=dict(passed=all(checks.values()),day=day,checks=checks,counts=counts,correction='Initial comparator missed nested audit fill receipt.at; saved account events were not rerun or changed.',source_checkpoint_sha256=hashlib.sha256((p/'checkpoint.pkl').read_bytes()).hexdigest())
 (p/'VERIFIED_BOUNDARY.json').write_text(json.dumps(result,indent=2)+'\n');assert result['passed'],checks
 print(json.dumps(result))
if __name__=='__main__':main()

