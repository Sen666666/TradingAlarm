"""Independent saved-only resource arithmetic; no native objects or mark reconstruction."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
from datetime import datetime
import gzip,json,hashlib,time
R=Path(__file__).resolve().parent; P=R.parent; F=P/'funding'; W=P.parent
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
 with gzip.open(p,'rt')as f:
  for line in f:yield json.loads(line)
def dec(x):return D(str(x))
t0=time.monotonic(); ev=load(P/'P_EVENTS.json'); pm={(x['window'],x['sid'],x['day']):x for x in ev};assert len(pm)==len(ev)==35699
meta=load('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'); semis={s for s,m in meta.items()if m['industry']=='半导体'};assert len(semis)==126
out=[]; basic=defaultdict(Counter); strat=defaultdict(Counter); sidsets=defaultdict(set); epgroups=defaultdict(set); seen=set(); compared=changed=0; margins=[]; tests=Counter(); groupout=defaultdict(list)
for x in rows(F/'P_ORIGINAL_RESOURCE_CONTEXT.jsonl.gz'):
 k=x['window'],x['sid'],x['day'];assert k in pm and k not in seen;seen.add(k); p=pm[k]
 assert x['state']==p['state'] and x['e0_run_start']==p['e0_run_start']
 g=x['G1'];expect='G1_unknown'if any(g[f]is None for f in ['ready','grade','fresh_up'])else'G1_not_ready'if not g['ready']else'G1_ready_below_warm'if g['grade']<2 else'G1_warm_no_fresh'if not g['fresh_up']else'G1_warm_fresh';assert g['current_category']==expect
 locked=x['last_actual_CORE_fill']is not None and x['last_actual_CORE_fill']['epoch']==x['native_current_epoch'];assert locked==x['actual_CORE_epoch_consumed']
 if x['last_actual_CORE_fill']:assert datetime.fromisoformat(x['last_actual_CORE_fill']['at'])<=datetime.fromisoformat(x['day']+'T15:10:00+08:00')
 pending=[v for v in x['original_barriers']if v in ['exit_pending','buy_pending']];assert pending==x['original_pending_barriers']
 isB=x['state']=='B_I_on_no_i_buy';co=isB and not x['original_held']and x['ACT_on']and not pending and not locked and x['original_continuing_S0_Q']is True;assert co==x['B_flat_ACT_S0_epoch_pending_intersection']
 s=x.get('original_S0');q=x['B_minimum_unit_necessary_only']or{};safe=None
 if s:
  assert (dec(s['actual_sector_inventory_capital'])>D('.02')*dec(s['optimistic_NAV_upper']))==s['sector_capital_already_exceeds_2pct_NAV_upper']
 if 'signal_minimum_risk'in q:
  tests['signal_minimum']+=1
  assert (dec(q['signal_minimum_risk'])<=dec(q['risk_budget'])and dec(q['signal_minimum_gross'])<=dec(q['nominal_cap']))==q['signal_minimum_risk_and_2pct_cap_pass']
  assert dec(q['risk_budget'])/D('.0025')==dec(q['nominal_cap'])/D('.02')
 if 'OPEN_minimum_gross'in q:
  tests['OPEN_minimum']+=1;cost=dec(q['OPEN_minimum_gross'])+dec(q['OPEN_minimum_buy_fee']);free=dec(s['cash'])-D('.1')*dec(s['decision_NAV'])
  assert free==dec(q['original_S0_cash_after_cash10']);assert (cost<=free)==q['isolated_original_S0_cash_can_pay_minimum']
  margin=dec(s['actual_sector_inventory_capital'])+dec(q['OPEN_minimum_gross'])-D('.02')*dec(s['optimistic_NAV_upper']);safe_margin=margin-D('.02')*D('.000001')-D('.000001');safe=safe_margin>0
  assert (margin>0)==q['certified_sector_capital_failure_even_optimistic_NAV'];compared+=1;changed+=safe!=(margin>0)
  if margin>0:margins.append(margin)
 c=basic[x['window']+'|'+x['state']];c['events']+=1;c[expect]+=1;c['original_held']+=bool(x['original_held']);c['ACT_on']+=bool(x['ACT_on']);c['CORE_epoch_consumed']+=locked;c['CP_same_day']+=x['original_CP_same_day']is not None;c['B_flat_ACT_S0_epoch_pending_intersection']+=co
 sp=bool(q.get('signal_minimum_risk_and_2pct_cap_pass'));op=bool(q.get('OPEN_minimum_risk_and_2pct_necessary_pass'));cash=bool(q.get('isolated_original_S0_cash_can_pay_minimum'));nc=x['next_original_CP'];same=x['original_CP_same_day']is not None
 if co:
  for key,val in [('intersection_CP_same_day',same),('intersection_no_same_CP',not same),('intersection_next_CP_same_I_epoch',nc is not None and nc['same_native_I_epoch']),('intersection_signal_minimum_pass',sp),('intersection_OPEN_minimum_necessary_pass',op),('intersection_isolated_S0_cash_minimum_pass',cash),('intersection_certified_sector_capital_failure',q.get('certified_sector_capital_failure_even_optimistic_NAV',False))]:c[key]+=bool(val)
 if isB:
  h1=x['window']=='strong'and x['day']>='2026-01-01'
  for scope in [x['window']]+(['H1_2026']if h1 else[]):
   for universe in ['all1709']+(['semiconductor126']if x['sid']in semis else[]):
    sk='|'.join([scope,universe,expect]);v=strat[sk];v['B_price_events']+=1
    if co:
     v['flat_ACT_otherS0_noPending_COREunconsumed']+=1;sidsets[sk].add(x['sid']);epgroups[sk].add((x['sid'],p['source_segment'],x['e0_run_start']))
     fields={'CP_same_day':same,'no_CP_same_day':not same,'later_CP_same_I_epoch':nc is not None and nc['same_native_I_epoch'],'no_same_CP_but_later_CP_same_I':not same and nc is not None and nc['same_native_I_epoch'],'signal_minimum_pass':sp,'OPEN_minimum_necessary_pass':op,'isolated_S0_cash_minimum_pass':cash,'signal_and_OPEN_and_cash_minimum_pass':sp and op and cash,'certified_sector_capital_failure_SAFE':safe is True,'sector_certificate_unknown':safe is None,'not_eliminated_by_minimum_cash_and_sector_tests_UPPER_ONLY':sp and op and cash and safe is False}
     for name,value in fields.items():v[name]+=bool(value)
     if scope=='H1_2026'and universe=='semiconductor126'and sp and op and cash and safe is False:groupout[expect].append({'sid':x['sid'],'day':x['day']})
assert seen==set(pm)
bs=load(F/'P_ORIGINAL_RESOURCE_SUMMARY.json')
for k,v in bs['groups'].items():assert dict(basic[k])==v,(k,dict(basic[k]),v)
ss=load(F/'P_B_G1_STRATIFIED_NECESSARY_SUMMARY.json')
for k,c in strat.items():
 c['intersection_distinct_stocks']=len(sidsets[k]);c['intersection_distinct_source_E0_segments']=len(epgroups[k]);assert dict(c)==ss['groups'][k],(k,c,ss['groups'][k])
assert set(strat)==set(ss['groups'])
a=load(F/'P_SECTOR_BOUND_TOLERANCE_AUDIT.json');assert compared==a['compared']and changed==a['reclassified']==0 and str(min(margins))==a['minimum_raw_positive_failure_margin']
diffs=[dec(x['NAV_upper_above_exact'])for x in bs['exact_S0_13_checks']];assert len(diffs)==13 and all(x['units_exact']and dec(x['capital_difference'])==0 for x in bs['exact_S0_13_checks']);assert max(abs(v)for v in diffs)<D('.000001')
size=load(P/'ORIGINAL_CORE_SIZE_CENSUS.json');fg=[x for x in size['groups']if x['window']=='strong'and x['period']=='2026_H1'and x['universe']=='semiconductor126'];sz={x['result']:x for x in fg};assert sz['minimum_unit_exceeds_risk_or_nominal_cap']['events']==1169 and sz['minimum_unit_exceeds_risk_or_nominal_cap']['stocks']==68;assert sz['actual_core_layer']['events']==1
report=dict(passed=True,scope='Saved-only exact event join/group/Decimal minimum-size/cash and conservative sector-obstruction arithmetic; no 1709 mark rebuild, native Account or new orders.',events=len(seen),basic_group_exact=len(basic),stratified_group_exact=len(strat),arithmetic_checks=dict(tests),sector_bound_compared=compared,safe_cushion_reclassifications=changed,minimum_positive_sector_obstruction_margin=str(min(margins)),reported_13_snapshot_checks={'units_and_capital_all_exact':True,'independent_mark_reconstruction':False,'minimum_NAV_upper_minus_exact':str(min(diffs)),'maximum_NAV_upper_minus_exact':str(max(diffs)),'safe_NAV_currency_cushion':'.000001'},actual_802_epoch_checks={'code_assertions':bs['original_CORE_fill_epoch_identity_checks'],'independent_all_802_fact_rebuild':False},H1_semiconductor_residual_upper_by_G1=dict(groupout),H1_original_CORE_size={'combined_minimum_risk_or_amount_rejection_events':1169,'rejection_distinct_stocks':68,'actual_CORE_layers':1,'single_risk_cause_established':False},critical_semantics=['Original i_buy is warm && (entered || fresh) within active I; P OR i_buy replaces a composite proof. S0 has no independent G1-warm check.','Original S0 quantities retain original actions/protection sells; last-CLOSE quantities subtract original same-OPEN buys only.','Sector rejection is a sufficient obstruction against optimistic NAV, not full execution permission. Cash is shared, repeated stock/E0 P events dependent.','Survivors remain optimistic upper counts: full probe/sector/stock risk, original frozen max, pending/migration, priority and new economic feedback not projected.','No financial or adapter admission.'],upstream_overrun=load(F/'RESOURCE_CENSUS_OVERRUN.json'),source_sha256={str(p):sha(p)for p in [Path(__file__),P/'P_EVENTS.json',F/'census_original_p_resources.py',F/'aggregate_p_necessary.py',F/'P_ORIGINAL_RESOURCE_CONTEXT.jsonl.gz',F/'P_ORIGINAL_RESOURCE_SUMMARY.json',F/'P_B_G1_STRATIFIED_NECESSARY_SUMMARY.json',F/'P_SECTOR_BOUND_TOLERANCE_AUDIT.json',P/'ORIGINAL_CORE_SIZE_CENSUS.json']},seconds=time.monotonic()-t0,new_accounts=0,new_orders=0,new_mark_reconstructions=0)
(R/'SAVED_RESOURCE_CONTEXT_REVIEW.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k not in ['source_sha256','critical_semantics','upstream_overrun']},ensure_ascii=False,indent=2))
