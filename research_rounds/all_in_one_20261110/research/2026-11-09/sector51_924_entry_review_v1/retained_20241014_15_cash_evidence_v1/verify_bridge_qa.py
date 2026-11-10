from pathlib import Path
from decimal import Decimal as D
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
a=json.loads((O/'EXTRA_REVIEWED_EQUITY_EVENTS_20241014_15_SEVEN_V1.json').read_text())
qa=[]
for e in a:
 for p,h in e['evidence_hashes'].items():assert sha(p)==h,(p,'hash mismatch')
 action=json.loads(Path(e['local_action_path']).read_text())['events'][e['local_action_ordinal']-1]
 assert action['effective_date']==e['ex_date'] and D(action['split_ratio'])==1 and D(action['cash_per_old_share'])==D(e['d_source'])
 z=pd.read_parquet(e['signal_path']);old=z[z.index<pd.Timestamp(e['ex_date'])].iloc[-1];new=z.loc[pd.Timestamp(e['ex_date'])]
 assert str(old.name.date())==e['record_date']
 for k in ('source_kind','source_path','segment_id'):assert str(old.get(k))==str(new.get(k))
 fo,fn,pc=map(lambda x:D(str(x)),[old.adjustment_factor,new.adjustment_factor,old.raw_close])
 res=fo*pc/(pc-D(e['d_source']))/fn-1
 assert abs(res)<D('1e-11') and str(res)==e['source_coordinate_residual']
 ref=fo*pc/(pc-D(e['d_ref']))/fn-1 if e['d_ref'] is not None else None
 assert (str(ref) if ref is not None else None)==e['official_reference_coordinate_residual']
 qa.append({k:e[k] for k in ['sid','record_date','ex_date','pay_date','d_source','d_cash','d_ref','source_coordinate_residual','official_reference_coordinate_residual']})
print(json.dumps({'status':'PASS','events':qa,'no_engine_or_account_run':True,'reference_residual_is_diagnostic_not_admission_test':True},indent=2))
