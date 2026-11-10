"""Formal synthetic boundary audit against frozen v4; no empirical ranks/prices/labels."""
from pathlib import Path
import json,csv,hashlib
import reference_state_machine as R
O=Path(__file__).resolve().parent
FROZEN=O.parent/'FROZEN_DESIGN.txt'
EXPECTED_SHA='29af69f156ea9c14ea62ab5eea3fc1a7ee56dcdebdd33a3fc01d5e493e30e495'
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert h(FROZEN)==EXPECTED_SHA,'Root freeze changed; obtain the updated contract before formal audit'
(O/'FROZEN_DESIGN_USED.txt').write_bytes(FROZEN.read_bytes())
cases=[]
def case(name,orders,initial,expected_states,expected_mature=None,t=None,sessions=None,expected_union=None):
 actual=R.run_path(orders,initial,t,sessions);expected=[tuple(x) if isinstance(x,(tuple,list)) else (x,) for x in expected_states]
 checks={'states':all(tuple(a['states_after'])==e for a,e in zip(actual,expected)) and len(actual)==len(expected)}
 if expected_mature is not None:checks['mature']=all(a['public_mature'] is v for a,v in zip(actual,expected_mature))
 if expected_union is not None:checks['union']=all(a['union'] is v for a,v in zip(actual,expected_union))
 assert all(checks.values()),(name,checks,actual,expected)
 cases.append({'case':name,'initial':R.ordered_states(initial),'P_orders':orders,'expected_states':expected,'expected_public_mature':expected_mature,'expected_union':expected_union,'checks':checks,'actual':actual})
case('second_top5_close_enters',[5,5],['I0'],['I1','A0'],[False,True])
case('rank6_interrupts_entry',[1,6,2,5],['I0'],['I1','I0','I1','A0'],[False,False,False,True])
case('third_over10_close_exits',[11,11,11],['A0'],['A1','A2','I0'],[True,True,False])
case('6_to10_retains_maturity',[6,7,8,9,10],['A0'],['A0']*5,[True]*5)
case('rank10_clears_exit_count',[11,11,10,11,11,11],['A0'],['A1','A2','A0','A1','A2','I0'],[True,True,True,True,True,False])
case('missing_breaks_entry',[1,None,1,1],['I0'],['I1','I0','I1','A0'],[False,None,False,True])
case('missing_breaks_exit_not_memory',[11,11,None,11,11,11],['A0'],['A1','A2','A0','A1','A2','I0'],[True,True,None,True,True,False])
case('cross_year_entry_no_reset',[5,5],['I0'],['I1','A0'],[False,True],sessions=['2021-last-CSI-session','2022-first-CSI-session'])
case('cross_year_exit_no_reset',[11,11,11],['A0'],['A1','A2','I0'],[True,True,False],sessions=['2021-penultimate-CSI-session','2021-last-CSI-session','2022-first-CSI-session'])
case('T_observation_does_not_enter_P',[6,6],['I0'],['I0','I0'],[False,False],t=[True,True],expected_union=[True,True])
case('T_observation_does_not_block_P_exit',[11,11,11],['A0'],['A1','A2','I0'],[True,True,False],t=[False,False,True],expected_union=[True,True,True])
case('all_initial_states_two_top5_synchronize',[5,5],R.ALL_INITIAL,[('I1','A0'),('A0',)],[None,True])
case('all_initial_states_three_over10_synchronize',[11,11,11],R.ALL_INITIAL,[('I0','A1','A2'),('I0','A2'),('I0',)],[None,None,False])
case('buffer_initial_uncertainty_is_fixed_point',[6,10,6,10],R.ALL_INITIAL,[('I0','A0')]*4,[None]*4)
case('missing_does_not_choose_inactive_initialization',[None,5,5],R.ALL_INITIAL,[('I0','A0'),('I1','A0'),('A0',)],[None,None,True])
case('missing_with_T_true_union_is_true',[None],['A0'],['A0'],[None],t=[True],expected_union=[True])
case('missing_with_T_false_union_stays_unknown',[None],['A0'],['A0'],[None],t=[False],expected_union=[None])
# Exact transition-table boundary cells, independent expected literal rows.
expected={
 'I0':['I1','I1','I0','I0','I0','I0','I0'],
 'I1':['A0','A0','I0','I0','I0','I0','I0'],
 'A0':['A0','A0','A0','A0','A1','A1','A0'],
 'A1':['A0','A0','A0','A0','A2','A2','A0'],
 'A2':['A0','A0','A0','A0','I0','I0','A0']}
