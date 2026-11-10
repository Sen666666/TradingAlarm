"""Two minimal synthetic report regressions; no old bounded or full-cohort replay."""
from pathlib import Path
import sys,json,hashlib,copy
import engine_known_halt_v1 as E
from halt_evidence_v1 import HaltEvidence
import report_known_halt_v1 as broken
import report_known_halt_v2 as corrected
sys.path.insert(0,str(E.HERE.parent/'execution_bridge_v1'))
import test_execution_v4 as fixture
fixture.E=E
HERE=Path(__file__).resolve().parent
out=HERE/'report_v2_targeted_qa';out.mkdir(exist_ok=False)
def save(n,v):(out/n).write_text(json.dumps(v,default=str,ensure_ascii=False,indent=2)+'\n')
s=E.bridge.load_original('2022');results=[]
for unsettled in (False,True):
    b,st,ds=fixture.buy_and_close(s);sid=fixture.SID;rid=st['round_id']
    s.local_actions=lambda sid:{'events':[]}
    b.open_phase(ds[2]);assert st['add']>0
    if unsettled:
        e=dict(sid=sid,economic_event_id='SYNTHETIC_REPORT_ONLY_CLAIM',evidence_version='SYNTHETIC',record_date=ds[2],coordinate_snapshot_day=ds[2],ex_date=ds[3],pay_date=s.pd.Timestamp('2022-01-12'),entitlement_verified=True,d_cash=E.D(1))
        s.BY_RECORD={ds[2]:[e]};s.BY_EX={ds[3]:[e]};s.BY_PAY={e['pay_date']:[e]}
    s.raw[sid][ds[2]]['raw_close']=107.
    b.close_phase(ds[2]);assert st['addexitpending']
    b.open_phase(ds[3]);b.close_phase(ds[3]);assert st['core']>0 and st['add']==0 and s.actions[-1]['side']=='sell_add'
    end=s.pd.Timestamp('2022-01-11')
    b.halts=HaltEvidence([dict(evidence_id='SYNTHETIC_REPORT_HALT',sid=sid,session=str(end.date()),scope='FULL_DAY',known_at='2022-01-11T08:00:00+08:00')],synthetic=True)
    b.open_phase(end);b.close_phase(end);assert st['state']==E.HALT and b.snapshot(end,'CLOSE').nav is None
    before=b.capture_runtime();raw_before=copy.deepcopy(s.raw[sid]);base=corrected.base.reports(b,end);v1=broken.reports(b,end);v2=corrected.reports(b,end)
    assert before==b.capture_runtime() and raw_before==s.raw[sid],'Reporting mutated economic runtime or source bars'
    old_add=next(x for x in base['layers'] if x['layer']=='add');new_add=next(x for x in v2['layers'] if x['layer']=='add');core=next(x for x in v2['layers'] if x['layer']=='core')
    expected='EXECUTION_CLOSED_SETTLEMENT_OPEN' if unsettled else 'EXECUTION_AND_SETTLEMENT_CLOSED'
    assert old_add['layer_status']==expected and new_add['layer_status']==expected
    assert new_add['q']==0 and new_add['NET80'] is not None and new_add['current_liquidation_value_known'] and not new_add['known_full_day_suspension']
    assert new_add['round_status']=='KNOWN_HALT_UNCERTIFIED' and core['layer_status']=='KNOWN_HALT_UNCERTIFIED' and core['NET80'] is None
    assert all(new_add[k]==v for k,v in old_add.items() if k!='round_status')
    assert next(x for x in v1['layers'] if x['layer']=='add')['layer_status']=='KNOWN_HALT_UNCERTIFIED','Regression fixture did not expose old bug'
    save(('UNSETTLED' if unsettled else 'CLOSED')+'_REPORTS.json',dict(base=base,old_overlay=v1,new_overlay=v2))
    results.append(dict(name='halted_CORE_with_'+('unsettled' if unsettled else 'settled')+'_closed_ADD',status='PASS',expected_ADD_layer_status=expected,ADD_NET80=new_add['NET80'],report_did_not_mutate_economic_state=True))
save('RESULT.json',dict(status='AUTHOR_PASS_TARGETED_REPORT_ONLY',tests=results,full_cohort_run=False,old_bounded_prefix_rerun=False,engine_sha256=E.bridge.sha(HERE/'engine_known_halt_v1.py')))
save('OUTPUT_SEAL.json',{p.name:E.bridge.sha(p) for p in out.iterdir() if p.is_file()})
print(json.dumps(results,default=str))
