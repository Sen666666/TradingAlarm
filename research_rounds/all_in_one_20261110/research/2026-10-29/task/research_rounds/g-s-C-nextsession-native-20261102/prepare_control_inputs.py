"""Read-only original source export; full vs physically deleted future control."""
from pathlib import Path
import sys,importlib.util,json,copy,shutil,hashlib
import pandas as pd
HERE=Path(__file__).resolve().parent;W=HERE.parent;OLD=W/'g-s-historical-native-nextsession-20261101'
sys.path.insert(0,str(OLD));from common_next import *
NEXT_SOURCE=W/'g-s-historical-native-nextsession-20261101'
def export():
 spec=importlib.util.spec_from_file_location('c_original_future_export',HERE/'future_export_source.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 m.O=HERE/'future-export';m.O.mkdir(exist_ok=False)
 m.SPECS={'2022':dict(old_end='2022-01-05',next_day='2022-01-07'),'2025_26':dict(old_end='2025-07-02',next_day='2025-07-04')};m.run()
def prepare():
 rows=[]
 for k,s in SPECS.items():
  actual=NEXT_SOURCE/'inputs'/k;future=HERE/'future-export/inputs'/k;root=HERE/'inputs'/k/'full';root.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(actual,root)
  m=LD.read(root/'MANIFEST.json');fm=LD.read(future/'MANIFEST.json');base=copy.deepcopy(m['files']);nextday=s['next_day'];futureday='2022-01-07' if k=='2022' else '2025-07-04'
  m['days']=m['days']+[futureday];m['horizon_extension']['authorized_next_session']=nextday;m['horizon_extension']['future_control_through']=futureday
  for name,rec in m['extensions'].items():
   p=root/rec['path'];q=future/fm['extensions'][name]['path']
   if p.suffix=='.parquet':z=pd.concat([pd.read_parquet(p),pd.read_parquet(q)],ignore_index=True);z.to_parquet(p,index=False)
   else:
    z=LD.read(p);other=LD.read(q)
    if name=='metadata':z={sid:z[sid]+other[sid] for sid in z}
    else:z=z+other
    LD.write(p,z)
   rec['sha256']=sha(p);rec['rows']=len(z)
  LD.write(root/'MANIFEST.json',m)
  cut=root.parent/'physical';shutil.copytree(root,cut);cm=LD.read(cut/'MANIFEST.json');cm['days']=[d for d in cm['days'] if d<=nextday];removed={}
  for name,rec in cm['extensions'].items():
   p=cut/rec['path']
   if p.suffix=='.parquet':z=pd.read_parquet(p);before=len(z);z=z[z.day<=nextday];removed[name]=before-len(z);z.to_parquet(p,index=False)
   else:
    z=LD.read(p)
    if name=='metadata':
     before=sum(map(len,z.values()));z={sid:[r for r in rr if r['observed_day']<=nextday] for sid,rr in z.items()};removed[name]=before-sum(map(len,z.values()))
    else:
     before=len(z);field='confirmed_day' if name=='receipts' else 'paid_at' if name=='payments' else 'effective_date';z=[r for r in z if r.get(field) and r[field][:10]<=nextday];removed[name]=before-len(z)
    LD.write(p,z)
   rec['sha256']=sha(p);rec['rows']=len(z)
  cm['horizon_extension']['future_physically_deleted_after']=nextday;LD.write(cut/'MANIFEST.json',cm)
  assert m['files']==cm['files']==base
  for n,r in base.items():assert sha(root/r['path'])==sha(cut/r['path'])==r['sha256']
  rows.append(dict(window=k,nextday=nextday,future_control_day=futureday,full=str(root/'MANIFEST.json'),full_sha256=sha(root/'MANIFEST.json'),physical=str(cut/'MANIFEST.json'),physical_sha256=sha(cut/'MANIFEST.json'),removed=removed,old_prefix_base_all_exact=True,calendar_note='Original published exchange schedule retained for next legal OPEN; not future market observations.'))
 save(HERE/'INPUT_FREEZE.json',dict(financial_events=0,models_recomputed=0,original_exporter_sha256=sha(NEXT_SOURCE/'prepare_inputs.py'),exporter_cutoff_only_sha256=sha(HERE/'future_export_source.py'),rows=rows))
 print(json.dumps(rows,ensure_ascii=False,indent=2))
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='export':export()
 else:prepare()
