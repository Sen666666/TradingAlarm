"""Compare saved signal outputs, never execute a model or account."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd
BASE=Path(__file__).resolve().parents[1]
OLD=BASE/'results/v0';NEW=BASE/'results/v0-input-fixed'
out=BASE/'validation/input-fixed-result-comparison.json'
if out.exists(): raise FileExistsError(out)
state_discrete=['target','entered','exited','pending','pending_id','pending_since','created','response','consumed_by_base','independent_entry','ended_id','entry_kind','high_effort','declined','price_event','ready','original_target','original_entered','original_exited','price_target','all_target','legacy_target','rank_score','peer_count','pool']
ledger_discrete=['id','created_date','created_observation','created_on_exit','resolved_date','outcome','response','independent_entry','original_entry_same_day','waiting_observations']
upstream_discrete=['leg_direction','event','target','entered','exited','pivot_age','confirmed_pivot_date','developing_extreme_date']
records=[]
for path in sorted(NEW.glob('*.csv')):
 a=pd.read_csv(OLD/path.name,float_precision='round_trip');b=pd.read_csv(path,float_precision='round_trip')
 assert list(a)==list(b),(path.name,'columns')
 discrete=state_discrete if path.name.endswith('-states.csv') else ledger_discrete if path.name.endswith('-events.csv') else upstream_discrete if path.name.endswith('-upstream.csv') else list(a.columns)
 exact=[];substantive=[]
 if a.shape!=b.shape: substantive.append({'shape':[a.shape,b.shape]})
 else:
  for c in a:
   if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c]):
    av=a[c].to_numpy(float);bv=b[c].to_numpy(float)
    eq=(av==bv)|(np.isnan(av)&np.isnan(bv));near=np.isclose(av,bv,atol=1e-10,rtol=1e-10,equal_nan=True)
   else:
    eq=(a[c].fillna('<NA>').astype(str)==b[c].fillna('<NA>').astype(str)).to_numpy();near=eq
   if not eq.all():exact.append({'field':c,'cells':int((~eq).sum())})
   good=eq if c in discrete else near
   if not good.all():substantive.append({'field':c,'rows':a.loc[~good].to_dict('records'),'new_rows':b.loc[~good].to_dict('records')})
 records.append({'file':path.name,'old_sha256':hashlib.sha256((OLD/path.name).read_bytes()).hexdigest(),'new_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'discrete_fields':discrete,'all_contract_fields_equal':not substantive,'exact_changed':exact,'contract_differences':substantive})
record={'meaning':'All saved signal columns, ledger identity, rankings and summary outputs before/after source arithmetic repair; discrete exact, continuous atol/rtol1e-10','files':records,'passed':all(r['all_contract_fields_equal'] for r in records),'account_runs':0,'model_runs':0}
out.write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'files':len(records),'passed':record['passed'],'failed_files':[r['file'] for r in records if not r['all_contract_fields_equal']]}))
