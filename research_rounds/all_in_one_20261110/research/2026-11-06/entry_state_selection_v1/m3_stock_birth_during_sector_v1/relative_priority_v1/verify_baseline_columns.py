from pathlib import Path
import json
import pandas as pd
O=Path(__file__).resolve().parent;E=O.parent
checks={}
for name,key in [('ROUNDS.csv',['round_id']),('ACTIONS.csv',['round_id','day','side']),('DECISIONS.csv',['window','day','sector','sid']),('END_STATES.csv',['window','sid'])]:
 old=pd.read_csv(E/'lifecycle_v1'/name,float_precision='round_trip');old=old[old.arm.eq('A_UNION_B')]
 new=pd.read_csv(O/'baseline'/name,float_precision='round_trip')
 assert set(old.columns)==set(new.columns),name
 new=new[old.columns]
 old=old.sort_values(key).reset_index(drop=True);new=new.sort_values(key).reset_index(drop=True)
 pd.testing.assert_frame_equal(old,new,check_dtype=False,check_exact=True)
 checks[name]=dict(rows=len(new),all_columns_exact=True)
(O/'BASELINE_QA.json').write_text(json.dumps(dict(passed=True,checks=checks),indent=2)+'\n')
print(checks)
