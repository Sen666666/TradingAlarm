"""Pre-recovery physical-prefix and future-perturbation check, original bridge off."""
import engine as s
from engine import pd,np,copy
for sid in set(r['sid'] for r in s.permits.values()):s.load(sid)
originals={name:copy.deepcopy(getattr(s,name)) for name in ['raw','facts','cp','capacity','sector','cal','permits','EVENTS']}
def restore():
 for name,v in originals.items():setattr(s,name,copy.deepcopy(v))
 s.install_events([])
def digest():
 return dict(actions=s.copy.deepcopy(s.actions),rounds=s.copy.deepcopy(s.rounds),marks=s.copy.deepcopy(s.marks),claims=s.copy.deepcopy(s.all_claims),registrations=s.copy.deepcopy(s.registrations))
def run(cut):
 s.reset()
 for rid,r in s.permits.items():
  if r['day']<=cut:s.run_fixed(rid,cut)
 return digest()
def normalize(x):return s.json.dumps(x,sort_keys=True,default=str,allow_nan=True)
results=[]
for cutoff in ['2026-03-31','2026-05-15','2026-05-18','2026-06-10','2026-06-30']:
 cut=pd.Timestamp(cutoff);restore();base=run(cut)
 for mode in ['TRUNCATE','PERTURB']:
  restore()
  for name in ['raw','facts','cp']:
   for sid,v in getattr(s,name).items():
    if mode=='TRUNCATE':v.frame=v.frame.loc[v.frame.index<=cut].copy()
    else:
     for col in v.frame.columns:
      mask=v.frame.index>cut
      if pd.api.types.is_numeric_dtype(v.frame[col].dtype) and not pd.api.types.is_bool_dtype(v.frame[col].dtype):v.frame.loc[mask,col]=v.frame.loc[mask,col]*7
  for sid,caps in s.capacity.items():s.capacity[sid]={d:(v if d<=cut else -999.) for d,v in caps.items() if mode!='TRUNCATE' or d<=cut}
  for sec,days in s.sector.items():s.sector[sec]={d:(v if d<=cut else -1) for d,v in days.items() if mode!='TRUNCATE' or d<=cut}
  if mode=='TRUNCATE':s.cal=s.cal[s.cal<=cut];s.permits={rid:r for rid,r in s.permits.items() if r['day']<=cut}
  out=run(cut);assert normalize(base)==normalize(out),(cutoff,mode)
  results.append(dict(cutoff=cutoff,mode=mode,rounds=len(out['rounds']),actions=len(out['actions']),pass_=True))
restore();s.save(s.O/'PREFIX_QA.json',dict(pass_=True,cases=results,scope='bridge-off fixed-permit economic paths; source-enabled OPEN gates separately tested with d HLC/volume/flags perturbation and overlap prefix',new_recovery_economic_runs=0));print('PREFIX_PASS',len(results))
