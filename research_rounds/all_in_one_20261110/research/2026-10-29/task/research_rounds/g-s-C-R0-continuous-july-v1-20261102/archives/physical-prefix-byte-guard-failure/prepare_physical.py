"""Physically delete future rows in original raw/derived file channels, no models."""
from pathlib import Path
import copy,json,shutil,hashlib
import pandas as pd
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'g-s-C-month-continuation-20261102/inputs/2025_26';OUT=ROOT/'physical-through-Jul2';CUT='2025-07-02'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=json.loads((OLD/'MANIFEST.json').read_text());OUT.mkdir(exist_ok=False);removed={}
for group in ['files','extensions','month_extension']:
 for key,rec in m[group].items():
  src=OLD/rec['path'];dst=OUT/rec['path'];dst.parent.mkdir(parents=True,exist_ok=True)
  if src.suffix=='.parquet':
   z=pd.read_parquet(src);before=len(z)
   if 'day' in z.columns:z=z[z['day']<=CUT]
   z.to_parquet(dst,index=False);removed[group+'/'+key]=before-len(z)
  else:
   z=json.loads(src.read_text());before=0;after=0
   if key=='metadata':
    if group=='files':
     for sid,x in z.items():
      before+=len(x['structure_observations']);x['structure_observations']=[r for r in x['structure_observations'] if r['observed_day']<=CUT];after+=len(x['structure_observations'])
    else:
     before=sum(map(len,z.values()));z={sid:[r for r in rs if r['observed_day']<=CUT] for sid,rs in z.items()};after=sum(map(len,z.values()))
   elif key in ['actions','receipts','payments']:
    field={'actions':'effective_date','receipts':'confirmed_day','payments':'paid_at'}[key];before=len(z);z=[r for r in z if r.get(field) and r[field][:10]<=CUT];after=len(z)
   else:before=after=0 # Published rules/calendar, seeds, universe/provenance fixed.
   dst.write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n');removed[group+'/'+key]=before-after
  rec['sha256']=sha(dst)
  if 'rows' in rec:rec['rows']=len(z)
m['days']=[d for d in m['days'] if d<=CUT];m['physical_control']=dict(actual_future_rows_deleted_after=CUT,published_calendar_retained=True,models_recomputed=False)
(OUT/'MANIFEST.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
(ROOT/'PHYSICAL_INPUT.json').write_text(json.dumps(dict(path=str(OUT/'MANIFEST.json'),sha256=sha(OUT/'MANIFEST.json'),removed=removed,financial_events=0,channels=sorted(removed)),ensure_ascii=False,indent=2)+'\n')
print('PHYSICAL_INPUT_READY',sha(OUT/'MANIFEST.json'),sum(removed.values()),'future rows removed',flush=True)
