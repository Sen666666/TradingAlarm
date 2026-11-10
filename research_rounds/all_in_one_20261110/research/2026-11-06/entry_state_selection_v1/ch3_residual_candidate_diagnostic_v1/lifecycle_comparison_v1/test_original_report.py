"""No lifecycle calls: attribution of already frozen original outputs only."""
import pandas as pd
from adapter import O,ENGINES,OLD_OUTPUTS,load_engine,compare_table,save,sha
from report import derive_original_report,add_gross
out={}
for window in ['2022','2024_924']:
 s=load_engine(window)
 z,cov=derive_original_report(s,window,OLD_OUTPUTS[window])
 a=pd.read_csv(OLD_OUTPUTS[window]/'ACTIONS.csv',float_precision='round_trip',low_memory=False)
 z=add_gross(z,a)
 original=pd.read_csv(ENGINES[window].parent/'report/CORE_AND_FULL_ROUNDS.csv',float_precision='round_trip',low_memory=False)
 out[window]=compare_table(z,original,['round_id'])
 assert not s.rounds and not s.actions and not s.claims and not s.decisions
 print('ORIGINAL_REPORT_PASS',window,out[window],flush=True)
 del s
out.update(no_lifecycle_called=True,no_new_economic_path=True,report_sha256=sha(O/'report.py'))
save(O/'TEST_ORIGINAL_REPORT_QA.json',out)
