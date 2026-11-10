"""One bounded saved-facts and original-money audit; no model/accounts/counterfactual."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import Counter
import hashlib,json
import pandas as pd
getcontext().prec=60
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/independent_review');T=O.parent;P=T/'loss_correction/mobile_current_grade_quickcheck_v1';B=T/'risk_constraints/ma63_information_diagnostic_v1'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
summary=load(P/'SUMMARY.json');ft=load(P/'FIXED_ORIGINAL_TAILS.json');src=load(P/'SOURCES_AND_LIMITS.json');scope=load(P/'SCOPE.json');allowed=load(T/'loss_correction/volume_neutral_interpretation_v1/NATIVE_ENTRY_SEMANTICS_AUDIT.json')['facts_source_sha256'];paths={Path(p).stem:p for p in allowed};frames={};reports={}
for p,h in src['facts_sources'].items():assert allowed[p]==h and sha(p)==h
assert sha(P/'analyze.py')==src['script_sha256'];assert src['new_model_events']==src['new_account_events']==src['new_neutral_features']==0
legs=load(T/'pvr_pool_feasibility/market_phase_2022_2023/HS300_ALL_LEGS.json')
def check_group(rows,expected):
 assert len(rows)==expected['layers'];assert len({x['sid']for x in rows})==expected['stocks']
 for key,field in [('cost','original_cost'),('net','original_net')]:assert abs(sum((D(x[key])for x in rows),D(0))-D(expected[field]))<D('1e-20')
 return dict(layers=len(rows),original_cost=expected['original_cost'],original_net=expected['original_net'],original_positive_net=expected['original_positive_net'],original_negative_net=expected['original_negative_net'])
for win in ['2022_2024','strong']:
 rows=load(P/(win+'_ROWS.json'));old=load(B/(win+'_ENTRIES.json'));assert len(rows)==len(old)
 for x,z in zip(rows,old):
  assert all(x[k]==v for k,v in z.items()),('originalrowmutated',win,x['layer'])
  sid=x['sid'];day=pd.Timestamp(x['decision_at'][:10])
  if sid not in frames:frames[sid]=pd.read_parquet(paths[sid],columns=['g_grade','g_ready','i_buy','i_target'])
  r=frames[sid].loc[day];g=r.g_grade;group='unknown'if pd.isna(g)else'grade_lt2'if float(g)<2 else'grade_ge2'
  assert group==x['grade_class'];assert bool(r.g_ready)==x['current_g_ready']and float(g)==x['current_g_grade'];assert bool(r.i_target)and pd.notna(r.i_buy)
  if bool(r.i_buy):assert group=='grade_ge2'
  if x['role']=='core':assert group=='grade_ge2'
 cohorts={'ALL':rows}
 if win=='2022_2024':
  cohorts['2022_2023']=[x for x in rows if x['opened'][:10]<='2023-12-29']
  for leg in legs:
   if leg['id']in['L03','L04']:
    lo,hi=leg['first_analysis_day'],leg['last_analysis_day'];cohorts[leg['id']+'_decision_cohort']=[x for x in rows if lo<=x['decision_at'][:10]<=hi];cohorts[leg['id']+'_actual_fill_cohort']=[x for x in rows if lo<=x['opened'][:10]<=hi]
  cohorts['strict303_postOct8_newfills']=[x for x in rows if '2024-10-08'<x['opened'][:10]<='2024-12-31'];assert len(cohorts['strict303_postOct8_newfills'])==303
 reports[win]={}
 for k,z in cohorts.items():
  check_group(z,summary[win][k]['all']);r={}
  for role in ['core','mobile']:
   r[role]={g:check_group([x for x in z if x['role']==role and x['grade_class']==g],summary[win][k]['by_role_and_current_grade'][role][g])for g in ['grade_lt2','grade_ge2','unknown']}
  reports[win][k]=r
fixed=load(B/'ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json')['members'];tails={}
for win in ['2022_2024','strong']:
 rows=ft[win]['full_original_rows'];assert len(rows)==len(fixed[win])
 for x,z in zip(rows,fixed[win]):
  assert all(x[k]==v for k,v in z.items())
  if x['grade_class']=='unknown':assert x['grade_unknown']=='outside_previous1205_facts_scope'and x['sid']=='301338.SZ'
  else:
   sid=x['sid'];day=pd.Timestamp(x['decision_at'][:10]);r=frames[sid].loc[day];assert float(r.g_grade)==x['current_g_grade'];assert ('grade_lt2'if r.g_grade<2 else'grade_ge2')==x['grade_class']
 tails[win]={role:{g:check_group([x for x in rows if x['role']==role and x['grade_class']==g],ft[win]['by_role_and_grade'][role][g])for g in ['grade_lt2','grade_ge2','unknown']}for role in ['core','mobile']}
assert len(frames)==1205
x=dict(status='NONREDUNDANT_BUT_FAILS_MAIN_LOSS_COVERAGE_STOP_NO_WIRING_CARD_OR_ACCOUNT',semantic_findings=['market_buyable describes historicalavailability/identity only, notG1warm.','S0 checks I_target/common/RS/sector/cap etc withoutg_grade; continuing mobile replaces dailyi_buy withmarketbuyable, so freshCP1 can fund while G1gradecold butIactive.','Original G1_I retains holdings throughcoldgrade, exits onlyE0/floor; thisnewmobileadmission-only condition differs fromX/IXcoldselling.','i_buyTrue alreadyrequiresgrade>=2; allcoldmobile rows fallwithin140/38 nofreshI subsets.'],
 original_facts_sources_and_all3436rows_checked=1205,groups=reports,fixed_original_tail_groups=tails,
 verdict='Do not promote. Most actual loss association is already inwarm mobile, includingstrict303 andL03/L04; coldsubset has offsetting originalpositives andnegatives. The gate doesnot addressmainloss scale. No need wiring/account or expandingmissingonefixedtail fact toreachthisprioritydecision.',
 quantitative_scope='Allcost/net are originallifecycle contribution associations, not avoidableloss/newNAV. L03/L04 entrydecision cohorts notphasewealth; fillcohort separatelykept. Core/holding/exits unchanged inquestion only, not implemented. All83/94fixedtails retained; strong1mobiletailunknown14819.44 notzero; fixedtail split-money absentfields remainNA.',
 reviewer_model_or_account_runs=0,inputs={str(p):sha(p)for p in [P/'SCOPE.json',P/'SUMMARY.json',P/'FIXED_ORIGINAL_TAILS.json',P/'2022_2024_ROWS.json',P/'strong_ROWS.json',P/'SOURCES_AND_LIMITS.json',P/'analyze.py',Path(__file__)]})
(O/'MOBILE_CURRENT_WARM_QUICK_AUDIT.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=x['status'],main={w:reports[w]['ALL']['mobile']for w in reports},post303=reports['2022_2024']['strict303_postOct8_newfills']['mobile'])))
