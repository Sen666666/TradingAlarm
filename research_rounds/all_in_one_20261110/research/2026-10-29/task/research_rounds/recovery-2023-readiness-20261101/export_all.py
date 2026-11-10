"""Approved 2023 receipt-only export. Frozen numeric models are never recalculated."""
from pathlib import Path
import importlib.util,sys,time,traceback
O=Path(__file__).resolve().parent;W=O.parent
spec=importlib.util.spec_from_file_location('original_trace_export_2023',W/'2022-normal-reference-20261031/export_receipts.py')
X=importlib.util.module_from_spec(spec);sys.modules[spec.name]=X;spec.loader.exec_module(X)
X.O=O;X.BEGIN='2023-01-01';X.END='2023-12-29';X.CUT='2023-06-30'
def main():
 started=time.monotonic();sm=X.read(X.L.U/'STOCK_MANIFEST.json');im=X.read(X.L.U/'INDUSTRY_MANIFEST.json')
 identity={str(p):X.sha(p) for p in [Path(__file__),Path(X.__file__),X.L.U/'STOCK_MANIFEST.json',X.L.U/'INDUSTRY_MANIFEST.json',X.L.U/'FREEZE.json',W/'cp1-evidence-trace-20261031/trace.py']}
 f=O/'inputs/FREEZE.json'
 if f.exists():assert X.read(f)['source_SHA256']==identity
 else:X.save(f,dict(window=[X.BEGIN,X.END],source_SHA256=identity,new_models=0,new_account_events=0))
 pilot={r['sid']:r for r in X.read(O/'PILOT.json')['series']};rows=[];reused=0
 for i,r in enumerate(sm+im):
  sid=r.get('symbol',r.get('series'));item=O/'inputs/items'/(sid+'.json')
  old=X.read(item) if item.exists() else pilot.get(sid)
  if old and old['original_output_sha256']==r['output_sha256'] and Path(old['output_path']).is_file() and X.sha(old['output_path'])==old['output_sha256']:
   out=old;reused+=1;X.save(item,out)
  else:out=X.one(r,'series' in r)
  rows.append(out)
  if (i+1)%100==0:
   X.save(O/'inputs/PROGRESS.json',dict(done=len(rows),total=1799,seconds=time.monotonic()-started,reused=reused,last=sid));print('EXPORT',len(rows),round(time.monotonic()-started,2),flush=True)
 assert len(rows)==1799 and sum(r['receipt_count'] for r in rows if not r['industry'])==18781 and sum(r['receipt_count'] for r in rows if r['industry'])==1270
 X.save(O/'inputs/MANIFEST.json',rows);X.save(O/'inputs/COMPLETION.json',dict(passed=True,series=len(rows),stock_receipts=18781,industry_receipts=1270,seconds=time.monotonic()-started,pilot_reused=reused,new_models=0,new_account_events=0))
 print('EXPORT_DONE',round(time.monotonic()-started,3),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:X.save(O/'inputs/ERROR.json',dict(reason=str(e),traceback=traceback.format_exc()));raise
