"""Read-only20 new normalized artifacts; no producer/model imports."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np,pyarrow as pa,pyarrow.parquet as pq
O=Path(__file__).resolve().parent;R=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(Path(p).read_text())
f=read(R/'FREEZE.json');schema=pa.ipc.read_schema(pa.BufferReader((R/'DAILY_SCHEMA.arrow').read_bytes()));grid=pd.DatetimeIndex(pd.read_parquet(f['grid_path']).day)
assert sha(R/'run_cache.py')==f['code_sha256'][str((R/'run_cache.py').resolve())]
checks=[];cells=0;diff=[];bound=[R/'FREEZE.json',R/'run_cache.py',R/'DAILY_SCHEMA.arrow',R/'REUSE20_INTEGRATION_CHECK.json',R/'REUSE20_RECEIPT.json',Path(__file__)]
for sid,ref in f['reuse20'].items():
 old=Path(ref['path']);assert sha(old)==ref['sha256'];rec=read(R/'receipts'/f'{sid}.json');path=R/rec['file']
 assert rec['sid']==sid and rec['status']=='DONE_VALIDATED'and rec['cache_identity']==f['cache_identity']and rec['origin']=='REUSED_SEALED_PILOT20_NORMALIZED_SCHEMA_NO_MODEL'
 assert sha(path)==rec['file_sha256']and path.stat().st_size==rec['file_bytes']
 a=pq.read_table(old);b=pq.read_table(path);assert b.schema.remove_metadata().equals(schema)and b.num_rows==rec['rows']==1054
 assert b.schema.metadata[b'local_cache_identity'].decode()==f['cache_identity']and b.schema.metadata[b'local_cache_sid'].decode()==sid
 x,y=a.to_pandas(),b.to_pandas();assert x.columns.equals(y.columns)and list(y.columns)==f['schema_columns']and pd.DatetimeIndex(y.day).equals(grid)
 for c in x:
  u,v=x[c],y[c];assert u.isna().equals(v.isna()),(sid,c,'NA')
  k=u.notna()
  if pd.api.types.is_numeric_dtype(u)and not pd.api.types.is_bool_dtype(u):assert np.array_equal(u[k].to_numpy(float).view(np.uint64),v[k].to_numpy(float).view(np.uint64)),(sid,c,'bits')
  else:assert u[k].astype(str).equals(v[k].astype(str)),(sid,c,'values')
 assert x.size==rec['details']['normalized_schema_value_cells'] and rec['details']['original_pilot_file_sha256']==ref['sha256']
 assert y.historical_trading_eligibility.eq('UNKNOWN_NONPIT').all()
 if not a.schema.remove_metadata().equals(schema):diff.append({'sid':sid,'fields':[(i.name,str(i.type),str(j.type))for i,j in zip(a.schema,schema)if i!=j]})
 cells+=x.size;checks.append({'sid':sid,'rows':1054,'columns':len(y.columns),'cells':x.size,'original_sha256':ref['sha256'],'normalized_sha256':rec['file_sha256']})
 bound.extend([old,path,R/'receipts'/f'{sid}.json'])
assert len(checks)==20 and cells==1918280 and len(diff)==11
out={'status':'PASS_INDEPENDENT_REUSE20_NORMALIZED_SCHEMA_ALL91_VALUES','remaining_blocks':[],'cache_identity':f['cache_identity'],'stocks':20,'rows':21080,'columns':91,'value_and_null_cells':cells,'original_schema_incompatible_files_found':diff,'findings':['Original20 file SHA unchanged. New20 files now exactly follow explicit schema; semantic values/null masks all independently compared.','These are normalized new copies, not byte-identical copies; original-source SHA preserved in each receipt.','Initial rev0 single-schema bytecopy contradiction is corrected before model execution; old preexecution freeze/driver archive preserved.'],'source_sha256':{str(p.resolve()):sha(p)for p in bound},'reviewer_models':0,'reviewer_accounts':0}
p=O/'REUSE20_OUTPUT_AUDIT.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':out['status'],'sha256':sha(p),'cells':cells,'incompatible_original_schemas':len(diff)},ensure_ascii=False))
