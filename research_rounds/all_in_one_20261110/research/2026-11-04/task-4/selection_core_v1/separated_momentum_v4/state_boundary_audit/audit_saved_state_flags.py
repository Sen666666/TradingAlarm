"""Counter/event/carry audit from saved orders and symbolic states, no scores/labels."""
from pathlib import Path
import pandas as pd,json,hashlib,collections
import reference_state_machine as R
O=Path(__file__).resolve().parent;P=O.parent/'ranking/STATES_ALL_2021_2026.parquet';CODE=O.parent/'ranking/run_v4.py'
cols=['date','sector_id_static','P_order','T_order','P_known','possible_states_before','possible_states_after','P_mature','P_prevpublic','T_selected','UNION_selected','P_entry_counts_possible','P_exit_counts_possible','P_state_event','P_known_new_maturity','P_known_exit','P_unknown_to_true','P_unknown_to_false','P_input_missing_counter_break','main_day90known']
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def tri(x):return None if pd.isna(x) else bool(x)
def phase(s):return R.public_mature(s,True)
def first(g,k):
 a=[r['date'] for r in g if r[k] is True];return a[0] if a else None
sha=h(P);D=pd.read_parquet(P,columns=cols);D.date=pd.to_datetime(D.date).dt.strftime('%Y-%m-%d');assert len(D)==119520
errors=[];checked=collections.Counter();actual_events=collections.Counter();expected_events=collections.Counter();reference=[];years=[];convergence=[]
for sid,g in D.groupby('sector_id_static',sort=True):
 g=g.sort_values('date');memory=R.ALL_INITIAL;previous_public=None;previous_date=None;previous_after=None;first_single=None;first_phase=None
 for a in g.itertuples(index=False):
  rank=R.normalize_rank(None if pd.isna(a.P_order)else a.P_order);known=rank is not None;bm=phase(memory);step=R.step(memory,rank,tri(a.T_selected));after=step['states_after'];am=phase(after);pub=step['public_mature']
  new=known and bm is False and am is True;exit_=known and bm is True and am is False
  if not known:event='INPUT_MISSING'
  elif new:event='NEW_MATURE'
  elif exit_:event='REMOVED'
  elif bm is None and am is True:event='RESOLVED_ACTIVE'
  elif bm is None and am is False:event='RESOLVED_INACTIVE'
  elif previous_public is None and pub is True:event='DATA_RESUME_ACTIVE'
  elif previous_public is None and pub is False:event='DATA_RESUME_INACTIVE'
  else:event='AMBIGUOUS' if pub is None else 'RETAIN_ACTIVE' if pub else 'RETAIN_INACTIVE'
  ex={'P_prevpublic':previous_public,'P_entry_counts_possible':sorted({int(s[1])for s in after if s.startswith('I')}),'P_exit_counts_possible':sorted({int(s[1])for s in after if s.startswith('A')}),'P_state_event':event,'P_known_new_maturity':new,'P_known_exit':exit_,'P_unknown_to_true':previous_public is None and pub is True and not new,'P_unknown_to_false':previous_public is None and pub is False and not exit_,'P_input_missing_counter_break':not known}
  for k,v in ex.items():
   ac=getattr(a,k)
   if k in ['P_entry_counts_possible','P_exit_counts_possible']:ac=json.loads(ac)
   elif k!='P_state_event':ac=tri(ac)
   checked[k]+=1
   if ac!=v:errors.append({'date':a.date,'sector':sid,'field':k,'expected':v,'actual':ac,'P_order':rank})
  expected_events[event]+=1;actual_events[a.P_state_event]+=1
  if first_single is None and len(after)==1:first_single=a.date
  if first_phase is None and pub is not None:first_phase=a.date
  if previous_date is not None and a.date[:4]!=previous_date[:4]:years.append({'sector':sid,'previous_date':previous_date,'new_year_first_date':a.date,'previous_states_after':list(previous_after),'current_states_before':json.loads(a.possible_states_before),'exact_carry':tuple(previous_after)==tuple(json.loads(a.possible_states_before))})
  reference.append({'date':a.date,'sector':sid,'P_order':rank,'T_order':None if pd.isna(a.T_order)else int(a.T_order),'P_before_states':list(R.ordered_states(memory)),'P_after_states':list(after),'internal_phase_before':bm,'P_prevpublic':previous_public,'P_mature':pub,'T_selected':tri(a.T_selected),'union':step['union'],'P_new_maturity':new,'P_exit':exit_,'P_state_event':event})
  memory=frozenset(after);previous_public=pub;previous_date=a.date;previous_after=after
 convergence.append({'sector':sid,'first_singleton_date':first_single,'first_public_phase_known_date':first_phase})
