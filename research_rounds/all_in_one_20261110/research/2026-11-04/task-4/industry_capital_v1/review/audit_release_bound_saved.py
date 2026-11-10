"""All saved capital-bound arithmetic, no native mark rebuild or account."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D
from datetime import datetime
import gzip,json,hashlib,time
R=Path(__file__).resolve().parent;I=R.parent;P=I/'release_bound';Z=D(0);E=D('.000001')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
 with gzip.open(p,'rt')as h:
  for s in h:yield json.loads(s)
t0=time.monotonic();ms=read(P/'OPEN_MARK_STATUS.json');marks={x['sid']+'|'+x['OPEN']:x for x in ms};assert len(marks)==len(ms)==18703
for m in ms:
 if m['strict_OPEN_identity']:
  assert m['status']=='SAME_OPEN_RAW'and D(m['mark'])==D(m['raw_OPEN']);assert datetime.fromisoformat(m['known_at'])==datetime.fromisoformat(m['OPEN']+'T09:30:00+08:00')
ss=read(P/'SNAPSHOT_OPEN_VALUES.json')
for key,s in ss.items():
 gross=locked=Z;bad=[]
 for x in s['layers']:
  m=marks[x['mark_key']];q=D(x['qty']);v=q*D(m['mark'])if m.get('mark')is not None else None;assert (D(x['value'])if x['value']is not None else None)==v
  dl=x['source_prior_pending']and x['source_prior_reason']in ['ACT_pause','I_structure_exit','CP1_add_protection'];assert dl==x['definitely_prior_exit_locked']
  if not m['strict_OPEN_identity']:bad.append(x['sid']);continue
  gross+=v
  if dl:locked+=v
 assert s['all_strict_OPEN_prices']==(not bad)
 if not bad:assert D(s['old_inventory_gross'])==gross and D(s['definitely_locked_old_gross'])==locked and D(s['nonlocked_old_gross_upper'])==gross-locked
allrows=list(rows(P/'RELEASE_BOUND_EVENTS.jsonl.gz'));assert len(allrows)==33569 and len({x['key']for x in allrows})==33569
for x in allrows:
 s=ss[x['snapshot_key']];assert x['old_inventory_gross']==s['old_inventory_gross']and x['nonlocked_old_gross_upper']==s['nonlocked_old_gross_upper']
 if x['release_amount_status']!='KNOWN_NECESSARY_BOUND':continue
 old=D(x['old_inventory_gross']);front=D(x['front_same_sector_actual_reserved_gross']);qn=D(x['qmin_gross']);allow=D('.02')*(D(x['NAV_optimistic_upper_source'])+E);raw=max(Z,old+front+qn-allow);safe=max(Z,raw-E)
 assert D(x['pre_candidate_industry_capital_from_old_plus_actual_front'])==old+front and D(x['sector_allowance_optimistic_upper'])==allow and D(x['required_sector_relief_formula'])==raw and D(x['required_sector_relief_lower_bound_SAFE'])==safe
 assert D(x['relief_to_new_minimum_gross'])==safe/qn and x['relief_exceeds_all_old_inventory_SAFE']==(safe>old+E)and x['relief_exceeds_nonlocked_old_upper_SAFE']==(safe>D(s['nonlocked_old_gross_upper'])+E);assert x['qmin_itself_exceeds_sector_allowance_SAFE']==(qn>allow+E)
summ=read(P/'RELEASE_BOUND_SUMMARY.json');groups={'ALL_RAW':allrows,'ALL_FIRST':[x for x in allrows if x['is_first']],'LONG_RAW':[x for x in allrows if x['window']=='long'],'STRONG_RAW':[x for x in allrows if x['window']=='strong'],'H1_2026_SEMICONDUCTOR_RAW':[x for x in allrows if x['window']=='strong'and x['OPEN']>='2026-01-01'and x['semiconductor126']],'H1_2026_SEMICONDUCTOR_FIRST':[x for x in allrows if x['window']=='strong'and x['OPEN']>='2026-01-01'and x['semiconductor126']and x['is_first']]};medians={}
for name,a in groups.items():
 g=summ['groups'][name];kn=[x for x in a if x['release_amount_status']=='KNOWN_NECESSARY_BOUND'];assert len(a)==g['events']and len(kn)==g['known_bounds'];assert dict(Counter(x['release_amount_status']for x in a if x['release_amount_status']!='KNOWN_NECESSARY_BOUND'))==g['unknown_reasons']
 assert sum(x['no_old_inventory']for x in a)==g['no_old_inventory']and sum(x['relief_exceeds_all_old_inventory_SAFE']for x in kn)==g['required_relief_exceeds_all_old_gross'];assert sum(x['qmin_itself_exceeds_sector_allowance_SAFE']for x in kn)==g['minimum_itself_above_sector_allowance'];assert sum(D(x['required_sector_relief_lower_bound_SAFE'])>0 for x in kn)==g['positive_relief']
 medians[name]={}
 for field,stat in [('required_sector_relief_lower_bound_SAFE','relief_amount'),('relief_to_new_minimum_gross','relief_to_new_minimum_gross')]:
  v=sorted(D(x[field])for x in kn);n=len(v);mid=v[n//2]if n%2 else(v[n//2-1]+v[n//2])/2;upper=v[n//2];assert D(g[stat]['median'])==upper;medians[name][stat]={'n':n,'stored_upper_middle':str(upper),'conventional_median':str(mid),'stored_equals_conventional':mid==upper}
assert len(ss)==summ['snapshots']==7634 and Counter(x['status']for x in ms)==Counter(summ['mark_status_counts'])
output={'passed_for_saved_arithmetic_and_bound_scope':True,'events':33569,'snapshots':7634,'stock_OPEN_marks':18703,'strict_current_OPEN_marks':18656,'stale_marks':47,'known_raw_bounds':summ['groups']['ALL_RAW']['known_bounds'],'known_first_bounds':summ['groups']['ALL_FIRST']['known_bounds'],'first_bounds_exceed_all_old_gross':summ['groups']['ALL_FIRST']['required_relief_exceeds_all_old_gross'],'H1_semiconductor_first':summ['groups']['H1_2026_SEMICONDUCTOR_FIRST'],'source_mark_rebuild_by_reviewer':False,'economic_admission':False,'presentation_issue':'Stored median uses upper-middle value for even N; label as upper-middle or correct presentation from saved values only. No economic or mark recomputation required.','stored_vs_conventional_medians':medians,'source_exception_boundary_note':'mark_open currently catches all Exception; no SOURCE_UNKNOWN exposed in produced marks. Before future reuse limit exception-to-unknown to native RuleUnavailable; programming errors must propagate.','bound_limits':['Necessary original-path capital relief only; oldSC+actualfront+qmin comparison against optimistic NAV excludes sale fee/NAV drag, so gross release is optimistic lower bound.','Actual front commitments cannot be assumed cancelled; sameOPEN filled new layers are not sellable T+1 old donors.','Nonlocked gross excludes only proven old exit lock; T+1/bonus/capacity/floor/order constraints may make less actually saleable.','Negative or zero lower bound does not prove cash, sector risk, probe risk, stock limit, execution or funding capacity.','Money lower bounds/ratios for repeated stock-days or normalized units cannot sum as portfolio returns or funding deficit.'],'reviewer_new_accounts':0,'reviewer_new_marks':0,'source_sha256':{str(p.resolve()):sha(p)for p in [Path(__file__),P/'calculate_release_bound.py',P/'RELEASE_BOUND_EVENTS.jsonl.gz',P/'RELEASE_BOUND_SUMMARY.json',P/'SNAPSHOT_OPEN_VALUES.json',P/'OPEN_MARK_STATUS.json']},'seconds':time.monotonic()-t0}
(R/'RELEASE_BOUND_SAVED_REVIEW.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in output.items()if k not in ['source_sha256','bound_limits','H1_semiconductor_first','stored_vs_conventional_medians']},indent=2));print(json.dumps({k:medians[k]for k in ['ALL_FIRST','H1_2026_SEMICONDUCTOR_FIRST']},indent=2))