transition=[]
for s in R.STATES:
 for rank,e in zip([1,5,6,10,11,90,None],expected[s]):
  a=R.transition_one(s,rank);assert a==e
  transition.append({'state_before':s,'P_order':rank,'expected_state_after':e,'actual_state_after':a,'pass':a==e})
# Public maturity is phase unanimity, not requiring a singleton counter state.
assert R.public_mature({'A0','A1','A2'},True) is True
assert R.public_mature({'I0','I1'},True) is False
assert R.public_mature({'I0','A0'},True) is None
assert R.public_mature({'A0'},False) is None
kleene=[]
expected_or={(True,True):True,(True,False):True,(True,None):True,(False,True):True,(False,False):False,(False,None):None,(None,True):True,(None,False):None,(None,None):None}
for (a,b),e in expected_or.items():
 actual=R.kleene_or(a,b);assert actual is e;kleene.append({'P_mature':a,'T_selected':b,'expected_union':e,'actual_union':actual})
# Six globally consistent exact rankings; no second mature top5 cap.
names=['A','B','C','D','E','F'];matrix=[[1,2,3,4,5,6],[1,2,3,4,5,6],[2,3,4,5,6,1],[2,3,4,5,6,1]];states={s:frozenset(['I0']) for s in names};six=[]
for day,ranks in enumerate(matrix,1):
 assert sorted(ranks)==list(range(1,7))
 row={'session':day,'ranks':dict(zip(names,ranks)),'states':{}}
 for name,rank in zip(names,ranks):
  states[name]=R.transition_set(states[name],rank);row['states'][name]=R.ordered_states(states[name])
 row['mature']=sorted(n for n in names if R.public_mature(states[n],True) is True);row['mature_count']=len(row['mature']);six.append(row)
assert [x['mature_count'] for x in six]==[0,5,5,6]
# No calendar or empirical warmup loaded: this is the deterministic nonconvergence proof.
assert R.transition_set({'I0','A0'},6)==frozenset({'I0','A0'})
assert R.transition_set({'I0','A0'},10)==frozenset({'I0','A0'})
summary={'status':'PASS','root_freeze_SHA256':h(FROZEN),'rank_is_one_based':True,'synthetic_path_cases':len(cases),'exact_transition_boundary_cells':len(transition),'kleene_OR_cells':len(kleene),'six_industry_mature_counts':[x['mature_count'] for x in six],'public_mature_uses_phase_unanimity_not_singleton':True,'fixed_warmup_2021_CSI_sessions':243,'warmup_length_alone_does_not_prove_convergence':True,'all_initial_states_converge_two_top5':'A0','all_initial_states_converge_three_over10':'I0','6_to10_initial_uncertainty_fixed_point':['I0','A0'],'unknown_breaks_continuity_and_is_published_unknown':True,'T_never_updates_P_state':True,'accounts_or_market_or_future_labels_read':False,'parameters_fitted_or_changed':False,'empirical_2022_state_resolution_not_claimed':True}
for fn,obj in [('DETERMINISTIC_CASES_EXPECTED_AND_ACTUAL.json',cases),('EXACT_TRANSITION_TABLE.json',transition),('KLEENE_OR_EXPECTED_AND_ACTUAL.json',kleene),('SIX_INDUSTRY_MORE_THAN_FIVE_MATURE.json',six),('AUDIT_SUMMARY.json',summary)]:
 (O/fn).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
flat=[]
for c in cases:
 for r in c['actual']:flat.append(dict(case=c['case'],**r))
with (O/'SYNTHETIC_PATHS.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
sha={str(p.resolve()):h(p) for p in [FROZEN,O/'reference_state_machine.py',Path(__file__)]};(O/'SOURCE_SHA256.json').write_text(json.dumps(sha,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
