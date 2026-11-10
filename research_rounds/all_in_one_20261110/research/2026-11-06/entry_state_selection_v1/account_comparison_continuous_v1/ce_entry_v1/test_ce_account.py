"""Synthetic-only CE integration tests. No Account/Runner construction or replay."""
from pathlib import Path
from collections import Counter
from types import SimpleNamespace
import ast, copy, json, math, pickle, random, sys
import pandas as pd
import ce_account as X
sys.path.insert(0, str(X.CE_DIR))
from empty_first_rank import rank_empty_first_stock_slots

DAY = '2022-01-05'


class Lookup:
    def __init__(self, values): self.values = values; self.calls = []
    def query(self, sid, day):
        self.calls.append((sid, day))
        value = self.values.get((sid, day), math.nan)
        return dict(CE=value, CE_known=math.isfinite(value),
                    reason='known_original_fresh_CP' if math.isfinite(value) else 'no_original_cached_fresh_CP_on_requested_day',
                    formation_n=4 if math.isfinite(value) else math.nan,
                    variance_budget=.04 if math.isfinite(value) else math.nan)


class SyntheticAccount:
    def __init__(self, specs):
        self.label = 'PVR'; self.pending = []; self.quantities = {}
        for sid, rank, roles, quantity, pvr, ready in specs:
            self.quantities[sid] = quantity
            for role in roles:
                self.pending.append(dict(sid=sid, rank=rank, role=role,
                    PVR_score=pvr, PVR_ready=ready, priority_rank=rank,
                    original_H1_rank=rank + 200, priority_policy='original_PVR',
                    quote=dict(raw_price=8.5), clock=SimpleNamespace(decision_at=DAY),
                    CP1_trace={'nested': [sid, 1, {'untouched': True}]},
                    CP1_id='fresh-' + sid if role == 'mobile' else None,
                    floor=7.5, cap=100, budget=850, kind='core' if role=='core' else 'add'))
        self.decisions = [dict(at=DAY+' 15:10:00+08:00', intents=[{k:copy.deepcopy(v) for k,v in i.items() if k not in ('quote','clock','CP1_trace')} for i in self.pending])]
    def quantity(self, sid): return self.quantities.get(sid, 0)


def independent_expected(specs, lookup_values):
    ordered = sorted(specs, key=lambda s: s[1])
    movable = [s for s in ordered if not s[3] and s[5] and s[4] is not None and math.isfinite(s[4]) and math.isfinite(lookup_values.get((s[0],DAY),math.nan))]
    slots = [s[1] for s in movable]
    ranked = sorted(movable, key=lambda s: (-round(lookup_values[(s[0],DAY)],12), -round(s[4],12), s[1], s[0]))
    result = {s[0]:s[1] for s in ordered}
    result.update({s[0]:rank for s,rank in zip(ranked,slots)})
    return result


def check(specs, values, expected=None):
    account = SyntheticAccount(specs)
    before_pending = X.nonrank_snapshot(account.pending)
    before_decisions = X.nonrank_snapshot(account.decisions[-1]['intents'])
    before_quantities = dict(account.quantities)
    lookup = Lookup(values)
    rows, audit = X.apply_ce_priority(account, DAY, lookup, rank_empty_first_stock_slots)
    expected = expected or independent_expected(specs,values)
    assert {i['sid']:i['rank'] for i in account.pending} == expected
    assert {i['sid']:i['rank'] for i in account.decisions[-1]['intents']} == expected
    assert X.nonrank_snapshot(account.pending) == before_pending
    assert X.nonrank_snapshot(account.decisions[-1]['intents']) == before_decisions
    assert account.quantities == before_quantities
    assert len(rows) == len(specs)
    assert len(lookup.calls) == len(specs) and all(d == DAY for _,d in lookup.calls)
    assert audit['unchanged_all_nonrank_intent_fields']
    assert audit['was_empty_measured_at'] == 'AFTER_NATIVE_PLANNING_SIGNAL_CLOSE'
    assert Counter((i['sid'],i['role']) for i in account.pending) == Counter((i['sid'],i['role']) for i in account.decisions[-1]['intents'])
    return rows, audit


