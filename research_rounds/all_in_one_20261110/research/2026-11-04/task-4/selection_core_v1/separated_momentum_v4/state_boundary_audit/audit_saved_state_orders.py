"""Independent replay of FIVE SYMBOLIC STATES from saved P_order only.

This does not recompute market inputs, scores, ranks, or any future labels.
Only the completed production state table is read; no production state code imported.
"""
from pathlib import Path
import argparse,json,hashlib,collections
import pandas as pd
import reference_state_machine as R
O=Path(__file__).resolve().parent
FROZEN=O.parent/'FROZEN_DESIGN.txt'
EXPECTED_SHA='29af69f156ea9c14ea62ab5eea3fc1a7ee56dcdebdd33a3fc01d5e493e30e495'
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def tri(x):return None if pd.isna(x) else bool(x)
def states(x):
 a=json.loads(x) if isinstance(x,str) else list(x)
 return R.ordered_states(a)
def main(path):
 assert h(FROZEN)==EXPECTED_SHA,'Unexpected root contract revision'
 cols=['date','sector_id_static','P_order','P_known','possible_states_before','possible_states_after','P_mature','T_selected','UNION_selected']
 path=Path(path);before=h(path);D=pd.read_parquet(path,columns=cols) if path.suffix=='.parquet' else pd.read_csv(path,usecols=cols)
 D.date=pd.to_datetime(D.date).dt.strftime('%Y-%m-%d')
 if path.suffix!='.parquet':
  for b in ['P_known','P_mature','T_selected','UNION_selected']:D[b]=D[b].map(lambda x:None if pd.isna(x) else str(x).lower()=='true')
 assert len(D)==119520 and not D.duplicated(['date','sector_id_static']).any()
 dates=sorted(D.date.unique());assert len(dates)==1328 and dates[0]=='2021-01-04' and dates[-1]=='2026-06-30'
 assert sum(x.startswith('2021') for x in dates)==243
 assert D.sector_id_static.nunique()==90 and D.groupby('date').size().eq(90).all()
 errors=[];checked=collections.Counter();boundary=[];normalization=[]
 for day,g in D.groupby('date',sort=True):
  vals=sorted(R.normalize_rank(x) for x in g.P_order.dropna())
  if vals!=list(range(1,len(vals)+1)):errors.append({'date':day,'error':'P_order_not_exact_1based_known_permutation'})
 for sid,g in D.groupby('sector_id_static',sort=True):
  g=g.sort_values('date');assert g.date.tolist()==dates
  memory=R.ALL_INITIAL;lastwarm=None
  for row in g.itertuples(index=False):
   rank=R.normalize_rank(None if pd.isna(row.P_order) else row.P_order);known=rank is not None
   if tri(row.P_known) is not known:errors.append({'date':row.date,'sector':sid,'error':'P_known_differs_rank_presence'})
   expected_before=R.ordered_states(memory);actual_before=states(row.possible_states_before)
   expected=R.step(memory,rank,tri(row.T_selected));actual_after=states(row.possible_states_after)
   for name,ex,ac in [('states_before',expected_before,actual_before),('states_after',expected['states_after'],actual_after),('P_mature',expected['public_mature'],tri(row.P_mature)),('UNION_selected',expected['union'],tri(row.UNION_selected))]:
    checked[name]+=1
    if ex!=ac:errors.append({'date':row.date,'sector':sid,'error':name,'P_order':rank,'expected':ex,'actual':ac})
   memory=frozenset(expected['states_after'])
   if row.date=='2021-12-31':lastwarm={'sector':sid,'warm_last_date':row.date,'possible_states_after':list(expected['states_after']),'internal_state_identified':len(memory)==1,'public_mature':expected['public_mature'],'P_order':rank}
   if row.date==dates[243]:
    assert lastwarm is not None
    boundary.append(dict(lastwarm,first_study_date=row.date,first_study_states_before=list(expected_before),boundary_memory_exact=tuple(lastwarm['possible_states_after'])==expected_before))
 assert before==h(path),'Production table mutated during independent audit'
 summary={'status':'PASS' if not errors else 'FAIL','production_table':str(path.resolve()),'production_SHA256':before,'root_freeze_SHA256':h(FROZEN),'rows':len(D),'sessions':len(dates),'warmup_sessions':243,'study_sessions':1085,'industries':90,'checks_by_field':dict(checked),'P_order_permutation_days_checked':len(dates),'mismatch_count':len(errors),'warm_end_singleton_industries':sum(x['internal_state_identified'] for x in boundary),'warm_end_unresolved_industries':sum(not x['internal_state_identified'] for x in boundary),'all2022_boundary_memory_exact':all(x['boundary_memory_exact'] for x in boundary),'computed_features_scores_or_ranks':False,'read_future_labels':False,'new_accounts':0,'independent_reference_not_production_code':True,'aux_event_flags_and_counter_annotation_columns_not_checked':True}
 (O/'REAL_SAVED_STATE_AUDIT_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(O/'REAL_SAVED_STATE_MISMATCHES.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2)+'\n');(O/'REAL_2021_TO2022_STATE_BOUNDARY.json').write_text(json.dumps(boundary,ensure_ascii=False,indent=2)+'\n');(O/'REAL_STATE_AUDIT_SOURCE_SHA256.json').write_text(json.dumps({str(p.resolve()):h(p)for p in [path,FROZEN,O/'reference_state_machine.py',Path(__file__)]},ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
 if errors:raise SystemExit(1)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('path');args=a.parse_args();main(args.path)
