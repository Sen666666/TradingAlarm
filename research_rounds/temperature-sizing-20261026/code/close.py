from common import *
def event_time(x):return x.get('at') or x.get('receipt',{}).get('at') or x.get('receivable',{}).get('ex_at')
def prefix():
 p=HERE/'technical/prefix';cutoff='2018-12-28';aids=read(p/'summary.json')['accounts'];counts={}
 for name in ['daily','fills','audit']:
  n=0
  for aid in aids:
   source=HERE/('technical/controls-v2' if aid.startswith('F100') else 'accounts-v1');a=[];b=[]
   for x in rows(source/f'{name}.jsonl.gz'):
    if event_time(x)[:10]>cutoff:break
    if x['account']==aid:a.append(x)
   b=[x for x in rows(p/f'{name}.jsonl.gz') if x['account']==aid];assert a==b,(name,aid,'physical prefix mismatch');n+=len(a)
  counts[name]=n
 write(HERE/'technical/prefix-identity.json',dict(passed=True,paths=7,cutoff=cutoff,rows=counts,removed_future=['raw_prices','derived_raw_arrays','actions','eligibility_and_temperature_packets'],signal_causality='inherited prior original physical prefix checks; this checks new financial execution'))
 print(counts,flush=True)
def close():
 for p in [HERE/'analysis-v1/accounting.json',HERE/'analysis-v1/funding.json',HERE/'technical/prefix-identity.json',HERE/'technical/controls-v2-identity.json']:assert read(p)['passed']
 f=read(HERE/'account-freeze-v1.json');bad=[p for p,h in f['sha256'].items() if sha(ROOT/p)!=h];assert not bad,bad
 state=read(HERE/'RUN_STATE.json');state.update(phase='complete',remaining=[],new_economic_paths=18,reused_full_controls=3,economic_runs=1,economic_reruns=0,rule_revisions_after_economic=0);(HERE/'RUN_STATE.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 paths=[p for p in HERE.rglob('*') if p.is_file() and p.name!='complete.json' and p.suffix!='.log'];write(HERE/'complete.json',dict(status='complete',new_economic=18,reused_controls=3,economic_runs=1,economic_reruns=0,rule_revisions=0,downloads=0,frozen_inputs_and_code_unchanged=True,sha256={str(p.relative_to(HERE)):sha(p) for p in paths}));print('complete',flush=True)
if __name__=='__main__':prefix() if sys.argv[1]=='prefix' else close()
