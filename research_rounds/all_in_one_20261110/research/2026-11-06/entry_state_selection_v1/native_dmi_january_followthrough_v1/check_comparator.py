"""Read-only final timestamp comparator regression. Zero account events."""
from pathlib import Path
import json,gzip,hashlib
import continue_accounts as F
B=F.B;O=F.O

def check():
 cases={
 '2022Jan_OPEN':('2022-01-28 15:10:00+08:00','2022-02-07 09:30:00+08:00',[213,19,1012,344],[0,0,17,0,0,0,1]),
 '2022Jan_CLOSE':('2022-01-28 15:10:00+08:00','2022-02-07 15:10:00+08:00',[213,20,1017,344],[1,1709,17,65,1,156,1]),
 '2026Jan_OPEN':('2026-01-30 15:10:00+08:00','2026-02-02 09:30:00+08:00',[5978,989,28940,9350],[0,0,161,0,0,0,1]),
 '2026Jan_CLOSE':('2026-01-30 15:10:00+08:00','2026-02-02 15:10:00+08:00',[5978,990,28977,9350],[1,1709,164,43,1,35,1])}
 results={k:dict(history={},streams={}) for k in cases}
 def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 with gzip.open(B.BASE/'pair/PVR.json.gz','rt') as f:a=json.load(f)
 for name,(_,cut,hc,sc) in cases.items():
  for idx,key in enumerate(['trades','decisions','audit','journal']):
   new=[x for x in a[key] if F.saved_event_time(x,'account_history')<=F.pd.Timestamp(cut)]
   prior=[x for x in a[key] if F.record_at(x)<=cut]
   assert new==prior and len(new)==hc[idx],(name,key,len(new),hc[idx])
   results[name]['history'][key]=dict(rows=len(new),exact_selected_records_sha256=digest(new))
 del a
 specs=[('daily','at'),('opportunities','day'),('funding','at'),('industry','day'),('balances','at'),('rank-policy','day'),('OPEN_CASH_CHECKS','at')]
 for idx,(key,dt) in enumerate(specs):
  path=B.BASE/(key+'.jsonl.gz') if key=='OPEN_CASH_CHECKS' else B.BASE/'pair'/(key+'.jsonl.gz')
  rows=[x for x in B.rows(path) if x['account']=='PVR']
  for name,(lo,cut,hc,sc) in cases.items():
   new=[x for x in rows if F.pd.Timestamp(lo)<F.saved_event_time(x,dt)<=F.pd.Timestamp(cut)]
   if key=='OPEN_CASH_CHECKS':prior=[x for x in rows if F.pd.Timestamp(lo)<F.pd.Timestamp(x['at'])<=F.pd.Timestamp(cut)]
   else:prior=[x for x in rows if lo[:10]<x[dt][:10]<=cut[:10] and ((x[dt]<cut[:10] or 'CLOSE' in name) if dt=='day' else x[dt]<=cut)]
   assert new==prior and len(new)==sc[idx],(name,key,len(new),sc[idx])
   results[name]['streams'][key]=dict(rows=len(new),exact_selected_records_sha256=digest(new))
 for name,z in results.items():
  w,phase=name.rsplit('_',1);q=B.read(O/'engineering'/(w+'_verified2')/'RESULT.json')
  e=next(e for e in q['checks'] if e['phase']==phase)
  for key,v in {**z['history'],**z['streams']}.items():assert e['exact_checks'][key]['rows']==v['rows'],(name,key,'ENGINEERING_COUNT_CHANGED')
 B.save(O/'COMPARATOR_REGRESSION.json',dict(passed=True,account_events=0,all_four_final_parsed_time_record_selections_exact=True,unknown_time_schema_fails=True,day_logs_explicit_close_1510=True,monetary_values_and_IDs_unchanged=True,actual_OPEN_cash_at_formatted_as_original_isoformat_only=True,results=results,source_sha256={str(p):B.sha(p) for p in [Path(__file__),O/'continue_accounts.py',B.BASE/'OUTPUT_HASHES.json']}))
 print('COMPARATOR_PASS',flush=True)
if __name__=='__main__':check()