def main():
    tests = []
    specs = [('dual', 2, ['mobile','core'],0,10.,True),
             ('held', 7, ['mobile'],100,9.,True),
             ('noce', 19, ['core'],0,8.,True),
             ('nopvr', 31, ['core','mobile'],0,None,False),
             ('onlycore', 108, ['core'],0,6.,True),
             ('notready', 230, ['mobile'],0,5.,False),
             ('mobile', 708, ['mobile'],0,4.,True)]
    vals = {(sid,DAY):v for sid,v in [('dual',1.),('held',1000.),('nopvr',900.),('onlycore',5.),('notready',800.),('mobile',3.)]}
    rows,audit = check(specs,vals,{'dual':708,'held':7,'noce':19,'nopvr':31,'onlycore':2,'notready':230,'mobile':108})
    assert audit['CORE_groups_moved'] == 2
    assert {r['sid']:r['roles'] for r in rows}['dual'] == ['core','mobile']
    tests.append('all_empty_CORE_and_MOBILE_groups_move_held_unknown_and_sparse_slots_fixed')
    check([],{}); tests.append('empty_pending_queue_with_explicit_numeric_boolean_dtypes')
    check([('a',3,['core'],0,None,False),('b',19,['mobile'],0,None,False)],{('a',DAY):8.,('b',DAY):9.})
    tests.append('all_PVR_None_no_object_isfinite_failure')
    check([('a',3,['core'],0,1.,True)],{('a','2022-01-04'):100.})
    tests.append('CORE_without_current_fresh_CE_fixed_no_old_receipt_carry')
    check([('a',3,['mobile'],100,1.,True),('b',19,['core','mobile'],20,2.,True)],{('a',DAY):8.,('b',DAY):9.})
    tests.append('all_held_groups_fixed_at_signal_close')
    check([('a',3,['core','mobile'],0,2.,True)],{('a',DAY):8.})
    tests.append('single_movable_group_unchanged')
    check([('a',3,['mobile'],0,1.,True),('b',19,['core'],0,2.,True),('c',91,['mobile'],0,2.,True)],{('a',DAY):1.,('b',DAY):1.+1e-14,('c',DAY):1.}, {'a':91,'b':3,'c':19})
    tests.append('round12_CE_then_PVR_then_original_rank_ties')
    # A serialization restart is tested only for synthetic inputs, not an account.
    a = SyntheticAccount(specs); restored = pickle.loads(pickle.dumps(a,protocol=5))
    left = X.apply_ce_priority(a,DAY,Lookup(vals),rank_empty_first_stock_slots)
    right = X.apply_ce_priority(restored,DAY,Lookup(vals),rank_empty_first_stock_slots)
    assert left == right; tests.append('synthetic_restart_exact')
    # Deterministic broad property check, no economic data and no score tuning.
    rng=random.Random(20261106)
    for trial in range(160):
        n=rng.randrange(0,31); ranks=sorted(rng.sample(range(0,1709),n)); specs=[]; vals={}
        for j,rank in enumerate(ranks):
            sid=f's{j:03d}'; roles=rng.choice([['core'],['mobile'],['core','mobile']]); qty=rng.choice([0,0,100]); pvr=rng.choice([None,1.,2.,3.]); ready=pvr is not None and rng.choice([True,True,False])
            specs.append((sid,rank,roles,qty,pvr,ready))
            if rng.choice([True,True,False]): vals[(sid,DAY)]=rng.choice([1.,2.,3.])
        rng.shuffle(specs); check(specs,vals)
    tests.append('160_deterministic_synthetic_invariant_cases_no_accounts')
    assert X.CERunner.route is X.A.Runner.route
    assert X.CERunner.opening is X.J.Runner.opening
    assert X.CERunner.planning is not X.N.Runner.planning
    source=Path(X.__file__).read_text(); driver=(X.HERE/'run_ce_entry.py').read_text()
    for path in (Path(X.__file__),X.HERE/'run_ce_entry.py',Path(__file__),X.HERE/'verify_preflight.py'):
        ast.parse(path.read_text(),filename=str(path))
    assert 'N.Runner.planning(self, at)' in source
    assert 'profit_gate' not in source and 'profit_gate' not in driver and 'cost_books' not in source and 'cost_books' not in driver
    assert 'PREDECLARED.json' in driver and "CAPITAL=D('1200000')" in driver
    assert "ap.add_argument('--execute'" in driver and 'RESTART_OPEN_PERTURB_GATE.json' in driver
    tests.append('static_native_wiring_original_route_opening_and_safe_driver')
    import run_ce_entry as driver_module
    identity=driver_module.read(X.O/'run_1200000/PREDECLARED.json')['input_identity']
    identity['seconds']+=1
    baseline_check=driver_module.assert_baseline_inputs(identity)
    assert baseline_check['excluded_fields']==['seconds']
    changed_identity=copy.deepcopy(identity);changed_identity['stock_manifest_sha256']='deliberately_wrong_synthetic_hash'
    try:driver_module.assert_baseline_inputs(changed_identity)
    except AssertionError:pass
    else:raise AssertionError('Changed data hash was ignored by baseline guard')
    tests.append('baseline_exact_identity_and_sources_only_elapsed_seconds_excluded')
    report=dict(passed=True,tests=tests,checks=len(tests),synthetic_property_cases=160,
                account_initializations=0,account_runs=0,full_replay_not_started=True,
                ce_source_final_freeze_required_separately=True)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
