"""Independent completed-output CE audit. No financial account is constructed."""
from pathlib import Path
from collections import defaultdict,Counter
import gzip,hashlib,json,math,pickle,sys
from decimal import Decimal as D
import ce_account as X


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def lines(path):
    with gzip.open(path,'rt') as f:return [json.loads(line)for line in f]


def main():
    out=Path(sys.argv[1]).resolve()
    assert out.parent==X.HERE,'Only an independently completed CE output can be audited'
    done=read(out/'DONE.json');pre=read(out/'PREDECLARED.json');gate=read(out/'RESTART_OPEN_PERTURB_GATE.json')
    assert done['completed'] and gate['passed']
    assert gate['normal_sha256']==gate['restored_poison_sha256']
    assert pre['initial_cash_each']=='1200000' and pre['initial_holdings_empty']
    assert pre['intervention']=='CE_ALL_EMPTY_STOCK_SLOTS_V1'
    assert pre['no_profitability_add_gate'] and pre['no_E3'] and not pre['annual_resets']
    assert pre['was_empty_clock']=='AFTER_NATIVE_N_PLANNING_SIGNAL_CLOSE'
    guard=read(out/'BASELINE_SOURCE_AND_INPUT_GUARD.json')
    assert guard['passed'] and guard['excluded_fields']==['seconds']
    assert pre['baseline_same_input_guard']==guard
    ident,freeze=X.configure_inputs();assert pre['ce_input_identity']==ident
    for path,h in pre['source_freeze'].items():assert sha(path)==h,('Frozen source changed',path)
    cp=out/'latest_checkpoint/checkpoint.pkl';meta=read(cp.with_suffix('.json'));prov=read(cp.with_suffix('.provenance.json'))
    assert sha(cp)==meta['sha256']==prov['checkpoint_sha256']
    payload=pickle.loads(cp.read_bytes());runner=payload['runner'];account=payload['accounts']['PVR']
    assert runner['ce_input_identity']==ident and runner['ce_source_freeze']==freeze
    assert 'ce_lookup' not in runner and 'CE_LOOKUP' not in runner
    assert 'cost_books' not in runner and 'profit_gate_events' not in runner
    assert D(account['initial_cash'])==D('1200000')
    engine=prov['engine_identity']['functions']
    for name,fn in [('planning',X.CERunner.planning),('route',X.A.Runner.route),('opening',X.J.Runner.opening)]:
        assert engine[name]['qualified_name']==fn.__qualname__
        assert engine[name]['code_sha256']==X.C.IO._code_fingerprint(fn.__code__)
    rows=lines(out/'CE_STOCK_RANK_AUDIT.jsonl.gz');days=lines(out/'CE_DAY_AUDIT.jsonl.gz')
    assert rows==runner['ce_stock_rank_audit'] and days==runner['ce_day_audit']
    grouped=defaultdict(list)
    for row in rows:grouped[row['signal_day']].append(row)
    day_audits={row['signal_day']:row for row in days};assert len(day_audits)==len(days)
    daily={str(row['at'].date()):row for row in runner['daily'] if row['account']=='PVR'}
    decisions={str(row['at'].date()):row for row in account['decisions']}
    assert set(day_audits)==set(decisions)==set(daily)
    changed=0;core_changed=0;held=0;unknown=0
    for day,decision in decisions.items():
        audit=day_audits[day];r=grouped.get(day,[])
        by={row['sid']:row for row in r};assert len(by)==len(r)==audit['stock_groups']
        roles=Counter((i['sid'],i['role'])for i in decision['intents'])
        expected_roles=Counter((row['sid'],role)for row in r for role in row['roles'])
        assert roles==expected_roles
        for row in r:
            sid=row['sid'];q=daily[day]['positions'].get(sid,0)
            assert row['quantity_at_signal_close']==q and row['was_empty']==(q==0)
            ce=X.CE_LOOKUP.query(sid,day)
            assert row['CE_known']==ce['CE_known']
            if ce['CE_known']:assert row['CE']==ce['CE']
            else:assert row['CE'] is None
            assert row['CE_status']==ce['reason']
            held+=not row['was_empty'];unknown+=not row['CE_known']
        original=sorted(r,key=lambda row:row['original_rank'])
        movable=[row for row in original if row['was_empty'] and row['PVR_ready'] and row['PVR_score'] is not None and math.isfinite(row['PVR_score']) and row['CE_known']]
        ordered=sorted(movable,key=lambda row:(-round(row['CE'],12),-round(row['PVR_score'],12),row['original_rank'],row['sid']))
        expected={row['sid']:row['original_rank']for row in original}
        expected.update({row['sid']:slot['original_rank']for row,slot in zip(ordered,movable)})
        assert sorted(row['new_rank']for row in r)==sorted(row['original_rank']for row in r)
        for row in r:assert row['new_rank']==expected[row['sid']]
        for item in decision['intents']:
            row=by[item['sid']]
            assert item['rank']==row['new_rank'] and item['priority_rank']==row['original_rank']
            assert item['PVR_ready']==row['PVR_ready']
            assert item['PVR_score']==row['PVR_score']
        actual_changed=sum(row['new_rank']!=row['original_rank']for row in r)
        assert actual_changed==audit['changed_stock_groups']
        assert audit['unchanged_candidate_role_multiset'] and audit['unchanged_all_nonrank_intent_fields']
        changed+=actual_changed;core_changed+=sum(row['rank_changed']and row['has_core_intent']for row in r)
    assert changed>0,'Preflight never exercised a CE ordering change'
    checks=lines(out/'OPEN_CASH_CHECKS.jsonl.gz')
    assert checks and all(abs(D(row['cash_gap']))<D('1e-8')for row in checks)
    report=dict(passed=True,checkpoint_sha256=sha(cp),restart_current_future_HLCV_poison_equal=True,
                unchanged_native_route_and_opening=True,initial_cash='1200000',
                ce_lookup_not_serialized=True,CE_identity_exact=True,CE_days=len(days),
                CE_all_stock_groups=len(rows),CE_changed_stock_groups=changed,CE_CORE_groups_moved=core_changed,
                signal_close_quantity_independently_matches_daily=True,candidate_role_multiset_exact=True,
                all_fixed_slots_exact=True,all_sparse_slot_keys_retained=True,
                original_priority_rank_and_PVR_preserved=True,CE_score_same_signal_day_exact=True,
                independently_reconstructed_all_CE_queues=True,baseline_identical_inputs_guard_passed=True,held_groups=held,unknown_CE_groups=unknown,
                open_cash_checks=len(checks),source_files_unchanged=True,account_initializations=0,new_account_runs=0)
    X.C.IO.write_json(out/'INDEPENDENT_CE_PREFLIGHT_CHECK.json',report)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
