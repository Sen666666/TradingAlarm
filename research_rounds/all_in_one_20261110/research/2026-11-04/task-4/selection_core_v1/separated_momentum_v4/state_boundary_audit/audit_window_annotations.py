"""Independent first-visible versus identifiable-new/carry annotation checks; state tables only."""
from pathlib import Path
import pandas as pd,json,hashlib,collections
import reference_state_machine as R
O=Path(__file__).resolve().parent;P=O.parent/'ranking/STATES_ALL_2021_2026.parquet';W=O.parent/'ranking/FIXED_WINDOWS_ALL90.csv'
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def nullstr(x):return None if pd.isna(x)else str(x)
def tri(x):
 if pd.isna(x):return None
 if isinstance(x,str):return {'True':True,'False':False}[x]
 return bool(x)
D=pd.read_parquet(P,columns=['date','sector_id_static','T_order','T_selected','P_mature','UNION_selected','P_state_event']);D.date=pd.to_datetime(D.date).dt.strftime('%Y-%m-%d')
errors=[];tcount=0
for a in D.itertuples(index=False):
 rank=R.normalize_rank(None if pd.isna(a.T_order)else a.T_order);ex=None if rank is None else rank<=3;ac=tri(a.T_selected);tcount+=1
 if ex is not ac:errors.append({'date':a.date,'sector':a.sector_id_static,'error':'T_order_vs_observation_selection','expected':ex,'actual':ac})
for d,g in D.groupby('date'):
 vals=sorted(R.normalize_rank(x)for x in g.T_order.dropna())
 if vals!=list(range(1,len(vals)+1)):errors.append({'date':d,'error':'T_order_not_1based_permutation'})
 if int(g.T_selected.eq(True).sum())>3:errors.append({'date':d,'error':'T_more_than3'})
source=pd.read_csv(W);own=json.loads((O/'REFERENCE_FIXED_WINDOWS_STATE_ONLY.json').read_text());lookup={(x['sector'],x['first_session'],x['last_session']):x for x in own};checks=[]
for a in source.to_dict('records'):
 key=(a['sector_id_static'],a['first_session'],a['last_session']);e=lookup[key];tests={'P_carryin':(e['public_P_carryin'],tri(a['P_carryin'])),'P_states_before_window':(e['states_before_first_session'],json.loads(a['P_states_before_window'])),'sessions':(e['session_count'],int(a['sessions'])),'P_first_observed_mature':(e['first_observed_P_mature'],nullstr(a['P_first_observed_mature'])),'P_first_true_new_maturity':(e['first_identifiable_NEW_MATURE'],nullstr(a['P_first_true_new_maturity'])),'P_true_new_maturities':(e['P_new_events'],int(a['P_true_new_maturities'])),'P_true_removals':(e['P_exit_events'],int(a['P_true_removals'])),'P_first_observed_selected':(e['first_observed_P_mature'],nullstr(a['P_first_observed_selected'])),'T_first_observed_selected':(e['first_observed_T_selected'],nullstr(a['T_first_observed_selected'])),'union_first_observed_selected':(e['first_observed_union_true'],nullstr(a['union_first_observed_selected']))}
 for field,(ex,ac) in tests.items():
  checks.append({'window':a['window'],'sector':a['sector_id_static'],'field':field,'expected':ex,'actual':ac,'equal':ex==ac})
  if ex!=ac:errors.append({'window':a['window'],'sector':a['sector_id_static'],'field':field,'expected':ex,'actual':ac})
events=D.assign(year=D.date.str[:4]).groupby(['year','P_state_event']).size().rename('rows').reset_index();events.to_csv(O/'VERIFIED_STATE_EVENTS_BY_YEAR.csv',index=False)
carry=[x for x in own if x['first_visible_P_can_be_carry_not_new']];late=[x for x in own if x['first_observed_P_mature']!=x['first_identifiable_NEW_MATURE']]
summary={'status':'PASS'if not errors else'FAIL','T_selection_rows_checked':tcount,'T_1based_permutation_days_checked':int(D.date.nunique()),'fixed_window_rows_checked':len(source),'fixed_window_annotation_cells_checked':len(checks),'mismatch_count':len(errors),'fixed_window_first_P_visible_on_carry_not_new_rows':len(carry),'fixed_window_first_visible_P_differs_identifiable_new_rows':len(late),'all_rows_scope_includes2021_warmup':True,'no_market_scores_or_labels_recomputed_or_read':True,'new_accounts':0,'source_SHA256':{str(p.resolve()):h(p)for p in [P,W,O/'REFERENCE_FIXED_WINDOWS_STATE_ONLY.json',Path(__file__)]}}
(O/'FIXED_WINDOW_ANNOTATION_AUDIT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(O/'FIXED_WINDOW_ANNOTATION_EXPECTED_AND_ACTUAL.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n');(O/'FIXED_WINDOW_ANNOTATION_MISMATCHES.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2)+'\n');(O/'FIXED_WINDOW_CARRY_NOT_NEW_EXAMPLES.json').write_text(json.dumps(carry,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False));print(events.to_string(index=False))
if errors:raise SystemExit(1)
