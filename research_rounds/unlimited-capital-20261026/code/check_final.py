from pathlib import Path
import gzip,json,sys,hashlib
from funding_audit import verify
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
def read(p):return json.loads(Path(p).read_text())
def rows(p,aid=None):
 with gzip.open(p,'rt') as f:
  for line in f:
   x=json.loads(line)
   if aid is None or x['account']==aid:yield x
def write(p,x):
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def event_time(x):return x.get('at') or x.get('decision_at') or x.get('receipt',{}).get('at') or x.get('receivable',{}).get('ex_at')
def main(mode):
 if mode=='funding':
  receipts=[];src=HERE/'accounts-v1'
  for aid in read(src/'summary.json')['accounts']:
   r=verify(list(rows(src/'audit.jsonl.gz',aid)),list(rows(src/'daily.jsonl.gz',aid)),read(src/f'{aid}-final.json'));receipts.append(dict(account=aid,**r));print(dict(funding_verified=aid,operations=r['operations']),flush=True)
  write(HERE/'analysis-v1/funding-audit.json',dict(passed=True,accounts=receipts))
 elif mode=='prefix':
  cutoff='2015-03-31';pref=HERE/'technical/prefix';src=HERE/'accounts-v1';aids=read(pref/'summary.json')['accounts'];counts={}
  for name in ['daily','decisions','fills','audit']:
   n=0
   for aid in aids:
    a=[]
    for x in rows(src/f'{name}.jsonl.gz',aid):
     if event_time(x)[:10]>cutoff:break
     a.append(x)
    b=list(rows(pref/f'{name}.jsonl.gz',aid))
    assert a==b,(name,aid,'prefix mismatch');n+=len(a)
   counts[name]=n
  write(HERE/'technical/prefix-identity.json',dict(passed=True,cutoff=cutoff,paths=3,rows=counts,removed_future=['raw_execution_bars','E0_prepared_states','H1_matrix','I_IX_market_evidence','corporate_actions'],I_projection_rebuilt_from_prefix=True));print(counts,flush=True)
 elif mode=='close':
  for p in [HERE/'analysis-v1/accounting.json',HERE/'analysis-v1/funding-audit.json',HERE/'technical/prefix-identity.json']:assert read(p)['passed']
  freeze=read(HERE/'account-freeze-v1.json');frozen=freeze['sha256'];assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen.items())
  for item in freeze['source_receipt']['signals']:
   p=ROOT/'research_rounds/ix-a-share-entry-20261025/signals'/(item['sid']+'.parquet')
   assert hashlib.sha256(p.read_bytes()).hexdigest()==item['source_sha256'],str(p)
  r=read(HERE/'RUN_STATE.json');r.update(phase='complete',economic_paths=9,economic_runs=1,economic_rule_revisions=0,economic_reruns=0,remaining=[])
  (HERE/'RUN_STATE.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
  paths=[p for p in HERE.rglob('*') if p.is_file() and p.name not in ['complete.json'] and p.suffix!='.log']
  write(HERE/'complete.json',dict(status='complete',economic_paths=9,economic_runs=1,economic_reruns=0,economic_rule_revisions=0,downloads=0,frozen_inputs_unchanged=True,sha256={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}));print('complete',flush=True)
 else:raise ValueError(mode)
if __name__=='__main__':main(sys.argv[1])
