"""Parallel independent series production, identical frozen bridge equations."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import json,sys
from current_pool_bridge import load_bundle,build_series,sha256,RESEARCH_BASIS

def worker(args):
 n,record,base,scope,output=args
 item=build_series(record,Path(base),scope)
 directory=Path(output)/f'{n:06d}';directory.mkdir()
 files={}
 for name in ('signal','events','states','memories'):
  frame=getattr(item,name)
  if frame is not None:
   p=directory/(name+'.parquet');frame.to_parquet(p)
   files[name]={'path':str(p.relative_to(output)),'sha256':sha256(p)}
 return dict(series_id=record['series_id'],blocked_reason=item.blocked_reason,
  raw_rows=len(item.raw) if item.raw is not None else 0,
  signal_observations=len(item.states) if item.states is not None else 0,
  synthetic_action_rows=int(item.signal.synthetic_event_bar.sum()) if item.signal is not None else 0,files=files)

def main(manifest,output):
 bundle=load_bundle(manifest);output=Path(output);output.mkdir(exist_ok=False)
 jobs=[(i,item.record,str(bundle.manifest_path.parent),bundle.manifest['scope_date'],str(output))
       for i,(sid,item) in enumerate(sorted(bundle.series.items()))]
 rows=[]
 with ProcessPoolExecutor(max_workers=8) as pool:
  for row in pool.map(worker,jobs,chunksize=1):
   rows.append(row)
   if len(rows)%50==0:print(json.dumps({'prepared':len(rows),'total':len(jobs),'last':row['series_id'],'blocked':sum(x['blocked_reason'] is not None for x in rows)}),flush=True)
 bridge=Path(__file__).with_name('current_pool_bridge.py')
 summary=dict(schema_version=1,source_manifest=str(bundle.manifest_path),source_manifest_sha256=sha256(bundle.manifest_path),
  bridge_sha256=sha256(bridge),research_basis=RESEARCH_BASIS,technical_sample=False,
  signal_ready=all(x['blocked_reason'] is None for x in rows),data_pool_closeout_claim=False,execution_certified=False,
  accounts_run=0,algorithm_changes=0,writer_sha256=sha256(__file__),parallel_independent_series_workers=8,series=rows)
 (output/'manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'prepared':len(rows),'blocked':[(x['series_id'],x['blocked_reason']) for x in rows if x['blocked_reason']]}),flush=True)

if __name__=='__main__':main(sys.argv[1],sys.argv[2])
