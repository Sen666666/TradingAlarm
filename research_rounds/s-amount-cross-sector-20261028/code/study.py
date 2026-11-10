from sa_common import *
import sys,importlib.util

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def setup(sector,version,run_root,cutoff=None):
 if sector=='TECH':
  old=load('sa_old_tech',SFOLD/'code/study.py');old.setup(cutoff)
  holder=old;R=old.R;E=old.E;R.HERE=run_root
 else:
  sys.path.insert(0,str(LOCAL/'code'))
  old=load('sa_old_drug',LOCAL/'code/study.py');old.setup(run_root,cutoff)
  holder=old.Q;R=old.R;E=old.E
 if version=='AMT':holder.STRICT={sid:pd.read_parquet(O/'signals'/sector/f'{sid}.parquet').loc[:cutoff] for sid in pool(sector).symbol}
 else:assert version=='OLD'
 if cutoff:E.risk_policy.RECOVERY=E.risk_policy.RECOVERY.loc[:cutoff].copy()
 return R

def main(sector,version,stage):
 root=O/sector/version;root.mkdir(parents=True,exist_ok=True)
 link=root/'execution-rules-v2.json'
 if not link.exists():link.symlink_to(PRIOR/'execution-rules-v2.json')
 if stage=='economic':
  assert read(O/'admission.json')['passed']
  for path,h in read(O/'freeze.json')['sha256'].items():assert sha(path)==h,path
 end='2024-03-13' if stage=='short' else '2026-06-30' if stage=='prefix' else END
 R=setup(sector,version,root,end if stage=='prefix' else None)
 out=root/({'short':'technical/short-v2','prefix':'technical/prefix','economic':'accounts-v2'}[stage])
 R.run(out,modes=['S'],stresses=['base','cost2','delay1'],start='2023-12-29',end=end,cutoff=end if stage=='prefix' else None,technical=stage!='economic')
if __name__=='__main__':main(*sys.argv[1:])