windows=[]
for sid in sorted(D.sector_id_static.unique()):
 hist=[r for r in reference if r['sector']==sid]
 for name,begin,end in [('RALLY_924','2024-09-24','2024-12-31'),('SEMIS_2026H1','2026-01-01','2026-06-30')]:
  g=[r for r in hist if begin<=r['date']<=end];x=g[0];z={'window':name,'sector':sid,'first_session':x['date'],'last_session':g[-1]['date'],'session_count':len(g),'public_P_carryin':x['P_prevpublic'],'internal_phase_carryin':x['internal_phase_before'],'states_before_first_session':x['P_before_states'],'first_observed_P_mature':first(g,'P_mature'),'first_identifiable_NEW_MATURE':first(g,'P_new_maturity'),'first_observed_T_selected':first(g,'T_selected'),'first_observed_union_true':first(g,'union'),'first_visible_P_can_be_carry_not_new':x['P_mature'] is True and not x['P_new_maturity'],'P_new_events':sum(r['P_new_maturity'] for r in g),'P_exit_events':sum(r['P_exit'] for r in g)};windows.append(z)
assert sha==h(P)
RDF=pd.DataFrame(reference);mature_byday=RDF.groupby('date').P_mature.apply(lambda x:int(x.eq(True).sum()));warm=D.date.lt('2022-01-01');study=~warm
summary={'status':'PASS'if not errors else'FAIL','rows':len(D),'checked_counter_event_fields':dict(checked),'mismatch_count':len(errors),'event_counts_expected':dict(expected_events),'event_counts_actual':dict(actual_events),'warm_P_missing_rows':int(D.loc[warm,'P_known'].eq(False).sum()),'study_P_missing_rows':int(D.loc[study,'P_known'].eq(False).sum()),'all_year_boundary_rows':len(years),'all_year_boundaries_exact':all(r['exact_carry']for r in years),'fixed_window_reference_rows':len(windows),'max_public_mature_count':int(mature_byday.max()),'sessions_mature_count_over5':int(mature_byday.gt(5).sum()),'study_main_day90known_all':bool(D.loc[study,'main_day90known'].eq(True).all()),'production_SHA256':sha,'no_feature_score_recalculation':True,'no_future_labels_read':True,'accounts':0,'annotation_semantics':'NEW/EXIT use unanimous before/after internal phase; unknown resume/initial resolution is separate, event naming priority documented from production run_v4.py:139-156. States/phases independently recomputed by frozen reference.'}
for fn,v in [('REAL_COUNTER_EVENT_AUDIT_SUMMARY.json',summary),('REAL_COUNTER_EVENT_MISMATCHES.json',errors),('REFERENCE_FIXED_WINDOWS_STATE_ONLY.json',windows)]: (O/fn).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
pd.DataFrame(years).to_csv(O/'REAL_ALL_YEAR_BOUNDARIES.csv',index=False);pd.DataFrame(convergence).to_csv(O/'REFERENCE_WARM_CONVERGENCE_ALL90.csv',index=False);pd.DataFrame(windows).to_csv(O/'REFERENCE_FIXED_WINDOWS_STATE_ONLY.csv',index=False)
focus=RDF[RDF.sector.eq('URFI881121')&RDF.date.between('2025-12-31','2026-01-15')];focus.to_csv(O/'SEMICONDUCTOR_TO_JAN15_STATE_ONLY.csv',index=False)
(O/'REAL_COUNTER_EVENT_AUDIT_SOURCE_SHA256.json').write_text(json.dumps({str(p.resolve()):h(p)for p in[P,CODE,O/'reference_state_machine.py',Path(__file__)]},ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False));print('JAN15_SEMI',focus[focus.date.eq('2026-01-15')].to_json(orient='records'))
if errors:raise SystemExit(1)
