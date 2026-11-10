"""Six fixed series only; reuse original trace, never generate model values/accounts."""
from pathlib import Path
import importlib.util,sys,time,json,traceback,hashlib
O=Path(__file__).resolve().parent;W=O.parent
source=W/'2022-normal-reference-20261031/export_receipts.py'
spec=importlib.util.spec_from_file_location('readonly_2023_export_pilot',source)
X=importlib.util.module_from_spec(spec);sys.modules[spec.name]=X;spec.loader.exec_module(X)
X.O=O/'pilot';X.BEGIN='2023-01-01';X.END='2023-12-29';X.CUT='2023-06-30'
def main():
 started=time.monotonic();sm=X.read(X.L.U/'STOCK_MANIFEST.json');im=X.read(X.L.U/'INDUSTRY_MANIFEST.json')
 rows=[]
 for r in sorted(sm,key=lambda r:r['symbol'])[:3]+sorted(im,key=lambda r:r['series'])[:3]:
  out=X.one(r,industry='series' in r,prefix=True);rows.append(out)
  print('PILOT',out['sid'],out['receipt_count'],round(out['seconds'],4),flush=True)
 stock=sum(r['seconds'] for r in rows if not r['industry'])/3
 industry=sum(r['seconds'] for r in rows if r['industry'])/3
 result=dict(passed=True,window=[X.BEGIN,X.END],fixed_series_selection='first 3 sorted stock and industry identifiers',series=rows,
  seconds=time.monotonic()-started,conservative_export_estimate_seconds=1709*stock+90*industry,
  estimate_includes_extra_prefix_and_original_2025_26_checks=True,
  old_2022_measured_full_export_seconds=116.45,all1799_export_executed=False,
  new_numeric_models=0,new_accounts=0,original_export_source=str(source),original_export_SHA256=X.sha(source))
 X.save(O/'PILOT.json',result);print('DONE',result['seconds'],result['conservative_export_estimate_seconds'],flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  X.save(O/'PILOT_ERROR.json',dict(reason=str(e),traceback=traceback.format_exc(),new_accounts=0));raise
