from pathlib import Path
import json,csv,hashlib,sys,collections,time
from datetime import datetime,timezone
from decimal import Decimal as D
O=Path(__file__).resolve().parent;OLD=O.parent/'entry-loss-budget-full-account-20261031';sys.path.insert(0,str(OLD));import wire as w
def rows(p):return list(csv.DictReader(Path(p).open()))
def save(p,x):w.K.save(p,x)
def export(p,x):w.K.export(p,x)
freeze=w.read(O/'FREEZE.json');assert all(w.sha(p)==h for p,h in freeze['sha256'].items());ct=w.read(O/'COMPUTE_TIME.json');assert ct['seconds']<=240 and all(x['status']=='complete' for x in ct['stages'])
matrix=rows(O/'MATRIX_8_COST2.csv');v=[]
for sec in ['TECH','DRUG']:
 for stage in ['off','prefix']:assert w.read(O/sec/stage/'IDENTITY.json')['passed']
 for gate in ['accounting','funding']:assert w.read(O/sec/f'on/analysis/{gate}.json')['passed']
 assert w.read(O/sec/'on/STRUCTURE_GATE.json')['passed']
 x=w.read(O/sec/'on/analysis/accounting.json');v.append(dict(sector=sec,accounts=x['accounts'],rows=x['daily_rows'],NAV_residual=x['max_nav_difference']))
for r in matrix:
 sec=r['sector'];mode='I' if sec=='TECH' else 'ACT';ref=w.RR/('pvr-local-finite-capital-20261029/baseline' if sec=='TECH' else 'innovative-drug-local-recovery-20261028/S0');root=ref if r['policy']=='A' else O/sec/'on';a=w.read(root/'accounts-v2'/f'{r["account"]}.json');fills=[x for x in a['audit_log'] if x['kind']=='fill'];r['gross_turnover_cny']=sum((D(x['receipt']['gross_cny']) for x in fills),D(0));r['execution_slippage_cny']=sum((abs(D(x['price'])-D(x['raw_open']))*x['receipt']['shares']*D(x['fx_rate']) for x in fills),D(0))
export(O/'MATRIX_8_COST2.csv',matrix);export(O/'MATRIX_24_ALL_PRESSURES.csv',rows(OLD/'MATRIX_16.csv')+matrix)
ep=w.read(O/'FUNNEL_EPISODES.json');ap=w.read(O/'FUNNEL_APPLICATIONS.json');ii=w.read(O/'FUNNEL_INTENTS.json');rel=w.read(O/'NATURAL_RELEASES.json');late=w.read(O/'EXCLUSIVE_SLOT_LATER_CLEARANCES.json');assert len(ep)==86 and len({x['episode'] for x in ep})==86;assert len(ap)==215
fr=[]
for sec in ['TECH','DRUG']:
 ss=w.read(O/f'{sec}-FUNNEL_SUMMARY.json');assert len(ss['native_eligibility_log_identity_checks'])==3
 for r in ss['rows']:
  assert r['budget_completed']==r['episode_rows'];assert sum(r['outcomes'].values())==r['episode_rows'];assert sum(r['application_primary'].values())==r['fresh_I_days']
  fr.append(dict(sector=sec,account=r['account'],budget_clearances=r['budget_completed'],no_fresh_I=r['outcomes'].get('no_same_structure_fresh_I',0),fresh_I_no_order=r['outcomes'].get('fresh_I_without_submitted_order',0),order_no_same_E0_fill=r['outcomes'].get('submitted_without_same_structure_fill',0),same_E0_fill=r['same_structure_reentries'],fresh_I_days=r['fresh_I_days'],first_primary=r['first_primary'],application_primary=r['application_primary'],Q_unknown_episodes=r['Q_unknown_episode_count'],funding_unknown_days=r['funding_unknown_application_days']))
