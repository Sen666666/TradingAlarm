"""Independent-audit reporting correction only; no execution or outcome tuning."""
from pathlib import Path
import ast,json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O/'report';D=O/'report_coverage_overlay';assert not D.exists()
source=(O/'summarize_fixed_permits.py').read_text();tree=ast.parse(source)
for n in tree.body:
 if isinstance(n,ast.FunctionDef) and n.name=='metric':exec(compile(ast.get_source_segment(source,n),'sealed_metric','exec'),globals())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
summary=json.loads((R/'SUMMARY.json').read_text());a=pd.read_csv(R/'BASELINE_CORE_ONLY_AUDIT.csv');bad=[]
for r in a.to_dict('records'):
 p=Path(r['rights_source']);assert sha(p)==r['rights_source_sha256'];j=json.loads(p.read_text())
 if j.get('raw_response_empty') or j.get('unresolved'):
  bad.append(dict(original_round_id=r['original_round_id'],sid=r['sid'],reason='raw_response_empty' if j.get('raw_response_empty') else 'unresolved_actions',rights_source=str(p),source_sha256=sha(p)))
badids={r['original_round_id'] for r in bad};assert len(badids)==11
full=pd.read_csv(R/'FULL_CORE_PLUS_ADD_FIXED_PERMITS.csv');core=pd.read_csv(R/'CORE_ONLY_FIXED_PERMITS.csv');base=pd.read_csv(R/'BASELINE_CORE_ONLY.csv')
for z in [core,base]:
 hit=z.round_id.isin(badids);assert hit.sum()==11
 z.loc[hit,'status']='CORE_BASELINE_ACTION_COVERAGE_UNKNOWN';z.loc[hit,['net_pnl','net_return_on_buy_cash']]=np.nan
closed=['COMPLETE_CONDITIONAL_STOCK_ROUND','SCENARIO_CLOSED_NOT_FACT','CORE_ONLY_CLOSED_ALGEBRAIC'];x=full.set_index('round_id');y=core.set_index('round_id');ids=sorted(set(x[x.status.isin(closed)].index)&set(y[y.status.isin(closed)].index));x=x.loc[ids];y=y.loc[ids]
pairs=pd.DataFrame({'round_id':ids,'full_pnl':x.net_pnl.values,'core_pnl':y.net_pnl.values,'pnl_delta_add_mode':(x.net_pnl-y.net_pnl).values,'full_win':(x.net_pnl>0).values,'core_win':(y.net_pnl>0).values,'cohort':x.report_cohort.values})
summary['before402_core_only_algebraic']=metric(base);summary['core_baseline_action_unknown']=sorted(badids);summary['after402_fixed_permits']['CORE_ONLY']=metric(core)
summary['common_closed']={'count':len(ids),'full':metric(x),'core':metric(y),'core_win_full_loss':int(((pairs.core_pnl>0)&(pairs.full_pnl<0)).sum()),'core_loss_full_win':int(((pairs.core_pnl<0)&(pairs.full_pnl>0)).sum()),'nonpositive_count_full':int((pairs.full_pnl<=0).sum()),'nonpositive_count_core':int((pairs.core_pnl<=0).sum()),'pnl_delta_full_minus_core_sum':float(pairs.pnl_delta_add_mode.sum()),'pnl_delta_note':'Independent-permit sum, not an account return. Buy-cash denominators differ.'}
summary['strict_initial_original_without_entry_bridges']=metric(base[base.report_cohort!='TEN_ENTRY_FACTOR_BRIDGES'])
summary['coverage_correction']={'reason':'Independent audit found raw_response_empty=true in 11 local actions sources. Nonempty file did not prove absent corporate actions. Strict initial-only baseline marks all 11 UNKNOWN.','economic_execution_changed':False,'full_mode_evidence_changed':False,'report_preserved':str(R),'corrected_report':str(D),'excluded_ids':sorted(badids),'remaining_initial_unknown':109+11,'baseline_still_conditional':'Local declared-source no-supported-event evidence, not PIT or exhaustive issuer-action certification.'}
by=[]
for mode,z in [('FULL_CORE_PLUS_ADD',full),('CORE_ONLY',core)]:
 for field in ['report_cohort','birth_quarter','event_type']:
  for val,g in z.groupby(field):by.append(dict(mode=mode,group_field=field,group_value=val,**metric(g)))
 for (co,q),g in z.groupby(['report_cohort','birth_quarter']):by.append(dict(mode=mode,group_field='cohort_and_birth_quarter',group_value=f'{co}|Q{q}',**metric(g)))
# Explicit distribution selection diagnostics, without calling cohort differences causal.
dists=[]
for mode,z in [('FULL_CORE_PLUS_ADD',full),('CORE_ONLY',core)]:
 z=z[z.status.isin(closed)].copy();z['holding_calendar_days']=(pd.to_datetime(z.exit_day)-pd.to_datetime(z.entry_day)).dt.days
 for co,g in z.groupby('report_cohort'):dists.append(dict(mode=mode,cohort=co,count=len(g),mean_holding_calendar_days=g.holding_calendar_days.mean(),median_holding_calendar_days=g.holding_calendar_days.median(),max_holding_calendar_days=g.holding_calendar_days.max()))
D.mkdir();save(D/'SUMMARY.json',summary);save(D/'CORRECTION_MANIFEST.json',{'correction_code_sha256':sha(Path(__file__)),'prior_report_sources':{str(p):sha(p) for p in R.iterdir() if p.is_file()},'reason':summary['coverage_correction'],'no_economic_rerun':True});pd.DataFrame(bad).to_csv(D/'CORE_BASELINE_SOURCE_COVERAGE_UNKNOWN.csv',index=False);base.to_csv(D/'BASELINE_CORE_ONLY.csv',index=False);core.to_csv(D/'CORE_ONLY_FIXED_PERMITS.csv',index=False);full.to_csv(D/'FULL_CORE_PLUS_ADD_FIXED_PERMITS.csv',index=False);pairs.to_csv(D/'COMMON_CLOSED_PAIRS.csv',index=False);pd.DataFrame(by).to_csv(D/'DISTRIBUTION_GROUPS.csv',index=False);pd.DataFrame(dists).to_csv(D/'HOLDING_DURATION_DISTRIBUTION.csv',index=False);save(D/'OUTPUT_HASHES.json',{p.name:sha(p) for p in D.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'});print(json.dumps({k:summary[k] for k in ['before402_core_only_algebraic','after402_fixed_permits','common_closed','strict_initial_original_without_entry_bridges']},indent=2))
