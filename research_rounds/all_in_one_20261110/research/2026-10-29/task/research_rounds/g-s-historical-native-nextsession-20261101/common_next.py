from pathlib import Path
import sys,hashlib,json,importlib.util,copy
O=Path(__file__).resolve().parent;W=O.parent;OLD=W/'g-s-historical-native-prefix-20261101'
sys.path.insert(0,str(OLD))
import historical_binding as H
from historical_binding import N,C,F1,IO,LD,D,Z,ONE,iso,digest,sha,HistoricalReceipt
sys.path.insert(0,str(H.LOADER_PATH.parent))
spec=importlib.util.spec_from_file_location('gs_r2_structure_export_source',H.LOADER_PATH.parent/'prepare.py');PREP=importlib.util.module_from_spec(spec);spec.loader.exec_module(PREP)
OLD_INDEX_SHA='3da0a63f8753a230d1ebdd5c5f1c25ebc487ace9415873d2391b811afb6ad9c4'
SPECS={'2025_26':dict(old_end='2025-07-02',next_day='2025-07-03'),'2022':dict(old_end='2022-01-05',next_day='2022-01-06')}
def save(p,x):IO.write_json(p,json.loads(json.dumps(x,default=N.encode,allow_nan=False)))
def normalize(x):return json.loads(json.dumps(x,default=N.encode,sort_keys=True,allow_nan=False))
def state_hash(x):return hashlib.sha256(json.dumps(normalize(x),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def old_checkpoint(k):return OLD/'runs'/k/'primary-resume'/(SPECS[k]['old_end']+'-CLOSE.pkl')
def original_guard():
 H.guards();assert sha(OLD/'INPUT_OUTPUT_SHA256.json')==OLD_INDEX_SHA
 idx=LD.read(OLD/'INPUT_OUTPUT_SHA256.json')
 for k in SPECS:
  p=old_checkpoint(k)
  assert sha(p)==idx[str(p.relative_to(OLD))]
  assert sha(p.with_suffix('.provenance.json'))==idx[str(p.with_suffix('.provenance.json').relative_to(OLD))]