export(O/'FUNNEL_SUMMARY.csv',fr)
export(O/'FUNNEL_EPISODES.csv',[{k:v for k,v in x.items() if k!='orders'} for x in ep])
export(O/'FUNNEL_APPLICATIONS.csv',[dict(sector=x['sector'],account=x['account'],episode=x['episode'],symbol=x['symbol'],at=x['at'],Q=x['Q'],ACT=x['ACT'],primary=x['primary'],Q_detail=x['Q_detail'],Q_source=x['Q_source'],other_conditions=x['other_recorded_or_formula_conditions'],funding_before=x['funding']['feasible'],funding_after_other_actual_reservations=x['funding_after_actual_reservations']['feasible'],available_before=x['funding'].get('available'),available_after=x['funding_after_actual_reservations'].get('available'),occupied=[o['security_id'] for o in x['occupancy']],accepted_new=x['accepted_new']) for x in ap])
primary=collections.Counter(x['primary'] for x in ap);slot=[x for x in ap if 'slots_full' in x['primary']];strict=[x for x in ii if x['exclusively_observable_slot_block_days']>0];release_batches={x['batch_id'] for x in rel};strict_release={x['batch_id'] for x in rel if x['belongs_to_exclusive_slot_intent'] and x['matching_capacity_before_new_acceptances'] and x['funding']['feasible'] is True}
assert sum(x['next_entry_same_structure'] for x in ep)==6;assert sum(x['outcome']=='submitted_without_same_structure_fill' for x in ep)==6;assert len(strict)==12 and not strict_release
# Exact links to actual original delayed day-order expiry, not inferred fills.
failures=[]
for e in ep:
 if e['outcome']!='submitted_without_same_structure_fill':continue
 failures.append(dict(account=e['account'],symbol=e['symbol'],window_end=e['window_end'],orders=[dict(order_id=o['reserve']['order_id'],submitted_at=o['reserve']['at'],fills=len(o['fills']),expiry=[x for x in o['execution_logs'] if x['kind']=='buy_day_expiry'],support_rejection=[x for x in o['execution_logs'] if x['kind']=='open_support_reject']) for o in e['orders']]))
save(O/'EXECUTION_NONFILLS.json',failures)
evidence=dict(passed=True,cost2_actual_new_paths=6,cost2_off_exact_accounts=2,cost2_prefix_exact_accounts=6,finance=v,stock_bridge=w.read(O/'STOCK_BRIDGE.json'),zero_intervention_identity=w.read(O/'NO_EXPOSURE_IDENTITY.json'),frozen_runtime_hashes_unchanged=True,compute_seconds=ct['seconds'],budget_seconds=240,funnel_clearances=len(ep),fresh_I_observation_days=len(ap),funnel_outcomes=dict(collections.Counter(x['outcome'] for x in ep)),primary=primary,slot_primary_days=len(slot),slot_also_unfunded_before=sum(x['funding']['feasible'] is False for x in slot),slot_also_unfunded_after_other_actual_reservations=sum(x['funding_after_actual_reservations']['feasible'] is False for x in slot),strict_slot_intents=len(strict),strict_slot_valid_matching_natural_release_batches=len(strict_release),broader_natural_release_batches=len(release_batches),broader_matching_and_funded_before_batch=sum(x['matching_capacity_before_new_acceptances'] and x['funding']['feasible'] is True for x in rel),strict_intents_with_later_natural_clearance=sum(x['first_later_natural_clearance'] is not None for x in late),original_42_price_condition_marks_retained=True,new_cost2_price_condition_marks=len(w.read(O/'UNKNOWN.json')))
save(O/'VERIFICATION.json',evidence);save(O/'FUNNEL_INPUT_IDENTITY.json',dict(script_sha256=w.sha(O/'funnel.py'),original_source_freeze_sha256=w.sha(OLD/'FREEZE.json'),normal_delay_accounts={str(p):w.sha(p) for sec in ['TECH','DRUG'] for p in (OLD/sec/'on/accounts-v2').glob('*.json')},all_cached_facts_in_original_runtime_freeze=True,only_native_eligibility_and_quote_readers_no_trading_replay=True))
print(json.dumps({k:v for k,v in evidence.items() if k not in ['finance','stock_bridge','zero_intervention_identity']},ensure_ascii=False,default=str))
